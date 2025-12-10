# PvZmoD Spawn System Map Generator - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Features Overview](#features-overview)
4. [Using the Map Interface](#using-the-map-interface)
5. [Filtering Zones](#filtering-zones)
6. [Danger Level Heat Mapping](#danger-level-heat-mapping)
7. [Editing Zones](#editing-zones)
8. [Adding New Zones](#adding-new-zones)
9. [Resizing and Moving Zones](#resizing-and-moving-zones)
10. [Exporting Changes](#exporting-changes)
11. [Unused Items Analysis](#unused-items-analysis)
12. [Tips and Best Practices](#tips-and-best-practices)
13. [Troubleshooting](#troubleshooting)

---

## Overview

The PvZmoD Spawn System Map Generator is a powerful tool for visualizing and editing DayZ PvZmoD zombie spawn zones. It creates an interactive HTML map that displays:

- **Dynamic Zones** - Rectangular spawn areas (displayed as colored rectangles)
- **Static Zones** - Point-based spawn locations (displayed as colored dots)
- **Zombie Categories** - What types of zombies spawn in each zone
- **Danger Levels** (optional) - Color-coded threat assessment based on zombie health

The tool also provides full editing capabilities, allowing you to modify existing zones, add new ones, and export your changes back to your DayZ server files.

---

## Getting Started

### Initial Setup

1. **Launch the Application**
   - Run `pvzmod_spawn_map_generator.exe` (or `launch_zone_map_generator.bat`)
   - The GUI window will open

2. **Select Required Files**
   - **DynamicSpawnZones.c** - Contains rectangular spawn zones
   - **StaticSpawnDatas.c** - Contains point-based spawn locations
   - **ZombiesChooseCategories.c** - Defines which zombie categories each config uses
   - **ZombiesCategories.c** - Defines which zombie classnames are in each category
   - **Background Image** - Your DayZ map image (PNG or JPG)

3. **Optional: Enable Danger Level Heat Mapping**
   - Select **PvZmoD_CustomisableZombies_Characteristics.xml** 
   - This enables color-coded danger levels based on zombie health
   - Leave blank for standard yellow zones

4. **Configure Output**
   - **Output Directory** - Where to save the generated map
   - **Output Filename** - Name for the HTML file (default: `zone_map.html`)
   - **World Size** - DayZ world coordinates (default: 16384)
   - **Image Size** - Background image size in pixels (default: 4096)

5. **Generate Map**
   - Click **Generate Map**
   - Wait for processing (progress shown)
   - Click **Open in Browser** to view your map

---

## Features Overview

### Core Features
- **Interactive Map** - Pan (left-click drag) and zoom (mouse wheel)
- **Zone Visualization** - All dynamic and static zones displayed
- **Hover Tooltips** - Quick zone info on mouse hover
- **Click Popups** - Detailed zone information on click
- **Filtering** - Show only specific configs, categories, or zombies
- **Danger Coloring** (optional) - Visual threat assessment

### Editing Features
- **Edit Existing Zones** - Change config and comments
- **Add New Dynamic Zones** - Draw new rectangular zones (up to 150 total)
- **Resize Zones** - Adjust zone boundaries
- **Move Zones** - Reposition zones on the map
- **Export Changes** - Download ready-to-paste code for your .c files

### Analysis Features
- **Unused Items Detection** - Find unused configs, categories, and zombies
- **Change Tracking** - Badge indicators show pending changes
- **Export Summary** - Detailed JSON with all modifications

---

## Using the Map Interface

### Navigation
- **Pan**: Left-click and drag anywhere on the map
- **Zoom**: Use mouse wheel to zoom in/out
- **Reset View**: Refresh the page to reset pan/zoom

### Zone Types

#### Dynamic Zones (Rectangles)
- Displayed as colored rectangles with labels
- Zone ID format: `Zone1`, `Zone2`, etc.
- Can be edited, resized, and moved
- Maximum 150 dynamic zones total

#### Static Zones (Dots)
- Displayed as colored circles
- Zone ID format: `HordeStatic1`, `HordeStatic2`, etc.
- Can edit config and comment only (cannot move/resize due to Y-coordinate)

### Interacting with Zones

#### Hover (Mouse Over)
Shows quick tooltip with:
- Zone ID
- Comment
- Config number
- Categories
- Average health (if danger mapping enabled)

#### Left-Click
Opens detailed popup with:
- Full zone information
- All zombie categories
- Complete list of zombie classnames
- Danger level (if enabled)

#### Right-Click
Opens edit popup for modifying the zone

---

## Filtering Zones

The toolbar at the top provides three filter options. **Only one filter can be active at a time.**

### Filter Types

1. **Config Filter**
   - Shows only zones with the selected `num_config` value
   - Example: "Config 50" shows all zones using config 50

2. **Category Filter**
   - Shows only zones containing the selected category
   - Example: "MilitaryZombies" shows zones with military zombies

3. **Zombie Filter**
   - Shows only zones containing the selected zombie classname
   - Example: "ZmbM_PatrolNormal_Summer" shows zones with that specific zombie

### Using Filters

1. Select a filter from any dropdown
2. Other filters automatically disable
3. Map updates to show only matching zones
4. Select "Show All" to clear the filter and re-enable other filters

**Note**: Filtered zones are completely hidden (not just grayed out)

---

## Danger Level Heat Mapping

If you provided the `PvZmoD_CustomisableZombies_Characteristics.xml` file, zones are color-coded by threat level.

### Color Scale
- **Green** - Low danger (weakest zombies)
- **Yellow** - Moderate danger
- **Orange** - High danger
- **Red** - Very high danger
- **Dark Red** - Extreme danger (strongest zombies)

### How It's Calculated
- Averages the health points of all zombies in the zone
- Compares to the range across all zones
- Assigns color based on relative danger

### Legend
- Bottom-right corner shows the danger scale
- Displays min/max average health values

### Toggle
- Use the **Danger Coloring** checkbox in the toolbar
- Turn off to see all zones in standard yellow
- Turn on to restore danger colors

---

## Editing Zones

### Opening Edit Mode
1. Right-click any zone
2. Edit popup appears with current values

### Editable Fields

#### For All Zones
- **Config (num_config)**: Select from dropdown (required)
- **Comment**: Text description (optional)

#### Read-Only Fields
- **Zone ID**: Cannot be changed
- **Coordinates**: Display only (use Resize/Move to change)

### Dynamic Zone Options
- **Enable Resize/Move** button appears for dynamic zones (Zone1-Zone150)
- Static zones (HordeStatic) cannot be resized/moved due to Y-coordinate

### Saving Changes
1. Modify config and/or comment
2. Click **Save Changes**
3. Edit popup closes
4. **Export Changes** button shows badge with change count

### Canceling
- Click **Cancel** to discard changes
- Zone remains unchanged

**Important**: Changes are NOT written to files until you export and manually copy the code.

---

## Adding New Zones

You can create new dynamic zones up to the maximum of 150 total zones.

### Step-by-Step Process

1. **Enter Drawing Mode**
   - Click **+ Add Zone** button in toolbar
   - Toolbar shows "DRAWING MODE" indicator
   - Button changes to "Cancel Drawing"

2. **Draw the Zone**
   - **Right-click and drag** on the map to draw a rectangle
   - You'll see a yellow dashed outline as you drag
   - Release right mouse button to finish
   - **Minimum size**: 20x20 pixels (zones smaller than this are rejected)

3. **Set Configuration**
   - Edit popup opens automatically
   - Zone ID is assigned automatically (next available Zone number)
   - **Select a config** (required)
   - Add optional comment
   - Coordinates are already set from your drawing

4. **Save the New Zone**
   - Click **Save Changes**
   - Zone appears on map with yellow outline
   - **Export Changes** button shows (+1)

### Notes
- Left-click still pans the map while in drawing mode
- Right-click is reserved for drawing
- Click "Cancel Drawing" to exit without creating a zone
- If all 150 zones are used, the Add Zone button is disabled

---

## Resizing and Moving Zones

Dynamic zones can be resized and repositioned. **Note**: Static zones cannot be moved due to the Y-coordinate (altitude) requirement.

### Entering Resize/Move Mode

1. Right-click a dynamic zone
2. Click **📐 Enable Resize/Move** button
3. Edit popup closes
4. Zone turns **bright blue** with **dashed border**
5. **4 yellow corner handles** appear
6. Toolbar shows only:
   - **✓ Done Resizing** (green button)
   - **✗ Cancel Resize** (red button)

### Moving a Zone

1. **Right-click and drag** anywhere inside the blue rectangle (not on handles)
2. Entire zone moves with your mouse
3. Release to stop moving
4. Left-click still pans the map

### Resizing a Zone

1. **Right-click and drag** any of the 4 yellow corner handles
2. Zone resizes from that corner
3. Handles follow your mouse
4. **10-unit minimum size** prevents accidental collapse

### Multiple Adjustments

You can resize and move multiple times before exiting:
- Grab handles repeatedly to fine-tune size
- Drag the body multiple times to adjust position
- All changes are tracked

### Finishing Resize/Move

**Option 1: Save Changes**
1. Click **✓ Done Resizing** (green button)
2. Edit popup reopens with new coordinates
3. Click **Save Changes** to confirm
4. Zone reverts to normal color
5. Change is tracked for export

**Option 2: Cancel**
1. Click **✗ Cancel Resize** (red button)
2. Zone reverts to original position/size
3. Edit popup reopens with original values
4. No change is tracked

### Important Notes
- **Blue color** indicates active resize mode
- Only one zone can be in resize mode at a time
- Cannot edit other zones while in resize mode
- Left-click always pans (even in resize mode)
- Right-click is reserved for resizing/moving

---

## Exporting Changes

After editing, resizing, or adding zones, you need to export your changes.

### Export Process

1. **Check the Badge**
   - **Export Changes** button shows a badge with the number of changes
   - Example: "Export Changes (3)" means 3 zones modified/added

2. **Click Export Changes**
   - Downloads `zone_changes.json` to your browser's download folder
   - File contains everything you need

3. **Review the Export File**

The JSON file contains three sections:

#### A. Summary
```json
{
  "summary": {
    "modified_dynamic": 2,
    "modified_static": 0,
    "new_zones": 1,
    "zones_remaining": 146
  }
}
```

#### B. Detailed Changes (JSON)
Complete before/after data for all modifications

#### C. Ready-to-Paste C Code
```c
// ===== NEW ZONES - Add these to DynamicSpawnZones.c =====

ref autoptr TIntArray data_Zone47 = {60, 5084, 9186, 5410, 8972, 0, 0}; // New industrial area

// ===== MODIFIED ZONES - Replace these in their respective .c files =====

// Zone17: Config: 20 → 60, Coords: [1000,2000,1500,2500] → [900,1900,1600,2600], Comment updated
ref autoptr TIntArray data_Zone17 = {60, 900, 1900, 1600, 2600, 0, 0}; // Updated town
```

### Applying Changes to Your Server

1. **Open your DayZ server files**
2. **For new zones**: 
   - Open `DynamicSpawnZones.c`
   - Find the section where zones are defined
   - Copy and paste the new zone lines
3. **For modified zones**:
   - Find the existing line for that zone
   - Replace it with the new line from the export
4. **Save the file**
5. **Restart your server** to apply changes

### Important Notes
- Changes are NOT automatically written to files (safety feature)
- You must manually copy/paste the code
- Always backup your original files first
- Comments in the C code show what changed
- Static zone config changes require manual update of `ChoseZconfiguration` value

---

## Unused Items Analysis

Find unused configs, categories, and zombie classnames in your spawn system.

### Accessing the Analysis

1. Click **Unused Items** button (shows badge with total count)
2. Popup opens with three expandable sections

### What It Shows

#### 1. Unused Configs
- Configs defined in `ZombiesChooseCategories.c`
- But not referenced by any zone
- **Use case**: Remove unused configs to clean up files

#### 2. Unused Categories
- Categories defined in `ZombiesCategories.c`
- But not used by any config
- **Use case**: Identify forgotten categories or cleanup targets

#### 3. Unused Zombies
- Zombie classnames in `ZombiesCategories.c`
- But never appearing in any category that's actually used
- **Use case**: Remove from categories to optimize

### Using the Information

- **Click a section header** to expand/collapse
- **Review the lists** to identify cleanup opportunities
- **Note**: Empty category means "Empty" is not counted as unused

### Benefits
- Reduces file size
- Improves maintainability
- Finds forgotten content
- Quality assurance check

---

## Tips and Best Practices

### General Usage

1. **Always backup your files** before applying any changes
2. **Test on a test server** before deploying to production
3. **Use descriptive comments** when creating/editing zones
4. **Review the export file** before applying changes

### Editing Workflow

**Recommended approach:**
1. Make all your changes in one session
2. Export once when finished
3. Review the export carefully
4. Apply to test server
5. Test in-game
6. Apply to production if successful

**Avoid:**
- Making changes, exporting, then making more changes (you'll have multiple export files)
- Editing the same zone multiple times without purpose
- Creating zones smaller than visible area

### Zone Placement

1. **Use the background map** to align zones with buildings/features
2. **Test zone size in-game** - what looks good on map may need adjustment
3. **Consider overlap** - zones can overlap, zombies will spawn in both
4. **Leave space around edges** - zones at map edges may cause issues

### Performance Considerations

1. **Too many zones** can impact server performance
2. **Very large zones** may cause spawn issues
3. **Too many zombies per zone** (via categories) can lag clients
4. **Balance is key** - test and iterate

### Config Management

1. **Group similar zones** with the same config for easier management
2. **Use consistent naming** in comments (e.g., "Industrial - Harbor")
3. **Document your config system** (what does config 50 mean?)
4. **Review unused items** periodically for cleanup

---

## Troubleshooting

### Map Generation Issues

**Problem**: "No zones found" or very few zones
- **Check**: File paths are correct
- **Check**: Files are the right format (not empty or corrupted)
- **Check**: DayZ mod syntax is correct in .c files

**Problem**: Map image doesn't load
- **Check**: Image file format (PNG, JPG supported)
- **Check**: Image path is correct
- **Check**: Image isn't too large (4096x4096 recommended)

**Problem**: Danger colors not working
- **Check**: XML file path is correct
- **Check**: XML contains `Health_Points` Day values
- **Check**: Danger Coloring checkbox is enabled

### Interface Issues

**Problem**: Can't pan or zoom
- **Solution**: Refresh the page
- **Check**: Not in drawing or resize mode

**Problem**: Right-click shows browser context menu
- **Normal**: This happens outside zones or when not in edit mode
- **In Edit Mode**: Right-click should be reserved for drawing/resizing

**Problem**: Changes not showing in export
- **Check**: You clicked "Save Changes" in the edit popup
- **Check**: The Export button shows a badge number
- **Check**: Not in incognito/private browsing (file downloads may be blocked)

### Editing Issues

**Problem**: Can't resize a zone
- **Check**: It's a dynamic zone (Zone1-Zone150), not static (HordeStatic)
- **Check**: You clicked "Enable Resize/Move" button
- **Check**: Zone turned blue with handles

**Problem**: Zone disappeared after resizing
- **Check**: Did you click Cancel by accident?
- **Check**: Coordinates may be invalid (very rare)
- **Solution**: Refresh page to reset (you'll lose unsaved changes)

**Problem**: Can't add new zones
- **Check**: Total zones (existing + new) doesn't exceed 150
- **Check**: Button says "Cancel Drawing" (you're already in drawing mode)

### Export Issues

**Problem**: Export button disabled
- **Reason**: No changes have been made
- **Solution**: Make at least one change to a zone

**Problem**: Can't find the export file
- **Check**: Your browser's download folder
- **Check**: File is named `zone_changes.json`
- **Solution**: Check browser download settings

**Problem**: C code in export doesn't work
- **Check**: You copied the entire line
- **Check**: Syntax matches your existing .c file
- **Check**: No extra characters added during copy/paste

### Performance Issues

**Problem**: Map is slow or laggy
- **Cause**: Very large number of zones (200+)
- **Solution**: Close other browser tabs
- **Solution**: Use a modern browser (Chrome, Firefox, Edge)
- **Check**: Background image isn't too large

**Problem**: Browser crashes when generating
- **Cause**: Very large input files or many zones
- **Solution**: Try generating in smaller batches
- **Solution**: Increase available system RAM

---

## Keyboard Shortcuts

Currently, the map interface uses only mouse controls. Keyboard shortcuts may be added in future versions.

---

## Credits

PvZmoD Spawn System Map Generator
- Developed for DayZ PvZmoD server administrators
- Interactive HTML map with full editing capabilities
- Supports DayZ Expansion, Community Framework, and PvZmoD mods

---

## Version History

**Current Version**: Full release with editing capabilities

**Features**:
- Interactive map visualization
- Filtering by config, category, zombie
- Danger level heat mapping
- Full zone editing (config, comment)
- Add new dynamic zones
- Resize and move zones
- Export changes to .c files
- Unused items analysis

---

## Support

For issues, questions, or feature requests:
1. Check this guide first
2. Review your input files for syntax errors
3. Check the error log (if application crashes): `~/pvzmod_zonemap_error.log`

**Common support needs:**
- File format issues (check .c file syntax)
- Coordinate system questions (DayZ uses X/Z, origin at bottom-left)
- Export application (manual copy/paste required)

---

## Appendix: File Formats

### DynamicSpawnZones.c Format
```c
ref autoptr TIntArray data_Zone1 = {50, 5084, 9186, 5410, 8972, 0, 0}; // Industrial area
//                                  ^   ^     ^     ^     ^     ^  ^
//                                  |   |     |     |     |     |  |
//                                  |   |     |     |     |     |  +-- Always 0
//                                  |   |     |     |     |     +----- Always 0
//                                  |   |     |     |     +----------- coordz_lowerright
//                                  |   |     |     +----------------- coordx_lowerright
//                                  |   |     +----------------------- coordz_upleft
//                                  |   +----------------------------- coordx_upleft
//                                  +--------------------------------- num_config
```

### Coordinate System
- **Origin**: Bottom-left corner (0, 0)
- **X-axis**: Increases west → east (left to right)
- **Z-axis**: Increases south → north (bottom to top)
- **upleft**: Northwest corner (lower X, higher Z)
- **lowerright**: Southeast corner (higher X, lower Z)
- **Range**: 0 to 16384 (default DayZ map size)

---

*End of User Guide*
