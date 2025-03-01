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

def fetch_mod_version(mod_url, file_id):
    try:
        options = Options()
        options.headless = True
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        version_url = f"{mod_url}/files/{file_id}"
        print(f"Fetching: {version_url}")
        driver.get(version_url)
        time.sleep(5)
        
        filename = "Unknown Version"
        try:
            filename_element = driver.find_element(By.CSS_SELECTOR, "section.section-file-info h2")
            filename = filename_element.text.strip()
        except Exception:
            filename = "File not found!"
        
        driver.quit()
        return filename
    except Exception as e:
        print(f"Error fetching file name: {e}")
        return "Unknown Version"
    finally:
        driver.quit()

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

def generate_changelog(old_zip, new_zip):
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
    
    with ThreadPoolExecutor() as executor:
        mod_infos = {project_id: executor.submit(fetch_mod_info_from_cflookup, project_id) for project_id in new_mods}
    
    for project_id, new_file_id in new_mods.items():
        mod_name, mod_url = mod_infos[project_id].result()
        old_file_id = old_mods.get(project_id)
        if old_file_id and old_file_id != new_file_id:
            old_version = fetch_mod_version(mod_url, old_file_id)
            new_version = fetch_mod_version(mod_url, new_file_id)
            updated[mod_name] = f"{old_version} → {new_version}"
    
    changelog = "# Modpack Changelog\n\n"
    if added:
        changelog += "## Added Mods\n" + "\n".join(f"- **[{mod}]({new_mod_links.get(mod, '#')})**" for mod in added) + "\n\n"
    if removed:
        changelog += "## Removed Mods\n" + "\n".join(f"- ~~[{mod}]({old_mod_links.get(mod, '#')})~~" for mod in removed) + "\n\n"
    if updated:
        changelog += "## Updated Mods\n" + "\n".join(f"- **[{name}]({new_mod_links.get(name, '#')})**: {version}" for name, version in updated.items()) + "\n\n"
    
    return changelog

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
        
        tk.Button(self.root, text="Generate Changelog", command=self.generate_changelog).pack(pady=10)
        
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=100, height=30)
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    
    def select_old_folder(self):
        self.old_folder.set(filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")]))
    
    def select_new_folder(self):
        self.new_folder.set(filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")]))
    
    def generate_changelog(self):
        changelog = generate_changelog(self.old_folder.get(), self.new_folder.get())
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, changelog)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModpackChangelogApp(root)
    root.mainloop()