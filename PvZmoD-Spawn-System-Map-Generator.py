#!/usr/bin/env python3
"""
DayZ Zone Map Generator - GUI Version with Error Logging
Interactive interface for generating zone maps with automatic file handling.
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

# ============================================================================
# ERROR LOGGING
# ============================================================================

def setup_error_logging():
    """Setup error logging to file."""
    log_file = Path.home() / "dayz_zonemap_error.log"
    
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

def combine_zones_with_data(dynamic_zones, static_zones, categories, category_classnames, progress_callback=None):
    """Combine all zones with their category data and expand to classnames."""
    if progress_callback:
        progress_callback("Combining zones with categories...")
    
    all_zones = {}
    
    for zone_id, zone_data in {**dynamic_zones, **static_zones}.items():
        num_config = zone_data.get('num_config')
        
        if num_config is not None and num_config in categories:
            cat_data = categories[num_config]
            
            for cat_key in ['category1', 'category2', 'category3']:
                cat_name = cat_data.get(cat_key)
                
                if cat_name and cat_name != "Empty":
                    if cat_name in category_classnames:
                        zone_data[cat_name] = category_classnames[cat_name]
                    else:
                        zone_data[cat_name] = []
        
        all_zones[zone_id] = zone_data
    
    return all_zones

def generate_html_map(zones_data, output_path, world_size, image_size, background_image, progress_callback=None):
    """Generate the interactive HTML zone map."""
    if progress_callback:
        progress_callback("Generating HTML map...")
    
    zones_js = json.dumps(zones_data, indent=2)
    
    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DayZ Zone Map - Interactive</title>
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
        
        #map-wrapper {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
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
            stroke: yellow;
            stroke-width: 2;
            pointer-events: all;
            cursor: pointer;
        }}
        
        .zone-rect.hovered {{
            fill: rgba(255, 255, 0, 0.3);
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
        }}
        
        .static-dot {{
            fill: white;
            stroke: black;
            stroke-width: 1;
            cursor: pointer;
        }}
        
        .static-dot.hovered {{
            fill: yellow;
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
    </style>
</head>
<body>
    <div id="map-wrapper">
        <div id="map-container">
            <img id="map-image" src="{background_image}" alt="DayZ Map">
            <svg id="map-svg"></svg>
        </div>
    </div>
    
    <div id="tooltip"></div>
    <div id="popup"></div>
    
    <script>
        const zonesData = {zones_js};
        initializeMap();
        
        function initializeMap() {{
            const svg = document.getElementById('map-svg');
            const tooltip = document.getElementById('tooltip');
            const popup = document.getElementById('popup');
            
            const WORLD_SIZE = {world_size};
            const IMAGE_SIZE = {image_size};
            const SCALE = IMAGE_SIZE / WORLD_SIZE;
            
            function worldToPixel(x, z) {{
                const pixelX = x * SCALE;
                const pixelY = IMAGE_SIZE - (z * SCALE);
                return {{ x: pixelX, y: pixelY }};
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
                    }} else {{
                        console.warn(`Skipping invalid dynamic zone: ${{key}}`);
                    }}
                }} else if (key.startsWith('HordeStatic')) {{
                    if (value && value.coordx !== undefined && value.coordz !== undefined &&
                        !isNaN(value.coordx) && !isNaN(value.coordz)) {{
                        const zoneNum = parseInt(key.replace('HordeStatic', ''));
                        staticZones.push({{ id: key, num: zoneNum, data: value }});
                    }} else {{
                        console.warn(`Skipping invalid static zone: ${{key}}`);
                    }}
                }}
            }}
            
            dynamicZones.sort((a, b) => a.num - b.num);
            staticZones.sort((a, b) => a.num - b.num);
            
            console.log(`Loaded ${{dynamicZones.length}} dynamic zones and ${{staticZones.length}} static zones`);
            
            dynamicZones.forEach(zone => {{
                const topLeft = worldToPixel(zone.data.coordx_upleft, zone.data.coordz_upleft);
                const bottomRight = worldToPixel(zone.data.coordx_lowerright, zone.data.coordz_lowerright);
                
                const x = topLeft.x;
                const y = topLeft.y;
                const width = bottomRight.x - topLeft.x;
                const height = bottomRight.y - topLeft.y;
                
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y);
                rect.setAttribute('width', width);
                rect.setAttribute('height', height);
                rect.classList.add('zone-rect');
                rect.dataset.zoneId = zone.id;
                
                rect.addEventListener('mouseenter', (e) => {{
                    rect.classList.add('hovered');
                    const skipFields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 'coordz_lowerright', 'comment'];
                    const categories = Object.keys(zone.data).filter(k => !skipFields.includes(k)).join(', ');
                    tooltip.innerHTML = `<strong>${{zone.id}}</strong><br>${{zone.data.comment}}<br>num_config: ${{zone.data.num_config}}<br>Categories: ${{categories}}`;
                    tooltip.style.display = 'block';
                }});
                
                rect.addEventListener('mousemove', (e) => {{
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                }});
                
                rect.addEventListener('mouseleave', () => {{
                    rect.classList.remove('hovered');
                    tooltip.style.display = 'none';
                }});
                
                rect.addEventListener('click', (e) => {{
                    e.stopPropagation();
                    showPopup(zone.id, zone.data, e.clientX, e.clientY);
                }});
                
                svg.appendChild(rect);
                
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', x + width / 2);
                text.setAttribute('y', y + height / 2);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('dominant-baseline', 'middle');
                text.classList.add('zone-label');
                text.textContent = zone.id;
                svg.appendChild(text);
            }});
            
            staticZones.forEach(zone => {{
                const pos = worldToPixel(zone.data.coordx, zone.data.coordz);
                
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', pos.x);
                circle.setAttribute('cy', pos.y);
                circle.setAttribute('r', 8);
                circle.classList.add('static-dot');
                circle.dataset.zoneId = zone.id;
                
                circle.addEventListener('mouseenter', (e) => {{
                    circle.classList.add('hovered');
                    const skipFields = ['num_config', 'coordx', 'coordy', 'coordz', 'comment'];
                    const categories = Object.keys(zone.data).filter(k => !skipFields.includes(k)).join(', ');
                    tooltip.innerHTML = `<strong>${{zone.id}}</strong><br>${{zone.data.comment}}<br>Coordinates: ${{zone.data.coordx}}, ${{zone.data.coordy}}, ${{zone.data.coordz}}<br>num_config: ${{zone.data.num_config}}<br>Categories: ${{categories}}`;
                    tooltip.style.display = 'block';
                }});
                
                circle.addEventListener('mousemove', (e) => {{
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                }});
                
                circle.addEventListener('mouseleave', () => {{
                    circle.classList.remove('hovered');
                    tooltip.style.display = 'none';
                }});
                
                circle.addEventListener('click', (e) => {{
                    e.stopPropagation();
                    showPopup(zone.id, zone.data, e.clientX, e.clientY);
                }});
                
                svg.appendChild(circle);
            }});
            
            function showPopup(zoneId, data, mouseX, mouseY) {{
                let html = `<h3>${{zoneId}}</h3>`;
                
                if (data.comment) {{
                    html += `<p style="margin-bottom: 15px; color: #aaa;">${{data.comment}}</p>`;
                }}
                
                const skipFields = ['num_config', 'coordx_upleft', 'coordz_upleft', 'coordx_lowerright', 'coordz_lowerright', 'coordx', 'coordy', 'coordz', 'comment'];
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
                 progress_callback=None):
    """Main processing function."""
    try:
        # Parse all data
        dynamic_zones = parse_dynamic_zones(dynamic_file, progress_callback)
        static_zones = parse_static_zones(static_file, progress_callback)
        categories = parse_zombie_categories(categories_file, progress_callback)
        category_classnames = parse_zombie_classnames(classnames_file, progress_callback)
        
        # Combine data
        all_zones = combine_zones_with_data(dynamic_zones, static_zones, categories, 
                                           category_classnames, progress_callback)
        
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
                         bg_filename, progress_callback)
        
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
        self.root.geometry("700x650")
        self.root.resizable(False, False)
        
        # Load saved settings
        self.config_file = Path.home() / ".dayz_zonemap_config.json"
        self.settings = self.load_settings()
        
        # Variables
        self.dynamic_file = tk.StringVar(value=self.settings.get("dynamic_file", ""))
        self.static_file = tk.StringVar(value=self.settings.get("static_file", ""))
        self.categories_file = tk.StringVar(value=self.settings.get("categories_file", ""))
        self.classnames_file = tk.StringVar(value=self.settings.get("classnames_file", ""))
        self.background_file = tk.StringVar(value=self.settings.get("background_file", ""))
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
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
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
        self.browse_file(self.dynamic_file, "Select Dynamic Zones File", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_static(self):
        self.browse_file(self.static_file, "Select Static Zones File", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_categories(self):
        self.browse_file(self.categories_file, "Select Categories File", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_classnames(self):
        self.browse_file(self.classnames_file, "Select Classnames File", 
                        [("C Files", "*.c"), ("All Files", "*.*")])
    
    def browse_background(self):
        self.browse_file(self.background_file, "Select Background Image", 
                        [("Image Files", "*.png *.jpg *.jpeg"), ("All Files", "*.*")])
    
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
            errors.append("Dynamic Zones file is required")
        elif not Path(self.dynamic_file.get()).exists():
            errors.append("Dynamic Zones file does not exist")
            
        if not self.static_file.get():
            errors.append("Static Zones file is required")
        elif not Path(self.static_file.get()).exists():
            errors.append("Static Zones file does not exist")
            
        if not self.categories_file.get():
            errors.append("Categories file is required")
        elif not Path(self.categories_file.get()).exists():
            errors.append("Categories file does not exist")
            
        if not self.classnames_file.get():
            errors.append("Classnames file is required")
        elif not Path(self.classnames_file.get()).exists():
            errors.append("Classnames file does not exist")
            
        if not self.background_file.get():
            errors.append("Background Image file is required")
        elif not Path(self.background_file.get()).exists():
            errors.append("Background Image file does not exist")
            
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
                progress_window.update_status
            )
            
            # Close progress window
            progress_window.close()
            
            # Re-enable button
            self.generate_btn.config(state='normal')
            
            if success:
                # Show success dialog with options
                self.show_success_dialog(result, dyn_count, stat_count, total_count)
            else:
                messagebox.showerror("Error", f"Failed to generate map:\n\n{result}")
        
        thread = Thread(target=process)
        thread.daemon = True
        thread.start()
    
    def show_success_dialog(self, html_path, dyn_count, stat_count, total_count):
        """Show success dialog with options."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Success!")
        dialog.geometry("500x250")
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