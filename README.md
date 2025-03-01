# Modpack Changelog Generator

A powerful, user-friendly tool for generating comprehensive changelogs between Minecraft modpack versions.

## Overview

This application compares two Minecraft modpack ZIP files and generates detailed changelogs that include information about added, removed, and updated mods, as well as changes to configs, datapacks, and options. The result is a neatly formatted changelog in your preferred format.

## Features

- **Mod Comparison**
  - Detects added and removed mods
  - Shows updated mods with version changes
  - Tracks custom mods in the overrides folder
  - Generates links to mod pages

- **Configuration Changes**
  - Analyzes config file differences
  - Formats changes for readability
  - Groups similar modifications
  - Supports spoiler/details tags

- **Additional Tracking**
  - Datapack changes (Paxi integration)
  - options.txt modifications
  - Ignores irrelevant changes like timestamps

- **User-Friendly Interface**
  - Progress bar and status updates
  - Search functionality with highlighting
  - Section filtering
  - Recent files history
  - Stop button for long operations

- **Export Options**
  - Markdown (.md)
  - HTML with styling (.html)
  - BBCode for forums (.txt)
  - Reddit-optimized format (.reddit)

## Requirements

- Python 3.6+
- Chrome browser (for mod version lookups)
- Python packages:
  - tkinter
  - beautifulsoup4
  - requests
  - selenium
  - webdriver-manager
  - markdown

## Installation

1. Install Python dependencies:
   ```
   pip install requests beautifulsoup4 selenium webdriver-manager markdown
   ```

2. Download the script and run it:
   ```
   python modpackchangegen.py
   ```

## Usage

1. Select an old modpack ZIP file
2. Select a new modpack ZIP file
3. Choose which sections to include via the dropdown
4. Click "Generate Changelog"
5. Once complete, use search/filter to explore results
6. Save the changelog in your preferred format

## How It Works

The tool extracts and compares manifest files, modlists, config files, and other content from the modpack ZIPs. For updated mods, it uses web scraping to fetch version information from CurseForge. The differential analysis is performed with intelligent similarity detection to provide meaningful change reports.

## Notes

- Generation can take several minutes for large modpacks
- Internet connection is required for fetching mod update information
- First run may take longer as it downloads the Chrome WebDriver

## License

This tool is provided as open-source software. Feel free to modify and distribute according to your needs.
