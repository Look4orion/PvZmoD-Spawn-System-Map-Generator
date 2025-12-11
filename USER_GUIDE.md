# PvZmoD Zone Editor - User Guide

A standalone desktop application for editing DayZ PvZmoD zombie spawn zones with visual danger color coding.

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Features](#features)
- [Usage Guide](#usage-guide)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Danger Color Coding](#danger-color-coding)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Installation

### Option 1: Windows Installer (Recommended)

**For most users - easiest installation**

1. Download `PvZmoD_Zone_Editor_Setup_v1.0.exe` from the [Releases](../../releases) page
2. Run the installer
3. Follow the installation wizard
4. Launch from Start Menu or Desktop shortcut
5. No additional software required

**Advantages:**
- ✅ One-click installation
- ✅ Start Menu integration
- ✅ Desktop shortcut
- ✅ Easy uninstall via Windows Settings
- ✅ No Python required

---

### Option 2: Portable Executable

**For users who don't want to install**

1. Download `PvZmoD_Zone_Editor.exe` from the [Releases](../../releases) page
2. Place it in any folder
3. Double-click to run
4. No installation required

**Advantages:**
- ✅ No installation needed
- ✅ Run from USB drive
- ✅ No registry changes
- ✅ Easy to move/delete

**Requirements:**
- Windows 10 or Windows 11 (64-bit)
- No Python installation needed

---

### Option 3: Run from Python Source

**For developers or users who want to modify the code**

#### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

#### Installation Steps

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/pvzmod-zone-editor.git
   cd pvzmod-zone-editor
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Or install manually:
   ```bash
   pip install PyQt5>=5.15.0 Pillow>=10.0.0 lxml>=4.9.0
   ```

3. **Run the application:**
   ```bash
   python pvzmod_zone_editor.py
   ```

**Advantages:**
- ✅ Can modify source code
- ✅ Latest development version
- ✅ Cross-platform (Windows, Linux, macOS)
- ✅ Full control

---

### Option 4: Build Your Own Executable

**For users who want to compile from source**

#### Prerequisites

- Python 3.8 or higher
- PyInstaller

#### Build Steps

1. **Install dependencies:**
   ```bash
   pip install PyQt5 Pillow lxml pyinstaller
   ```

2. **Build using the provided spec file:**
   ```bash
   pyinstaller pvzmod_zone_editor.spec
   ```

   Or use the build script:
   ```bash
   build.bat
   ```

3. **Find the executable:**
   - Location: `dist/PvZmoD_Zone_Editor.exe`
   - Size: ~50-60 MB

#### Build Windows Installer (Optional)

**Requires [Inno Setup](https://jrsoftware.org/isinfo.php)**

1. Install Inno Setup
2. Open `installer_script.iss`
3. Compile
4. Find installer in `installer_output/`

---

## Getting Started

### Quick Start

1. **Launch the application**
2. **File → Open Files** (or wait for auto-dialog)
3. **Configure your map:**
   - Select Map Preset (Deer Isle, Chernarus, Livonia, or Custom)
   - World size auto-fills (or enter manually for Custom)
4. **Select required files:**
   - DynamicSpawnZones.c
   - StaticSpawnDatas.c
   - ZombiesChooseCategories.c
   - ZombiesCategories.c
   - Map.png (must be square, e.g., 2048x2048 or 4096x4096)
5. **Optional:** PvZmoD_CustomisableZombies_Characteristics.xml (for danger colors)
6. Click **Load Files**
7. Start editing zones!

### File Locations

Your DayZ server files are typically located at:
```
YourServerFolder/
├── mpmissions/
│   └── dayzOffline.chernarusplus/
│       ├── DynamicSpawnZones.c
│       ├── StaticSpawnDatas.c
│       └── Map.png
└── @PvZmoD_Code/
    ├── ZombiesChooseCategories.c
    ├── ZombiesCategories.c
    └── PvZmoD_CustomisableZombies_Characteristics.xml
```

**Note:** Files can be in different folders - browse to each one individually.

### Map Configuration

**The app supports multiple DayZ maps with automatic coordinate conversion:**

#### Map Presets

| Map | World Size |
|-----|------------|
| Deer Isle | 16384x16384 |
| Chernarus/Chernarus+ | 15360x15360 |
| Livonia | 12800x12800 |
| Custom | Enter manually |

#### How It Works

1. **Select map preset** from dropdown
2. **World size auto-fills** (or enter for Custom)
3. **Choose map image** (must be square: 2048x2048, 4096x4096, etc.)
4. **Image size auto-detected** from your PNG file
5. **Coordinates converted automatically** between world units and pixels

#### Requirements

- **Map image MUST be square** (width = height)
- Common sizes: 1024x1024, 2048x2048, 4096x4096, 8192x8192
- Format: PNG (JPG also supported)
- World size must match your zone coordinate ranges

#### Settings Persistence

Your map configuration is saved between sessions:
- Last used map preset
- World size (if Custom)
- All file paths

**Result:** Open once, set and forget! Map config loads automatically next time.

---

## Features

### Core Features

✅ **Visual Zone Editing**
- See all zones on an interactive map
- Click zones on map or in list to select
- Drag and resize dynamic zones
- Color-coded danger levels

✅ **Zone Management**
- Edit config numbers and comments
- Add new dynamic zones
- Delete zones (sets config to 0)
- 150 dynamic zone slots
- 262 static zones

✅ **Danger Color Coding**
- Automatic color based on zombie health
- Relative to YOUR zombie configuration
- 5 danger levels (green to red)
- Works with any health range

✅ **Advanced Filtering**
- Filter by Config number
- Filter by Category
- Filter by Zombie Class
- One filter active at a time

✅ **Analysis Tools**
- Show unused configs
- Show unused categories
- Show unused zombies
- Plan better zone distribution

✅ **Safety Features**
- Automatic backups (.backup files)
- Unsaved changes warning
- Settings persistence
- Error logging

---

## Usage Guide

### Working with Zones

#### Selecting Zones

**Two ways to select:**

1. **From list (left panel):**
   - Click zone name → Highlights on map

2. **From map (center panel):**
   - Click zone → Selects in list
   - Blue highlight indicates selection

**Both methods synchronized - select in one, highlights in both**

---

#### Editing Zone Config & Comment

**For both dynamic and static zones:**

1. Select a zone
2. In Properties panel (right):
   - **Config dropdown:** Click and type number to jump (e.g., type "60")
   - **Hover config:** See zombie preview tooltip
   - **Comment field:** Add description
3. Click **Save Changes**
4. Categories update automatically

**Config selection tips:**
- Type to search: "60" jumps to Config 60
- Hover for preview: Shows categories and first 10 zombies
- Click "View All Zombies" to see complete list

---

#### Moving/Resizing Dynamic Zones

**Only dynamic zones can be moved/resized:**

1. Select a dynamic zone
2. Click **Move/Resize Zone** button (toolbar)
3. Blue handles appear at corners
4. **To move:** Drag zone body
5. **To resize:** Drag corner handles
6. Click **Done Editing** when finished

**Constraints:**
- Minimum size: 10 world units
- Cannot flip corners
- Automatic coordinate correction

---

#### Adding New Dynamic Zones

**Creates zones in available slots (config=0):**

1. Click **Add Dynamic Zone** button (toolbar)
2. Button changes to "Draw Zone Rectangle"
3. Click and drag on map to draw rectangle
4. Blue handles appear - resize as needed
5. Click **Done Adding**
6. Dialog appears:
   - Select available zone slot (e.g., Zone049)
   - Choose config number
   - Add comment
7. Click OK
8. Automatically returns to Select mode

**Zone slots:**
- 150 total slots (Zone001-Zone150)
- Slots with config=0 are available
- Adding a zone assigns it to an available slot

---

#### Deleting Zones

**Important:** You don't actually delete zones from the file. Instead, you set their config and coordinates to 0, making them "available" for reuse.

1. Select the zone
2. Set Config to **0**
3. Click **Save Changes**
4. Zone disappears from map
5. Zone slot becomes available for "Add Dynamic Zone"

**Example:** Zone049 with config=0 becomes an empty slot ready to be reassigned.

---

### Navigation Controls

**Mouse controls:**
- **Zoom:** Mouse wheel (in/out)
- **Pan:** Middle mouse button + drag
- **Select:** Left click

**Keyboard shortcuts:**
- **Ctrl++** Zoom in
- **Ctrl+-** Zoom out
- **Ctrl+S** Save changes
- **Ctrl+N** Add dynamic zone
- **F1** User guide

**Zoom limits:**
- Cannot zoom out past entire map view
- Maximum zoom: 10x magnification

---

### Filtering Zones

**Three filter types (one active at a time):**

#### Filter by Config
1. Click first dropdown: **"Config"**
2. Second dropdown shows all configs
3. Select config number (e.g., Config 60)
4. Only zones with that config are visible

#### Filter by Category
1. Click first dropdown: **"Category"**
2. Second dropdown shows all categories
3. Select category (e.g., Zombie_Type_BigTown_Low)
4. Shows all zones containing that category

#### Filter by Zombie Class
1. Click first dropdown: **"Zombie Class"**
2. Second dropdown shows all zombies
3. Select zombie (e.g., ZmbM_PatrolNormal_Autumn)
4. Shows all zones where that zombie can spawn

**To clear filter:** Select **"None"** from first dropdown

---

### Analysis Tools

**Access via "Show Unused ▼" button in toolbar**

#### Show Unused Configs
- Lists configs from ZombiesChooseCategories.c not used by any zones
- Shows config number and category count
- Useful for planning new zones

#### Show Unused Categories
- Lists categories from ZombiesCategories.c not used by any active zones
- Shows category name and zombie count
- Helps identify underutilized content

#### Show Unused Zombies
- **Requires:** PvZmoD_CustomisableZombies_Characteristics.xml
- Lists zombie types not used by any active zones
- Shows zombie name and health points
- Helps balance zombie variety

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+S** | Save changes |
| **Ctrl+N** | Add dynamic zone |
| **Ctrl++** | Zoom in |
| **Ctrl+-** | Zoom out |
| **F1** | Show user guide |
| **Middle Mouse + Drag** | Pan map |
| **Mouse Wheel** | Zoom in/out |

---

## Danger Color Coding

### How It Works

When `PvZmoD_CustomisableZombies_Characteristics.xml` is loaded, zones are automatically color-coded based on the average health of zombies that can spawn there.

### Relative Color System

**Colors are calculated from YOUR zombie health range:**

The app finds the minimum and maximum health values in your characteristics.xml file, then divides the range into 5 equal parts (quintiles):

| Color | Danger Level | Percentile | Meaning |
|-------|-------------|-----------|---------|
| 🟢 Green | Very Low | Bottom 20% | Weakest zombies |
| 🟡 Yellow-Green | Low | 20-40% | Below average |
| 🟡 Yellow | Medium | 40-60% | Average zombies |
| 🟠 Orange | High | 60-80% | Above average |
| 🔴 Red | Very High | Top 20% | Strongest zombies |

### Examples

**Example 1: Vanilla-style (100-200 health)**
```
Range: 100 units
Green: ≤ 120 (weakest 20%)
Yellow: ≤ 160 (average)
Red: > 180 (strongest 20%)
```

**Example 2: Hardcore server (100-1000 health)**
```
Range: 900 units
Green: ≤ 280 (weakest 20%)
Yellow: ≤ 640 (average)
Red: > 820 (strongest 20%)
```

### Visual Styles

**Dynamic Zones (Rectangles):**
- Translucent colored fill
- Shows area-wide danger
- Background layer

**Static Zones (Circles):**
- Solid colored fill
- White borders for visibility
- Always on top layer
- 12px diameter

### Without Characteristics File

If you don't load the characteristics.xml file:
- All zones appear yellow (default)
- Full editing functionality still works
- No danger color coding

---

## Troubleshooting

### Common Issues

#### App won't start

**Portable/Installer versions:**
- Ensure Windows 10/11 (64-bit)
- Try running as administrator
- Check Windows Defender isn't blocking it

**Python version:**
- Verify Python 3.8+ installed: `python --version`
- Check dependencies: `pip list`
- Reinstall dependencies: `pip install -r requirements.txt`

#### Files won't load

**Check file format:**
- DynamicSpawnZones.c must have `TIntArray` entries
- StaticSpawnDatas.c must have `TFloatArray` entries
- XML files must be well-formed
- Map.png must be valid image

**Check file permissions:**
- Ensure files aren't open in another program
- Verify read permissions on all files

#### Zones not visible

**Try these steps:**
1. Check if filter is active (set to "None")
2. Zoom out to see full map
3. Verify zone has config > 0
4. Check if zone coordinates are valid

#### Zones not aligned / in wrong positions

**Map configuration mismatch:**
- Verify world size matches your zone files
- Check zone coordinate ranges in DynamicSpawnZones.c
- If zones go up to 16384, world size should be 16384
- If zones go up to 15360, world size should be 15360

**Solution:**
1. Reload files with correct map preset
2. Or use "Custom" and enter correct world size

#### Map image won't load

**Common causes:**
- Image is not square (width ≠ height)
- Invalid file format
- Corrupted image file

**Solution:**
- Ensure image is square: 2048x2048, 4096x4096, etc.
- Use PNG format (JPG also supported)
- Try re-exporting image from source

#### Colors not showing

**Requirements for danger colors:**
- PvZmoD_CustomisableZombies_Characteristics.xml must be loaded
- File must contain valid health values
- Zombies must have Day health defined

#### Changes not saving

**Common causes:**
- File is read-only (check permissions)
- File is open in another program
- Disk is full
- Path is invalid

**Solution:**
- Check .backup files are created
- Verify write permissions
- Close other editors

### Debug Information

**Log file location:**
- Same folder as executable: `pvzmod_editor_debug.log`
- Check for detailed error messages

**Settings file:**
- `pvzmod_editor_settings.json` in same folder
- Delete to reset settings

### Getting Help

1. Check the log file: `pvzmod_editor_debug.log`
2. Check Issues on GitHub
3. Create a new issue with:
   - Error message from log file
   - Steps to reproduce
   - Screenshots if relevant

---

## Best Practices

### Zone Management

✅ **DO:**
- Save frequently (Ctrl+S)
- Test changes on non-production server first
- Use comments to document zones
- Keep backups of working configurations

❌ **DON'T:**
- Edit files while server is running
- Delete .backup files until tested
- Set hundreds of zones to same config
- Use invalid config numbers

### Performance

**For best performance:**
- Close other programs while editing
- Don't load extremely large map images
- Use filtering when working with many zones
- Save periodically, don't make hundreds of changes

### Server Integration

**After editing:**
1. Test on development server first
2. Verify zones spawn correctly
3. Check for overlapping issues
4. Monitor server performance
5. Deploy to production

---

## File Formats

### DynamicSpawnZones.c

```cpp
ref autoptr TIntArray data_Zone001 = {30, 5000, 10000, 6000, 11000, 100, 25}; // Big Town
```

Parameters:
1. Config number
2. X coordinate (upper-left)
3. Z coordinate (upper-left)
4. X coordinate (lower-right)
5. Z coordinate (lower-right)
6. Quantity ratio (fixed 100)
7. Max zombies (fixed 25)

### StaticSpawnDatas.c

```cpp
ref autoptr TFloatArray data_HordeStatic001 = {radius, min, max, x, y, z, density, size, loadout, zmin, zmax, CONFIG, ...}; // Comment
```

**Editable:** Config (parameter 12) and Comment

### ZombiesChooseCategories.c

```cpp
data_Horde_30_ZombiesChooseCategories = new Param5<string, int, ref TStringArray, ref TStringArray, ref TStringArray>(
    "Zombie_Type_BigTown_Low", 100,
    Zombie_Type_BigTown_Mid, Zombie_Type_BigTown_High, Empty
);
```

Maps config numbers to categories.

### ZombiesCategories.c

```cpp
data_Zombie_Type_BigTown_Low = new Param4<string, int, ref TStringArray, ref TStringArray>(
    "Zombie_Type_BigTown_Low", 100,
    {"ZmbM_PatrolNormal_Autumn", "ZmbF_CitizenANormal_Beige", ...},
    {"", "", "", ""}
);
```

Maps categories to zombie classes.

### PvZmoD_CustomisableZombies_Characteristics.xml

```xml
<type name="ZmbM_PatrolNormal_Autumn">
    <Health_Points Day="100" Night="100"/>
</type>
```

Defines zombie health for danger color coding.

---

## Advanced Tips

### Efficient Workflow

1. **Use filters** to isolate zones you're working on
2. **Middle mouse pan** to navigate quickly
3. **Type in config dropdown** to jump to specific configs
4. **Hover over configs** to preview zombies
5. **Save often** to avoid losing work

### Zone Planning

1. **Start with dynamic zones** for area coverage
2. **Add static zones** for specific hotspots
3. **Use danger colors** to visualize difficulty
4. **Check unused configs** to find variety
5. **Test overlapping zones** carefully

### Overlapping Zones

**Remember:** Lower zone numbers take precedence
- Zone001 overrides Zone050 if overlapping
- Plan high-priority zones with lower numbers
- Use filters to see overlapping zones

---

## System Requirements

### Minimum Requirements

- **OS:** Windows 10 (64-bit)
- **RAM:** 2 GB
- **Disk:** 100 MB free space
- **Display:** 1280x720 resolution

### Recommended

- **OS:** Windows 11 (64-bit)
- **RAM:** 4 GB
- **Disk:** 500 MB free space
- **Display:** 1920x1080 resolution
- **Mouse:** 3-button mouse with scroll wheel

### Map Image Requirements

- **Format:** PNG or JPG
- **Dimensions:** Must be square (width = height)
- **Common sizes:** 1024x1024, 2048x2048, 4096x4096, 8192x8192
- **World size:** Must match zone coordinate ranges

---

## License

This program is licensed under the **GNU General Public License v3.0**.

```
PvZmoD Zone Editor
Copyright (C) 2025

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

Full license text: https://www.gnu.org/licenses/gpl-3.0.html

---

## Credits

**Development:** Created using Python, PyQt5, and open source libraries

**Libraries:**
- PyQt5 - GUI framework
- Pillow - Image processing
- lxml - XML parsing

**Special Thanks:**
- DayZ modding community
- PvZmoD framework developers

---

## Version History

### Version 1.0 (Current)

**Features:**
- Visual zone editing with danger color coding
- Support for dynamic and static zones
- Relative difficulty based on zombie health
- Advanced filtering (config/category/zombie)
- Analysis tools (show unused content)
- Settings persistence
- Comprehensive error handling
- Automatic backups

---

## Support

- **Issues:** Report bugs on GitHub Issues
- **Questions:** Check existing issues or create new one
- **Contributions:** Pull requests welcome

**Project Page:** [GitHub Repository](https://github.com/YOUR_USERNAME/pvzmod-zone-editor)

---

**Thank you for using PvZmoD Zone Editor!** 🎮
