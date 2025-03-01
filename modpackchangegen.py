import os
import zipfile
import tempfile
import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import difflib
from tkinter import ttk

class PersistentChromeBrowser:
    def __init__(self):
        self.driver = None
    
    def get_driver(self):
        if self.driver is None:
            options = Options()
            # Don't use headless mode - CurseForge detects it
            # options.add_argument("--headless")
            options.add_argument("--headless=new")  # Use newer headless implementation
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")  # Set a realistic window size
            options.add_argument("--window-position=-32000,-32000")  # Position window off-screen
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Execute CDP commands to prevent detection
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
            })
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return self.driver
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

def extract_file_from_zip(zip_path, filename):
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.endswith(filename):
                zip_ref.extract(file, temp_dir)
                return os.path.join(temp_dir, file)
    return None

def setup_selenium():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--enable-unsafe-webgl")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

@lru_cache(maxsize=100)
def fetch_mod_info_from_cflookup(project_id):
    lookup_url = f"https://cflookup.com/{project_id}"
    try:
        response = requests.get(lookup_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        mod_name_tag = soup.find("h2").find("a", class_="text-white")
        mod_name = mod_name_tag.text.strip() if mod_name_tag else f"Mod {project_id}"
        mod_url = mod_name_tag['href'] if mod_name_tag else None
        return mod_name, mod_url
    except requests.RequestException as e:
        print(f"Request Error: {e}")
        return f"Mod {project_id}", None

def fetch_mod_version(mod_url, file_id, browser):
    try:
        driver = browser.get_driver()
        version_url = f"{mod_url}/files/{file_id}"
        print(f"Fetching: {version_url}")
        driver.get(version_url)
        
        # Wait more dynamically instead of fixed sleep
        try:
            # First try to wait for the right element
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.section-file-info h2"))
            )
            filename_element = driver.find_element(By.CSS_SELECTOR, "section.section-file-info h2")
            filename = filename_element.text.strip()
            
            # If we got an empty string, try alternative selectors
            if not filename:
                # Try alternative selectors
                try:
                    filename_element = driver.find_element(By.CSS_SELECTOR, ".file-name span")
                    filename = filename_element.text.strip()
                except:
                    pass
                
                if not filename:
                    try:
                        filename_element = driver.find_element(By.CSS_SELECTOR, "h3.font-bold")
                        filename = filename_element.text.strip()
                    except:
                        pass
        except Exception as e:
            print(f"Element not found: {e}")
            # Take a screenshot for debugging
            driver.save_screenshot(f"debug_{file_id}.png")
            filename = "File not found!"
        
        return filename
    except Exception as e:
        print(f"Error fetching file name: {e}")
        return "Unknown Version"

def extract_mods_from_manifest(manifest_path):
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return {str(mod["projectID"]): str(mod["fileID"]) for mod in data.get("files", [])}

def extract_mods_from_modlist(modlist_path):
    if not os.path.exists(modlist_path):
        return set()
    with open(modlist_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        mods = set()
        for mod in soup.find_all("li"):
            mod_name = mod.text.strip()
            mods.add(mod_name)
        return mods

def parse_modlist_html(modlist_path):
    if not os.path.exists(modlist_path):
        return {}
    with open(modlist_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        mod_links = {}
        for mod in soup.find_all("li"):
            mod_name = mod.text.strip()
            mod_url = mod.find("a")["href"]
            mod_links[mod_name] = mod_url
        return mod_links

def read_file_content(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readlines()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            return f.readlines()

def compare_files(old_file, new_file):
    old_content = read_file_content(old_file) if old_file else []
    new_content = read_file_content(new_file) if new_file else []
    diff = difflib.unified_diff(old_content, new_content, fromfile='old', tofile='new')
    return ''.join(diff)

def extract_and_compare_configs(old_zip, new_zip):
    old_configs = extract_files_from_zip(old_zip, "overrides/config/")
    new_configs = extract_files_from_zip(new_zip, "overrides/config/")
    config_changes = {}
    for config in set(old_configs.keys()).union(new_configs.keys()):
        if "datapacks" not in config:  # Exclude datapacks folder
            old_file = old_configs.get(config)
            new_file = new_configs.get(config)
            diff = compare_files(old_file, new_file)
            if diff:
                config_changes[os.path.basename(config)] = diff
    return config_changes

def extract_and_compare_datapacks(old_zip, new_zip):
    old_datapacks = extract_files_from_zip(old_zip, "overrides/config/paxi/datapacks/")
    new_datapacks = extract_files_from_zip(new_zip, "overrides/config/paxi/datapacks/")
    added_datapacks = set(new_datapacks.keys()) - set(old_datapacks.keys())
    removed_datapacks = set(old_datapacks.keys()) - set(new_datapacks.keys())
    
    datapack_changes = {}
    if added_datapacks:
        datapack_changes["Added"] = list(added_datapacks)
    if removed_datapacks:
        datapack_changes["Removed"] = list(removed_datapacks)
    
    return datapack_changes

def extract_and_compare_custom_mods(old_zip, new_zip):
    old_mods = extract_files_from_zip(old_zip, "mods/")
    new_mods = extract_files_from_zip(new_zip, "mods/")
    added_mods = set(new_mods.keys()) - set(old_mods.keys())
    removed_mods = set(old_mods.keys()) - set(new_mods.keys())
    return added_mods, removed_mods

def extract_files_from_zip(zip_path, folder):
    temp_dir = tempfile.mkdtemp()
    files = {}
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.startswith(folder):
                zip_ref.extract(file, temp_dir)
                files[file] = os.path.join(temp_dir, file)
    return files

def generate_changelog(old_zip, new_zip, include_updated_mods=True, include_changed_configs=True, include_added_removed_mods=True, include_datapacks=True, include_options_changes=True):
    old_manifest = extract_file_from_zip(old_zip, "manifest.json")
    new_manifest = extract_file_from_zip(new_zip, "manifest.json")
    old_modlist = extract_file_from_zip(old_zip, "modlist.html")
    new_modlist = extract_file_from_zip(new_zip, "modlist.html")
    
    old_mods = extract_mods_from_manifest(old_manifest) if old_manifest else {}
    new_mods = extract_mods_from_manifest(new_manifest) if new_manifest else {}
    old_modlist_set = extract_mods_from_modlist(old_modlist) if old_modlist else set()
    new_modlist_set = extract_mods_from_modlist(new_modlist) if new_modlist else set()
    
    added = new_modlist_set - old_modlist_set
    removed = old_modlist_set - new_modlist_set
    updated = {}
    
    new_mod_links = parse_modlist_html(new_modlist)
    old_mod_links = parse_modlist_html(old_modlist)
    
    if include_updated_mods:
        with ThreadPoolExecutor() as executor:
            mod_infos = {project_id: executor.submit(fetch_mod_info_from_cflookup, project_id) for project_id in new_mods}
        
        browser = PersistentChromeBrowser()
        try:
            for project_id, new_file_id in new_mods.items():
                mod_name, mod_url = mod_infos[project_id].result()
                old_file_id = old_mods.get(project_id)
                if old_file_id and old_file_id != new_file_id:
                    old_version = fetch_mod_version(mod_url, old_file_id, browser)
                    new_version = fetch_mod_version(mod_url, new_file_id, browser)
                    updated[mod_name] = f"{old_version} → {new_version}"
        finally:
            browser.close()
    
    changelog = "# Modpack Changelog\n\n"
    
    if include_added_removed_mods:
        if added:
            changelog += "## Added Mods\n" + "\n".join(f"- **[{mod}]({new_mod_links.get(mod, '#')})**" for mod in added) + "\n\n"
        if removed:
            changelog += "## Removed Mods\n" + "\n".join(f"- ~~[{mod}]({old_mod_links.get(mod, '#')})~~" for mod in removed) + "\n\n"
    
    if include_updated_mods and updated:
        changelog += "## Updated Mods\n" + "\n".join(f"- **[{name}]({new_mod_links.get(name, '#')})**: {version}" for name, version in updated.items()) + "\n\n"
    
    if include_datapacks:
        datapack_changes = extract_and_compare_datapacks(old_zip, new_zip)
        if datapack_changes:
            changelog += "## Forced Datapacks\n"
            if "Added" in datapack_changes:
                changelog += "### Added\n" + "\n".join(f"- **{os.path.basename(datapack)}**" for datapack in datapack_changes["Added"]) + "\n\n"
            if "Removed" in datapack_changes:
                changelog += "### Removed\n" + "\n".join(f"- ~~{os.path.basename(datapack)}~~" for datapack in datapack_changes["Removed"]) + "\n\n"
    
    if include_changed_configs:
        config_changes = extract_and_compare_configs(old_zip, new_zip)
        if config_changes:
            changelog += "## Config Changes\n"
            for config, diff in config_changes.items():
                if diff.strip():  # Only include changes, not new or removed files
                    changelog += f"### {config}\n"
                    changelog += format_diff(diff)
    
    if include_options_changes:
        old_options = extract_file_from_zip(old_zip, "overrides/options.txt")
        new_options = extract_file_from_zip(new_zip, "overrides/options.txt")
        options_diff = compare_files(old_options, new_options)
        if options_diff.strip():  # Only include changes, not new or removed files
            changelog += "## Options Changes\n"
            changelog += format_diff(options_diff)
    
    return changelog

def format_diff(diff):
    formatted_diff = ""
    for line in diff.splitlines():
        if line.startswith('---') or line.startswith('+++'):
            continue  # Skip the file headers
        elif line.startswith('@@'):
            formatted_diff += "\n**Context:**\n"
        elif line.startswith('-'):
            formatted_diff += f"- Changed: {line[1:]}\n"
        elif line.startswith('+'):
            formatted_diff += f"+ Changed to: {line[1:]}\n"
        else:
            formatted_diff += f"  {line}\n"
    return formatted_diff

class ModpackChangelogApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft Modpack Changelog Generator")
        self.root.geometry("900x600")
        
        self.old_folder = tk.StringVar()
        self.new_folder = tk.StringVar()
        
        frame = tk.Frame(self.root)
        frame.pack(pady=10)
        
        tk.Label(frame, text="Old Modpack (ZIP):").grid(row=0, column=0, padx=5, pady=5)
        tk.Entry(frame, textvariable=self.old_folder, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(frame, text="Browse", command=self.select_old_folder).grid(row=0, column=2, padx=5, pady=5)
        
        tk.Label(frame, text="New Modpack (ZIP):").grid(row=1, column=0, padx=5, pady=5)
        tk.Entry(frame, textvariable=self.new_folder, width=50).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(frame, text="Browse", command=self.select_new_folder).grid(row=1, column=2, padx=5, pady=5)
        
        self.include_updated_mods = tk.BooleanVar(value=True)
        self.include_changed_configs = tk.BooleanVar(value=True)
        self.include_added_removed_mods = tk.BooleanVar(value=True)
        self.include_datapacks = tk.BooleanVar(value=True)
        self.include_options_changes = tk.BooleanVar(value=True)
        
        settings_frame = tk.LabelFrame(self.root, text="Changelog Settings")
        settings_frame.pack(pady=10, padx=10, fill="x")
        
        tk.Checkbutton(settings_frame, text="Include Updated Mods", variable=self.include_updated_mods).pack(anchor="w")
        tk.Checkbutton(settings_frame, text="Include Changed Configs", variable=self.include_changed_configs).pack(anchor="w")
        tk.Checkbutton(settings_frame, text="Include Added/Removed Mods", variable=self.include_added_removed_mods).pack(anchor="w")
        tk.Checkbutton(settings_frame, text="Include Datapacks", variable=self.include_datapacks).pack(anchor="w")
        tk.Checkbutton(settings_frame, text="Include Options Changes", variable=self.include_options_changes).pack(anchor="w")
        
        tk.Button(self.root, text="Generate Changelog", command=self.generate_changelog).pack(pady=10)
        tk.Button(self.root, text="Save Changelog", command=self.save_changelog).pack(pady=10)
        
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(fill="x", padx=10, pady=5)
        
        self.status_label = tk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side="left")
        
        self.progress_bar = ttk.Progressbar(self.status_frame, orient="horizontal", 
                                           length=300, mode="determinate")
        self.progress_bar.pack(side="right", padx=10)
        
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=100, height=30)
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    
    def select_old_folder(self):
        self.old_folder.set(filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")]))
    
    def select_new_folder(self):
        self.new_folder.set(filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")]))
    
    def generate_changelog(self):
        old_path = self.old_folder.get()
        new_path = self.new_folder.get()
        
        if not old_path or not new_path:
            messagebox.showerror("Error", "Please select both old and new modpack zip files")
            return
        
        # Reset UI state
        self.progress_bar["value"] = 0
        self.status_label.config(text="Initializing...")
        self.text_area.delete(1.0, tk.END)
        
        # Run the actual generation in a separate thread
        threading.Thread(target=self._run_changelog_generation, 
                        args=(old_path, new_path), 
                        daemon=True).start()
    
    def _run_changelog_generation(self, old_path, new_path):
        try:
            # Extract manifest files to get mod counts
            old_manifest = extract_file_from_zip(old_path, "manifest.json")
            new_manifest = extract_file_from_zip(new_path, "manifest.json")
            
            self.root.after(0, lambda: self.status_label.config(text="Loading mod information..."))
            
            # Load mod data
            old_mods = extract_mods_from_manifest(old_manifest) if old_manifest else {}
            new_mods = extract_mods_from_manifest(new_manifest) if new_manifest else {}
            
            # Setup for tracking updated mods
            updated_mods_count = 0
            potential_updated_mods = 0
            
            for project_id, new_file_id in new_mods.items():
                old_file_id = old_mods.get(project_id)
                if old_file_id and old_file_id != new_file_id:
                    potential_updated_mods += 1
            
            # Only proceed if we have mods to update
            if potential_updated_mods > 0:
                browser = PersistentChromeBrowser()
                
                try:
                    # Fetch mod info concurrently
                    with ThreadPoolExecutor() as executor:
                        mod_infos = {project_id: executor.submit(fetch_mod_info_from_cflookup, project_id) 
                                    for project_id in new_mods}
                    
                    # Process each mod with progress updates
                    updated_mods = {}
                    for project_id, new_file_id in new_mods.items():
                        old_file_id = old_mods.get(project_id)
                        
                        if old_file_id and old_file_id != new_file_id:
                            # Update status
                            mod_name, mod_url = mod_infos[project_id].result()
                            self.root.after(0, lambda text=f"Fetching: {mod_name}": 
                                self.status_label.config(text=text))
                            
                            # Fetch versions
                            old_version = fetch_mod_version(mod_url, old_file_id, browser)
                            new_version = fetch_mod_version(mod_url, new_file_id, browser)
                            updated_mods[mod_name] = f"{old_version} → {new_version}"
                            
                            # Update progress
                            updated_mods_count += 1
                            progress = (updated_mods_count / potential_updated_mods) * 100
                            self.root.after(0, lambda p=progress: self._update_progress(p))
                    
                finally:
                    browser.close()
                
                # Generate the changelog
                self.root.after(0, lambda: self.status_label.config(text="Generating changelog..."))
                self.changelog = self._generate_full_changelog(old_path, new_path, updated_mods)
                
                # Update UI with result
                self.root.after(0, lambda: self._update_ui_with_changelog())
            else:
                self.root.after(0, lambda: self.status_label.config(text="No mod updates found"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {str(e)}"))
            self.root.after(0, lambda: self.status_label.config(text="Error occurred"))
    
    def _update_progress(self, value):
        self.progress_bar["value"] = value
    
    def _update_ui_with_changelog(self):
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, self.changelog)
        self.status_label.config(text="Changelog generation complete")
        self.progress_bar["value"] = 100
    
    def _generate_full_changelog(self, old_zip, new_zip, updated_mods):
        # Extract all the non-mod version parts of the changelog generation
        # This code is similar to the existing generate_changelog function but uses
        # the already fetched updated_mods instead of fetching them again
        
        old_manifest = extract_file_from_zip(old_zip, "manifest.json")
        new_manifest = extract_file_from_zip(new_zip, "manifest.json")
        old_modlist = extract_file_from_zip(old_zip, "modlist.html")
        new_modlist = extract_file_from_zip(new_zip, "modlist.html")
        
        old_modlist_set = extract_mods_from_modlist(old_modlist) if old_modlist else set()
        new_modlist_set = extract_mods_from_modlist(new_modlist) if new_modlist else set()
        
        added = new_modlist_set - old_modlist_set
        removed = old_modlist_set - new_modlist_set
        
        new_mod_links = parse_modlist_html(new_modlist)
        old_mod_links = parse_modlist_html(old_modlist)
        
        changelog = "# Modpack Changelog\n\n"
        
        if self.include_added_removed_mods.get():
            if added:
                changelog += "## Added Mods\n" + "\n".join(f"- **[{mod}]({new_mod_links.get(mod, '#')})**" for mod in added) + "\n\n"
            if removed:
                changelog += "## Removed Mods\n" + "\n".join(f"- ~~[{mod}]({old_mod_links.get(mod, '#')})~~" for mod in removed) + "\n\n"
        
        if self.include_updated_mods.get() and updated_mods:
            changelog += "## Updated Mods\n" + "\n".join(f"- **[{name}]({new_mod_links.get(name, '#')})**: {version}" for name, version in updated_mods.items()) + "\n\n"
        
        if self.include_datapacks.get():
            datapack_changes = extract_and_compare_datapacks(old_zip, new_zip)
            if datapack_changes:
                changelog += "## Forced Datapacks\n"
                if "Added" in datapack_changes:
                    changelog += "### Added\n" + "\n".join(f"- **{os.path.basename(datapack)}**" for datapack in datapack_changes["Added"]) + "\n\n"
                if "Removed" in datapack_changes:
                    changelog += "### Removed\n" + "\n".join(f"- ~~{os.path.basename(datapack)}~~" for datapack in datapack_changes["Removed"]) + "\n\n"
        
        if self.include_changed_configs.get():
            config_changes = extract_and_compare_configs(old_zip, new_zip)
            if config_changes:
                changelog += "## Config Changes\n"
                for config, diff in config_changes.items():
                    if diff.strip():  # Only include changes, not new or removed files
                        changelog += f"### {config}\n"
                        changelog += format_diff(diff)
        
        if self.include_options_changes.get():
            old_options = extract_file_from_zip(old_zip, "overrides/options.txt")
            new_options = extract_file_from_zip(new_zip, "overrides/options.txt")
            options_diff = compare_files(old_options, new_options)
            if options_diff.strip():  # Only include changes, not new or removed files
                changelog += "## Options Changes\n"
                changelog += format_diff(options_diff)
        
        return changelog
    
    def save_changelog(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown files", "*.md")])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(self.changelog)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModpackChangelogApp(root)
    root.mainloop()