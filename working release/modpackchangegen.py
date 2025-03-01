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
import pickle
import os.path
import re
import markdown

class PersistentChromeBrowser:
    def __init__(self):
        self.driver = None
    
    def get_driver(self):
        if self.driver is None:
            options = Options()
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

# Fix the extract_and_compare_custom_mods function
def extract_and_compare_custom_mods(old_zip, new_zip):
    # Change "mods/" to "overrides/mods/"
    old_mods = extract_files_from_zip(old_zip, "overrides/mods/")
    new_mods = extract_files_from_zip(new_zip, "overrides/mods/")
    
    # Filter for only JAR files to avoid processing directories or other files
    old_mod_files = {path for path in old_mods.keys() if path.lower().endswith('.jar')}
    new_mod_files = {path for path in new_mods.keys() if path.lower().endswith('.jar')}
    
    added_mods = new_mod_files - old_mod_files
    removed_mods = old_mod_files - new_mod_files
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
                # Only include non-empty changes
                if diff.strip():
                    formatted_diff = format_diff_for_display(diff)
                    # Skip this config if there are no actual changes after formatting
                    if formatted_diff.strip():
                        changelog += f"<details>\n<summary><strong>{config}</strong></summary>\n\n```\n"
                        changelog += formatted_diff
                        changelog += "\n```\n</details>\n\n"
    
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

def format_diff_for_display(diff):
    """Format diff output to only show changes to existing lines, hiding additions/removals"""
    formatted_lines = []
    removed_lines = []
    added_lines = []
    
    # First pass: collect all added and removed lines
    for line in diff.splitlines():
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@') or line.startswith(' '):
            continue
            
        # Skip timestamp lines
        if line.startswith('-') or line.startswith('+'):
            content = line[1:].strip()
            if (content.startswith('#') and 
                (any(tz in content for tz in ["CET", "UTC", "GMT", "EST", "PST", "PDT", "EDT"]) or
                 any(month in content for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]))):
                continue
        
        if line.startswith('-'):
            removed_lines.append(line[1:])
        elif line.startswith('+'):
            added_lines.append(line[1:])
    
    # Second pass: only include pairs of lines that are similar (actual changes)
    i, j = 0, 0
    while i < len(removed_lines) and j < len(added_lines):
        removed = removed_lines[i]
        added = added_lines[j]
        
        # Are these lines similar? (likely a change rather than insert/delete)
        if similarity_score(removed, added) > 0.5:  # Threshold for considering it a change
            formatted_lines.append(f"Changed: {removed}")
            formatted_lines.append(f"Changed to: {added}")
            i += 1
            j += 1
        else:
            # Not similar enough, so advance both counters to look for better matches
            # This skips pure additions/removals as requested
            i += 1
            j += 1
    
    # Don't include any remaining lines since they're pure additions/removals
    
    return '\n'.join(formatted_lines)

# Helper function to assess similarity between two strings
def similarity_score(str1, str2):
    """Calculate a similarity score between 0 and 1"""
    # Simple implementation - can be improved
    if '=' in str1 and '=' in str2:
        # For config lines with key=value format, compare the keys
        key1 = str1.split('=')[0].strip()
        key2 = str2.split('=')[0].strip()
        return 1.0 if key1 == key2 else 0.0
    
    # For other formats, use string similarity
    try:
        import difflib
        return difflib.SequenceMatcher(None, str1, str2).ratio()
    except:
        # Fallback if difflib not available
        common = set(str1) & set(str2)
        return len(common) / max(len(set(str1)), len(set(str2)))

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
        
        # Create dropdown menu for settings
        settings_frame = tk.LabelFrame(self.root, text="Changelog Settings")
        settings_frame.pack(pady=10, padx=10, fill="x")

        # Define settings variables
        self.include_updated_mods = tk.BooleanVar(value=True)
        self.include_changed_configs = tk.BooleanVar(value=True)
        self.include_added_removed_mods = tk.BooleanVar(value=True)
        self.include_datapacks = tk.BooleanVar(value=True)
        self.include_options_changes = tk.BooleanVar(value=True)
        self.include_custom_mods = tk.BooleanVar(value=True)

        # Create dropdown button
        self.dropdown_button = tk.Button(settings_frame, text="Sections to Include ▼", 
                                        command=self.toggle_dropdown)
        self.dropdown_button.pack(anchor="w", padx=10, pady=5)

        # Create dropdown menu (hidden initially)
        self.dropdown_menu = tk.Frame(settings_frame, relief=tk.RAISED, borderwidth=1)
        self.dropdown_menu.pack(fill="x", padx=10, pady=5)
        self.dropdown_menu.pack_forget()  # Hide initially

        # Add checkboxes to the dropdown
        tk.Checkbutton(self.dropdown_menu, text="Updated Mods", 
                    variable=self.include_updated_mods).pack(anchor="w", padx=5, pady=2)
        tk.Checkbutton(self.dropdown_menu, text="Changed Configs", 
                    variable=self.include_changed_configs).pack(anchor="w", padx=5, pady=2)
        tk.Checkbutton(self.dropdown_menu, text="Added/Removed Mods", 
                    variable=self.include_added_removed_mods).pack(anchor="w", padx=5, pady=2)
        tk.Checkbutton(self.dropdown_menu, text="Datapacks", 
                    variable=self.include_datapacks).pack(anchor="w", padx=5, pady=2)
        tk.Checkbutton(self.dropdown_menu, text="Options Changes", 
                    variable=self.include_options_changes).pack(anchor="w", padx=5, pady=2)
        tk.Checkbutton(self.dropdown_menu, text="Custom Mods (overrides/mods folder)", 
                    variable=self.include_custom_mods).pack(anchor="w", padx=5, pady=2)
        
        # Add this to the ModpackChangelogApp.__init__ method after the Generate and Save buttons

        # Create button frame with Generate, Stop, and Save buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        self.generate_button = tk.Button(button_frame, text="Generate Changelog", command=self.generate_changelog)
        self.generate_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(button_frame, text="Stop Generation", command=self.stop_generation, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.save_button = tk.Button(button_frame, text="Save Changelog", command=self.save_changelog)
        self.save_button.pack(side=tk.LEFT, padx=5)

        # Remove the old buttons that are now in the button_frame
        # (Delete these two lines)
        # tk.Button(self.root, text="Generate Changelog", command=self.generate_changelog).pack(pady=10)
        # tk.Button(self.root, text="Save Changelog", command=self.save_changelog).pack(pady=10)

        # Add cancellation flag
        self.is_cancelled = False
        
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(fill="x", padx=10, pady=5)
        
        self.status_label = tk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side="left")
        
        self.progress_bar = ttk.Progressbar(self.status_frame, orient="horizontal", 
                                           length=300, mode="determinate")
        self.progress_bar.pack(side="right", padx=10)
        
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=100, height=30)
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Add this to ModpackChangelogApp.__init__ after creating the dropdown
        # Close dropdown when clicking elsewhere
        def close_dropdown(event):
            if self.dropdown_menu.winfo_viewable():
                # Check if click is outside the dropdown area
                if not (self.dropdown_button.winfo_containing(event.x_root, event.y_root) or
                        self.dropdown_menu.winfo_containing(event.x_root, event.y_root)):
                    self.dropdown_menu.pack_forget()
                    self.dropdown_button.config(text="Sections to Include ▼")
                    
        self.root.bind('<Button-1>', close_dropdown)
        
        # Recent files history
        self.history_file = os.path.join(os.path.expanduser("~"), ".modpack_changelog_history")
        self.recent_files = {"old": [], "new": []}
        self.load_recent_files()
        
        # Add dropdown menus for recent files
        if self.recent_files["old"]:
            old_dropdown = tk.OptionMenu(frame, self.old_folder, *self.recent_files["old"])
            old_dropdown.grid(row=0, column=3, padx=5, pady=5)
            old_dropdown.config(width=15)
        else:
            old_label = tk.Label(frame, text="No recent files")
            old_label.grid(row=0, column=3, padx=5, pady=5)

        if self.recent_files["new"]:
            new_dropdown = tk.OptionMenu(frame, self.new_folder, *self.recent_files["new"]) 
            new_dropdown.grid(row=1, column=3, padx=5, pady=5)
            new_dropdown.config(width=15)
        else:
            new_label = tk.Label(frame, text="No recent files")
            new_label.grid(row=1, column=3, padx=5, pady=5)
        
        # Add search frame
        search_frame = tk.Frame(self.root)
        search_frame.pack(fill="x", padx=10, pady=5, before=self.text_area)
        
        self.search_var = tk.StringVar()
        tk.Label(search_frame, text="Search:").pack(side="left", padx=5)
        tk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side="left", padx=5)
        tk.Button(search_frame, text="Find", command=self.search_changelog).pack(side="left", padx=5)
        tk.Button(search_frame, text="Clear", command=self.clear_search).pack(side="left", padx=5)
        
        # Add filter options
        self.filter_var = tk.StringVar(value="All")
        filter_options = ["All", "Added Mods", "Removed Mods", "Updated Mods", "Config Changes"]
        tk.Label(search_frame, text="Filter:").pack(side="left", padx=10)
        tk.OptionMenu(search_frame, self.filter_var, *filter_options, command=self.apply_filter).pack(side="left")
    
    def load_recent_files(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'rb') as f:
                    self.recent_files = pickle.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
            self.recent_files = {"old": [], "new": []}

    def save_recent_files(self):
        try:
            # Keep only the last 5 entries
            self.recent_files["old"] = self.recent_files["old"][:5] 
            self.recent_files["new"] = self.recent_files["new"][:5]
            
            with open(self.history_file, 'wb') as f:
                pickle.dump(self.recent_files, f)
        except Exception as e:
            print(f"Error saving history: {e}")

    def select_old_folder(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if path:
            self.old_folder.set(path)
            # Update history
            if path in self.recent_files["old"]:
                self.recent_files["old"].remove(path)
            self.recent_files["old"].insert(0, path)
            self.save_recent_files()
    
    def select_new_folder(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if path:
            self.new_folder.set(path)
            # Update history
            if path in self.recent_files["new"]:
                self.recent_files["new"].remove(path)
            self.recent_files["new"].insert(0, path)
            self.save_recent_files()
    
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
        self.is_cancelled = False
        
        # Update button states
        self.generate_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Run the actual generation in a separate thread
        threading.Thread(target=self._run_changelog_generation, 
                        args=(old_path, new_path), 
                        daemon=True).start()
    
    def _run_changelog_generation(self, old_path, new_path):
        try:
            # Extract manifest files to get mod counts
            old_manifest = extract_file_from_zip(old_path, "manifest.json")
            new_manifest = extract_file_from_zip(new_path, "manifest.json")
            
            if self.is_cancelled:
                self._handle_generation_end()
                return
                
            self.root.after(0, lambda: self.status_label.config(text="Loading mod information..."))
            
            # Load mod data
            old_mods = extract_mods_from_manifest(old_manifest) if old_manifest else {}
            new_mods = extract_mods_from_manifest(new_manifest) if new_manifest else {}
            
            # Initialize empty updated_mods
            updated_mods = {}
            
            # Only fetch mod updates if the option is enabled and not cancelled
            if self.include_updated_mods.get() and not self.is_cancelled:
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
                        for project_id, new_file_id in new_mods.items():
                            if self.is_cancelled:
                                break
                            old_file_id = old_mods.get(project_id)
                            
                            if old_file_id and old_file_id != new_file_id:
                                # Update status
                                mod_name, mod_url = mod_infos[project_id].result()
                                self.root.after(0, lambda text=f"Fetching: {mod_name}": 
                                    self.status_label.config(text=text))
                                
                                # Fetch versions
                                old_version = fetch_mod_version(mod_url, old_file_id, browser)
                                new_version = fetch_mod_version(mod_url, new_file_id, browser)
                                
                                # Store both version info and URL
                                updated_mods[mod_name] = {
                                    "version": f"{old_version} → {new_version}",
                                    "url": mod_url
                                }
                                
                                # Update progress
                                updated_mods_count += 1
                                progress = (updated_mods_count / potential_updated_mods) * 100
                                self.root.after(0, lambda p=progress: self._update_progress(p))
                        
                    finally:
                        browser.close()
            
            # Only generate changelog if not cancelled
            if not self.is_cancelled:
                # Generate the changelog
                self.root.after(0, lambda: self.status_label.config(text="Generating changelog..."))
                self.changelog = self._generate_full_changelog(old_path, new_path, updated_mods)
                
                # Update UI with result
                self.root.after(0, lambda: self._update_ui_with_changelog())
            else:
                self._handle_generation_end()
                    
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {str(e)}"))
            self.root.after(0, lambda: self.status_label.config(text="Error occurred"))
            self.root.after(0, lambda: self._handle_generation_end())
    
    def _update_progress(self, value):
        self.progress_bar["value"] = value
    
    def _update_ui_with_changelog(self):
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, self.changelog)
        self.status_label.config(text="Changelog generation complete")
        self.progress_bar["value"] = 100
        self._handle_generation_end()  # Reset buttons
    
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
        
        old_ver, new_ver = self._detect_versions(old_zip, new_zip)
        changelog = f"# Modpack Changelog: {old_ver} → {new_ver}\n\n"
        
        # Also add a version summary section at the top
        changelog += f"*Updated from version {old_ver} to {new_ver}*\n\n"
        
        if self.include_added_removed_mods.get():
            if added:
                changelog += "## Added Mods\n"
                # Simple alphabetical list instead of categorization
                for mod in sorted(added):
                    changelog += f"- **[{mod}]({new_mod_links.get(mod, '#')})**\n"
                changelog += "\n"
            
            if removed:
                changelog += "## Removed Mods\n"
                # Simple alphabetical list instead of categorization
                for mod in sorted(removed):
                    changelog += f"- ~~[{mod}]({old_mod_links.get(mod, '#')})~~\n"
                changelog += "\n"
        
        if self.include_updated_mods.get() and updated_mods:
            changelog += "## Updated Mods\n" + "\n".join(
                f"- **[{name}]({info['url'] or '#'})**: {info['version']}" 
                for name, info in updated_mods.items()
            ) + "\n\n"
        
        if self.include_custom_mods.get():
            # Check for custom mods in overrides/mods folder
            added_custom_mods, removed_custom_mods = extract_and_compare_custom_mods(old_zip, new_zip)
            
            if added_custom_mods or removed_custom_mods:
                changelog += "## Custom Mods Changes (overrides/mods folder)\n"
                
                if added_custom_mods:
                    changelog += "### Added Custom Mods\n"
                    for mod in sorted(added_custom_mods):
                        mod_name = os.path.basename(mod)
                        changelog += f"- **{mod_name}**\n"
                    changelog += "\n"
                
                if removed_custom_mods:
                    changelog += "### Removed Custom Mods\n"
                    for mod in sorted(removed_custom_mods):
                        mod_name = os.path.basename(mod)
                        changelog += f"- ~~{mod_name}~~\n"
                    changelog += "\n"
        
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
                    # Only include non-empty changes
                    if diff.strip():
                        formatted_diff = format_diff_for_display(diff)
                        # Skip this config if there are no actual changes after formatting
                        if formatted_diff.strip():
                            changelog += f"<details>\n<summary><strong>{config}</strong></summary>\n\n```\n"
                            changelog += formatted_diff
                            changelog += "\n```\n</details>\n\n"
        
        if self.include_options_changes.get():
            old_options = extract_file_from_zip(old_zip, "overrides/options.txt")
            new_options = extract_file_from_zip(new_zip, "overrides/options.txt")
            options_diff = compare_files(old_options, new_options)
            if options_diff.strip():  # Only include changes, not new or removed files
                changelog += "## Options Changes\n"
                changelog += "<details>\n<summary><strong>Click to expand options.txt changes</strong></summary>\n\n```\n"
                changelog += format_diff_for_display(options_diff)  # Use the new function here
                changelog += "\n```\n</details>\n\n"
        
        return changelog
    
    def save_changelog(self):
        file_types = [
            ("Markdown", "*.md"),
            ("HTML", "*.html"), 
            ("BBCode for Forums", "*.txt"),
            ("Reddit Markdown", "*.reddit")
        ]
        file_path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=file_types)
        
        if file_path:
            format_type = os.path.splitext(file_path)[1].lower()
            content = self.changelog  # Default markdown
            
            if format_type == '.html':
                content = self._convert_to_html()
            elif format_type == '.txt':
                content = self._convert_to_bbcode()
            elif format_type == '.reddit':
                content = self._convert_to_reddit()
            
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
                self.status_label.config(text=f"Changelog saved as {os.path.basename(file_path)}")

    def _convert_to_html(self):
        """Convert the markdown changelog to HTML format"""
        try:
            import markdown
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Modpack Changelog</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1 {{ color: #333; }}
                    h2 {{ color: #444; margin-top: 30px; border-bottom: 1px solid #ddd; }}
                    h3 {{ color: #555; }}
                    details {{ margin-bottom: 15px; }}
                    summary {{ cursor: pointer; font-weight: bold; }}
                    pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                    .added {{ color: #2e7d32; }}
                    .removed {{ color: #c62828; text-decoration: line-through; }}
                    .changed {{ color: #1565c0; }}
                    .changed-to {{ color: #0277bd; }}
                </style>
            </head>
            <body>
                {markdown.markdown(self.changelog, extensions=['tables', 'fenced_code'])}
            </body>
            </html>
            """
            return html
        except ImportError:
            # Fallback if markdown module isn't available
            messagebox.showinfo("Module Missing", "Please install the 'markdown' module for better HTML conversion")
            simple_html = self.changelog.replace("\n", "<br>")
            simple_html = simple_html.replace("# ", "<h1>").replace("## ", "<h2>").replace("### ", "<h3>")
            simple_html = simple_html.replace("- ", "• ").replace("```", "<pre>").replace("</pre><br>", "</pre>")
            return f"<html><body>{simple_html}</body></html>"

    def _convert_to_bbcode(self):
        """Convert the markdown changelog to BBCode for forums"""
        bbcode = self.changelog
        
        # Headers
        bbcode = re.sub(r'^# (.+)$', r'[size=6][b]\1[/b][/size]', bbcode, flags=re.MULTILINE)
        bbcode = re.sub(r'^## (.+)$', r'[size=5][b]\1[/b][/size]', bbcode, flags=re.MULTILINE)
        bbcode = re.sub(r'^### (.+)$', r'[size=4][b]\1[/b][/size]', bbcode, flags=re.MULTILINE)
        
        # Links
        bbcode = re.sub(r'\[(.+?)\]\((.+?)\)', r'[url=\2]\1[/url]', bbcode)
        
        # Bold
        bbcode = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', bbcode)
        
        # Code blocks
        bbcode = re.sub(r'```(?:\w+)?\n(.*?)\n```', r'[code]\1[/code]', bbcode, flags=re.DOTALL)
        
        # Lists
        bbcode = re.sub(r'^- ', r'[*] ', bbcode, flags=re.MULTILINE)
        
        # Spoiler tags (for detailed sections)
        bbcode = re.sub(r'<details>\s*<summary>(.+?)</summary>', r'[spoiler=\1]', bbcode)
        bbcode = re.sub(r'</details>', r'[/spoiler]', bbcode)
        
        return bbcode

    def _convert_to_reddit(self):
        """Convert to Reddit-friendly markdown"""
        reddit_md = self.changelog
        
        # Replace HTML details/summary with Reddit spoiler format
        pattern = r'<details>\s*<summary>(.+?)</summary>\s*\n\n```\s*(.*?)\s*```\s*</details>'
        replacement = r'>! \1\n\n```\n\2\n```\n!<'
        reddit_md = re.sub(pattern, replacement, reddit_md, flags=re.DOTALL)
        
        return reddit_md

    # Add this method to ModpackChangelogApp class
    def toggle_dropdown(self):
        if self.dropdown_menu.winfo_viewable():
            self.dropdown_menu.pack_forget()
            self.dropdown_button.config(text="Sections to Include ▼")
        else:
            self.dropdown_menu.pack(fill="x", padx=10, pady=5)
            self.dropdown_button.config(text="Sections to Include ▲")

    def stop_generation(self):
        """Stop the changelog generation process"""
        self.is_cancelled = True
        self.status_label.config(text="Cancelling generation...")
        # The thread will check this flag and terminate gracefully

    def _handle_generation_end(self):
        """Reset UI state after generation ends for any reason"""
        self.generate_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if self.is_cancelled:
            self.status_label.config(text="Generation cancelled")
    
    def search_changelog(self):
        """Search for text in the changelog"""
        search_text = self.search_var.get().lower()
        if not search_text or not hasattr(self, 'changelog'):
            return
        
        # Reset any previous search formatting
        self.text_area.tag_remove("search", "1.0", tk.END)
        
        # Configure tag for highlighting
        self.text_area.tag_configure("search", background="yellow")
        
        # Search and highlight
        start_pos = "1.0"
        while True:
            start_pos = self.text_area.search(search_text, start_pos, tk.END, nocase=True)
            if not start_pos:
                break
                
            end_pos = f"{start_pos}+{len(search_text)}c"
            self.text_area.tag_add("search", start_pos, end_pos)
            start_pos = end_pos
        
        # Count matches
        matches = len(self.text_area.tag_ranges("search")) // 2
        self.status_label.config(text=f"Found {matches} matches for '{search_text}'")
        
        # Scroll to first match if found
        if matches > 0:
            self.text_area.see("search.first")

    def clear_search(self):
        """Clear search highlights"""
        self.search_var.set("")
        self.text_area.tag_remove("search", "1.0", tk.END)
        if hasattr(self, 'changelog'):
            self.status_label.config(text="Changelog generation complete")

    def apply_filter(self, selection):
        """Filter the changelog to show only selected section"""
        if not hasattr(self, 'changelog'):
            return
            
        # Reset to full changelog
        self.text_area.delete(1.0, tk.END)
        
        if selection == "All":
            self.text_area.insert(tk.END, self.changelog)
            return
        
        # Use regex to find the specific section and its content
        pattern = f"## {selection}.*?(?=## |$)"
        match = re.search(pattern, self.changelog, re.DOTALL)
        
        if match:
            section_content = match.group(0)
            self.text_area.insert(tk.END, section_content)
            self.status_label.config(text=f"Filtered: Showing only {selection}")
        else:
            self.text_area.insert(tk.END, f"No {selection} section found in the changelog.")
    
    def _detect_versions(self, old_path, new_path):
        """Attempt to detect modpack versions from filenames or manifest data"""
        old_ver = "Old Version"
        new_ver = "New Version"
        
        # Try from filenames first
        old_basename = os.path.basename(old_path).replace('.zip', '')
        new_basename = os.path.basename(new_path).replace('.zip', '')
        
        # Look for version patterns in filenames (like v1.2.3, 1.2.3, etc.)
        version_pattern = r'[-_]?v?(\d+\.\d+(?:\.\d+)?(?:[a-z]?(?:\d+)?)?)'
        
        old_match = re.search(version_pattern, old_basename, re.IGNORECASE)
        if old_match:
            old_ver = old_match.group(1)
        
        new_match = re.search(version_pattern, new_basename, re.IGNORECASE)
        if new_match:
            new_ver = new_match.group(1)
        
        # Try from manifest.json if available
        try:
            old_manifest_path = extract_file_from_zip(old_path, "manifest.json")
            if old_manifest_path:
                with open(old_manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "version" in data:
                        old_ver = data["version"]
                    elif "minecraft" in data and "version" in data["minecraft"]:
                        old_ver = f"MC-{data['minecraft']['version']}"
        except:
            pass  # Use already detected version
        
        try:
            new_manifest_path = extract_file_from_zip(new_path, "manifest.json")
            if new_manifest_path:
                with open(new_manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "version" in data:
                        new_ver = data["version"]
                    elif "minecraft" in data and "version" in data["minecraft"]:
                        new_ver = f"MC-{data['minecraft']['version']}"
        except:
            pass  # Use already detected version
        
        return old_ver, new_ver

if __name__ == "__main__":
    root = tk.Tk()
    app = ModpackChangelogApp(root)
    root.mainloop()