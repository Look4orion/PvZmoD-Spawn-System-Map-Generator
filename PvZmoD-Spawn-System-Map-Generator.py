#!/usr/bin/env python3
"""
PvZmoD Spawn System Map Generator - With Danger Level Heat Mapping
Interactive interface for generating zone maps with optional danger level coloring.
"""

import re
import json
import shutil
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from threading import Thread
import sys
import traceback
from datetime import datetime
import xml.etree.ElementTree as ET

# ============================================================================
# ERROR LOGGING
# ============================================================================

def setup_error_logging():
    """Setup error logging to file."""
    log_file = Path.home() / "pvzmod_zonemap_error.log"
    
    def log_error(exc_type, exc_value, exc_traceback):
        """Log unhandled exceptions."""
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Error at {datetime.now()}\n")
            f.write(f"{'='*60}\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        
        # Show error dialog
        try:
            root = tk.Tk()
            root.withdraw()
            error_msg = f"An error occurred. Log saved to:\n{log_file}\n\n"
            error_msg += f"{exc_type.__name__}: {exc_value}"
            messagebox.showerror("Error", error_msg)
            root.destroy()
        except:
            pass
    
    sys.excepthook = log_error

# ============================================================================
# CORE PROCESSING FUNCTIONS
# ============================================================================

def parse_dynamic_zones(filepath, progress_callback=None):
    """Parse DynamicSpawnZones.c and extract zone rectangles."""
    if progress_callback:
        progress_callback("Parsing dynamic zones...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    pattern = r'ref autoptr\s+TIntArray\s+data_(Zone\d+)\s+=\s+\{(\d+),\s+(\d+),\s+(\d+),\s+(\d+),\s+(\d+),\s+\d+,\s+\d+\};\s+//\s*(.+)'
    zones = {}
    
    for match in re.finditer(pattern, content):
        zone_id = match.group(1)
        num_config = int(match.group(2))
        coordx_upleft = int(match.group(3))
        coordz_upleft = int(match.group(4))
        coordx_lowerright = int(match.group(5))
        coordz_lowerright = int(match.group(6))
        comment = match.group(7).strip()
        
        zones[zone_id] = {
            "num_config": num_config,
            "coordx_upleft": coordx_upleft,
            "coordz_upleft": coordz_upleft,
            "coordx_lowerright": coordx_lowerright,
            "coordz_lowerright": coordz_lowerright,
            "comment": comment
        }
    
    return zones

def parse_static_zones(filepath, progress_callback=None):
    """Parse StaticSpawnDatas.c and extract static spawn points."""
    if progress_callback:
        progress_callback("Parsing static zones...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    zones = {}
    pattern = (
        r'ref autoptr TFloatArray data_HordeStatic(\d+)\s*=\s*\{'
        r'[^}]*?'
        r'(\d+),\s*'
        r'\d+,\s*'
        r'\d+,\s*'
        r'\d+,\s*'
        r'(-?\d+(?:\.\d+)?),\s*'
        r'(-?\d+(?:\.\d+)?),\s*'
        r'(-?\d+(?:\.\d+)?),\s*'
        r'\d+,\s*'
        r'\d+,\s*'
        r'\d+,\s*'
        r'\d+,\s*'
        r'(\d+),'
        r'[^}]*'
        r'\};\s*//\s*(.+?)$'
    )
    
    for match in re.finditer(pattern, content, re.MULTILINE):
        horde_id = match.group(1)
        coord_x = float(match.group(3))
        coord_y = float(match.group(4))
        coord_z = float(match.group(5))
        chose_z_config = int(match.group(6))
        comment = match.group(7).strip()
        
        zone_id = f"HordeStatic{horde_id}"
        zones[zone_id] = {
            "num_config": chose_z_config,
            "coordx": coord_x,
            "coordy": coord_y,
            "coordz": coord_z,
            "comment": comment
        }
    
    return zones

def parse_zombie_categories(filepath, progress_callback=None):
    """Parse ZombiesChooseCategories.c to extract categories for each Horde config."""
    if progress_callback:
        progress_callback("Parsing zombie categories...")
    
    categories = {}
    
    with open(filepath, 'r') as f:
        for line in f:
            match = re.search(
                r'data_Horde_(\d+)_\w+Categories\s+=\s+new\s+Param5[^(]+\([^,]+,[^,]+,\s*(\w+),\s*(\w+),\s*(\w+)\)',
                line
            )
            
            if match:
                horde_num = int(match.group(1))
                category1 = match.group(2)
                category2 = match.group(3)
                category3 = match.group(4)
                
                categories[horde_num] = {
                    "category1": category1,
                    "category2": category2,
                    "category3": category3
                }
    
    return categories

def parse_zombie_classnames(filepath, progress_callback=None):
    """Parse ZombiesCategories.c to extract zombie classnames for each category."""
    if progress_callback:
        progress_callback("Parsing zombie classnames...")
    
    category_classnames = {}
    
    with open(filepath, 'r') as f:
        content = f.read()
        pattern = r'ref\s+autoptr\s+TStringArray\s+(\w+)\s*=\s*\{([^}]*)\};'
        
        for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
            category_name = match.group(1)
            classnames_block = match.group(2)
            
            if category_name == "Empty":
                category_classnames[category_name] = []
                continue
            
            zombies = re.findall(r'"([^"]+)"', classnames_block)
            category_classnames[category_name] = zombies
    
    return category_classnames

def parse_zombie_characteristics(filepath, progress_callback=None):
    """Parse zombie characteristics XML to get health values for each zombie type."""
    if progress_callback:
        progress_callback("Parsing zombie characteristics...")
    
    characteristics = {}
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        for zombie_type in root.findall('type'):
            name = zombie_type.get('name')
            health_elem = zombie_type.find('Health_Points')
            
            if name and health_elem is not None:
                # Use day health value
                day_health = health_elem.get('Day')
                if day_health:
                    try:
                        characteristics[name] = float(day_health)
                    except ValueError:
                        pass
        
        return characteristics
        
    except Exception as e:
        if progress_callback:
            progress_callback(f"Warning: Could not parse characteristics XML: {e}")
        return {}

def calculate_zone_danger(zone_data, characteristics):
    """Calculate average health (danger level) for a zone based on its zombies."""
    total_health = 0
    zombie_count = 0
    
    # Get all zombie classnames from the zone's categories
    skip_fields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 
                   'coordz_lowerright', 'coordx', 'coordy', 'coordz', 'comment']
    
    for key, value in zone_data.items():
        if key not in skip_fields and isinstance(value, list):
            for zombie_classname in value:
                if zombie_classname in characteristics:
                    total_health += characteristics[zombie_classname]
                    zombie_count += 1
    
    if zombie_count == 0:
        return 0
    
    return total_health / zombie_count

def get_danger_color(danger_value, min_danger, max_danger):
    """Get color for a danger value on a green-to-red scale."""
    if max_danger == min_danger:
        return "#ffff00"  # Yellow if all zones have same danger
    
    # Normalize to 0-1 range
    normalized = (danger_value - min_danger) / (max_danger - min_danger)
    
    # Color scale: green -> yellow -> orange -> red -> dark red
    if normalized < 0.25:
        # Green to yellow
        r = int(normalized * 4 * 255)
        g = 255
        b = 0
    elif normalized < 0.5:
        # Yellow to orange
        r = 255
        g = int((1 - (normalized - 0.25) * 4) * 255)
        b = 0
    elif normalized < 0.75:
        # Orange to red
        r = 255
        g = int((1 - (normalized - 0.5) * 4) * 128)
        b = 0
    else:
        # Red to dark red
        r = int((1 - (normalized - 0.75) * 4 * 0.5) * 255)
        g = 0
        b = 0
    
    return f"#{r:02x}{g:02x}{b:02x}"

def combine_zones_with_data(dynamic_zones, static_zones, categories, category_classnames, 
                            characteristics=None, progress_callback=None):
    """Combine all zones with their category data and expand to classnames."""
    if progress_callback:
        progress_callback("Combining zones with categories...")
    
    all_zones = {}
    used_configs = set()
    used_categories = set()
    used_zombies = set()
    
    for zone_id, zone_data in {**dynamic_zones, **static_zones}.items():
        num_config = zone_data.get('num_config')
        
        # Track used config
        if num_config is not None:
            used_configs.add(num_config)
        
        if num_config is not None and num_config in categories:
            cat_data = categories[num_config]
            
            for cat_key in ['category1', 'category2', 'category3']:
                cat_name = cat_data.get(cat_key)
                
                if cat_name and cat_name != "Empty":
                    # Track used category
                    used_categories.add(cat_name)
                    
                    if cat_name in category_classnames:
                        zone_data[cat_name] = category_classnames[cat_name]
                        # Track used zombies
                        for zombie in category_classnames[cat_name]:
                            used_zombies.add(zombie)
                    else:
                        zone_data[cat_name] = []
        
        # Calculate danger level if characteristics provided
        if characteristics:
            danger = calculate_zone_danger(zone_data, characteristics)
            zone_data['danger_level'] = danger
        
        all_zones[zone_id] = zone_data
    
    # Calculate unused items
    if progress_callback:
        progress_callback("Calculating unused items...")
    
    # All defined configs
    all_defined_configs = set(categories.keys())
    unused_configs = sorted(list(all_defined_configs - used_configs))
    
    # All defined categories
    all_defined_categories = set(category_classnames.keys())
    all_defined_categories.discard("Empty")  # Don't count Empty as unused
    unused_categories = sorted(list(all_defined_categories - used_categories))
    
    # All defined zombies
    all_defined_zombies = set()
    for cat_zombies in category_classnames.values():
        for zombie in cat_zombies:
            all_defined_zombies.add(zombie)
    unused_zombies = sorted(list(all_defined_zombies - used_zombies))
    
    unused_items = {
        'configs': unused_configs,
        'categories': unused_categories,
        'zombies': unused_zombies
    }
    
    # Calculate color mapping if we have danger levels
    danger_colors = None
    if characteristics:
        if progress_callback:
            progress_callback("Calculating danger levels...")
        
        dangers = [z.get('danger_level', 0) for z in all_zones.values() if z.get('danger_level', 0) > 0]
        if dangers:
            min_danger = min(dangers)
            max_danger = max(dangers)
            
            danger_colors = {
                'min': min_danger,
                'max': max_danger,
                'zones': {}
            }
            
            for zone_id, zone_data in all_zones.items():
                danger = zone_data.get('danger_level', 0)
                if danger > 0:
                    color = get_danger_color(danger, min_danger, max_danger)
                    danger_colors['zones'][zone_id] = {
                        'color': color,
                        'danger': danger
                    }
    
    return all_zones, danger_colors, unused_items

def generate_html_map(zones_data, output_path, world_size, image_size, background_image, 
                     danger_colors=None, unused_items=None, progress_callback=None):
    """Generate the interactive HTML zone map."""
    if progress_callback:
        progress_callback("Generating HTML map...")
    
    zones_js = json.dumps(zones_data, indent=2)
    danger_colors_js = json.dumps(danger_colors, indent=2) if danger_colors else "null"
    unused_items_js = json.dumps(unused_items, indent=2) if unused_items else "null"
    has_danger = danger_colors is not None
    
    # Collect all unique configs, categories, and zombie classnames for filters
    configs = set()
    categories = set()
    zombies = set()
    
    skip_fields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 
                   'coordz_lowerright', 'coordx', 'coordy', 'coordz', 'comment', 'danger_level']
    
    for zone_data in zones_data.values():
        if 'num_config' in zone_data:
            configs.add(zone_data['num_config'])
        
        for key, value in zone_data.items():
            if key not in skip_fields and isinstance(value, list):
                categories.add(key)
                for zombie in value:
                    zombies.add(zombie)
    
    configs_list = sorted(list(configs))
    categories_list = sorted(list(categories))
    zombies_list = sorted(list(zombies))
    
    configs_js = json.dumps(configs_list)
    categories_js = json.dumps(categories_list)
    zombies_js = json.dumps(zombies_list)
    
    # Generate legend HTML if we have danger colors
    legend_html = ""
    if danger_colors:
        min_d = danger_colors['min']
        max_d = danger_colors['max']
        legend_html = f'''
        <div id="legend">
            <div style="font-weight: bold; margin-bottom: 10px;">Danger Level</div>
            <div style="font-size: 11px; margin-bottom: 5px;">Avg Zombie Health</div>
            <div class="legend-gradient"></div>
            <div style="display: flex; justify-content: space-between; font-size: 10px; margin-top: 5px;">
                <span>{min_d:.0f}</span>
                <span>{max_d:.0f}</span>
            </div>
        </div>
        '''
    
    # Generate danger toggle if we have danger colors
    danger_toggle = ""
    if has_danger:
        danger_toggle = '''
        <label class="toggle-container">
            <input type="checkbox" id="dangerToggle" checked>
            <span>Danger Coloring</span>
        </label>
        '''
    
    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PvZmoD Spawn System Map</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            background: #1a1a1a;
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}
        
        #filter-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(20, 20, 20, 0.95);
            border-bottom: 2px solid #444;
            padding: 10px 20px;
            z-index: 3000;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
        }}
        
        #filter-bar .left-controls {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}
        
        #filter-bar .right-controls {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}
        
        #filter-bar label {{
            color: white;
            font-size: 12px;
            font-weight: bold;
            margin-right: 5px;
        }}
        
        #filter-bar select {{
            background: #333;
            color: white;
            border: 1px solid #555;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            min-width: 180px;
        }}
        
        #filter-bar select:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        #filter-bar select:hover:not(:disabled) {{
            background: #444;
            border-color: #666;
        }}
        
        .toggle-container {{
            display: flex;
            align-items: center;
            gap: 8px;
            color: white;
            font-size: 12px;
            cursor: pointer;
            user-select: none;
        }}
        
        .toggle-container input[type="checkbox"] {{
            width: 40px;
            height: 20px;
            cursor: pointer;
            appearance: none;
            background: #555;
            border-radius: 10px;
            position: relative;
            transition: background 0.3s;
        }}
        
        .toggle-container input[type="checkbox"]:checked {{
            background: #4CAF50;
        }}
        
        .toggle-container input[type="checkbox"]::before {{
            content: '';
            position: absolute;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: white;
            top: 2px;
            left: 2px;
            transition: left 0.3s;
        }}
        
        .toggle-container input[type="checkbox"]:checked::before {{
            left: 22px;
        }}
        
        #map-wrapper {{
            position: fixed;
            top: 50px;
            left: 0;
            width: 100vw;
            height: calc(100vh - 50px);
            overflow: hidden;
        }}
        
        #map-container {{
            position: relative;
            width: {image_size}px;
            height: {image_size}px;
            transform-origin: 0 0;
        }}
        
        #map-image {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
        }}
        
        #map-svg {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }}
        
        .zone-rect {{
            fill: none;
            stroke-width: 2;
            pointer-events: all;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        
        .zone-rect.filtered {{
            display: none;
        }}
        
        .zone-rect.hovered {{
            fill-opacity: 0.3;
        }}
        
        .zone-label {{
            fill: white;
            font-size: 8pt;
            font-weight: bold;
            paint-order: stroke;
            stroke: black;
            stroke-width: 2px;
            pointer-events: none;
            user-select: none;
            transition: opacity 0.2s;
        }}
        
        .zone-label.filtered {{
            display: none;
        }}
        
        .static-dot {{
            stroke: black;
            stroke-width: 1;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        
        .static-dot.filtered {{
            display: none;
        }}
        
        .static-dot.hovered {{
            r: 10;
        }}
        
        #tooltip {{
            position: fixed;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            border: 1px solid yellow;
            font-size: 12px;
            pointer-events: none;
            display: none;
            z-index: 1000;
            max-width: 300px;
            white-space: pre-wrap;
        }}
        
        #popup {{
            position: fixed;
            background: rgba(20, 20, 20, 0.95);
            color: white;
            padding: 20px;
            border-radius: 8px;
            border: 2px solid yellow;
            display: none;
            z-index: 2000;
            max-width: 500px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }}
        
        #popup h3 {{
            margin-bottom: 15px;
            color: yellow;
            border-bottom: 1px solid yellow;
            padding-bottom: 8px;
        }}
        
        #popup .category {{
            margin-bottom: 15px;
        }}
        
        #popup .category-name {{
            color: yellow;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        #popup .classname {{
            color: #ccc;
            font-size: 11px;
            padding-left: 10px;
            line-height: 1.4;
        }}
        
        #popup::-webkit-scrollbar {{
            width: 8px;
        }}
        
        #popup::-webkit-scrollbar-track {{
            background: #2a2a2a;
        }}
        
        #popup::-webkit-scrollbar-thumb {{
            background: yellow;
            border-radius: 4px;
        }}
        
        #legend {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 15px;
            border-radius: 8px;
            border: 2px solid yellow;
            z-index: 1500;
            min-width: 150px;
        }}
        
        .legend-gradient {{
            height: 20px;
            background: linear-gradient(to right, 
                #00ff00 0%, 
                #ffff00 25%, 
                #ff8800 50%, 
                #ff0000 75%, 
                #880000 100%);
            border: 1px solid #666;
            border-radius: 3px;
        }}
        
        #unused-btn {{
            background: #444;
            color: white;
            border: 1px solid #666;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        #unused-btn:hover {{
            background: #555;
        }}
        
        .badge {{
            background: #ff6600;
            color: white;
            border-radius: 10px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        }}
        
        #unused-popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(20, 20, 20, 0.98);
            color: white;
            padding: 25px;
            border-radius: 8px;
            border: 2px solid yellow;
            display: none;
            z-index: 4000;
            max-width: 600px;
            max-height: 70vh;
            overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8);
        }}
        
        #unused-popup h2 {{
            margin: 0 0 20px 0;
            color: yellow;
            font-size: 18px;
            border-bottom: 2px solid yellow;
            padding-bottom: 10px;
        }}
        
        .unused-section {{
            margin-bottom: 20px;
        }}
        
        .unused-section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #2a2a2a;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            user-select: none;
        }}
        
        .unused-section-header:hover {{
            background: #333;
        }}
        
        .unused-section-title {{
            font-weight: bold;
            color: #ffaa00;
        }}
        
        .unused-count {{
            background: #ff6600;
            color: white;
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: bold;
        }}
        
        .unused-list {{
            display: none;
            margin-top: 10px;
            padding: 10px;
            background: #1a1a1a;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
        }}
        
        .unused-list.expanded {{
            display: block;
        }}
        
        .unused-item {{
            padding: 5px 10px;
            margin: 3px 0;
            background: #2a2a2a;
            border-radius: 3px;
            font-size: 11px;
            font-family: monospace;
        }}
        
        .close-popup-btn {{
            background: #ff6600;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            margin-top: 15px;
            width: 100%;
        }}
        
        .close-popup-btn:hover {{
            background: #ff8800;
        }}
        
        #unused-popup::-webkit-scrollbar {{
            width: 8px;
        }}
        
        #unused-popup::-webkit-scrollbar-track {{
            background: #1a1a1a;
        }}
        
        #unused-popup::-webkit-scrollbar-thumb {{
            background: yellow;
            border-radius: 4px;
        }}
        
        .unused-list::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .unused-list::-webkit-scrollbar-track {{
            background: #0a0a0a;
        }}
        
        .unused-list::-webkit-scrollbar-thumb {{
            background: #666;
            border-radius: 3px;
        }}
        
        /* Edit Mode Styles */
        .edit-mode-active {{
            cursor: default !important;
        }}
        
        .zone-handle {{
            fill: yellow;
            stroke: black;
            stroke-width: 2;
            cursor: pointer;
            r: 6;
            pointer-events: all;
        }}
        
        .zone-handle:hover {{
            fill: orange;
            r: 8;
        }}
        
        .zone-resizing {{
            stroke-dasharray: 8,4;
            stroke-width: 3;
            stroke: #0088ff !important;
        }}
        
        .zone-resizing-body {{
            cursor: move;
        }}
        
        .drawing-rect {{
            fill: rgba(255, 255, 0, 0.2);
            stroke: yellow;
            stroke-width: 3;
            stroke-dasharray: 5,5;
        }}
        
        #edit-popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(20, 20, 20, 0.98);
            color: white;
            padding: 25px;
            border-radius: 8px;
            border: 2px solid yellow;
            display: none;
            z-index: 4000;
            min-width: 400px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8);
        }}
        
        #edit-popup h3 {{
            margin: 0 0 20px 0;
            color: yellow;
            font-size: 16px;
            border-bottom: 2px solid yellow;
            padding-bottom: 10px;
        }}
        
        .edit-field {{
            margin-bottom: 15px;
        }}
        
        .edit-field label {{
            display: block;
            margin-bottom: 5px;
            color: #aaa;
            font-size: 12px;
        }}
        
        .edit-field select,
        .edit-field input {{
            width: 100%;
            background: #2a2a2a;
            color: white;
            border: 1px solid #555;
            padding: 8px;
            border-radius: 4px;
            font-size: 13px;
        }}
        
        .edit-field input:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        .edit-buttons {{
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }}
        
        .edit-btn {{
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-weight: bold;
        }}
        
        .edit-btn-save {{
            background: #00aa00;
            color: white;
        }}
        
        .edit-btn-save:hover {{
            background: #00cc00;
        }}
        
        .edit-btn-cancel {{
            background: #666;
            color: white;
        }}
        
        .edit-btn-cancel:hover {{
            background: #888;
        }}
        
        #add-zone-btn {{
            background: #00aa00;
            color: white;
            border: 1px solid #00cc00;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        
        #add-zone-btn:hover {{
            background: #00cc00;
        }}
        
        #add-zone-btn:disabled {{
            background: #444;
            border-color: #666;
            color: #888;
            cursor: not-allowed;
        }}
        
        #export-changes-btn {{
            background: #0066cc;
            color: white;
            border: 1px solid #0088ff;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        
        #export-changes-btn:hover {{
            background: #0088ff;
        }}
        
        #export-changes-btn:disabled {{
            background: #444;
            border-color: #666;
            color: #888;
            cursor: not-allowed;
        }}
        
        #done-resize-btn {{
            background: #00aa00;
            color: white;
            border: 1px solid #00cc00;
            padding: 8px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-weight: bold;
            display: none;
        }}
        
        #done-resize-btn:hover {{
            background: #00cc00;
        }}
        
        #cancel-resize-btn {{
            background: #cc0000;
            color: white;
            border: 1px solid #ff0000;
            padding: 8px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            display: none;
        }}
        
        #cancel-resize-btn:hover {{
            background: #ff0000;
        }}
        
        .toolbar-hidden {{
            display: none !important;
        }}
        
        .edit-mode-indicator {{
            background: rgba(255, 200, 0, 0.95);
            color: black;
            padding: 10px 20px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 13px;
            display: none;
        }}
        
        .edit-mode-indicator.active {{
            display: block;
        }}
        
        .has-changes {{
            position: relative;
        }}
        
        .has-changes::after {{
            content: '';
            position: absolute;
            top: -3px;
            right: -3px;
            width: 8px;
            height: 8px;
            background: #00ff00;
            border-radius: 50%;
            border: 2px solid black;
        }}
    </style>
</head>
<body>
    <div id="filter-bar">
        <div class="left-controls">
            <div>
                <label>Config:</label>
                <select id="configFilter">
                    <option value="">Show All</option>
                </select>
            </div>
            <div>
                <label>Category:</label>
                <select id="categoryFilter">
                    <option value="">Show All</option>
                </select>
            </div>
            <div>
                <label>Zombie:</label>
                <select id="zombieFilter">
                    <option value="">Show All</option>
                </select>
            </div>
        </div>
        <div class="right-controls">
            <button id="done-resize-btn" onclick="exitResizeMode(true)">✓ Done Resizing</button>
            <button id="cancel-resize-btn" onclick="exitResizeMode(false)">✗ Cancel Resize</button>
            <button id="add-zone-btn" title="Add new dynamic zone">+ Add Zone</button>
            <button id="export-changes-btn" disabled title="Export changes">Export Changes</button>
            <button id="unused-btn">
                <span>Unused Items</span>
                <span class="badge" id="unused-badge">0</span>
            </button>
            {danger_toggle}
            <div class="edit-mode-indicator" id="edit-mode-indicator">DRAWING MODE - Right-click and drag to create zone</div>
        </div>
    </div>
    
    <div id="map-wrapper">
        <div id="map-container">
            <img id="map-image" src="{background_image}" alt="DayZ Map">
            <svg id="map-svg"></svg>
        </div>
    </div>
    
    <div id="tooltip"></div>
    <div id="popup"></div>
    {legend_html}
    
    <div id="unused-popup">
        <h2>Unused Items Analysis</h2>
        
        <div class="unused-section">
            <div class="unused-section-header" onclick="toggleUnusedSection('configs')">
                <span class="unused-section-title">Unused Configs</span>
                <span class="unused-count" id="unused-configs-count">0</span>
            </div>
            <div class="unused-list" id="unused-configs-list"></div>
        </div>
        
        <div class="unused-section">
            <div class="unused-section-header" onclick="toggleUnusedSection('categories')">
                <span class="unused-section-title">Unused Categories</span>
                <span class="unused-count" id="unused-categories-count">0</span>
            </div>
            <div class="unused-list" id="unused-categories-list"></div>
        </div>
        
        <div class="unused-section">
            <div class="unused-section-header" onclick="toggleUnusedSection('zombies')">
                <span class="unused-section-title">Unused Zombies</span>
                <span class="unused-count" id="unused-zombies-count">0</span>
            </div>
            <div class="unused-list" id="unused-zombies-list"></div>
        </div>
        
        <button class="close-popup-btn" onclick="closeUnusedPopup()">Close</button>
    </div>
    
    <div id="edit-popup">
        <h3 id="edit-popup-title">Edit Zone</h3>
        
        <div class="edit-field">
            <label>Zone ID:</label>
            <input type="text" id="edit-zone-id" disabled>
        </div>
        
        <div class="edit-field">
            <label>Config (num_config):</label>
            <select id="edit-config"></select>
        </div>
        
        <div class="edit-field">
            <label>Comment:</label>
            <input type="text" id="edit-comment" placeholder="Optional description">
        </div>
        
        <div id="edit-coords-section">
            <div class="edit-field">
                <label>Coordinates (read-only):</label>
                <input type="text" id="edit-coords" disabled>
            </div>
            <button class="edit-btn" id="enable-resize-btn" style="width: 100%; margin-top: 10px; background: #0066cc; display: none;">
                📐 Enable Resize/Move
            </button>
        </div>
        
        <div class="edit-buttons">
            <button class="edit-btn edit-btn-cancel" onclick="cancelEdit()">Cancel</button>
            <button class="edit-btn edit-btn-save" onclick="saveEdit()">Save Changes</button>
        </div>
    </div>
    
    <script>
        const zonesData = {zones_js};
        const dangerColors = {danger_colors_js};
        const unusedItems = {unused_items_js};
        const configsList = {configs_js};
        const categoriesList = {categories_js};
        const zombiesList = {zombies_js};
        const hasDanger = {str(has_danger).lower()};
        
        // Unused items popup functions
        function initializeUnusedItems() {{
            if (!unusedItems) return;
            
            const totalUnused = (unusedItems.configs?.length || 0) + 
                              (unusedItems.categories?.length || 0) + 
                              (unusedItems.zombies?.length || 0);
            
            document.getElementById('unused-badge').textContent = totalUnused;
            document.getElementById('unused-configs-count').textContent = unusedItems.configs?.length || 0;
            document.getElementById('unused-categories-count').textContent = unusedItems.categories?.length || 0;
            document.getElementById('unused-zombies-count').textContent = unusedItems.zombies?.length || 0;
            
            // Populate lists
            const configsList = document.getElementById('unused-configs-list');
            (unusedItems.configs || []).forEach(config => {{
                const item = document.createElement('div');
                item.className = 'unused-item';
                item.textContent = `Config ${{config}}`;
                configsList.appendChild(item);
            }});
            
            const categoriesList = document.getElementById('unused-categories-list');
            (unusedItems.categories || []).forEach(category => {{
                const item = document.createElement('div');
                item.className = 'unused-item';
                item.textContent = category;
                categoriesList.appendChild(item);
            }});
            
            const zombiesList = document.getElementById('unused-zombies-list');
            (unusedItems.zombies || []).forEach(zombie => {{
                const item = document.createElement('div');
                item.className = 'unused-item';
                item.textContent = zombie;
                zombiesList.appendChild(item);
            }});
            
            // Setup button click
            document.getElementById('unused-btn').addEventListener('click', () => {{
                document.getElementById('unused-popup').style.display = 'block';
            }});
        }}
        
        function toggleUnusedSection(section) {{
            const list = document.getElementById(`unused-${{section}}-list`);
            list.classList.toggle('expanded');
        }}
        
        function closeUnusedPopup() {{
            document.getElementById('unused-popup').style.display = 'none';
        }}
        
        // Close popup when clicking outside
        document.addEventListener('click', (e) => {{
            const unusedPopup = document.getElementById('unused-popup');
            const unusedBtn = document.getElementById('unused-btn');
            if (unusedPopup.style.display === 'block' && 
                !unusedPopup.contains(e.target) && 
                !unusedBtn.contains(e.target)) {{
                closeUnusedPopup();
            }}
        }});
        
        initializeUnusedItems();
        
        // ========================================================================
        // EDIT MODE FUNCTIONALITY
        // ========================================================================
        
        const MAX_ZONES = 150;
        let editMode = {{
            active: false,
            drawing: false,
            startX: null,
            startY: null,
            drawingRect: null,
            changes: {{}},
            newZones: {{}},
            editingZone: null,
            resizing: false,
            resizingZone: null,
            resizeHandles: [],
            resizeOriginalCoords: null,
            resizeOriginalStroke: null,
            resizeDragging: false,
            resizeDragType: null, // 'corner' or 'body'
            resizeDragHandle: null,
            resizeDragCorner: null, // {{controlsLeft, controlsRight, controlsTop, controlsBottom}}
            resizeStartX: null,
            resizeStartY: null
        }};
        
        function initializeEditMode() {{
            const addZoneBtn = document.getElementById('add-zone-btn');
            const exportBtn = document.getElementById('export-changes-btn');
            
            // Check how many zones exist
            const existingZoneCount = Object.keys(zonesData).filter(k => k.startsWith('Zone')).length;
            const zonesRemaining = MAX_ZONES - existingZoneCount - Object.keys(editMode.newZones).length;
            
            if (zonesRemaining <= 0) {{
                addZoneBtn.disabled = true;
                addZoneBtn.title = 'Maximum zones (150) reached';
            }}
            
            addZoneBtn.addEventListener('click', enterDrawMode);
            exportBtn.addEventListener('click', exportChanges);
            
            // Populate config dropdown in edit popup
            const editConfigSelect = document.getElementById('edit-config');
            configsList.forEach(config => {{
                const option = document.createElement('option');
                option.value = config;
                option.textContent = `Config ${{config}}`;
                editConfigSelect.appendChild(option);
            }});
        }}
        
        function enterDrawMode() {{
            editMode.active = true;
            editMode.drawing = false;
            document.getElementById('edit-mode-indicator').classList.add('active');
            document.getElementById('map-wrapper').classList.add('edit-mode-active');
            document.getElementById('add-zone-btn').textContent = 'Cancel Drawing';
            document.getElementById('add-zone-btn').onclick = exitDrawMode;
        }}
        
        function exitDrawMode() {{
            editMode.active = false;
            editMode.drawing = false;
            editMode.startX = null;
            editMode.startY = null;
            
            if (editMode.drawingRect) {{
                editMode.drawingRect.remove();
                editMode.drawingRect = null;
            }}
            
            document.getElementById('edit-mode-indicator').classList.remove('active');
            document.getElementById('map-wrapper').classList.remove('edit-mode-active');
            document.getElementById('add-zone-btn').textContent = '+ Add Zone';
            document.getElementById('add-zone-btn').onclick = enterDrawMode;
        }}
        
        function enterResizeMode(zoneId) {{
            if (!zoneId.startsWith('Zone')) {{
                alert('Only dynamic zones can be resized');
                return;
            }}
            
            // Don't allow entering resize mode if already resizing
            if (editMode.resizing) {{
                return;
            }}
            
            editMode.resizing = true;
            editMode.resizingZone = zoneId;
            
            // Store original coordinates
            const zoneData = zonesData[zoneId];
            editMode.resizeOriginalCoords = {{
                coordx_upleft: zoneData.coordx_upleft,
                coordz_upleft: zoneData.coordz_upleft,
                coordx_lowerright: zoneData.coordx_lowerright,
                coordz_lowerright: zoneData.coordz_lowerright
            }};
            
            // Store original stroke color
            const rect = document.querySelector(`rect[data-zone-id="${{zoneId}}"]`);
            if (rect) {{
                editMode.resizeOriginalStroke = rect.getAttribute('stroke');
            }}
            
            // Hide edit popup
            document.getElementById('edit-popup').style.display = 'none';
            
            // Hide regular toolbar items
            document.getElementById('add-zone-btn').classList.add('toolbar-hidden');
            document.getElementById('export-changes-btn').classList.add('toolbar-hidden');
            document.getElementById('unused-btn').classList.add('toolbar-hidden');
            document.querySelectorAll('.left-controls > div').forEach(div => div.classList.add('toolbar-hidden'));
            
            // Show resize buttons
            document.getElementById('done-resize-btn').style.display = 'block';
            document.getElementById('cancel-resize-btn').style.display = 'block';
            
            // Add resize handles to zone
            addResizeHandles(zoneId);
            
            // Highlight zone with blue color
            if (rect) {{
                rect.classList.add('zone-resizing');
                rect.classList.add('zone-resizing-body');
                // Force blue stroke color
                rect.style.stroke = '#0088ff';
                rect.style.strokeDasharray = '8,4';
                rect.style.strokeWidth = '3';
            }}
        }}
        
        function exitResizeMode(save = false) {{
            if (!editMode.resizing) return;
            
            const zoneId = editMode.resizingZone;
            const zoneData = zonesData[zoneId];
            
            // Reset resize state FIRST (before updating visual)
            const wasResizing = editMode.resizing;
            editMode.resizing = false;
            editMode.resizingZone = null;
            
            if (save) {{
                // Coordinates already updated in zoneData during dragging
                // Check if coordinates actually changed
                const coordsChanged = editMode.resizeOriginalCoords && (
                    zoneData.coordx_upleft !== editMode.resizeOriginalCoords.coordx_upleft ||
                    zoneData.coordz_upleft !== editMode.resizeOriginalCoords.coordz_upleft ||
                    zoneData.coordx_lowerright !== editMode.resizeOriginalCoords.coordx_lowerright ||
                    zoneData.coordz_lowerright !== editMode.resizeOriginalCoords.coordz_lowerright
                );
                
                // Store original coords for later save (keep them until user saves or cancels edit)
                if (coordsChanged) {{
                    // Don't clear resizeOriginalCoords yet - saveEdit needs them
                    // They'll be cleared in saveEdit or cancelEdit
                }} else {{
                    // No change, can clear now
                    editMode.resizeOriginalCoords = null;
                }}
            }} else {{
                // Revert to original coordinates
                zoneData.coordx_upleft = editMode.resizeOriginalCoords.coordx_upleft;
                zoneData.coordz_upleft = editMode.resizeOriginalCoords.coordz_upleft;
                zoneData.coordx_lowerright = editMode.resizeOriginalCoords.coordx_lowerright;
                zoneData.coordz_lowerright = editMode.resizeOriginalCoords.coordz_lowerright;
                editMode.resizeOriginalCoords = null;
            }}
            
            // Update visual now that resize state is cleared
            updateZoneVisual(zoneId);
            // Clear stroke color storage (always safe to clear)
            editMode.resizeOriginalStroke = null;
            // Note: resizeOriginalCoords kept if coords changed - will be cleared in saveEdit/cancelEdit
            
            // Remove handles
            removeResizeHandles();
            
            // Remove highlight classes and restore normal color
            const rect = document.querySelector(`rect[data-zone-id="${{zoneId}}"]`);
            if (rect) {{
                rect.classList.remove('zone-resizing');
                rect.classList.remove('zone-resizing-body');
                // Clear inline styles
                rect.style.stroke = '';
                rect.style.strokeDasharray = '';
                rect.style.strokeWidth = '';
                // Restore original stroke color
                if (editMode.resizeOriginalStroke) {{
                    rect.setAttribute('stroke', editMode.resizeOriginalStroke);
                }}
            }}
            
            // Show regular toolbar items
            document.getElementById('add-zone-btn').classList.remove('toolbar-hidden');
            document.getElementById('export-changes-btn').classList.remove('toolbar-hidden');
            document.getElementById('unused-btn').classList.remove('toolbar-hidden');
            document.querySelectorAll('.left-controls > div').forEach(div => div.classList.remove('toolbar-hidden'));
            
            // Hide resize buttons
            document.getElementById('done-resize-btn').style.display = 'none';
            document.getElementById('cancel-resize-btn').style.display = 'none';
            
            // Reopen edit popup with (possibly new) coordinates
            showEditPopup(zoneId, false);
        }}
        
        function addResizeHandles(zoneId) {{
            const svg = document.getElementById('map-svg');
            const zoneData = zonesData[zoneId];
            
            const topLeft = worldToPixel(zoneData.coordx_upleft, zoneData.coordz_upleft);
            const bottomRight = worldToPixel(zoneData.coordx_lowerright, zoneData.coordz_lowerright);
            
            // Calculate actual visual corners (after any coordinate swapping)
            const minX = Math.min(topLeft.x, bottomRight.x);
            const maxX = Math.max(topLeft.x, bottomRight.x);
            const minY = Math.min(topLeft.y, bottomRight.y);
            const maxY = Math.max(topLeft.y, bottomRight.y);
            
            const corners = [
                {{ x: minX, y: minY, type: 'tl' }},
                {{ x: maxX, y: minY, type: 'tr' }},
                {{ x: maxX, y: maxY, type: 'br' }},
                {{ x: minX, y: maxY, type: 'bl' }}
            ];
            
            corners.forEach(corner => {{
                const handle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                handle.setAttribute('cx', corner.x);
                handle.setAttribute('cy', corner.y);
                handle.setAttribute('r', 6);
                handle.classList.add('zone-handle');
                handle.dataset.handleType = corner.type;
                handle.dataset.zoneId = zoneId;
                
                handle.addEventListener('mousedown', (e) => {{
                    if (e.button !== 2) return;
                    e.preventDefault();
                    e.stopPropagation();
                    startResizeDrag(zoneId, 'corner', corner.type, e);
                }});
                
                svg.appendChild(handle);
                editMode.resizeHandles.push(handle);
            }});
        }}
        
        function removeResizeHandles() {{
            editMode.resizeHandles.forEach(handle => handle.remove());
            editMode.resizeHandles = [];
        }}
        
        function updateZoneVisual(zoneId) {{
            const zoneData = zonesData[zoneId];
            const topLeft = worldToPixel(zoneData.coordx_upleft, zoneData.coordz_upleft);
            const bottomRight = worldToPixel(zoneData.coordx_lowerright, zoneData.coordz_lowerright);
            
            const rect = document.querySelector(`rect[data-zone-id="${{zoneId}}"]`);
            if (rect) {{
                // Use min/max to ensure x,y is always top-left corner
                const x = Math.min(topLeft.x, bottomRight.x);
                const y = Math.min(topLeft.y, bottomRight.y);
                const width = Math.abs(bottomRight.x - topLeft.x);
                const height = Math.abs(bottomRight.y - topLeft.y);
                
                rect.setAttribute('x', x);
                rect.setAttribute('y', y);
                rect.setAttribute('width', width);
                rect.setAttribute('height', height);
                
                // Reapply blue color if in resize mode
                if (editMode.resizing && editMode.resizingZone === zoneId) {{
                    rect.style.stroke = '#0088ff';
                    rect.style.strokeDasharray = '8,4';
                    rect.style.strokeWidth = '3';
                }}
            }}
            
            const label = document.querySelector(`text[data-zone-id="${{zoneId}}"]`);
            if (label) {{
                const x = Math.min(topLeft.x, bottomRight.x);
                const y = Math.min(topLeft.y, bottomRight.y);
                const width = Math.abs(bottomRight.x - topLeft.x);
                const height = Math.abs(bottomRight.y - topLeft.y);
                
                label.setAttribute('x', x + width / 2);
                label.setAttribute('y', y + height / 2);
            }}
            
            // Update handles if in resize mode
            if (editMode.resizing && editMode.resizingZone === zoneId) {{
                // Calculate actual visual corners (after min/max)
                const minX = Math.min(topLeft.x, bottomRight.x);
                const maxX = Math.max(topLeft.x, bottomRight.x);
                const minY = Math.min(topLeft.y, bottomRight.y);
                const maxY = Math.max(topLeft.y, bottomRight.y);
                
                const corners = [
                    {{ x: minX, y: minY, type: 'tl' }},
                    {{ x: maxX, y: minY, type: 'tr' }},
                    {{ x: maxX, y: maxY, type: 'br' }},
                    {{ x: minX, y: maxY, type: 'bl' }}
                ];
                
                editMode.resizeHandles.forEach((handle, i) => {{
                    handle.setAttribute('cx', corners[i].x);
                    handle.setAttribute('cy', corners[i].y);
                }});
            }}
        }}
        
        function startResizeDrag(zoneId, dragType, handleType, e) {{
            editMode.resizeDragging = true;
            editMode.resizeDragType = dragType;
            editMode.resizeDragHandle = handleType;
            editMode.resizeStartX = e.clientX;
            editMode.resizeStartY = e.clientY;
            
            if (dragType === 'corner') {{
                // Get handle's ACTUAL position from the DOM
                const handleElement = e.target;
                const handleX = parseFloat(handleElement.getAttribute('cx'));
                const handleY = parseFloat(handleElement.getAttribute('cy'));
                
                const zoneData = zonesData[zoneId];
                const topLeft = worldToPixel(zoneData.coordx_upleft, zoneData.coordz_upleft);
                const bottomRight = worldToPixel(zoneData.coordx_lowerright, zoneData.coordz_lowerright);
                
                // Get actual visual corners
                const minX = Math.min(topLeft.x, bottomRight.x);
                const maxX = Math.max(topLeft.x, bottomRight.x);
                const minY = Math.min(topLeft.y, bottomRight.y);
                const maxY = Math.max(topLeft.y, bottomRight.y);
                
                // Determine which VISUAL corner we're grabbing (5px threshold)
                const isVisualLeft = Math.abs(handleX - minX) < 5;
                const isVisualTop = Math.abs(handleY - minY) < 5;
                
                // Simple: just track which visual corner we're dragging
                // We'll figure out which coords to update in handleResizeDrag
                editMode.resizeDragCorner = {{
                    isVisualLeft: isVisualLeft,
                    isVisualTop: isVisualTop
                }};
            }}
        }}
        
        function handleResizeDrag(e) {{
            if (!editMode.resizeDragging) return;
            
            const svg = document.getElementById('map-svg');
            const rect = svg.getBoundingClientRect();
            const currentX = e.clientX - rect.left;
            const currentY = e.clientY - rect.top;
            
            const zoneId = editMode.resizingZone;
            const zoneData = zonesData[zoneId];
            
            if (editMode.resizeDragType === 'corner') {{
                const worldCoord = pixelToWorld(currentX, currentY);
                
                // DayZ coordinates: X increases west→east, Z increases south→north
                // So for a rectangle: coordx_upleft < coordx_lowerright (west < east)
                //                     coordz_upleft > coordz_lowerright (north > south)
                // upleft = northwest corner, lowerright = southeast corner
                
                // Determine current state
                const topLeft = worldToPixel(zoneData.coordx_upleft, zoneData.coordz_upleft);
                const bottomRight = worldToPixel(zoneData.coordx_lowerright, zoneData.coordz_lowerright);
                const minX = Math.min(topLeft.x, bottomRight.x);
                const maxX = Math.max(topLeft.x, bottomRight.x);
                const minY = Math.min(topLeft.y, bottomRight.y);
                const maxY = Math.max(topLeft.y, bottomRight.y);
                
                // upleft coords are on visual left if topLeft.x == minX
                const upleftIsVisualLeft = (topLeft.x === minX);
                // upleft coords are on visual top if topLeft.y == minY  
                const upleftIsVisualTop = (topLeft.y === minY);
                
                // X coordinate updates
                if (editMode.resizeDragCorner.isVisualLeft) {{
                    // Dragging left edge
                    if (upleftIsVisualLeft) {{
                        // upleft is on left, update coordx_upleft
                        zoneData.coordx_upleft = Math.min(worldCoord.x, zoneData.coordx_lowerright - 10);
                    }} else {{
                        // lowerright is on left, update coordx_lowerright
                        zoneData.coordx_lowerright = Math.min(worldCoord.x, zoneData.coordx_upleft - 10);
                    }}
                }} else {{
                    // Dragging right edge
                    if (upleftIsVisualLeft) {{
                        // lowerright is on right, update coordx_lowerright
                        zoneData.coordx_lowerright = Math.max(worldCoord.x, zoneData.coordx_upleft + 10);
                    }} else {{
                        // upleft is on right, update coordx_upleft
                        zoneData.coordx_upleft = Math.max(worldCoord.x, zoneData.coordx_lowerright + 10);
                    }}
                }}
                
                // Z coordinate updates
                if (editMode.resizeDragCorner.isVisualTop) {{
                    // Dragging top edge (north, higher Z values)
                    if (upleftIsVisualTop) {{
                        // upleft is on top, update coordz_upleft (make it larger)
                        zoneData.coordz_upleft = Math.max(worldCoord.z, zoneData.coordz_lowerright + 10);
                    }} else {{
                        // lowerright is on top, update coordz_lowerright (make it larger)
                        zoneData.coordz_lowerright = Math.max(worldCoord.z, zoneData.coordz_upleft + 10);
                    }}
                }} else {{
                    // Dragging bottom edge (south, lower Z values)
                    if (upleftIsVisualTop) {{
                        // lowerright is on bottom, update coordz_lowerright (make it smaller)
                        zoneData.coordz_lowerright = Math.min(worldCoord.z, zoneData.coordz_upleft - 10);
                    }} else {{
                        // upleft is on bottom, update coordz_upleft (make it smaller)
                        zoneData.coordz_upleft = Math.min(worldCoord.z, zoneData.coordz_lowerright - 10);
                    }}
                }}
                
            }} else if (editMode.resizeDragType === 'body') {{
                const deltaX = e.clientX - editMode.resizeStartX;
                const deltaY = e.clientY - editMode.resizeStartY;
                
                const deltaWorldX = Math.round(deltaX / (({image_size}) / ({world_size})));
                const deltaWorldZ = Math.round(-deltaY / (({image_size}) / ({world_size})));
                
                zoneData.coordx_upleft += deltaWorldX;
                zoneData.coordx_lowerright += deltaWorldX;
                zoneData.coordz_upleft += deltaWorldZ;
                zoneData.coordz_lowerright += deltaWorldZ;
                
                editMode.resizeStartX = e.clientX;
                editMode.resizeStartY = e.clientY;
            }}
            
            updateZoneVisual(zoneId);
        }}
        
        function stopResizeDrag() {{
            if (!editMode.resizeDragging) return;
            
            editMode.resizeDragging = false;
            editMode.resizeDragType = null;
            editMode.resizeDragHandle = null;
            editMode.resizeDragCorner = null;
        }}
        
        function worldToPixel(x, z) {{
            const WORLD_SIZE = {world_size};
            const IMAGE_SIZE = {image_size};
            const SCALE = IMAGE_SIZE / WORLD_SIZE;
            const pixelX = x * SCALE;
            const pixelY = IMAGE_SIZE - (z * SCALE);
            return {{ x: pixelX, y: pixelY }};
        }}
        
        function pixelToWorld(pixelX, pixelY) {{
            const WORLD_SIZE = {world_size};
            const IMAGE_SIZE = {image_size};
            const SCALE = IMAGE_SIZE / WORLD_SIZE;
            const worldX = Math.round(pixelX / SCALE);
            const worldZ = Math.round((IMAGE_SIZE - pixelY) / SCALE);
            return {{ x: worldX, z: worldZ }};
        }}
        
        function getNextZoneNumber() {{
            const existingNumbers = Object.keys(zonesData)
                .filter(k => k.startsWith('Zone'))
                .map(k => parseInt(k.replace('Zone', '')))
                .concat(Object.keys(editMode.newZones).map(k => parseInt(k.replace('Zone', ''))));
            
            for (let i = 1; i <= MAX_ZONES; i++) {{
                if (!existingNumbers.includes(i)) {{
                    return i;
                }}
            }}
            return null;
        }}
        
        function renderNewZone(zoneId) {{
            const svg = document.getElementById('map-svg');
            const zoneData = zonesData[zoneId];
            
            const topLeft = worldToPixel(zoneData.coordx_upleft, zoneData.coordz_upleft);
            const bottomRight = worldToPixel(zoneData.coordx_lowerright, zoneData.coordz_lowerright);
            
            const x = Math.min(topLeft.x, bottomRight.x);
            const y = Math.min(topLeft.y, bottomRight.y);
            const width = Math.abs(bottomRight.x - topLeft.x);
            const height = Math.abs(bottomRight.y - topLeft.y);
            
            // Create rectangle
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', width);
            rect.setAttribute('height', height);
            rect.setAttribute('stroke', '#ffff00');  // Default yellow
            rect.classList.add('zone-rect');
            rect.dataset.zoneId = zoneId;
            
            // Add hover effects
            rect.addEventListener('mouseenter', (e) => {{
                rect.classList.add('hovered');
                rect.setAttribute('fill', '#ffff00');
                
                const tooltip = document.getElementById('tooltip');
                let tooltipText = `<strong>${{zoneId}}</strong><br>${{zoneData.comment || 'New zone'}}<br>num_config: ${{zoneData.num_config || 'Not set'}}`;
                tooltip.innerHTML = tooltipText;
                tooltip.style.display = 'block';
            }});
            
            rect.addEventListener('mousemove', (e) => {{
                const tooltip = document.getElementById('tooltip');
                tooltip.style.left = (e.clientX + 15) + 'px';
                tooltip.style.top = (e.clientY + 15) + 'px';
            }});
            
            rect.addEventListener('mouseleave', () => {{
                rect.classList.remove('hovered');
                rect.setAttribute('fill', 'none');
                document.getElementById('tooltip').style.display = 'none';
            }});
            
            rect.addEventListener('click', (e) => {{
                e.stopPropagation();
                const popup = document.getElementById('popup');
                let html = `<h3>${{zoneId}}</h3>`;
                html += `<p style="margin-bottom: 15px; color: #aaa;">${{zoneData.comment || 'New zone'}}</p>`;
                html += `<p>Config: ${{zoneData.num_config || 'Not set'}}</p>`;
                popup.innerHTML = html;
                popup.style.display = 'block';
                popup.style.left = Math.max(10, e.clientX + 20) + 'px';
                popup.style.top = Math.max(10, e.clientY + 20) + 'px';
            }});
            
            rect.addEventListener('contextmenu', (e) => {{
                e.preventDefault();
                e.stopPropagation();
                showEditPopup(zoneId, true);
            }});
            
            rect.addEventListener('mousedown', (e) => {{
                if (e.button !== 2) return;
                if (editMode.resizing && editMode.resizingZone === zoneId) {{
                    e.preventDefault();
                    e.stopPropagation();
                    startResizeDrag(zoneId, 'body', null, e);
                }}
            }});
            
            svg.appendChild(rect);
            
            // Create label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', x + width / 2);
            text.setAttribute('y', y + height / 2);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('dominant-baseline', 'middle');
            text.classList.add('zone-label');
            text.dataset.zoneId = zoneId;
            text.textContent = zoneId;
            svg.appendChild(text);
        }}
        
        function showEditPopup(zoneId, isNew = false) {{
            // Don't allow editing other zones while in resize mode
            if (editMode.resizing && editMode.resizingZone !== zoneId) {{
                return;
            }}
            
            const popup = document.getElementById('edit-popup');
            const titleElem = document.getElementById('edit-popup-title');
            const zoneIdInput = document.getElementById('edit-zone-id');
            const configSelect = document.getElementById('edit-config');
            const commentInput = document.getElementById('edit-comment');
            const coordsInput = document.getElementById('edit-coords');
            const enableResizeBtn = document.getElementById('enable-resize-btn');
            
            editMode.editingZone = zoneId;
            
            if (isNew) {{
                const newZone = editMode.newZones[zoneId];
                titleElem.textContent = 'New Zone - Set Config';
                zoneIdInput.value = zoneId;
                configSelect.value = '';
                commentInput.value = newZone.comment || '';
                coordsInput.value = `[${{newZone.coordx_upleft}}, ${{newZone.coordz_upleft}}, ${{newZone.coordx_lowerright}}, ${{newZone.coordz_lowerright}}]`;
                enableResizeBtn.style.display = 'none';
            }} else {{
                const zoneData = zonesData[zoneId];
                const currentChange = editMode.changes[zoneId];
                
                titleElem.textContent = 'Edit Zone';
                zoneIdInput.value = zoneId;
                configSelect.value = currentChange?.new_config || zoneData.num_config;
                commentInput.value = currentChange?.new_comment || zoneData.comment || '';
                
                if (zoneId.startsWith('Zone')) {{
                    coordsInput.value = `[${{zoneData.coordx_upleft}}, ${{zoneData.coordz_upleft}}, ${{zoneData.coordx_lowerright}}, ${{zoneData.coordz_lowerright}}]`;
                    enableResizeBtn.style.display = 'block';
                    enableResizeBtn.onclick = () => enterResizeMode(zoneId);
                }} else {{
                    coordsInput.value = `[${{zoneData.coordx}}, ${{zoneData.coordy}}, ${{zoneData.coordz}}]`;
                    enableResizeBtn.style.display = 'none';
                }}
            }}
            
            popup.style.display = 'block';
        }}
        
        function saveEdit() {{
            const zoneId = editMode.editingZone;
            const configSelect = document.getElementById('edit-config');
            const commentInput = document.getElementById('edit-comment');
            const newConfig = parseInt(configSelect.value);
            const newComment = commentInput.value.trim();
            
            if (!newConfig) {{
                alert('Please select a config');
                return;
            }}
            
            if (editMode.newZones[zoneId]) {{
                // Saving new zone
                editMode.newZones[zoneId].num_config = newConfig;
                editMode.newZones[zoneId].comment = newComment;
                
                // Also update zonesData so the zone displays correctly
                zonesData[zoneId].num_config = newConfig;
                zonesData[zoneId].comment = newComment;
            }} else {{
                // Saving changes to existing zone
                const zoneData = zonesData[zoneId];
                const oldConfig = zoneData.num_config;
                const oldComment = zoneData.comment || '';
                
                // Check if this is a dynamic zone with original coords stored
                let coordsChanged = false;
                let oldCoords = null;
                
                if (zoneId.startsWith('Zone') && editMode.resizeOriginalCoords) {{
                    oldCoords = editMode.resizeOriginalCoords;
                    coordsChanged = (
                        zoneData.coordx_upleft !== oldCoords.coordx_upleft ||
                        zoneData.coordz_upleft !== oldCoords.coordz_upleft ||
                        zoneData.coordx_lowerright !== oldCoords.coordx_lowerright ||
                        zoneData.coordz_lowerright !== oldCoords.coordz_lowerright
                    );
                }}
                
                if (newConfig !== oldConfig || newComment !== oldComment || coordsChanged) {{
                    const change = {{
                        action: 'modified',
                        old_config: oldConfig,
                        new_config: newConfig,
                        old_comment: oldComment,
                        new_comment: newComment,
                        is_static: zoneId.startsWith('HordeStatic')
                    }};
                    
                    if (coordsChanged) {{
                        change.coords_changed = true;
                        change.old_coords = [oldCoords.coordx_upleft, oldCoords.coordz_upleft, 
                                           oldCoords.coordx_lowerright, oldCoords.coordz_lowerright];
                        change.new_coords = [zoneData.coordx_upleft, zoneData.coordz_upleft,
                                           zoneData.coordx_lowerright, zoneData.coordz_lowerright];
                    }}
                    
                    editMode.changes[zoneId] = change;
                }} else {{
                    delete editMode.changes[zoneId];
                }}
                
                // Clear resize original coords
                editMode.resizeOriginalCoords = null;
            }}
            
            updateExportButton();
            cancelEdit();
        }}
        
        function cancelEdit() {{
            document.getElementById('edit-popup').style.display = 'none';
            editMode.editingZone = null;
            editMode.resizeOriginalCoords = null;
        }}
        
        function updateExportButton() {{
            const exportBtn = document.getElementById('export-changes-btn');
            const changeCount = Object.keys(editMode.changes).length + Object.keys(editMode.newZones).length;
            
            if (changeCount > 0) {{
                exportBtn.disabled = false;
                exportBtn.textContent = `Export Changes (${{changeCount}})`;
                exportBtn.classList.add('has-changes');
            }} else {{
                exportBtn.disabled = true;
                exportBtn.textContent = 'Export Changes';
                exportBtn.classList.remove('has-changes');
            }}
        }}
        
        function exportChanges() {{
            const existingZoneCount = Object.keys(zonesData).filter(k => k.startsWith('Zone')).length;
            const zonesRemaining = MAX_ZONES - existingZoneCount - Object.keys(editMode.newZones).length;
            
            const exportData = {{
                summary: {{
                    modified_dynamic: Object.values(editMode.changes).filter(c => !c.is_static).length,
                    modified_static: Object.values(editMode.changes).filter(c => c.is_static).length,
                    new_zones: Object.keys(editMode.newZones).length,
                    zones_remaining: zonesRemaining
                }},
                changes: editMode.changes,
                new_zones: editMode.newZones,
                paste_into_c_file: []
            }};
            
            // Generate ready-to-paste C code
            if (Object.keys(editMode.newZones).length > 0) {{
                exportData.paste_into_c_file.push('// ===== NEW ZONES - Add these to DynamicSpawnZones.c =====');
                exportData.paste_into_c_file.push('');
                
                Object.entries(editMode.newZones).sort((a, b) => {{
                    const numA = parseInt(a[0].replace('Zone', ''));
                    const numB = parseInt(b[0].replace('Zone', ''));
                    return numA - numB;
                }}).forEach(([zoneId, data]) => {{
                    const line = `ref autoptr TIntArray data_${{zoneId}} = {{${{data.num_config}}, ${{data.coordx_upleft}}, ${{data.coordz_upleft}}, ${{data.coordx_lowerright}}, ${{data.coordz_lowerright}}, 0, 0}}; // ${{data.comment}}`;
                    exportData.paste_into_c_file.push(line);
                }});
                exportData.paste_into_c_file.push('');
            }}
            
            if (Object.keys(editMode.changes).length > 0) {{
                exportData.paste_into_c_file.push('// ===== MODIFIED ZONES - Replace these in their respective .c files =====');
                exportData.paste_into_c_file.push('');
                
                Object.entries(editMode.changes).forEach(([zoneId, change]) => {{
                    if (change.is_static) {{
                        exportData.paste_into_c_file.push(`// ${{zoneId}}: Config changed from ${{change.old_config}} to ${{change.new_config}}`);
                        exportData.paste_into_c_file.push('// (Manually update ChoseZconfiguration value in StaticSpawnDatas.c)');
                    }} else {{
                        const zoneData = zonesData[zoneId];
                        const comment = change.new_comment || zoneData.comment || '';
                        
                        // Add comment about what changed
                        const changes = [];
                        if (change.old_config !== change.new_config) {{
                            changes.push(`Config: ${{change.old_config}} → ${{change.new_config}}`);
                        }}
                        if (change.coords_changed) {{
                            changes.push(`Coords: [${{change.old_coords.join(',')}}] → [${{change.new_coords.join(',')}}]`);
                        }}
                        if (change.old_comment !== change.new_comment) {{
                            changes.push('Comment updated');
                        }}
                        
                        if (changes.length > 0) {{
                            exportData.paste_into_c_file.push(`// ${{zoneId}}: ${{changes.join(', ')}}`);
                        }}
                        
                        const line = `ref autoptr TIntArray data_${{zoneId}} = {{${{change.new_config}}, ${{zoneData.coordx_upleft}}, ${{zoneData.coordz_upleft}}, ${{zoneData.coordx_lowerright}}, ${{zoneData.coordz_lowerright}}, 0, 0}}; // ${{comment}}`;
                        exportData.paste_into_c_file.push(line);
                        exportData.paste_into_c_file.push('');
                    }}
                }});
            }}
            
            // Download as JSON
            const blob = new Blob([JSON.stringify(exportData, null, 2)], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'zone_changes.json';
            a.click();
            URL.revokeObjectURL(url);
        }}
        
        // Initialize edit mode
        initializeEditMode();
        
        // Wire up resize mode buttons
        document.getElementById('done-resize-btn').addEventListener('click', () => exitResizeMode(true));
        document.getElementById('cancel-resize-btn').addEventListener('click', () => exitResizeMode(false));
        
        // Global mouse handlers for resize dragging
        document.addEventListener('mousemove', (e) => {{
            if (editMode.resizeDragging) {{
                handleResizeDrag(e);
            }}
        }});
        
        document.addEventListener('mouseup', (e) => {{
            if (e.button === 2 && editMode.resizeDragging) {{
                stopResizeDrag();
            }}
        }});
        
        // Handle drawing mode for SVG
        const svg = document.getElementById('map-svg');
        const mapContainer = document.getElementById('map-container');
        
        svg.addEventListener('mousedown', (e) => {{
            if (!editMode.active) return;
            if (e.button !== 2) return; // Only right click for drawing
            e.preventDefault(); // Prevent context menu
            
            const rect = svg.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            editMode.drawing = true;
            editMode.startX = x;
            editMode.startY = y;
            
            // Create drawing rectangle
            editMode.drawingRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            editMode.drawingRect.classList.add('drawing-rect');
            svg.appendChild(editMode.drawingRect);
        }});
        
        svg.addEventListener('mousemove', (e) => {{
            if (!editMode.drawing) return;
            
            const rect = svg.getBoundingClientRect();
            const currentX = e.clientX - rect.left;
            const currentY = e.clientY - rect.top;
            
            const x = Math.min(editMode.startX, currentX);
            const y = Math.min(editMode.startY, currentY);
            const width = Math.abs(currentX - editMode.startX);
            const height = Math.abs(currentY - editMode.startY);
            
            editMode.drawingRect.setAttribute('x', x);
            editMode.drawingRect.setAttribute('y', y);
            editMode.drawingRect.setAttribute('width', width);
            editMode.drawingRect.setAttribute('height', height);
        }});
        
        svg.addEventListener('mouseup', (e) => {{
            if (!editMode.drawing) return;
            if (e.button !== 2) return; // Only handle right click release
            
            const rect = svg.getBoundingClientRect();
            const endX = e.clientX - rect.left;
            const endY = e.clientY - rect.top;
            
            const width = Math.abs(endX - editMode.startX);
            const height = Math.abs(endY - editMode.startY);
            
            // Minimum size check
            if (width < 20 || height < 20) {{
                alert('Zone too small. Draw a larger area.');
                editMode.drawingRect.remove();
                editMode.drawing = false;
                return;
            }}
            
            // Convert to world coordinates
            const topLeft = pixelToWorld(
                Math.min(editMode.startX, endX),
                Math.min(editMode.startY, endY)
            );
            const bottomRight = pixelToWorld(
                Math.max(editMode.startX, endX),
                Math.max(editMode.startY, endY)
            );
            
            // Get next zone number
            const zoneNum = getNextZoneNumber();
            if (zoneNum === null) {{
                alert('Maximum zones (150) reached!');
                editMode.drawingRect.remove();
                editMode.drawing = false;
                exitDrawMode();
                return;
            }}
            
            const zoneId = `Zone${{zoneNum}}`;
            
            // Store new zone
            editMode.newZones[zoneId] = {{
                action: 'created',
                coordx_upleft: topLeft.x,
                coordz_upleft: topLeft.z,
                coordx_lowerright: bottomRight.x,
                coordz_lowerright: bottomRight.z,
                comment: ''
            }};
            
            // Add to zonesData so it appears on map
            zonesData[zoneId] = {{
                coordx_upleft: topLeft.x,
                coordz_upleft: topLeft.z,
                coordx_lowerright: bottomRight.x,
                coordz_lowerright: bottomRight.z,
                comment: '',
                num_config: null  // Will be set when user saves
            }};
            
            // Remove drawing rect
            editMode.drawingRect.remove();
            editMode.drawing = false;
            
            // Exit draw mode and show edit popup
            exitDrawMode();
            
            // Render the new zone on the map
            renderNewZone(zoneId);
            
            showEditPopup(zoneId, true);
            updateExportButton();
            
            // Update add zone button if at limit
            const existingZoneCount = Object.keys(zonesData).filter(k => k.startsWith('Zone')).length;
            const zonesRemaining = MAX_ZONES - existingZoneCount - Object.keys(editMode.newZones).length;
            
            if (zonesRemaining <= 0) {{
                document.getElementById('add-zone-btn').disabled = true;
                document.getElementById('add-zone-btn').title = 'Maximum zones (150) reached';
            }}
        }});
        
        // Prevent context menu in drawing mode
        svg.addEventListener('contextmenu', (e) => {{
            if (editMode.active || editMode.drawing || editMode.resizing) {{
                e.preventDefault();
            }}
        }});
        
        initializeMap();
        
        function initializeMap() {{
            const svg = document.getElementById('map-svg');
            const tooltip = document.getElementById('tooltip');
            const popup = document.getElementById('popup');
            
            // Initialize filter dropdowns
            const configFilter = document.getElementById('configFilter');
            const categoryFilter = document.getElementById('categoryFilter');
            const zombieFilter = document.getElementById('zombieFilter');
            const dangerToggle = document.getElementById('dangerToggle');
            
            // Populate dropdowns
            configsList.forEach(config => {{
                const option = document.createElement('option');
                option.value = config;
                option.textContent = `Config ${{config}}`;
                configFilter.appendChild(option);
            }});
            
            categoriesList.forEach(category => {{
                const option = document.createElement('option');
                option.value = category;
                option.textContent = category;
                categoryFilter.appendChild(option);
            }});
            
            zombiesList.forEach(zombie => {{
                const option = document.createElement('option');
                option.value = zombie;
                option.textContent = zombie;
                zombieFilter.appendChild(option);
            }});
            
            // Filter change handlers - only allow one filter at a time
            configFilter.addEventListener('change', () => {{
                if (configFilter.value) {{
                    categoryFilter.value = '';
                    zombieFilter.value = '';
                    categoryFilter.disabled = true;
                    zombieFilter.disabled = true;
                }} else {{
                    categoryFilter.disabled = false;
                    zombieFilter.disabled = false;
                }}
                applyFilters();
            }});
            
            categoryFilter.addEventListener('change', () => {{
                if (categoryFilter.value) {{
                    configFilter.value = '';
                    zombieFilter.value = '';
                    configFilter.disabled = true;
                    zombieFilter.disabled = true;
                }} else {{
                    configFilter.disabled = false;
                    zombieFilter.disabled = false;
                }}
                applyFilters();
            }});
            
            zombieFilter.addEventListener('change', () => {{
                if (zombieFilter.value) {{
                    configFilter.value = '';
                    categoryFilter.value = '';
                    configFilter.disabled = true;
                    categoryFilter.disabled = true;
                }} else {{
                    configFilter.disabled = false;
                    categoryFilter.disabled = false;
                }}
                applyFilters();
            }});
            
            // Danger toggle handler
            if (dangerToggle) {{
                dangerToggle.addEventListener('change', () => {{
                    updateZoneColors();
                }});
            }}
            
            const WORLD_SIZE = {world_size};
            const IMAGE_SIZE = {image_size};
            const SCALE = IMAGE_SIZE / WORLD_SIZE;
            
            function worldToPixel(x, z) {{
                const pixelX = x * SCALE;
                const pixelY = IMAGE_SIZE - (z * SCALE);
                return {{ x: pixelX, y: pixelY }};
            }}
            
            function getZoneColor(zoneId) {{
                const dangerToggle = document.getElementById('dangerToggle');
                const useDanger = hasDanger && (!dangerToggle || dangerToggle.checked);
                
                if (useDanger && dangerColors && dangerColors.zones[zoneId]) {{
                    return dangerColors.zones[zoneId].color;
                }}
                return '#ffff00'; // Default yellow
            }}
            
            function zoneMatchesFilter(zoneId, zoneData) {{
                const configFilter = document.getElementById('configFilter');
                const categoryFilter = document.getElementById('categoryFilter');
                const zombieFilter = document.getElementById('zombieFilter');
                
                const selectedConfig = configFilter.value;
                const selectedCategory = categoryFilter.value;
                const selectedZombie = zombieFilter.value;
                
                // If no filters selected, show all
                if (!selectedConfig && !selectedCategory && !selectedZombie) {{
                    return true;
                }}
                
                // Config filter
                if (selectedConfig) {{
                    return zoneData.num_config == selectedConfig;
                }}
                
                // Category filter
                if (selectedCategory) {{
                    return selectedCategory in zoneData && Array.isArray(zoneData[selectedCategory]);
                }}
                
                // Zombie filter
                if (selectedZombie) {{
                    const skipFields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 
                                       'coordz_lowerright', 'coordx', 'coordy', 'coordz', 'comment', 'danger_level'];
                    for (const [key, value] of Object.entries(zoneData)) {{
                        if (!skipFields.includes(key) && Array.isArray(value)) {{
                            if (value.includes(selectedZombie)) {{
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }}
                
                return true;
            }}
            
            function applyFilters() {{
                dynamicZones.forEach(zone => {{
                    const matches = zoneMatchesFilter(zone.id, zone.data);
                    const rect = svg.querySelector(`rect[data-zone-id="${{zone.id}}"]`);
                    const label = svg.querySelector(`text[data-zone-id="${{zone.id}}"]`);
                    
                    if (rect) {{
                        if (matches) {{
                            rect.classList.remove('filtered');
                        }} else {{
                            rect.classList.add('filtered');
                        }}
                    }}
                    
                    if (label) {{
                        if (matches) {{
                            label.classList.remove('filtered');
                        }} else {{
                            label.classList.add('filtered');
                        }}
                    }}
                }});
                
                staticZones.forEach(zone => {{
                    const matches = zoneMatchesFilter(zone.id, zone.data);
                    const circle = svg.querySelector(`circle[data-zone-id="${{zone.id}}"]`);
                    
                    if (circle) {{
                        if (matches) {{
                            circle.classList.remove('filtered');
                        }} else {{
                            circle.classList.add('filtered');
                        }}
                    }}
                }});
            }}
            
            function updateZoneColors() {{
                dynamicZones.forEach(zone => {{
                    // Skip zones in resize mode - they have their own styling
                    if (editMode.resizing && editMode.resizingZone === zone.id) {{
                        return;
                    }}
                    
                    const color = getZoneColor(zone.id);
                    const rect = svg.querySelector(`rect[data-zone-id="${{zone.id}}"]`);
                    if (rect) {{
                        rect.setAttribute('stroke', color);
                    }}
                }});
                
                staticZones.forEach(zone => {{
                    const color = getZoneColor(zone.id);
                    const circle = svg.querySelector(`circle[data-zone-id="${{zone.id}}"]`);
                    if (circle) {{
                        circle.setAttribute('fill', color);
                    }}
                }});
            }}
            
            const dynamicZones = [];
            const staticZones = [];
            
            for (const [key, value] of Object.entries(zonesData)) {{
                if (key.startsWith('Zone')) {{
                    if (value && value.coordx_upleft !== undefined && value.coordz_upleft !== undefined &&
                        value.coordx_lowerright !== undefined && value.coordz_lowerright !== undefined &&
                        !isNaN(value.coordx_upleft) && !isNaN(value.coordz_upleft) &&
                        !isNaN(value.coordx_lowerright) && !isNaN(value.coordz_lowerright)) {{
                        const zoneNum = parseInt(key.replace('Zone', ''));
                        dynamicZones.push({{ id: key, num: zoneNum, data: value }});
                    }}
                }} else if (key.startsWith('HordeStatic')) {{
                    if (value && value.coordx !== undefined && value.coordz !== undefined &&
                        !isNaN(value.coordx) && !isNaN(value.coordz)) {{
                        const zoneNum = parseInt(key.replace('HordeStatic', ''));
                        staticZones.push({{ id: key, num: zoneNum, data: value }});
                    }}
                }}
            }}
            
            dynamicZones.sort((a, b) => a.num - b.num);
            staticZones.sort((a, b) => a.num - b.num);
            
            console.log(`Loaded ${{dynamicZones.length}} dynamic zones and ${{staticZones.length}} static zones`);
            if (dangerColors) {{
                console.log(`Danger levels: ${{dangerColors.min.toFixed(0)}} - ${{dangerColors.max.toFixed(0)}} avg health`);
            }}
            
            dynamicZones.forEach(zone => {{
                const topLeft = worldToPixel(zone.data.coordx_upleft, zone.data.coordz_upleft);
                const bottomRight = worldToPixel(zone.data.coordx_lowerright, zone.data.coordz_lowerright);
                
                const x = topLeft.x;
                const y = topLeft.y;
                const width = bottomRight.x - topLeft.x;
                const height = bottomRight.y - topLeft.y;
                
                const color = getZoneColor(zone.id);
                
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y);
                rect.setAttribute('width', width);
                rect.setAttribute('height', height);
                rect.setAttribute('stroke', color);
                rect.classList.add('zone-rect');
                rect.dataset.zoneId = zone.id;
                
                rect.addEventListener('mouseenter', (e) => {{
                    rect.classList.add('hovered');
                    rect.setAttribute('fill', color);
                    
                    const skipFields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 'coordz_lowerright', 'comment', 'danger_level'];
                    const categories = Object.keys(zone.data).filter(k => !skipFields.includes(k)).join(', ');
                    
                    let tooltipText = `<strong>${{zone.id}}</strong><br>${{zone.data.comment}}<br>num_config: ${{zone.data.num_config}}<br>Categories: ${{categories}}`;
                    
                    if (dangerColors && dangerColors.zones[zone.id]) {{
                        tooltipText += `<br>Avg Health: ${{dangerColors.zones[zone.id].danger.toFixed(0)}}`;
                    }}
                    
                    tooltip.innerHTML = tooltipText;
                    tooltip.style.display = 'block';
                }});
                
                rect.addEventListener('mousemove', (e) => {{
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                }});
                
                rect.addEventListener('mouseleave', () => {{
                    rect.classList.remove('hovered');
                    rect.setAttribute('fill', 'none');
                    tooltip.style.display = 'none';
                }});
                
                rect.addEventListener('click', (e) => {{
                    e.stopPropagation();
                    showPopup(zone.id, zone.data, e.clientX, e.clientY);
                }});
                
                rect.addEventListener('contextmenu', (e) => {{
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // If in resize mode and this is the zone being resized, don't open popup
                    if (editMode.resizing && editMode.resizingZone === zone.id) {{
                        return;
                    }}
                    
                    showEditPopup(zone.id, false);
                }});
                
                rect.addEventListener('mousedown', (e) => {{
                    if (e.button !== 2) return; // Only right-click
                    if (editMode.resizing && editMode.resizingZone === zone.id) {{
                        e.preventDefault();
                        e.stopPropagation();
                        startResizeDrag(zone.id, 'body', null, e);
                    }}
                }});
                
                svg.appendChild(rect);
                
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', x + width / 2);
                text.setAttribute('y', y + height / 2);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('dominant-baseline', 'middle');
                text.classList.add('zone-label');
                text.dataset.zoneId = zone.id;
                text.textContent = zone.id;
                svg.appendChild(text);
            }});
            
            staticZones.forEach(zone => {{
                const pos = worldToPixel(zone.data.coordx, zone.data.coordz);
                const color = getZoneColor(zone.id);
                
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', pos.x);
                circle.setAttribute('cy', pos.y);
                circle.setAttribute('r', 8);
                circle.setAttribute('fill', color);
                circle.classList.add('static-dot');
                circle.dataset.zoneId = zone.id;
                
                circle.addEventListener('mouseenter', (e) => {{
                    circle.classList.add('hovered');
                    
                    const skipFields = ['num_config', 'coordx', 'coordy', 'coordz', 'comment', 'danger_level'];
                    const categories = Object.keys(zone.data).filter(k => !skipFields.includes(k)).join(', ');
                    
                    let tooltipText = `<strong>${{zone.id}}</strong><br>${{zone.data.comment}}<br>Coordinates: ${{zone.data.coordx}}, ${{zone.data.coordy}}, ${{zone.data.coordz}}<br>num_config: ${{zone.data.num_config}}<br>Categories: ${{categories}}`;
                    
                    if (dangerColors && dangerColors.zones[zone.id]) {{
                        tooltipText += `<br>Avg Health: ${{dangerColors.zones[zone.id].danger.toFixed(0)}}`;
                    }}
                    
                    tooltip.innerHTML = tooltipText;
                    tooltip.style.display = 'block';
                }});
                
                circle.addEventListener('mousemove', (e) => {{
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                }});
                
                circle.addEventListener('mouseleave', () => {{
                    circle.classList.remove('hovered');
                    circle.setAttribute('r', 8);
                    tooltip.style.display = 'none';
                }});
                
                circle.addEventListener('click', (e) => {{
                    e.stopPropagation();
                    showPopup(zone.id, zone.data, e.clientX, e.clientY);
                }});
                
                circle.addEventListener('contextmenu', (e) => {{
                    e.preventDefault();
                    e.stopPropagation();
                    showEditPopup(zone.id, false);
                }});
                
                svg.appendChild(circle);
            }});
            
            function showPopup(zoneId, data, mouseX, mouseY) {{
                let html = `<h3>${{zoneId}}</h3>`;
                
                if (data.comment) {{
                    html += `<p style="margin-bottom: 15px; color: #aaa;">${{data.comment}}</p>`;
                }}
                
                if (dangerColors && dangerColors.zones[zoneId]) {{
                    const avgHealth = dangerColors.zones[zoneId].danger.toFixed(0);
                    const color = dangerColors.zones[zoneId].color;
                    html += `<p style="margin-bottom: 15px;">
                        <strong>Danger Level:</strong> 
                        <span style="color: ${{color}}; font-weight: bold;">${{avgHealth}} avg health</span>
                    </p>`;
                }}
                
                const skipFields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 'coordz_lowerright', 'coordx', 'coordy', 'coordz', 'comment', 'danger_level'];
                const categoryKeys = Object.keys(data).filter(k => !skipFields.includes(k));
                
                for (const category of categoryKeys) {{
                    const classnames = data[category];
                    if (Array.isArray(classnames)) {{
                        html += `<div class="category">`;
                        html += `<div class="category-name">${{category}} (${{classnames.length}}):</div>`;
                        classnames.forEach(classname => {{
                            html += `<div class="classname">${{classname}}</div>`;
                        }});
                        html += `</div>`;
                    }}
                }}
                
                popup.innerHTML = html;
                popup.style.display = 'block';
                
                let left = mouseX + 20;
                let top = mouseY + 20;
                
                const rect = popup.getBoundingClientRect();
                if (left + rect.width > window.innerWidth) {{
                    left = mouseX - rect.width - 20;
                }}
                if (top + rect.height > window.innerHeight) {{
                    top = window.innerHeight - rect.height - 20;
                }}
                
                popup.style.left = Math.max(10, left) + 'px';
                popup.style.top = Math.max(10, top) + 'px';
            }}
            
            document.addEventListener('click', (e) => {{
                if (!popup.contains(e.target)) {{
                    popup.style.display = 'none';
                }}
            }});
            
            initializePanZoom();
        }}
        
        function initializePanZoom() {{
            const wrapper = document.getElementById('map-wrapper');
            const container = document.getElementById('map-container');
            
            let scale = 1;
            let translateX = 0;
            let translateY = 0;
            let isDragging = false;
            let startX = 0;
            let startY = 0;
            
            function getMinScale() {{
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;
                const mapWidth = {image_size};
                const mapHeight = {image_size};
                return Math.min(viewportWidth / mapWidth, viewportHeight / mapHeight);
            }}
            
            let minScale = getMinScale();
            
            function centerMap() {{
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;
                const mapWidth = {image_size} * scale;
                const mapHeight = {image_size} * scale;
                translateX = (viewportWidth - mapWidth) / 2;
                translateY = (viewportHeight - mapHeight) / 2;
                updateTransform();
            }}
            
            function updateTransform() {{
                container.style.transform = `translate(${{translateX}}px, ${{translateY}}px) scale(${{scale}})`;
            }}
            
            wrapper.addEventListener('wheel', (e) => {{
                e.preventDefault();
                const rect = wrapper.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                const mapX = (mouseX - translateX) / scale;
                const mapY = (mouseY - translateY) / scale;
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                const newScale = Math.max(minScale, scale * delta);
                translateX = mouseX - mapX * newScale;
                translateY = mouseY - mapY * newScale;
                scale = newScale;
                updateTransform();
            }}, {{ passive: false }});
            
            wrapper.addEventListener('mousedown', (e) => {{
                if (e.button === 0) {{
                    isDragging = true;
                    startX = e.clientX - translateX;
                    startY = e.clientY - translateY;
                    wrapper.style.cursor = 'grabbing';
                }}
            }});
            
            document.addEventListener('mousemove', (e) => {{
                if (isDragging) {{
                    translateX = e.clientX - startX;
                    translateY = e.clientY - startY;
                    updateTransform();
                }}
            }});
            
            document.addEventListener('mouseup', () => {{
                if (isDragging) {{
                    isDragging = false;
                    wrapper.style.cursor = 'grab';
                }}
            }});
            
            wrapper.style.cursor = 'grab';
            
            window.addEventListener('resize', () => {{
                minScale = getMinScale();
                if (scale < minScale) {{
                    scale = minScale;
                    centerMap();
                }}
            }});
            
            scale = 1.0;
            centerMap();
        }}
    </script>
</body>
</html>'''
    
    with open(output_path, 'w') as f:
        f.write(html_template)

def process_zones(dynamic_file, static_file, categories_file, classnames_file, 
                 background_file, output_dir, output_filename, world_size, image_size,
                 characteristics_file=None, progress_callback=None):
    """Main processing function."""
    try:
        # Parse all data
        dynamic_zones = parse_dynamic_zones(dynamic_file, progress_callback)
        static_zones = parse_static_zones(static_file, progress_callback)
        categories = parse_zombie_categories(categories_file, progress_callback)
        category_classnames = parse_zombie_classnames(classnames_file, progress_callback)
        
        # Parse characteristics if provided
        characteristics = None
        if characteristics_file:
            characteristics = parse_zombie_characteristics(characteristics_file, progress_callback)
        
        # Combine data
        all_zones, danger_colors, unused_items = combine_zones_with_data(
            dynamic_zones, static_zones, categories, category_classnames,
            characteristics, progress_callback
        )
        
        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Copy background image to output directory
        if progress_callback:
            progress_callback("Copying background image...")
        bg_filename = Path(background_file).name
        bg_dest = output_path / bg_filename
        shutil.copy2(background_file, bg_dest)
        
        # Generate HTML
        html_path = output_path / output_filename
        generate_html_map(all_zones, html_path, world_size, image_size, 
                         bg_filename, danger_colors, unused_items, progress_callback)
        
        return True, html_path, len(dynamic_zones), len(static_zones), len(all_zones)
        
    except Exception as e:
        return False, str(e), 0, 0, 0

# ============================================================================
# GUI APPLICATION
# ============================================================================

class ZoneMapGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PvZmoD Spawn System Map Generator")
        self.root.geometry("700x750")
        self.root.resizable(False, False)
        
        # Load saved settings
        self.config_file = Path.home() / ".pvzmod_zonemap_config.json"
        self.settings = self.load_settings()
        
        # Variables
        self.dynamic_file = tk.StringVar(value=self.settings.get("dynamic_file", ""))
        self.static_file = tk.StringVar(value=self.settings.get("static_file", ""))
        self.categories_file = tk.StringVar(value=self.settings.get("categories_file", ""))
        self.classnames_file = tk.StringVar(value=self.settings.get("classnames_file", ""))
        self.background_file = tk.StringVar(value=self.settings.get("background_file", ""))
        self.characteristics_file = tk.StringVar(value=self.settings.get("characteristics_file", ""))
        self.output_dir = tk.StringVar(value=self.settings.get("output_dir", ""))
        self.output_filename = tk.StringVar(value=self.settings.get("output_filename", "zone_map.html"))
        self.world_size = tk.StringVar(value=self.settings.get("world_size", "16384"))
        self.image_size = tk.StringVar(value=self.settings.get("image_size", "4096"))
        self.last_dir = self.settings.get("last_dir", str(Path.home()))
        
        self.create_widgets()
        
    def load_settings(self):
        """Load saved settings from config file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_settings(self):
        """Save current settings to config file."""
        settings = {
            "dynamic_file": self.dynamic_file.get(),
            "static_file": self.static_file.get(),
            "categories_file": self.categories_file.get(),
            "classnames_file": self.classnames_file.get(),
            "background_file": self.background_file.get(),
            "characteristics_file": self.characteristics_file.get(),
            "output_dir": self.output_dir.get(),
            "output_filename": self.output_filename.get(),
            "world_size": self.world_size.get(),
            "image_size": self.image_size.get(),
            "last_dir": self.last_dir
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except:
            pass
    
    def create_widgets(self):
        """Create the GUI widgets."""
        # Main frame with scrollbar
        main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas, padding="10")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = scrollable_frame
        
        # Title
        title = ttk.Label(main_frame, text="PvZmoD Spawn System Map Generator", 
                         font=("Arial", 16, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        row = 1
        
        # Input Files Section
        ttk.Label(main_frame, text="Input Files", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # Dynamic Zones
        self.create_file_row(main_frame, row, "DynamicSpawnZones.c:", 
                           self.dynamic_file, self.browse_dynamic)
        row += 1
        
        # Static Zones
        self.create_file_row(main_frame, row, "StaticSpawnDatas.c:", 
                           self.static_file, self.browse_static)
        row += 1
        
        # Categories
        self.create_file_row(main_frame, row, "ZombiesChooseCategories.c:", 
                           self.categories_file, self.browse_categories)
        row += 1
        
        # Classnames
        self.create_file_row(main_frame, row, "ZombiesCategories.c:", 
                           self.classnames_file, self.browse_classnames)
        row += 1
        
        # Background Image
        self.create_file_row(main_frame, row, "Background Image:", 
                           self.background_file, self.browse_background)
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)
        row += 1
        
        # Optional Heat Mapping Section
        ttk.Label(main_frame, text="Danger Level Heat Mapping (Optional)", 
                 font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # Characteristics file
        self.create_file_row(main_frame, row, "Zombie Characteristics XML:", 
                           self.characteristics_file, self.browse_characteristics)
        row += 1
        
        # Info label
        info_label = ttk.Label(main_frame, 
            text="Leave blank for default yellow zones.\nProvide XML for color-coded danger levels.",
            font=("Arial", 9), foreground="gray")
        info_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)
        row += 1
        
        # Output Section
        ttk.Label(main_frame, text="Output Settings", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # Output Directory
        self.create_file_row(main_frame, row, "Output Directory:", 
                           self.output_dir, self.browse_output_dir, is_dir=True)
        row += 1
        
        # Output Filename
        ttk.Label(main_frame, text="Output Filename:").grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_filename, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)
        row += 1
        
        # Map Configuration
        ttk.Label(main_frame, text="Map Configuration", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # World Size
        ttk.Label(main_frame, text="World Size (game coords):").grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.world_size, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Image Size
        ttk.Label(main_frame, text="Image Size (pixels):").grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.image_size, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Generate Button
        self.generate_btn = ttk.Button(main_frame, text="Generate Map", 
                                      command=self.generate_map)
        self.generate_btn.grid(row=row, column=0, columnspan=3, pady=20)
        
    def create_file_row(self, parent, row, label, var, browse_cmd, is_dir=False):
        """Create a file selection row."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
        entry = ttk.Entry(parent, textvariable=var, width=40)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(0, 5))
        ttk.Button(parent, text="Browse...", command=browse_cmd).grid(
            row=row, column=2, pady=5)
    
    def browse_dynamic(self):
        self.browse_file(self.dynamic_file, "Select DynamicSpawnZones.c", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_static(self):
        self.browse_file(self.static_file, "Select StaticSpawnDatas.c", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_categories(self):
        self.browse_file(self.categories_file, "Select ZombiesChooseCategories.c", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_classnames(self):
        self.browse_file(self.classnames_file, "Select ZombiesCategories.c", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_background(self):
        self.browse_file(self.background_file, "Select Background Image", 
                        [("Image Files", "*.png *.jpg *.jpeg"), ("All Files", "*.*")])
    
    def browse_characteristics(self):
        self.browse_file(self.characteristics_file, "Select Zombie Characteristics XML (Optional)", 
                        [("XML Files", "*.xml"), ("All Files", "*.*")])
    
    def browse_output_dir(self):
        filename = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.last_dir
        )
        if filename:
            self.output_dir.set(filename)
            self.last_dir = str(Path(filename).parent)
    
    def browse_file(self, var, title, filetypes):
        """Browse for a file."""
        filename = filedialog.askopenfilename(
            title=title,
            initialdir=self.last_dir,
            filetypes=filetypes
        )
        if filename:
            var.set(filename)
            self.last_dir = str(Path(filename).parent)
    
    def validate_inputs(self):
        """Validate all inputs before processing."""
        errors = []
        
        if not self.dynamic_file.get():
            errors.append("DynamicSpawnZones.c file is required")
        elif not Path(self.dynamic_file.get()).exists():
            errors.append("DynamicSpawnZones.c file does not exist")
            
        if not self.static_file.get():
            errors.append("StaticSpawnDatas.c file is required")
        elif not Path(self.static_file.get()).exists():
            errors.append("StaticSpawnDatas.c file does not exist")
            
        if not self.categories_file.get():
            errors.append("ZombiesChooseCategories.c file is required")
        elif not Path(self.categories_file.get()).exists():
            errors.append("ZombiesChooseCategories.c file does not exist")
            
        if not self.classnames_file.get():
            errors.append("ZombiesCategories.c file is required")
        elif not Path(self.classnames_file.get()).exists():
            errors.append("ZombiesCategories.c file does not exist")
            
        if not self.background_file.get():
            errors.append("Background Image file is required")
        elif not Path(self.background_file.get()).exists():
            errors.append("Background Image file does not exist")
        
        # Characteristics file is optional
        if self.characteristics_file.get() and not Path(self.characteristics_file.get()).exists():
            errors.append("Zombie Characteristics XML file does not exist")
            
        if not self.output_dir.get():
            errors.append("Output Directory is required")
            
        if not self.output_filename.get():
            errors.append("Output Filename is required")
            
        try:
            world_size = int(self.world_size.get())
            if world_size <= 0:
                errors.append("World Size must be positive")
        except ValueError:
            errors.append("World Size must be a valid number")
            
        try:
            image_size = int(self.image_size.get())
            if image_size <= 0:
                errors.append("Image Size must be positive")
        except ValueError:
            errors.append("Image Size must be a valid number")
        
        return errors
    
    def generate_map(self):
        """Generate the zone map."""
        # Validate inputs
        errors = self.validate_inputs()
        if errors:
            messagebox.showerror("Validation Error", 
                               "Please fix the following errors:\n\n" + "\n".join(errors))
            return
        
        # Save settings
        self.save_settings()
        
        # Disable button
        self.generate_btn.config(state='disabled')
        
        # Show progress window
        progress_window = ProgressWindow(self.root)
        
        # Run processing in thread
        def process():
            characteristics_file = self.characteristics_file.get() if self.characteristics_file.get() else None
            
            success, result, dyn_count, stat_count, total_count = process_zones(
                self.dynamic_file.get(),
                self.static_file.get(),
                self.categories_file.get(),
                self.classnames_file.get(),
                self.background_file.get(),
                self.output_dir.get(),
                self.output_filename.get(),
                int(self.world_size.get()),
                int(self.image_size.get()),
                characteristics_file,
                progress_window.update_status
            )
            
            # Close progress window
            progress_window.close()
            
            # Re-enable button
            self.generate_btn.config(state='normal')
            
            if success:
                # Show success dialog with options
                has_danger = characteristics_file is not None
                self.show_success_dialog(result, dyn_count, stat_count, total_count, has_danger)
            else:
                messagebox.showerror("Error", f"Failed to generate map:\n\n{result}")
        
        thread = Thread(target=process)
        thread.daemon = True
        thread.start()
    
    def show_success_dialog(self, html_path, dyn_count, stat_count, total_count, has_danger):
        """Show success dialog with options."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Success!")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Success message
        ttk.Label(frame, text="✓ Map Generated Successfully!", 
                 font=("Arial", 14, "bold"), foreground="green").pack(pady=(0, 10))
        
        # Stats
        stats_text = f"Processed:\n"
        stats_text += f"  • {dyn_count} dynamic zones\n"
        stats_text += f"  • {stat_count} static zones\n"
        stats_text += f"  • {total_count} total zones"
        
        if has_danger:
            stats_text += "\n  • Danger level coloring enabled"
        
        ttk.Label(frame, text=stats_text, justify=tk.LEFT).pack(pady=10)
        
        # File location
        location_frame = ttk.Frame(frame)
        location_frame.pack(pady=10, fill=tk.X)
        
        ttk.Label(location_frame, text="Output file:").pack(anchor=tk.W)
        file_label = ttk.Label(location_frame, text=str(html_path), 
                              foreground="blue", cursor="hand2")
        file_label.pack(anchor=tk.W, padx=(10, 0))
        file_label.bind("<Button-1>", lambda e: self.open_file_location(html_path))
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Open in Browser", 
                  command=lambda: self.open_in_browser(html_path, dialog)).pack(
                      side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show in Folder", 
                  command=lambda: self.open_file_location(html_path)).pack(
                      side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", 
                  command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def open_in_browser(self, html_path, dialog=None):
        """Open the HTML file in the default browser."""
        try:
            webbrowser.open(f"file://{html_path}")
            if dialog:
                dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open browser:\n{e}")
    
    def open_file_location(self, file_path):
        """Open the file location in the system file browser."""
        try:
            import platform
            import subprocess
            
            folder = Path(file_path).parent
            
            if platform.system() == "Windows":
                subprocess.run(["explorer", str(folder)])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(folder)])
            else:  # Linux
                subprocess.run(["xdg-open", str(folder)])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder:\n{e}")

class ProgressWindow:
    """Progress window for showing processing status."""
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Processing...")
        self.window.geometry("400x150")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        
        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(self.window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Generating Zone Map...", 
                 font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        self.status_label = ttk.Label(frame, text="Initializing...", 
                                     wraplength=350)
        self.status_label.pack(pady=10)
        
        self.progress = ttk.Progressbar(frame, mode='indeterminate', length=350)
        self.progress.pack(pady=10)
        self.progress.start(10)
        
    def update_status(self, message):
        """Update the status message."""
        self.status_label.config(text=message)
        self.window.update()
    
    def close(self):
        """Close the progress window."""
        self.progress.stop()
        self.window.destroy()

# ============================================================================
# MAIN
# ============================================================================

def main():
    # Setup error logging
    setup_error_logging()
    
    # Create and run GUI
    root = tk.Tk()
    app = ZoneMapGeneratorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
