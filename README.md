# Modpack Comparison Script

A **Python script** for comparing exported modpacks from **CurseForge**.

Script will compare what mods was added, removed or updated. It will also detect what configs were changed and it will write down the changed configs and include the changes. This will work for options.txt as well.
All you need to do is select old and new modpack and just wait. It will open chrome browser to fetch data about updated mods so dont close it, its gonna close itself.

## 🛠 Requirements

Before using the script, install the necessary dependencies:

```bash
pip install requests beautifulsoup4 selenium webdriver-manager
