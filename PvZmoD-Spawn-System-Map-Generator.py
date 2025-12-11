#!/usr/bin/env python3
"""
PvZmoD Zone Editor - Standalone Desktop Application
For editing DayZ PvZmoD zombie spawn zones

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
"""

import sys
import os
import re
import json
import shutil
import traceback
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Get user data directory (writable location)
def get_user_data_dir():
    """Get user-writable directory for logs and settings"""
    if sys.platform == 'win32':
        # Windows: Use AppData/Local
        appdata = os.getenv('LOCALAPPDATA')
        if appdata:
            user_dir = os.path.join(appdata, 'PvZmoD_Zone_Editor')
        else:
            # Fallback to user home
            user_dir = os.path.join(os.path.expanduser('~'), '.pvzmod_zone_editor')
    else:
        # Linux/Mac: Use home directory
        user_dir = os.path.join(os.path.expanduser('~'), '.pvzmod_zone_editor')
    
    # Create directory if it doesn't exist
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

USER_DATA_DIR = get_user_data_dir()
LOG_FILE = os.path.join(USER_DATA_DIR, 'pvzmod_editor_debug.log')
SETTINGS_FILE = os.path.join(USER_DATA_DIR, 'pvzmod_editor_settings.json')

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QToolBar,
    QAction, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsTextItem, QDockWidget,
    QFormLayout, QSpinBox, QTextEdit, QTextBrowser, QGroupBox, QCheckBox,
    QDialog, QDialogButtonBox, QMenu
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, pyqtSignal, QTimer
)
from PyQt5.QtGui import (
    QPen, QBrush, QColor, QPixmap, QPainter, QTransform,
    QKeySequence, QFont, QCursor
)

from lxml import etree
from PIL import Image

# Constants
DEFAULT_WORLD_SIZE = 16384
DEFAULT_IMAGE_SIZE = 4096
MIN_ZONE_SIZE = 10  # Minimum zone size in world units
MAX_DYNAMIC_ZONES = 150

# Map presets
MAP_PRESETS = {
    "Deer Isle": 16384,
    "Chernarus/Chernarus+": 15360,
    "Livonia": 12800,
    "Custom": None
}

# Colors for zones
COLOR_DEFAULT = QColor(255, 255, 0, 100)  # Yellow
COLOR_SELECTED = QColor(0, 120, 255, 150)  # Blue
COLOR_HOVER = QColor(255, 165, 0, 120)  # Orange


class ZoneData:
    """Data class for zone information"""
    def __init__(self, zone_type='dynamic'):
        self.zone_id = ''
        self.zone_type = zone_type  # 'dynamic' or 'static'
        self.num_config = 0
        self.comment = ''
        self.categories = {}
        self.danger_level = 0.0
        
        # Dynamic zone specific
        self.coordx_upleft = 0
        self.coordz_upleft = 0
        self.coordx_lowerright = 0
        self.coordz_lowerright = 0
        
        # Static zone specific
        self.coordx = 0
        self.coordz = 0
        self.coordy = 0
        
    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get zone bounds as (x1, z1, x2, z2)"""
        if self.zone_type == 'dynamic':
            return (
                min(self.coordx_upleft, self.coordx_lowerright),
                min(self.coordz_upleft, self.coordz_lowerright),
                max(self.coordx_upleft, self.coordx_lowerright),
                max(self.coordz_upleft, self.coordz_lowerright)
            )
        else:
            # Static zones are points, return small box
            return (self.coordx - 5, self.coordz - 5, self.coordx + 5, self.coordz + 5)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        d = {
            'zone_id': self.zone_id,
            'zone_type': self.zone_type,
            'num_config': self.num_config,
            'comment': self.comment,
            'categories': self.categories,
            'danger_level': self.danger_level
        }
        if self.zone_type == 'dynamic':
            d.update({
                'coordx_upleft': self.coordx_upleft,
                'coordz_upleft': self.coordz_upleft,
                'coordx_lowerright': self.coordx_lowerright,
                'coordz_lowerright': self.coordz_lowerright
            })
        else:
            d.update({
                'coordx': self.coordx,
                'coordz': self.coordz,
                'coordy': self.coordy
            })
        return d
    
    @staticmethod
    def from_dict(d: dict) -> 'ZoneData':
        """Create from dictionary"""
        zone = ZoneData(d.get('zone_type', 'dynamic'))
        zone.zone_id = d.get('zone_id', '')
        zone.num_config = d.get('num_config', 0)
        zone.comment = d.get('comment', '')
        zone.categories = d.get('categories', {})
        zone.danger_level = d.get('danger_level', 0.0)
        
        if zone.zone_type == 'dynamic':
            zone.coordx_upleft = d.get('coordx_upleft', 0)
            zone.coordz_upleft = d.get('coordz_upleft', 0)
            zone.coordx_lowerright = d.get('coordx_lowerright', 0)
            zone.coordz_lowerright = d.get('coordz_lowerright', 0)
        else:
            zone.coordx = d.get('coordx', 0)
            zone.coordz = d.get('coordz', 0)
            zone.coordy = d.get('coordy', 0)
        
        return zone


class FileParser:
    """Parse PvZmoD configuration files"""
    
    @staticmethod
    def parse_dynamic_zones(filepath: str) -> List[ZoneData]:
        """Parse DynamicSpawnZones.c"""
        zones = []
        pattern = r'ref\s+autoptr\s+TIntArray\s+data_(Zone\d+)\s*=\s*\{(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*\d+,\s*\d+\};\s*//\s*(.*)$'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip commented lines
                if line.strip().startswith('///') or line.strip().startswith('//'):
                    continue
                    
                match = re.search(pattern, line)
                if match:
                    zone = ZoneData('dynamic')
                    zone.zone_id = match.group(1)
                    zone.num_config = int(match.group(2))
                    zone.coordx_upleft = int(match.group(3))
                    zone.coordz_upleft = int(match.group(4))
                    zone.coordx_lowerright = int(match.group(5))
                    zone.coordz_lowerright = int(match.group(6))
                    zone.comment = match.group(7).strip()
                    zones.append(zone)
        
        return zones
    
    @staticmethod
    def parse_static_zones(filepath: str) -> List[ZoneData]:
        """Parse StaticSpawnDatas.c"""
        zones = []
        pattern = r'ref\s+autoptr\s+TFloatArray\s+data_(HordeStatic\d+)\s*=\s*\{[^}]+\};\s*//\s*(.*)$'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip commented lines
                if line.strip().startswith('///') or line.strip().startswith('//'):
                    continue
                    
                match = re.search(pattern, line)
                if match:
                    zone_id = match.group(1)
                    comment = match.group(2).strip()
                    
                    # Extract parameters
                    params_match = re.search(r'\{([^}]+)\}', line)
                    if params_match:
                        params = [p.strip() for p in params_match.group(1).split(',')]
                        if len(params) >= 12:
                            zone = ZoneData('static')
                            zone.zone_id = zone_id
                            zone.coordx = int(float(params[4]))
                            zone.coordy = int(float(params[5]))
                            zone.coordz = int(float(params[6]))
                            zone.num_config = int(float(params[11]))
                            zone.comment = comment
                            zones.append(zone)
        
        return zones
    
    @staticmethod
    def parse_categories_mapping(filepath: str) -> Dict[int, Dict[str, List[str]]]:
        """Parse ZombiesChooseCategories.c"""
        config_mapping = {}
        pattern = r'data_Horde_(\d+)_\w+Categories\s*=\s*new\s+Param5[^(]+\([^,]+,[^,]+,\s*(\w+),\s*(\w+),\s*(\w+)\)'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for match in re.finditer(pattern, content):
            config_num = int(match.group(1))
            cat1 = match.group(2).strip()
            cat2 = match.group(3).strip()
            cat3 = match.group(4).strip()
            
            config_mapping[config_num] = {
                'category1': cat1 if cat1 != 'Empty' else None,
                'category2': cat2 if cat2 != 'Empty' else None,
                'category3': cat3 if cat3 != 'Empty' else None
            }
        
        return config_mapping
    
    @staticmethod
    def parse_categories_definitions(filepath: str) -> Dict[str, List[str]]:
        """Parse ZombiesCategories.c"""
        categories = {}
        pattern = r'ref\s+autoptr\s+TStringArray\s+(\w+)\s*=\s*\{([^}]*)\};'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
            category_name = match.group(1)
            classnames_block = match.group(2)
            
            # Extract quoted strings
            classnames = re.findall(r'"([^"]+)"', classnames_block)
            categories[category_name] = classnames
        
        return categories
    
    @staticmethod
    def parse_zombie_health(filepath: str) -> Dict[str, float]:
        """Parse PvZmoD_CustomisableZombies_Characteristics.xml"""
        health_map = {}
        
        try:
            tree = etree.parse(filepath)
            root = tree.getroot()
            
            for zombie_type in root.findall('.//type'):
                name = zombie_type.get('name')
                health_elem = zombie_type.find('Health_Points')
                if name and health_elem is not None:
                    day_health = float(health_elem.get('Day', 100))
                    health_map[name] = day_health
        except Exception as e:
            print(f"Warning: Could not parse zombie health: {e}")
        
        return health_map
    
    @staticmethod
    def save_dynamic_zones(zones: List[ZoneData], filepath: str):
        """Save dynamic zones back to DynamicSpawnZones.c"""
        # Create backup
        backup_path = filepath + '.backup'
        shutil.copy2(filepath, backup_path)
        
        lines = []
        lines.append('/// !!! Remember that the first zone found has priority on the others (if you have overlapping zones)\n')
        lines.append('\n')
        lines.append('/// LOOK AT THE END OF THE FILE FOR MORE HELP !\n')
        lines.append('/// CHERNARUS\n')
        lines.append('/// DYNAMIC SPAWN 		 : 			NUM CONFIG / COORDX-upleft / COORDZ-upleft / COORDX-lowerright / COORDZ-lowerright / QUANTITY RATIO / TOTAL MAX ZEDS NUMBER\n')
        
        for zone in sorted(zones, key=lambda z: z.zone_id):
            if zone.zone_type == 'dynamic':
                line = f"ref autoptr  TIntArray data_{zone.zone_id} = "
                line += f"{{{zone.num_config},\t\t\t{zone.coordx_upleft},\t\t\t{zone.coordz_upleft},\t\t\t"
                line += f"{zone.coordx_lowerright},\t\t\t\t{zone.coordz_lowerright},\t\t\t\t100,\t\t\t25}}; \t\t// {zone.comment}\n"
                lines.append(line)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    
    @staticmethod
    def save_static_zones(zones: List[ZoneData], filepath: str):
        """Save static zones back to StaticSpawnDatas.c (only config and comment can be edited)"""
        # Create backup
        backup_path = filepath + '.backup'
        shutil.copy2(filepath, backup_path)
        
        # Read original file to preserve all parameters
        with open(filepath, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()
        
        # Build map of zone_id to zone data
        zone_map = {z.zone_id: z for z in zones if z.zone_type == 'static'}
        
        # Process lines
        new_lines = []
        pattern = r'(ref\s+autoptr\s+TFloatArray\s+data_(HordeStatic\d+)\s*=\s*\{)([^}]+)(\};\s*)//\s*(.*)$'
        
        for line in original_lines:
            match = re.search(pattern, line)
            if match and match.group(2) in zone_map:
                # Update this line
                zone = zone_map[match.group(2)]
                prefix = match.group(1)
                params_str = match.group(3)
                suffix = match.group(4)
                
                # Parse params and update config (index 11)
                params = [p.strip() for p in params_str.split(',')]
                if len(params) >= 12:
                    params[11] = str(zone.num_config)
                    new_params_str = ', '.join(params)
                    new_line = f"{prefix}{new_params_str}{suffix}// {zone.comment}\n"
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)  # Keep original if parsing fails
            else:
                new_lines.append(line)  # Keep original line
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)


class MapCanvas(QGraphicsView):
    """Interactive map canvas for displaying and editing zones"""
    
    zone_selected = pyqtSignal(str)  # zone_id
    zone_modified = pyqtSignal(str)  # zone_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.world_size = DEFAULT_WORLD_SIZE
        self.image_size = DEFAULT_IMAGE_SIZE
        
        self.zones = {}  # zone_id -> ZoneData
        self.zone_graphics = {}  # zone_id -> QGraphicsRectItem/EllipseItem
        self.zone_labels = {}  # zone_id -> QGraphicsTextItem
        
        self.selected_zone_id = None
        self.hovered_zone_id = None
        
        self.drawing_mode = False
        self.draw_start = None
        self.draw_rect = None
        self.temp_new_zone = None  # Temporary zone being drawn
        
        # Zone editing
        self.editing_mode = False
        self.resize_handles = []
        self.resize_handle_size = 8
        self.active_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None
        
        # Panning with middle mouse button
        self.panning = False
        self.pan_start_pos = None
        
        # Zoom limits
        self.min_zoom = 0.1  # Can't zoom out past this
        self.max_zoom = 10.0  # Can't zoom in past this
        self.current_zoom = 1.0
        
        # Setup view
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)  # We'll handle panning manually
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Use standard arrow cursor
        self.viewport().setCursor(Qt.ArrowCursor)
        
        # Danger color coding
        self.zombie_health = {}  # Will be set by main window
        self._reset_health_thresholds()  # Initialize default thresholds
        
        # Background
        self.background_pixmap = None
        self.background_item = None
        
    def load_map_image(self, filepath: str):
        """Load background map image"""
        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", f"Could not load image: {filepath}")
            return
        
        self.background_pixmap = pixmap
        self.background_item = self.scene.addPixmap(pixmap)
        self.background_item.setZValue(-1)  # Behind everything
        
        # Set scene rect to match image
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        
        # Update image size for coordinate conversion
        self.image_size = pixmap.width()
        logger.info(f"Map image loaded: {pixmap.width()}x{pixmap.height()}")
    
    def set_map_config(self, world_size: int, image_size: int = None):
        """Set map configuration for coordinate conversion"""
        self.world_size = world_size
        if image_size:
            self.image_size = image_size
        logger.info(f"Map config set: world_size={world_size}, image_size={self.image_size}")
    
    def set_zombie_health(self, zombie_health: dict):
        """Set zombie health data for danger color coding"""
        self.zombie_health = zombie_health
        
        # Calculate health range for relative danger levels
        if zombie_health:
            valid_healths = [h for h in zombie_health.values() if h > 0]  # Ignore zero/negative
            if valid_healths:
                self.min_health = min(valid_healths)
                self.max_health = max(valid_healths)
                
                # Calculate quintiles (5 levels)
                health_range = self.max_health - self.min_health
                if health_range > 0:
                    self.health_20th = self.min_health + (health_range * 0.2)
                    self.health_40th = self.min_health + (health_range * 0.4)
                    self.health_60th = self.min_health + (health_range * 0.6)
                    self.health_80th = self.min_health + (health_range * 0.8)
                else:
                    # All zombies same health
                    self.health_20th = self.min_health
                    self.health_40th = self.min_health
                    self.health_60th = self.min_health
                    self.health_80th = self.min_health
            else:
                # No valid health data
                self._reset_health_thresholds()
        else:
            self._reset_health_thresholds()
        
        # Update colors for existing zones
        for zone_id, zone in self.zones.items():
            self._update_zone_color(zone_id)
    
    def _reset_health_thresholds(self):
        """Reset to default health thresholds"""
        self.min_health = 0
        self.max_health = 200
        self.health_20th = 80
        self.health_40th = 100
        self.health_60th = 120
        self.health_80th = 150
    
    def _calculate_danger_level(self, zone: ZoneData) -> float:
        """Calculate average health of zombies in zone (danger level)"""
        if not self.zombie_health or not hasattr(zone, 'categories') or not zone.categories:
            return 0.0
        
        total_health = 0.0
        zombie_count = 0
        
        for cat_name, zombie_list in zone.categories.items():
            for zombie_name in zombie_list:
                if zombie_name in self.zombie_health:
                    total_health += self.zombie_health[zombie_name]
                    zombie_count += 1
        
        if zombie_count == 0:
            return 0.0
        
        return total_health / zombie_count
    
    def _get_danger_color(self, avg_health: float) -> QColor:
        """Get color based on average zombie health (relative to loaded zombie set)
        
        Uses quintiles (20th, 40th, 60th, 80th percentiles) calculated from actual data:
        - Bottom 20%: Very Low (green)
        - 20-40%: Low (yellow-green)
        - 40-60%: Medium (yellow)
        - 60-80%: High (orange)
        - Top 20%: Very High (red)
        """
        if avg_health <= 0 or not hasattr(self, 'health_20th'):
            # No health data - use default yellow
            return QColor(255, 255, 0, 30)
        elif avg_health <= self.health_20th:
            # Very Low - Green (bottom 20%)
            return QColor(0, 255, 0, 30)
        elif avg_health <= self.health_40th:
            # Low - Yellow-Green (20-40%)
            return QColor(128, 255, 0, 30)
        elif avg_health <= self.health_60th:
            # Medium - Yellow (40-60%)
            return QColor(255, 255, 0, 30)
        elif avg_health <= self.health_80th:
            # High - Orange (60-80%)
            return QColor(255, 165, 0, 30)
        else:
            # Very High - Red (top 20%)
            return QColor(255, 0, 0, 30)
    
    def _update_zone_color(self, zone_id: str):
        """Update zone color based on danger level"""
        if zone_id not in self.zones or zone_id not in self.zone_graphics:
            return
        
        zone = self.zones[zone_id]
        graphic = self.zone_graphics[zone_id]
        
        danger_level = self._calculate_danger_level(zone)
        color = self._get_danger_color(danger_level)
        
        if zone.zone_type == 'dynamic':
            # Dynamic zones: semi-transparent fill
            graphic.setBrush(QBrush(color))
        else:
            # Static zones: more opaque for visibility
            if color.alpha() == 30:
                color.setAlpha(150)
            graphic.setBrush(QBrush(color))
    
    def set_zones(self, zones: List[ZoneData]):
        """Set all zones"""
        self.clear_zones()
        for zone in zones:
            self.add_zone(zone)
    
    def add_zone(self, zone: ZoneData):
        """Add a zone to the canvas"""
        self.zones[zone.zone_id] = zone
        
        if zone.zone_type == 'dynamic':
            self._add_dynamic_zone(zone)
        else:
            self._add_static_zone(zone)
    
    def _add_dynamic_zone(self, zone: ZoneData):
        """Add dynamic zone rectangle"""
        x1, z1 = self.world_to_pixel(zone.coordx_upleft, zone.coordz_upleft)
        x2, z2 = self.world_to_pixel(zone.coordx_lowerright, zone.coordz_lowerright)
        
        rect = QRectF(
            min(x1, x2), min(z1, z2),
            abs(x2 - x1), abs(z2 - z1)
        )
        
        rect_item = self.scene.addRect(rect)
        rect_item.setPen(QPen(COLOR_DEFAULT, 2))
        
        # Calculate danger color based on zombie health
        danger_level = self._calculate_danger_level(zone)
        color = self._get_danger_color(danger_level)
        rect_item.setBrush(QBrush(color))
        
        rect_item.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
        rect_item.setData(0, zone.zone_id)  # Store zone_id
        rect_item.setAcceptHoverEvents(True)
        
        # Set z-value based on area - smaller zones on top
        area = rect.width() * rect.height()
        # Invert so smaller = higher z value
        z_value = 1000000 / (area + 1)  # +1 to avoid division by zero
        rect_item.setZValue(z_value)
        
        self.zone_graphics[zone.zone_id] = rect_item
        
        # Add label
        label = self.scene.addText(f"{zone.zone_id}\nC:{zone.num_config}")
        label.setDefaultTextColor(Qt.yellow)
        label.setPos(rect.x() + 5, rect.y() + 5)
        label.setZValue(z_value + 1)  # Label on top of its zone
        self.zone_labels[zone.zone_id] = label
    
    def _add_static_zone(self, zone: ZoneData):
        """Add static zone point"""
        x, z = self.world_to_pixel(zone.coordx, zone.coordz)
        
        # Calculate danger color based on zombie health
        danger_level = self._calculate_danger_level(zone)
        color = self._get_danger_color(danger_level)
        
        # Make color more opaque for static zones (they're small circles)
        if color.alpha() == 30:
            color.setAlpha(150)  # More visible
        
        radius = 6  # Slightly larger for better visibility
        ellipse_item = self.scene.addEllipse(
            x - radius, z - radius, radius * 2, radius * 2
        )
        
        # White border for visibility over dynamic zones
        ellipse_item.setPen(QPen(QColor(255, 255, 255), 2))
        ellipse_item.setBrush(QBrush(color))
        ellipse_item.setFlag(QGraphicsEllipseItem.ItemIsSelectable, False)
        ellipse_item.setData(0, zone.zone_id)
        ellipse_item.setAcceptHoverEvents(True)
        
        # High z-value so static zones always visible above dynamic zones
        ellipse_item.setZValue(2000000)  # Higher than any dynamic zone
        
        self.zone_graphics[zone.zone_id] = ellipse_item
        
        # Add label with white text and shadow for visibility
        label = self.scene.addText(f"{zone.zone_id}\nC:{zone.num_config}")
        label.setDefaultTextColor(Qt.white)
        label.setPos(x + 8, z + 8)
        label.setZValue(2000001)  # Label on top of its zone
        self.zone_labels[zone.zone_id] = label
    
    def update_zone(self, zone: ZoneData):
        """Update an existing zone"""
        if zone.zone_id in self.zone_graphics:
            # Remove old graphics
            self.scene.removeItem(self.zone_graphics[zone.zone_id])
            self.scene.removeItem(self.zone_labels[zone.zone_id])
            del self.zone_graphics[zone.zone_id]
            del self.zone_labels[zone.zone_id]
        
        # Add new graphics
        self.zones[zone.zone_id] = zone
        if zone.zone_type == 'dynamic':
            self._add_dynamic_zone(zone)
        else:
            self._add_static_zone(zone)
    
    def remove_zone(self, zone_id: str):
        """Remove a zone"""
        if zone_id in self.zone_graphics:
            self.scene.removeItem(self.zone_graphics[zone_id])
            self.scene.removeItem(self.zone_labels[zone_id])
            del self.zone_graphics[zone_id]
            del self.zone_labels[zone_id]
            del self.zones[zone_id]
    
    def clear_zones(self):
        """Clear all zones"""
        for zone_id in list(self.zone_graphics.keys()):
            self.remove_zone(zone_id)
    
    def select_zone(self, zone_id: str):
        """Select a zone"""
        # Deselect previous
        if self.selected_zone_id and self.selected_zone_id in self.zone_graphics:
            item = self.zone_graphics[self.selected_zone_id]
            if isinstance(item, QGraphicsRectItem):
                # Dynamic zone - restore default yellow border
                item.setPen(QPen(COLOR_DEFAULT, 2))
            else:
                # Static zone - restore white border
                item.setPen(QPen(QColor(255, 255, 255), 2))
        
        # Remove old resize handles
        self._clear_resize_handles()
        
        # Select new
        self.selected_zone_id = zone_id
        if zone_id and zone_id in self.zone_graphics:
            item = self.zone_graphics[zone_id]
            item.setPen(QPen(COLOR_SELECTED, 3))
            
            # Only add resize handles if in edit mode
            zone = self.zones.get(zone_id)
            if zone and zone.zone_type == 'dynamic' and self.editing_mode:
                self._create_resize_handles(item)
            
            # Center on zone
            if isinstance(item, QGraphicsRectItem):
                self.centerOn(item.rect().center())
            else:
                self.centerOn(item.rect().center())
    
    def set_edit_mode(self, enabled: bool):
        """Enable or disable edit mode"""
        self.editing_mode = enabled
        
        if enabled:
            # Show resize handles for selected zone
            if self.selected_zone_id and self.selected_zone_id in self.zone_graphics:
                zone = self.zones.get(self.selected_zone_id)
                if zone and zone.zone_type == 'dynamic':
                    self._create_resize_handles(self.zone_graphics[self.selected_zone_id])
            self.viewport().setCursor(Qt.ArrowCursor)
        else:
            # Remove resize handles
            self._clear_resize_handles()
            self.viewport().setCursor(Qt.ArrowCursor)
    
    def _create_resize_handles(self, rect_item):
        """Create resize handles for a zone rectangle"""
        self._create_resize_handles_for_item(rect_item)
    
    def _create_resize_handles_for_item(self, rect_item):
        """Create resize handles for any rectangle item"""
        rect = rect_item.rect()
        handle_size = self.resize_handle_size
        
        # Create handles at corners
        positions = [
            ('nw', rect.topLeft()),
            ('ne', rect.topRight()),
            ('sw', rect.bottomLeft()),
            ('se', rect.bottomRight()),
        ]
        
        for handle_type, pos in positions:
            handle = self.scene.addRect(
                pos.x() - handle_size/2,
                pos.y() - handle_size/2,
                handle_size,
                handle_size
            )
            handle.setBrush(QBrush(QColor(0, 120, 255)))
            handle.setPen(QPen(QColor(255, 255, 255), 1))
            handle.setZValue(999999)  # Always on top
            handle.setData(0, f"handle_{handle_type}")
            handle.setData(1, 'temp' if rect_item == self.temp_new_zone else self.selected_zone_id)
            self.resize_handles.append(handle)
    
    def finish_drawing(self):
        """Clean up after finishing zone drawing"""
        if self.temp_new_zone:
            self.scene.removeItem(self.temp_new_zone)
            self.temp_new_zone = None
        self._clear_resize_handles()
        self.editing_mode = False
    
    def _clear_resize_handles(self):
        """Remove all resize handles"""
        for handle in self.resize_handles:
            self.scene.removeItem(handle)
        self.resize_handles.clear()
    
    def world_to_pixel(self, world_x: int, world_z: int) -> Tuple[float, float]:
        """Convert world coordinates to pixel coordinates"""
        pixel_x = world_x * (self.image_size / self.world_size)
        pixel_y = self.image_size - (world_z * (self.image_size / self.world_size))
        return pixel_x, pixel_y
    
    def pixel_to_world(self, pixel_x: float, pixel_y: float) -> Tuple[int, int]:
        """Convert pixel coordinates to world coordinates"""
        world_x = int(pixel_x * (self.world_size / self.image_size))
        world_z = int((self.image_size - pixel_y) * (self.world_size / self.image_size))
        return world_x, world_z
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        pos = self.mapToScene(event.pos())
        
        # Middle mouse button for panning
        if event.button() == Qt.MiddleButton:
            self.panning = True
            self.pan_start_pos = event.pos()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        
        if self.drawing_mode and event.button() == Qt.LeftButton and not self.temp_new_zone:
            self.draw_start = pos
            self.draw_rect = self.scene.addRect(
                QRectF(pos.x(), pos.y(), 0, 0),
                QPen(COLOR_SELECTED, 2, Qt.DashLine)
            )
            return
        
        # Check for resize handle (works for both temp and existing zones)
        items = self.scene.items(pos)
        for item in items:
            handle_type = item.data(0)
            if handle_type and isinstance(handle_type, str) and handle_type.startswith('handle_'):
                self.active_handle = handle_type.replace('handle_', '')
                self.drag_start_pos = pos
                zone_item = self.temp_new_zone if self.temp_new_zone else self.zone_graphics.get(self.selected_zone_id)
                if zone_item:
                    self.drag_start_rect = zone_item.rect()
                self.setDragMode(QGraphicsView.NoDrag)
                return
        
        # Check for zone body dragging (only in edit mode for existing zones)
        if self.editing_mode and not self.temp_new_zone:
            for item in items:
                zone_id = item.data(0)
                if zone_id and zone_id in self.zones:
                    zone = self.zones[zone_id]
                    if zone.zone_type == 'dynamic' and event.button() == Qt.LeftButton:
                        # Start drag mode
                        self.active_handle = 'move'
                        self.drag_start_pos = pos
                        self.drag_start_rect = self.zone_graphics[zone_id].rect()
                        self.setDragMode(QGraphicsView.NoDrag)
                        return
        
        # Check for zone selection (always allow selection, except when drawing temp zone)
        if not self.temp_new_zone:
            items = self.scene.items(pos)
            for item in items:
                zone_id = item.data(0)
                if zone_id and zone_id in self.zones:
                    self.zone_selected.emit(zone_id)
                    return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        pos = self.mapToScene(event.pos())
        
        # Handle panning with middle mouse button
        if self.panning:
            delta = event.pos() - self.pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.pan_start_pos = event.pos()
            return
        
        if self.drawing_mode and self.draw_rect:
            rect = QRectF(
                min(self.draw_start.x(), pos.x()),
                min(self.draw_start.y(), pos.y()),
                abs(pos.x() - self.draw_start.x()),
                abs(pos.y() - self.draw_start.y())
            )
            self.draw_rect.setRect(rect)
            return
        
        # Handle resizing (for both temp new zone and existing zones)
        if self.active_handle and self.drag_start_rect:
            zone_item = self.temp_new_zone if self.temp_new_zone else self.zone_graphics.get(self.selected_zone_id)
            if not zone_item:
                return
            
            delta_x = pos.x() - self.drag_start_pos.x()
            delta_y = pos.y() - self.drag_start_pos.y()
            
            old_rect = self.drag_start_rect
            new_rect = QRectF(old_rect)
            
            if self.active_handle == 'move':
                # Move entire zone
                new_rect.translate(delta_x, delta_y)
            elif self.active_handle == 'nw':
                # Top-left corner
                new_left = min(old_rect.left() + delta_x, old_rect.right() - MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_top = min(old_rect.top() + delta_y, old_rect.bottom() - MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_rect.setTopLeft(QPointF(new_left, new_top))
            elif self.active_handle == 'ne':
                # Top-right corner
                new_right = max(old_rect.right() + delta_x, old_rect.left() + MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_top = min(old_rect.top() + delta_y, old_rect.bottom() - MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_rect.setTopRight(QPointF(new_right, new_top))
            elif self.active_handle == 'sw':
                # Bottom-left corner
                new_left = min(old_rect.left() + delta_x, old_rect.right() - MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_bottom = max(old_rect.bottom() + delta_y, old_rect.top() + MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_rect.setBottomLeft(QPointF(new_left, new_bottom))
            elif self.active_handle == 'se':
                # Bottom-right corner
                new_right = max(old_rect.right() + delta_x, old_rect.left() + MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_bottom = max(old_rect.bottom() + delta_y, old_rect.top() + MIN_ZONE_SIZE * (self.image_size / self.world_size))
                new_rect.setBottomRight(QPointF(new_right, new_bottom))
            
            # Update zone rectangle
            zone_item.setRect(new_rect)
            
            # Update resize handles
            self._update_resize_handles(new_rect)
            
            # Update label position if exists
            if self.selected_zone_id and self.selected_zone_id in self.zone_labels:
                label = self.zone_labels[self.selected_zone_id]
                label.setPos(new_rect.x() + 5, new_rect.y() + 5)
            
            return
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        # Handle panning release
        if event.button() == Qt.MiddleButton and self.panning:
            self.panning = False
            self.viewport().setCursor(Qt.ArrowCursor)
            return
        
        if self.drawing_mode and self.draw_rect:
            rect = self.draw_rect.rect()
            
            # Check minimum size
            x1, z1 = self.pixel_to_world(rect.x(), rect.y())
            x2, z2 = self.pixel_to_world(rect.right(), rect.bottom())
            
            if abs(x2 - x1) >= MIN_ZONE_SIZE and abs(z2 - z1) >= MIN_ZONE_SIZE:
                # Convert temporary drawing to a zone with handles
                self.temp_new_zone = self.draw_rect
                self.temp_new_zone.setPen(QPen(COLOR_SELECTED, 2))
                self.temp_new_zone.setBrush(QBrush(QColor(0, 120, 255, 30)))
                
                # Create resize handles for the new zone
                self._create_resize_handles_for_item(self.temp_new_zone)
                
                # Enable resize mode for the temp zone
                self.editing_mode = True
                
                # Clear drawing state but keep the zone
                self.draw_rect = None
                self.draw_start = None
                
                # Update button text to "Done Adding"
                main_window = self.get_main_window()
                if main_window:
                    main_window.draw_mode_btn.setText("Done Adding")
            else:
                # Too small, just remove it
                self.scene.removeItem(self.draw_rect)
                self.draw_rect = None
                self.draw_start = None
            return
        
        # Handle resize/move completion for temp new zone
        if self.active_handle and self.temp_new_zone:
            # Just finish the drag, don't show dialog yet
            self.active_handle = None
            self.drag_start_pos = None
            self.drag_start_rect = None
            self.setDragMode(QGraphicsView.NoDrag)
            return
        
        # Handle resize/move completion for existing zones
        if self.active_handle and self.selected_zone_id:
            # Update zone data with new coordinates
            zone = self.zones.get(self.selected_zone_id)
            zone_item = self.zone_graphics.get(self.selected_zone_id)
            
            if zone and zone_item and zone.zone_type == 'dynamic':
                rect = zone_item.rect()
                
                # Convert back to world coordinates
                x1, z1 = self.pixel_to_world(rect.left(), rect.top())
                x2, z2 = self.pixel_to_world(rect.right(), rect.bottom())
                
                # Update zone coordinates (maintain upleft = NW, lowerright = SE)
                zone.coordx_upleft = min(x1, x2)
                zone.coordz_upleft = max(z1, z2)
                zone.coordx_lowerright = max(x1, x2)
                zone.coordz_lowerright = min(z1, z2)
                
                # Emit modification signal
                self.zone_modified.emit(zone.zone_id)
            
            self.active_handle = None
            self.drag_start_pos = None
            self.drag_start_rect = None
            self.setDragMode(QGraphicsView.NoDrag)
            return
        
        super().mouseReleaseEvent(event)
    
    def _update_resize_handles(self, rect):
        """Update positions of resize handles"""
        if len(self.resize_handles) != 4:
            return
        
        handle_size = self.resize_handle_size
        positions = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
        ]
        
        for i, pos in enumerate(positions):
            if i < len(self.resize_handles):
                handle = self.resize_handles[i]
                handle.setRect(
                    pos.x() - handle_size/2,
                    pos.y() - handle_size/2,
                    handle_size,
                    handle_size
                )
    
    def _create_resize_handles_for_item(self, rect_item):
        """Create resize handles for any rectangle item"""
        rect = rect_item.rect()
        handle_size = self.resize_handle_size
        
        positions = [
            ('nw', rect.topLeft()),
            ('ne', rect.topRight()),
            ('sw', rect.bottomLeft()),
            ('se', rect.bottomRight()),
        ]
        
        for handle_type, pos in positions:
            handle = self.scene.addRect(
                pos.x() - handle_size/2,
                pos.y() - handle_size/2,
                handle_size,
                handle_size
            )
            handle.setBrush(QBrush(QColor(0, 120, 255)))
            handle.setPen(QPen(QColor(255, 255, 255), 1))
            handle.setZValue(999999)
            handle.setData(0, f"handle_{handle_type}")
            handle.setData(1, "temp_new_zone")
            self.resize_handles.append(handle)
    
    def finalize_new_zone(self):
        """Finalize the new zone and show dialog"""
        if not self.temp_new_zone:
            logger.warning("No temp zone to finalize")
            return
        
        rect = self.temp_new_zone.rect()
        
        # Convert to world coordinates
        x1, z1 = self.pixel_to_world(rect.left(), rect.top())
        x2, z2 = self.pixel_to_world(rect.right(), rect.bottom())
        
        # Remove the temp zone and handles
        self.scene.removeItem(self.temp_new_zone)
        self._clear_resize_handles()
        self.temp_new_zone = None
        self.editing_mode = False
        
        # Show dialog
        self._show_new_zone_dialog(x1, z1, x2, z2)
    
    def _show_new_zone_dialog(self, x1: int, z1: int, x2: int, z2: int):
        """Show dialog for creating new zone"""
        dialog = NewZoneDialog(x1, z1, x2, z2, self)
        if dialog.exec_() == QDialog.Accepted:
            zone_data = dialog.get_zone_data()
            if zone_data:
                self.add_zone(zone_data)
                self.zone_modified.emit(zone_data.zone_id)
                # Switch back to select mode
                main_window = self.get_main_window()
                if main_window:
                    main_window._set_mode('select')
    
    def get_main_window(self):
        """Get the main window"""
        widget = self.parent()
        while widget:
            if isinstance(widget, QMainWindow):
                return widget
            widget = widget.parent()
        return None
    
    def zoom_in(self):
        """Zoom in with limit checking"""
        self._apply_zoom(1.15)
    
    def zoom_out(self):
        """Zoom out with limit checking"""
        self._apply_zoom(1 / 1.15)
    
    def _apply_zoom(self, factor):
        """Apply zoom with proper limit checking"""
        new_zoom = self.current_zoom * factor
        
        # Calculate minimum zoom to fit entire map in view
        if self.background_item:
            viewport_rect = self.viewport().rect()
            scene_rect = self.sceneRect()
            
            if scene_rect.width() > 0 and scene_rect.height() > 0:
                # Calculate scale needed to fit entire scene in viewport
                x_ratio = viewport_rect.width() / scene_rect.width()
                y_ratio = viewport_rect.height() / scene_rect.height()
                fit_zoom = min(x_ratio, y_ratio) * 0.95  # 95% to add some margin
                
                # Use the larger of fit_zoom or absolute minimum
                actual_min_zoom = max(fit_zoom, 0.05)
            else:
                actual_min_zoom = self.min_zoom
        else:
            actual_min_zoom = self.min_zoom
        
        # Constrain to limits
        if new_zoom < actual_min_zoom:
            new_zoom = actual_min_zoom
        elif new_zoom > self.max_zoom:
            new_zoom = self.max_zoom
        
        # Calculate actual scale factor to apply
        if new_zoom != self.current_zoom and abs(new_zoom - self.current_zoom) > 0.001:
            actual_factor = new_zoom / self.current_zoom
            self.scale(actual_factor, actual_factor)
            self.current_zoom = new_zoom
    
    def wheelEvent(self, event):
        """Handle zoom with mouse wheel"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._apply_zoom(factor)


class NewZoneDialog(QDialog):
    """Dialog for creating a new zone"""
    
    def __init__(self, x1, z1, x2, z2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Dynamic Zone")
        
        # Remove the help button that causes freezing
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.x1 = x1
        self.z1 = z1
        self.x2 = x2
        self.z2 = z2
        
        layout = QFormLayout()
        
        # Get available zones (config=0)
        canvas = self.parent()
        main_window = canvas.parent().parent().parent()  # Get MainWindow
        available_zones = [z for z in main_window.all_zones 
                          if z.zone_type == 'dynamic' and z.num_config == 0]
        
        if not available_zones:
            layout.addRow(QLabel("No available zone slots!"))
            layout.addRow(QLabel("All Zone001-Zone150 are assigned."))
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.reject)
            layout.addRow(close_btn)
            
            self.setLayout(layout)
            return
        
        # Zone ID selection
        layout.addRow(QLabel(f"{len(available_zones)} available zone slots:"))
        
        self.zone_id_combo = QComboBox()
        for zone in sorted(available_zones, key=lambda z: z.zone_id):
            self.zone_id_combo.addItem(zone.zone_id, zone)
        layout.addRow("Select Zone ID:", self.zone_id_combo)
        
        # Config dropdown with categories
        self.config_combo = QComboBox()
        self.config_combo.setEditable(True)
        self.config_combo.setInsertPolicy(QComboBox.NoInsert)
        
        # Populate with configs and tooltips
        if hasattr(main_window, 'config_mapping') and hasattr(main_window, 'category_definitions'):
            for config_num in sorted(main_window.config_mapping.keys()):
                # Build tooltip
                tooltip_parts = [f"Config {config_num}:"]
                mapping = main_window.config_mapping[config_num]
                
                for cat_key, cat_name in mapping.items():
                    if cat_name and cat_name in main_window.category_definitions:
                        zombies = main_window.category_definitions[cat_name]
                        tooltip_parts.append(f"\n{cat_name} ({len(zombies)} zombies):")
                        for zombie in zombies[:10]:
                            tooltip_parts.append(f"  • {zombie}")
                        if len(zombies) > 10:
                            tooltip_parts.append(f"  ... and {len(zombies) - 10} more")
                
                tooltip_text = "\n".join(tooltip_parts)
                
                self.config_combo.addItem(f"{config_num}", config_num)
                self.config_combo.setItemData(
                    self.config_combo.count() - 1,
                    tooltip_text,
                    Qt.ToolTipRole
                )
        
        # Default to config 10
        default_idx = self.config_combo.findData(10)
        if default_idx >= 0:
            self.config_combo.setCurrentIndex(default_idx)
        
        layout.addRow("Config:", self.config_combo)
        
        # Comment
        self.comment_input = QLineEdit()
        layout.addRow("Comment:", self.comment_input)
        
        # Coordinates (read-only)
        coord_text = f"({x1}, {z1}) - ({x2}, {z2})"
        layout.addRow("Coordinates:", QLabel(coord_text))
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_zone_data(self) -> Optional[ZoneData]:
        """Get the zone data from inputs"""
        if not hasattr(self, 'zone_id_combo'):
            return None
            
        zone = self.zone_id_combo.currentData()
        if not zone:
            return None
        
        # Update the existing zone with new data
        zone.num_config = self.config_combo.currentData()
        zone.comment = self.comment_input.text().strip()
        
        # Ensure upleft is northwest and lowerright is southeast
        zone.coordx_upleft = min(self.x1, self.x2)
        zone.coordz_upleft = max(self.z1, self.z2)
        zone.coordx_lowerright = max(self.x1, self.x2)
        zone.coordz_lowerright = min(self.z1, self.z2)
        
        return zone


class PropertiesPanel(QWidget):
    """Panel for editing zone properties"""
    
    zone_updated = pyqtSignal(ZoneData)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_zone = None
        self.config_mapping = {}
        self.category_definitions = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout()
        
        # Zone info
        group = QGroupBox("Zone Properties")
        form = QFormLayout()
        
        self.zone_id_label = QLabel("None")
        form.addRow("Zone ID:", self.zone_id_label)
        
        self.zone_type_label = QLabel("None")
        form.addRow("Type:", self.zone_type_label)
        
        self.config_combo = QComboBox()
        self.config_combo.setEditable(True)  # Allow typing to search
        self.config_combo.setInsertPolicy(QComboBox.NoInsert)  # Don't insert typed text
        self.config_combo.currentIndexChanged.connect(self._on_config_changed)
        form.addRow("Config:", self.config_combo)
        
        self.comment_input = QLineEdit()
        form.addRow("Comment:", self.comment_input)
        
        # Coordinates
        self.coords_label = QLabel()
        form.addRow("Coordinates:", self.coords_label)
        
        group.setLayout(form)
        layout.addWidget(group)
        
        # Categories display
        self.categories_text = QTextBrowser()
        self.categories_text.setReadOnly(True)
        self.categories_text.setMaximumHeight(200)
        self.categories_text.setOpenExternalLinks(False)  # Handle clicks internally
        layout.addWidget(QLabel("Categories & Zombies:"))
        layout.addWidget(self.categories_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        btn_layout.addWidget(self.save_btn)
        
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.clicked.connect(self._revert_changes)
        btn_layout.addWidget(self.revert_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.setLayout(layout)
        self.setEnabled(False)
    
    def set_config_mapping(self, config_mapping: Dict, category_definitions: Dict):
        """Set configuration mappings"""
        self.config_mapping = config_mapping
        self.category_definitions = category_definitions
        
        # Update combo
        self.config_combo.clear()
        for config_num in sorted(config_mapping.keys()):
            # Build tooltip text with categories and zombies
            tooltip_parts = [f"Config {config_num}:"]
            mapping = config_mapping[config_num]
            
            for cat_key, cat_name in mapping.items():
                if cat_name and cat_name in category_definitions:
                    zombies = category_definitions[cat_name]
                    tooltip_parts.append(f"\n{cat_name} ({len(zombies)} zombies):")
                    # Show first 10 zombies
                    for zombie in zombies[:10]:
                        tooltip_parts.append(f"  • {zombie}")
                    if len(zombies) > 10:
                        tooltip_parts.append(f"  ... and {len(zombies) - 10} more")
            
            tooltip_text = "\n".join(tooltip_parts)
            
            self.config_combo.addItem(f"{config_num}", config_num)
            self.config_combo.setItemData(
                self.config_combo.count() - 1, 
                tooltip_text, 
                Qt.ToolTipRole
            )
    
    def set_zone(self, zone: ZoneData):
        """Set current zone for editing"""
        try:
            logger.debug(f"Setting zone in properties panel: {zone.zone_id}")
            self.current_zone = zone
            self.setEnabled(True)
            
            # Update UI
            self.zone_id_label.setText(zone.zone_id)
            self.zone_type_label.setText(zone.zone_type.capitalize())
            
            # Set config
            logger.debug(f"Setting config combo to: {zone.num_config}")
            index = self.config_combo.findData(zone.num_config)
            if index >= 0:
                self.config_combo.setCurrentIndex(index)
            else:
                logger.warning(f"Config {zone.num_config} not found in combo box")
            
            self.comment_input.setText(zone.comment)
            
            # Coordinates
            if zone.zone_type == 'dynamic':
                coords_text = f"({zone.coordx_upleft}, {zone.coordz_upleft}) - ({zone.coordx_lowerright}, {zone.coordz_lowerright})"
            else:
                coords_text = f"({zone.coordx}, {zone.coordz})"
            self.coords_label.setText(coords_text)
            
            # Categories
            logger.debug("Updating categories display")
            self._update_categories_display()
            logger.debug("Zone set successfully")
            
        except Exception as e:
            logger.error(f"Error in set_zone: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def clear(self):
        """Clear the panel"""
        self.current_zone = None
        self.setEnabled(False)
        self.zone_id_label.setText("None")
        self.zone_type_label.setText("None")
        self.comment_input.clear()
        self.coords_label.clear()
        self.categories_text.clear()
    
    def _on_config_changed(self):
        """Handle config change"""
        if not self.current_zone:
            return
        
        config_num = self.config_combo.currentData()
        if config_num is not None and config_num in self.config_mapping:
            # Update zone categories
            mapping = self.config_mapping[config_num]
            self.current_zone.categories = {}
            
            for cat_key, cat_name in mapping.items():
                if cat_name and cat_name in self.category_definitions:
                    self.current_zone.categories[cat_name] = self.category_definitions[cat_name]
            
            self._update_categories_display()
    
    def _update_categories_display(self):
        """Update categories display"""
        try:
            logger.debug("Updating categories display")
            
            if not self.current_zone:
                logger.debug("No current zone")
                self.categories_text.setText("No zone selected")
                return
                
            if not self.current_zone.categories:
                logger.debug("No categories for zone")
                self.categories_text.setText("No categories")
                return
            
            text_parts = []
            all_zombies = []
            
            for cat_name, zombies in self.current_zone.categories.items():
                logger.debug(f"Processing category: {cat_name} with {len(zombies)} zombies")
                text_parts.append(f"<b>{cat_name}:</b>")
                for zombie in zombies[:5]:  # Show first 5
                    text_parts.append(f"  • {zombie}")
                if len(zombies) > 5:
                    text_parts.append(f"  <i>... and {len(zombies) - 5} more</i>")
                text_parts.append("")
                all_zombies.extend(zombies)
            
            # Add View All button if we truncated
            if any(len(zombies) > 5 for zombies in self.current_zone.categories.values()):
                text_parts.append("<br><a href='view_all'>View All Zombies</a>")
            
            self.categories_text.setHtml("<br>".join(text_parts))
            
            # Connect link click (disconnect first to avoid multiple connections)
            try:
                self.categories_text.anchorClicked.disconnect()
            except:
                pass
            self.categories_text.anchorClicked.connect(self._show_all_zombies)
            
            logger.debug("Categories display updated successfully")
            
        except Exception as e:
            logger.error(f"Error in _update_categories_display: {e}")
            logger.error(traceback.format_exc())
            self.categories_text.setText(f"Error displaying categories: {e}")
    
    def _save_changes(self):
        """Save changes to zone"""
        if not self.current_zone:
            return
        
        self.current_zone.num_config = self.config_combo.currentData()
        self.current_zone.comment = self.comment_input.text().strip()
        
        self.zone_updated.emit(self.current_zone)
    
    def _revert_changes(self):
        """Revert changes"""
        if self.current_zone:
            self.set_zone(self.current_zone)
    
    def _show_all_zombies(self, url):
        """Show all zombies in a dialog"""
        if not self.current_zone or url.toString() != 'view_all':
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"All Zombies - {self.current_zone.zone_id}")
        dialog.setMinimumSize(500, 600)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        text_parts = []
        for cat_name, zombies in self.current_zone.categories.items():
            text_parts.append(f"<h3>{cat_name} ({len(zombies)} zombies)</h3>")
            text_parts.append("<ul>")
            for zombie in zombies:
                text_parts.append(f"<li>{zombie}</li>")
            text_parts.append("</ul>")
        
        text_edit.setHtml("".join(text_parts))
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("PvZmoD Zone Editor")
        self.setGeometry(100, 100, 1400, 900)
        
        # Data
        self.all_zones = []  # All zones including config=0
        self.zones = []  # Only zones with config > 0 (displayed)
        self.config_mapping = {}
        self.category_definitions = {}
        self.zombie_health = {}
        
        # Map configuration
        self.map_preset = "Deer Isle"
        self.world_size = 16384
        self.image_size = 4096
        
        self.current_file_paths = {
            'dynamic': '',
            'static': '',
            'categories_mapping': '',
            'categories_definitions': '',
            'zombie_health': '',
            'map_image': ''
        }
        
        # Track unsaved changes
        self.has_unsaved_changes = False
        
        # Load previous settings
        self._load_settings()
        
        self._setup_ui()
        self._create_menu()
        self._create_toolbar()
        
        # Open file dialog on startup
        QTimer.singleShot(100, self._open_files)
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, 
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before exiting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self._save_files()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()
    
    def _save_settings(self):
        """Save current file paths and map config to settings file"""
        try:
            settings = {
                'file_paths': self.current_file_paths,
                'map_config': {
                    'preset': self.map_preset,
                    'world_size': self.world_size,
                    'image_size': self.image_size
                },
                'last_updated': datetime.now().isoformat()
            }
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
            logger.info("Settings saved")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def _load_settings(self):
        """Load previous file paths and map config from settings file"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.current_file_paths = settings.get('file_paths', self.current_file_paths)
                    
                    # Load map configuration
                    map_config = settings.get('map_config', {})
                    self.map_preset = map_config.get('preset', 'Deer Isle')
                    self.world_size = map_config.get('world_size', 16384)
                    self.image_size = map_config.get('image_size', 4096)
                    
                    logger.info(f"Settings loaded: map={self.map_preset}, world_size={self.world_size}")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
    
    def _setup_ui(self):
        """Setup UI"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout()
        
        # Left panel - Zone list
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        left_layout.addWidget(QLabel("Zones:"))
        
        self.zone_tree = QTreeWidget()
        self.zone_tree.setHeaderLabels(["Zone", "Config", "Type"])
        self.zone_tree.itemClicked.connect(self._on_zone_selected)
        
        # Set selection color to match the blue used elsewhere
        self.zone_tree.setStyleSheet("""
            QTreeWidget::item:selected {
                background-color: #0078D7;
                color: white;
            }
            QTreeWidget::item:selected:!active {
                background-color: #0078D7;
                color: white;
            }
        """)
        
        left_layout.addWidget(self.zone_tree)
        
        # Delete button
        self.delete_zone_btn = QPushButton("Delete Zone")
        self.delete_zone_btn.clicked.connect(self._delete_zone)
        left_layout.addWidget(self.delete_zone_btn)
        
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)
        
        # Center - Map canvas
        self.canvas = MapCanvas()
        self.canvas.zone_selected.connect(self._on_canvas_zone_selected)
        self.canvas.zone_modified.connect(self._on_zone_modified)
        
        # Right panel - Properties
        self.properties_panel = PropertiesPanel()
        self.properties_panel.zone_updated.connect(self._on_zone_updated)
        self.properties_panel.setMaximumWidth(350)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self.properties_panel)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        central.setLayout(layout)
    
    def _create_menu(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open Configuration Files...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_files)
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save Changes", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_files)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        add_action = QAction("Add Dynamic Zone", self)
        add_action.setShortcut(QKeySequence("Ctrl+N"))
        add_action.triggered.connect(self._toggle_draw_mode)
        edit_menu.addAction(add_action)
        
        delete_action = QAction("Delete Zone", self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self._delete_zone)
        edit_menu.addAction(delete_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        fit_action = QAction("Fit to Window", self)
        fit_action.triggered.connect(self._fit_to_window)
        view_menu.addAction(fit_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        guide_action = QAction("User Guide", self)
        guide_action.setShortcut(QKeySequence.HelpContents)
        guide_action.triggered.connect(self._show_user_guide)
        help_menu.addAction(guide_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Mode buttons
        self.select_mode_btn = QAction("Select", self)
        self.select_mode_btn.setCheckable(True)
        self.select_mode_btn.setChecked(True)
        self.select_mode_btn.triggered.connect(lambda: self._set_mode('select'))
        toolbar.addAction(self.select_mode_btn)
        
        self.draw_mode_btn = QAction("Add Dynamic Zone", self)
        self.draw_mode_btn.setCheckable(True)
        self.draw_mode_btn.triggered.connect(self._toggle_draw_mode)
        toolbar.addAction(self.draw_mode_btn)
        
        toolbar.addSeparator()
        
        # Move/Resize button
        self.edit_zone_btn = QAction("Move/Resize Zone", self)
        self.edit_zone_btn.setCheckable(True)
        self.edit_zone_btn.setEnabled(False)  # Disabled until zone selected
        self.edit_zone_btn.triggered.connect(self._toggle_edit_mode)
        toolbar.addAction(self.edit_zone_btn)
        
        toolbar.addSeparator()
        
        # Filter system
        toolbar.addWidget(QLabel("Filter by:"))
        
        # Filter type selection
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItem("None", "none")
        self.filter_type_combo.addItem("Config", "config")
        self.filter_type_combo.addItem("Category", "category")
        self.filter_type_combo.addItem("Zombie Class", "zombie")
        self.filter_type_combo.currentIndexChanged.connect(self._on_filter_type_changed)
        toolbar.addWidget(self.filter_type_combo)
        
        # Filter value selection (dynamically populated)
        self.filter_value_combo = QComboBox()
        self.filter_value_combo.setEnabled(False)
        self.filter_value_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_value_combo)
        
        toolbar.addSeparator()
        
        # Show unused dropdown
        show_unused_btn = QPushButton("Show Unused ▼")
        show_unused_menu = QMenu(self)
        
        unused_configs_action = QAction("Unused Configs", self)
        unused_configs_action.triggered.connect(self._show_unused_configs)
        show_unused_menu.addAction(unused_configs_action)
        
        unused_categories_action = QAction("Unused Categories", self)
        unused_categories_action.triggered.connect(self._show_unused_categories)
        show_unused_menu.addAction(unused_categories_action)
        
        unused_zombies_action = QAction("Unused Zombies", self)
        unused_zombies_action.triggered.connect(self._show_unused_zombies)
        show_unused_menu.addAction(unused_zombies_action)
        
        show_unused_btn.setMenu(show_unused_menu)
        toolbar.addWidget(show_unused_btn)
    
    def _open_files(self):
        """Open configuration files individually"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Open Configuration Files")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select each configuration file:"))
        
        # File selection widgets
        self.file_inputs = {}
        file_types = [
            ('dynamic', 'DynamicSpawnZones.c', 'Dynamic Zones', True),
            ('static', 'StaticSpawnDatas.c', 'Static Zones', True),
            ('categories_mapping', 'ZombiesChooseCategories.c', 'Categories Mapping', True),
            ('categories_definitions', 'ZombiesCategories.c', 'Categories Definitions', True),
            ('map_image', 'Map.png', 'Map Image', True),
            ('zombie_health', 'PvZmoD_CustomisableZombies_Characteristics.xml', 'Zombie Health (optional - for danger color coding)', False),
        ]
        
        for key, default_name, label, required in file_types:
            group = QHBoxLayout()
            
            req_label = "*" if required else ""
            lbl = QLabel(f"{req_label}{label}:")
            lbl.setMinimumWidth(150)
            group.addWidget(lbl)
            
            line_edit = QLineEdit()
            line_edit.setReadOnly(True)
            line_edit.setPlaceholderText(default_name)
            
            # Pre-populate with saved path if available
            if self.current_file_paths.get(key):
                line_edit.setText(self.current_file_paths[key])
            
            group.addWidget(line_edit)
            
            btn = QPushButton("Browse...")
            btn.clicked.connect(lambda checked, k=key, le=line_edit, dn=default_name: self._browse_file(k, le, dn))
            group.addWidget(btn)
            
            layout.addLayout(group)
            self.file_inputs[key] = {'widget': line_edit, 'required': required}
        
        layout.addWidget(QLabel("\n* Required files"))
        
        # Map Configuration Section
        layout.addWidget(QLabel("\n=== Map Configuration ==="))
        
        # Map preset dropdown
        map_preset_layout = QHBoxLayout()
        map_preset_layout.addWidget(QLabel("Map Preset:"))
        
        self.map_preset_combo = QComboBox()
        for preset_name in MAP_PRESETS.keys():
            self.map_preset_combo.addItem(preset_name)
        
        # Set saved preset
        index = self.map_preset_combo.findText(self.map_preset)
        if index >= 0:
            self.map_preset_combo.setCurrentIndex(index)
        
        self.map_preset_combo.currentTextChanged.connect(self._on_map_preset_changed)
        map_preset_layout.addWidget(self.map_preset_combo)
        map_preset_layout.addStretch()
        
        layout.addLayout(map_preset_layout)
        
        # World size field
        world_size_layout = QHBoxLayout()
        world_size_layout.addWidget(QLabel("World Size:"))
        
        self.world_size_input = QLineEdit()
        self.world_size_input.setText(str(self.world_size))
        self.world_size_input.setMaximumWidth(100)
        world_size_layout.addWidget(self.world_size_input)
        world_size_layout.addWidget(QLabel("units"))
        world_size_layout.addStretch()
        
        layout.addLayout(world_size_layout)
        
        # Enable/disable world size based on preset
        self._on_map_preset_changed(self.map_preset)
        
        # Image size info (read-only, updated when image loads)
        image_size_layout = QHBoxLayout()
        image_size_layout.addWidget(QLabel("Image Size:"))
        self.image_size_label = QLabel(f"{self.image_size}x{self.image_size} (auto-detected)")
        image_size_layout.addWidget(self.image_size_label)
        image_size_layout.addStretch()
        
        layout.addLayout(image_size_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        load_btn = QPushButton("Load Files")
        load_btn.clicked.connect(lambda: self._load_selected_files(dialog))
        btn_layout.addWidget(load_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        
        dialog.exec_()
    
    def _browse_file(self, key, line_edit, default_name):
        """Browse for a specific file"""
        if key == 'map_image':
            file_filter = "Images (*.png *.jpg *.jpeg)"
        elif key == 'zombie_health':
            file_filter = "XML Files (*.xml)"
        else:
            file_filter = "C Files (*.c)"
        
        filepath, _ = QFileDialog.getOpenFileName(
            self, f"Select {default_name}", "", file_filter
        )
        
        if filepath:
            line_edit.setText(filepath)
            self.current_file_paths[key] = filepath
    
    def _on_map_preset_changed(self, preset_name):
        """Handle map preset selection change"""
        world_size = MAP_PRESETS.get(preset_name)
        
        if world_size is None:  # Custom
            # Enable manual input
            self.world_size_input.setEnabled(True)
            self.world_size_input.setStyleSheet("")
        else:
            # Disable manual input and set preset value
            self.world_size_input.setText(str(world_size))
            self.world_size_input.setEnabled(False)
            self.world_size_input.setStyleSheet("background-color: #f0f0f0;")
    
    def _load_selected_files(self, dialog):
        """Load the selected files"""
        try:
            logger.info("Starting file loading...")
            
            # Check required files
            missing = []
            for key, info in self.file_inputs.items():
                if info['required'] and not info['widget'].text():
                    missing.append(key)
            
            if missing:
                QMessageBox.warning(
                    self, "Missing Files",
                    f"Please select required files: {', '.join(missing)}"
                )
                return
            
            # Get and validate map configuration
            try:
                self.map_preset = self.map_preset_combo.currentText()
                self.world_size = int(self.world_size_input.text())
                
                if self.world_size <= 0:
                    QMessageBox.warning(
                        self, "Invalid World Size",
                        "World size must be greater than 0"
                    )
                    return
                
                logger.info(f"Map configuration: preset={self.map_preset}, world_size={self.world_size}")
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid World Size",
                    "World size must be a valid number"
                )
                return
            
            # Dynamic zones
            dynamic_path = self.file_inputs['dynamic']['widget'].text()
            if dynamic_path:
                logger.info(f"Loading dynamic zones from: {dynamic_path}")
                dynamic_zones = FileParser.parse_dynamic_zones(dynamic_path)
                logger.info(f"Parsed {len(dynamic_zones)} dynamic zones")
                self.current_file_paths['dynamic'] = dynamic_path
            else:
                dynamic_zones = []
            
            # Static zones
            static_path = self.file_inputs['static']['widget'].text()
            if static_path:
                logger.info(f"Loading static zones from: {static_path}")
                static_zones = FileParser.parse_static_zones(static_path)
                logger.info(f"Parsed {len(static_zones)} static zones")
                self.current_file_paths['static'] = static_path
            else:
                static_zones = []
            
            # Categories mapping
            mapping_path = self.file_inputs['categories_mapping']['widget'].text()
            if mapping_path:
                logger.info(f"Loading category mappings from: {mapping_path}")
                self.config_mapping = FileParser.parse_categories_mapping(mapping_path)
                logger.info(f"Parsed {len(self.config_mapping)} config mappings")
                self.current_file_paths['categories_mapping'] = mapping_path
            
            # Categories definitions
            definitions_path = self.file_inputs['categories_definitions']['widget'].text()
            if definitions_path:
                logger.info(f"Loading category definitions from: {definitions_path}")
                self.category_definitions = FileParser.parse_categories_definitions(definitions_path)
                logger.info(f"Parsed {len(self.category_definitions)} category definitions")
                self.current_file_paths['categories_definitions'] = definitions_path
            
            # Map image
            map_path = self.file_inputs['map_image']['widget'].text()
            if map_path:
                logger.info(f"Loading map image from: {map_path}")
                
                # Load image and auto-detect size
                try:
                    with Image.open(map_path) as img:
                        # Validate square image
                        if img.width != img.height:
                            QMessageBox.critical(
                                self, "Invalid Map Image",
                                f"Map image must be square!\n\n"
                                f"Current size: {img.width}x{img.height}\n\n"
                                f"Please use a square image (e.g., 2048x2048, 4096x4096)"
                            )
                            logger.error(f"Non-square image rejected: {img.width}x{img.height}")
                            return
                        
                        self.image_size = img.width
                        logger.info(f"Image size auto-detected: {img.width}x{img.height}")
                except Exception as e:
                    logger.error(f"Failed to detect image size: {e}")
                    QMessageBox.critical(
                        self, "Error",
                        f"Failed to load map image:\n{e}"
                    )
                    return
                
                # Load map and configure canvas
                self.canvas.load_map_image(map_path)
                self.canvas.set_map_config(self.world_size, self.image_size)
                self.current_file_paths['map_image'] = map_path
                
                logger.info(f"Map configured: world={self.world_size}, image={self.image_size}")
            
            # Zombie health (optional)
            health_path = self.file_inputs['zombie_health']['widget'].text()
            if health_path:
                logger.info(f"Loading zombie health from: {health_path}")
                self.zombie_health = FileParser.parse_zombie_health(health_path)
                logger.info(f"Parsed health for {len(self.zombie_health)} zombie types")
                self.current_file_paths['zombie_health'] = health_path
            else:
                self.zombie_health = {}
                logger.info("No zombie health file provided (optional)")
            
            # Combine zones - ONLY show zones with config > 0
            logger.info("Processing zones...")
            self.all_zones = dynamic_zones + static_zones
            self.zones = [z for z in self.all_zones if z.num_config > 0]
            logger.info(f"Total zones: {len(self.all_zones)}, Active zones: {len(self.zones)}")
            
            # Populate categories for zones
            logger.info("Populating categories for zones...")
            for zone in self.zones:
                if zone.num_config in self.config_mapping:
                    mapping = self.config_mapping[zone.num_config]
                    zone.categories = {}
                    for cat_key, cat_name in mapping.items():
                        if cat_name and cat_name in self.category_definitions:
                            zone.categories[cat_name] = self.category_definitions[cat_name]
            
            logger.info("Updating UI...")
            # Update UI
            self.canvas.set_zones(self.zones)
            self._update_zone_tree()
            self.properties_panel.set_config_mapping(self.config_mapping, self.category_definitions)
            
            # Pass zombie health data to canvas for danger color coding
            if self.zombie_health:
                logger.info("Setting zombie health data for danger color coding")
                self.canvas.set_zombie_health(self.zombie_health)
                
                # Show health range info to user
                if hasattr(self.canvas, 'min_health') and hasattr(self.canvas, 'max_health'):
                    health_info = (
                        f"Danger color coding enabled!\n\n"
                        f"Health range: {self.canvas.min_health:.1f} - {self.canvas.max_health:.1f}\n\n"
                        f"Color thresholds (relative to your zombies):\n"
                        f"🟢 Green: ≤ {self.canvas.health_20th:.1f} (weakest 20%)\n"
                        f"🟡 Yellow-Green: ≤ {self.canvas.health_40th:.1f}\n"
                        f"🟡 Yellow: ≤ {self.canvas.health_60th:.1f} (average)\n"
                        f"🟠 Orange: ≤ {self.canvas.health_80th:.1f}\n"
                        f"🔴 Red: > {self.canvas.health_80th:.1f} (strongest 20%)"
                    )
                    logger.info(health_info.replace('\n', ' / '))
            
            # Populate filter options based on loaded data
            self._populate_filter_options()
            
            # Count active and available zones
            dynamic_active = len([z for z in dynamic_zones if z.num_config > 0])
            dynamic_available = len([z for z in dynamic_zones if z.num_config == 0])
            
            logger.info("File loading complete!")
            
            success_msg = (
                f"Map: {self.map_preset} ({self.world_size}x{self.world_size})\n"
                f"Image: {self.image_size}x{self.image_size}\n\n"
                f"Loaded {dynamic_active} active dynamic zones\n"
                f"{dynamic_available} available zone slots (config=0)\n"
                f"{len(static_zones)} static zones"
            )
            
            if self.zombie_health and hasattr(self.canvas, 'min_health'):
                success_msg += (
                    f"\n\n✓ Danger color coding: {self.canvas.min_health:.0f}-{self.canvas.max_health:.0f} HP"
                )
            
            QMessageBox.information(self, "Success", success_msg)
            
            # Save settings for next time
            self._save_settings()
            
            dialog.accept()
            
        except Exception as e:
            logger.error(f"Error loading files: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", f"Failed to load files: {e}\n\nSee log file for details:\n{LOG_FILE}")
    
    def _save_files(self):
        """Save changes to files"""
        if not self.current_file_paths['dynamic']:
            QMessageBox.warning(self, "Warning", "No files loaded to save")
            return
        
        try:
            # Save ALL dynamic zones (including config=0 ones)
            dynamic_zones = [z for z in self.all_zones if z.zone_type == 'dynamic']
            FileParser.save_dynamic_zones(dynamic_zones, self.current_file_paths['dynamic'])
            
            dynamic_active = len([z for z in dynamic_zones if z.num_config > 0])
            dynamic_available = len([z for z in dynamic_zones if z.num_config == 0])
            
            # Save static zones if loaded
            static_saved = False
            static_count = 0
            if self.current_file_paths['static']:
                static_zones = [z for z in self.all_zones if z.zone_type == 'static']
                FileParser.save_static_zones(static_zones, self.current_file_paths['static'])
                static_count = len([z for z in static_zones if z.num_config > 0])
                static_saved = True
            
            # Clear unsaved changes flag
            self.has_unsaved_changes = False
            self._update_title()
            
            message = f"Files saved successfully!\n\n"
            message += f"Dynamic zones: {dynamic_active} active, {dynamic_available} available\n"
            if static_saved:
                message += f"Static zones: {static_count} saved\n"
            message += f"\nBackup created with .backup extension"
            
            QMessageBox.information(self, "Success", message)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save files: {e}")
    
    def _update_zone_tree(self):
        """Update zone tree"""
        self.zone_tree.clear()
        
        for zone in self.zones:
            item = QTreeWidgetItem([
                zone.zone_id,
                str(zone.num_config),
                zone.zone_type.capitalize()
            ])
            item.setData(0, Qt.UserRole, zone.zone_id)
            self.zone_tree.addTopLevelItem(item)
    
    def _on_zone_selected(self, item, column):
        """Handle zone selection from tree"""
        try:
            logger.debug(f"Zone selected from tree: {item.text(0)}")
            zone_id = item.data(0, Qt.UserRole)
            logger.debug(f"Zone ID: {zone_id}")
            
            zone = self._find_zone(zone_id)
            if zone:
                logger.debug(f"Found zone: {zone.zone_id}, config: {zone.num_config}")
                self.canvas.select_zone(zone_id)
                self.properties_panel.set_zone(zone)
                
                # Enable/disable move/resize button based on zone type
                # Config and comment can be edited for both dynamic and static
                if zone.zone_type == 'dynamic':
                    self.edit_zone_btn.setEnabled(True)
                else:
                    # Static zones can't be moved/resized
                    self.edit_zone_btn.setEnabled(False)
                    self.edit_zone_btn.setChecked(False)
                    self.canvas.set_edit_mode(False)
                
                logger.debug("Zone selection complete")
            else:
                logger.error(f"Zone not found: {zone_id}")
        except Exception as e:
            logger.error(f"Error in _on_zone_selected: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", f"Failed to select zone: {e}\n\nSee log file for details:\n{LOG_FILE}")
    
    def _on_canvas_zone_selected(self, zone_id):
        """Handle zone selection from canvas"""
        try:
            logger.debug(f"Zone selected from canvas: {zone_id}")
            zone = self._find_zone(zone_id)
            if zone:
                logger.debug(f"Setting zone in properties panel: {zone.zone_id}")
                self.properties_panel.set_zone(zone)
                
                # Select in tree AND highlight in canvas
                for i in range(self.zone_tree.topLevelItemCount()):
                    item = self.zone_tree.topLevelItem(i)
                    if item.data(0, Qt.UserRole) == zone_id:
                        self.zone_tree.setCurrentItem(item)
                        break
                
                # Make sure canvas highlights the zone
                self.canvas.select_zone(zone_id)
                
                # Enable/disable move/resize button based on zone type
                # Config and comment can be edited for both dynamic and static
                if zone.zone_type == 'dynamic':
                    self.edit_zone_btn.setEnabled(True)
                else:
                    # Static zones can't be moved/resized
                    self.edit_zone_btn.setEnabled(False)
                    self.edit_zone_btn.setChecked(False)
                    self.canvas.set_edit_mode(False)
                
                logger.debug("Canvas zone selection complete")
            else:
                logger.error(f"Zone not found: {zone_id}")
        except Exception as e:
            logger.error(f"Error in _on_canvas_zone_selected: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", f"Failed to select zone: {e}\n\nSee log file for details:\n{LOG_FILE}")
    
    def _on_zone_modified(self, zone_id):
        """Handle zone modification"""
        zone = self._find_zone(zone_id)
        if zone:
            # If zone now has config > 0, add to visible zones
            if zone.num_config > 0 and zone not in self.zones:
                self.zones.append(zone)
            # If zone now has config = 0, remove from visible zones
            elif zone.num_config == 0 and zone in self.zones:
                self.zones.remove(zone)
            
            self._update_zone_tree()
            self.canvas.update_zone(zone)
            
            # Mark as unsaved
            self.has_unsaved_changes = True
            self._update_title()
    
    def _on_zone_updated(self, zone: ZoneData):
        """Handle zone update from properties panel"""
        self.canvas.update_zone(zone)
        self._update_zone_tree()
        
        # Mark as unsaved
        self.has_unsaved_changes = True
        self._update_title()
        
        QMessageBox.information(self, "Success", "Zone updated")
    
    def _find_zone(self, zone_id: str) -> Optional[ZoneData]:
        """Find zone by ID"""
        for zone in self.all_zones:
            if zone.zone_id == zone_id:
                return zone
        return None
    
    def _update_title(self):
        """Update window title to show unsaved changes"""
        base_title = "PvZmoD Zone Editor"
        if self.has_unsaved_changes:
            self.setWindowTitle(f"{base_title} *")
        else:
            self.setWindowTitle(base_title)
    
    def _fit_to_window(self):
        """Fit map to window"""
        if self.canvas.background_item:
            # Reset zoom tracking
            self.canvas.current_zoom = 1.0
            # Fit view
            self.canvas.fitInView(self.canvas.sceneRect(), Qt.KeepAspectRatio)
            # Update zoom tracking based on actual scale
            transform = self.canvas.transform()
            self.canvas.current_zoom = transform.m11()  # Get current scale
    
    def _set_mode(self, mode: str):
        """Set interaction mode"""
        self.select_mode_btn.setChecked(mode == 'select')
        self.draw_mode_btn.setChecked(mode == 'draw')
        
        self.canvas.drawing_mode = (mode == 'draw')
        
        if mode == 'draw':
            self.canvas.setDragMode(QGraphicsView.NoDrag)
            self.canvas.viewport().setCursor(Qt.CrossCursor)
        else:
            self.canvas.setDragMode(QGraphicsView.NoDrag)
            self.canvas.viewport().setCursor(Qt.ArrowCursor)
    
    def _toggle_draw_mode(self):
        """Toggle between Add Dynamic Zone and Done Adding"""
        if self.draw_mode_btn.isChecked():
            # Entering draw mode
            self.draw_mode_btn.setText("Draw Zone Rectangle")
            self._set_mode('draw')
            logger.debug("Entered draw mode")
        else:
            # Check if there's a temp zone to finalize
            if self.canvas.temp_new_zone:
                # Finalize the zone and show dialog
                self.draw_mode_btn.setText("Add Dynamic Zone")
                self.canvas.finalize_new_zone()
                self._set_mode('select')
                logger.debug("Finalized new zone")
            else:
                # Just exit draw mode
                self.draw_mode_btn.setText("Add Dynamic Zone")
                self._set_mode('select')
                logger.debug("Exited draw mode")
    
    def _toggle_edit_mode(self):
        """Toggle move/resize mode for selected zone"""
        if self.edit_zone_btn.isChecked():
            # Enter edit mode
            self.edit_zone_btn.setText("Done Editing")
            self.canvas.set_edit_mode(True)
            logger.debug("Entered edit mode")
        else:
            # Exit edit mode
            self.edit_zone_btn.setText("Move/Resize Zone")
            self.canvas.set_edit_mode(False)
            logger.debug("Exited edit mode")
    
    def _enable_draw_mode(self):
        """Enable drawing mode"""
        # Check for available zones (config=0)
        available_zones = [z for z in self.all_zones 
                          if z.zone_type == 'dynamic' and z.num_config == 0]
        
        if not available_zones:
            QMessageBox.warning(
                self, "No Available Zones",
                "All Zone001-Zone150 slots are assigned.\n\n"
                "To add a new zone, first set an existing zone's config to 0 to free it up."
            )
            return
        
        # Toggle drawing mode
        if not self.draw_mode_btn.isChecked():
            self.draw_mode_btn.setChecked(True)
            self.draw_mode_btn.setText("Done Adding")
            self._set_mode('draw')
            self.select_mode_btn.setEnabled(False)
            self.edit_zone_btn.setEnabled(False)
            QMessageBox.information(
                self, "Draw Mode",
                f"Click and drag on the map to draw a new zone rectangle.\n\n"
                f"You can resize the zone by dragging corners after drawing.\n"
                f"Click 'Done Adding' when you're happy with the size/position.\n\n"
                f"{len(available_zones)} zone slots available."
            )
        else:
            # User clicked "Done Adding" - finish the zone
            self._finish_adding_zone()
    
    def _finish_adding_zone(self):
        """Finish adding the new zone and show config dialog"""
        if not self.canvas.temp_new_zone:
            QMessageBox.warning(
                self, "No Zone",
                "Please draw a zone rectangle first before clicking 'Done Adding'."
            )
            return
        
        # Get the zone rectangle from canvas
        rect = self.canvas.temp_new_zone.rect()
        
        # Convert to world coordinates
        x1, z1 = self.canvas.pixel_to_world(rect.left(), rect.top())
        x2, z2 = self.canvas.pixel_to_world(rect.right(), rect.bottom())
        
        # Show dialog to configure the zone
        self.canvas._show_new_zone_dialog(x1, z1, x2, z2)
        
        # Clean up
        self.canvas.finish_drawing()
        
        # Reset button
        self.draw_mode_btn.setChecked(False)
        self.draw_mode_btn.setText("Add Dynamic Zone")
        self.select_mode_btn.setEnabled(True)
        self._set_mode('select')
    
    def _delete_zone(self):
        """Delete selected zone by setting config to 0"""
        zone_id = self.canvas.selected_zone_id
        if not zone_id:
            QMessageBox.warning(self, "Warning", "No zone selected")
            return
        
        zone = self._find_zone(zone_id)
        if not zone:
            return
        
        # Can only "delete" dynamic zones
        if zone.zone_type != 'dynamic':
            QMessageBox.warning(
                self, "Cannot Delete", 
                "Static zones cannot be deleted.\n\nOnly dynamic zones can be set to config 0."
            )
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Set {zone_id} to config 0 (make available)?\n\n"
            f"This will clear the zone's coordinates and config,\n"
            f"making the slot available for reuse.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Set config and coordinates to 0
            zone.num_config = 0
            zone.coordx_upleft = 0
            zone.coordz_upleft = 0
            zone.coordx_lowerright = 0
            zone.coordz_lowerright = 0
            zone.comment = ""
            zone.categories = {}
            
            # Remove from visible zones
            if zone in self.zones:
                self.zones.remove(zone)
            
            # Remove from canvas
            self.canvas.remove_zone(zone_id)
            
            # Update tree
            self._update_zone_tree()
            
            # Clear properties
            self.properties_panel.clear()
            
            # Disable edit button
            self.edit_zone_btn.setEnabled(False)
            
            QMessageBox.information(
                self, "Zone Deleted",
                f"{zone_id} is now available (config set to 0)"
            )
    
    def _on_filter_type_changed(self):
        """Handle filter type selection change"""
        filter_type = self.filter_type_combo.currentData()
        
        # Clear and disable value combo
        self.filter_value_combo.clear()
        
        if filter_type == "none":
            self.filter_value_combo.setEnabled(False)
            self._apply_filter()  # Show all zones
            return
        
        # Enable and populate value combo based on type
        self.filter_value_combo.setEnabled(True)
        
        if filter_type == "config":
            # Populate with config numbers
            for config_num in sorted(self.config_mapping.keys()):
                self.filter_value_combo.addItem(f"Config {config_num}", ("config", config_num))
        
        elif filter_type == "category":
            # Populate with all unique categories across all zones
            categories = set()
            for zone in self.zones:
                if hasattr(zone, 'categories') and zone.categories:
                    for cat_name in zone.categories.keys():
                        categories.add(cat_name)
            
            for cat_name in sorted(categories):
                self.filter_value_combo.addItem(cat_name, ("category", cat_name))
        
        elif filter_type == "zombie":
            # Populate with all unique zombie classes across all zones
            zombies = set()
            for zone in self.zones:
                if hasattr(zone, 'categories') and zone.categories:
                    for zombie_list in zone.categories.values():
                        for zombie in zombie_list:
                            zombies.add(zombie)
            
            for zombie in sorted(zombies):
                self.filter_value_combo.addItem(zombie, ("zombie", zombie))
        
        # Apply filter with first item selected
        if self.filter_value_combo.count() > 0:
            self._apply_filter()
    
    def _populate_filter_options(self):
        """Populate filter options after loading data"""
        # Reset to "None" filter
        self.filter_type_combo.setCurrentIndex(0)
        self.filter_value_combo.clear()
        self.filter_value_combo.setEnabled(False)
    
    def _apply_filter(self):
        """Apply zone filter based on selected type and value"""
        filter_type = self.filter_type_combo.currentData()
        
        if filter_type == "none":
            # Show all zones
            for zone in self.zones:
                if zone.zone_id in self.canvas.zone_graphics:
                    self.canvas.zone_graphics[zone.zone_id].setVisible(True)
                    self.canvas.zone_labels[zone.zone_id].setVisible(True)
            return
        
        # Get filter value
        filter_data = self.filter_value_combo.currentData()
        if not filter_data:
            return
        
        filter_value_type, filter_value = filter_data
        
        # Apply appropriate filter
        for zone in self.zones:
            if zone.zone_id not in self.canvas.zone_graphics:
                continue
            
            visible = False
            
            if filter_value_type == "config":
                # Filter by config number
                visible = (zone.num_config == filter_value)
            
            elif filter_value_type == "category":
                # Filter by category - show if zone has this category
                if hasattr(zone, 'categories') and zone.categories:
                    visible = filter_value in zone.categories
            
            elif filter_value_type == "zombie":
                # Filter by zombie class - show if zone has this zombie in any category
                if hasattr(zone, 'categories') and zone.categories:
                    for zombie_list in zone.categories.values():
                        if filter_value in zombie_list:
                            visible = True
                            break
            
            self.canvas.zone_graphics[zone.zone_id].setVisible(visible)
            self.canvas.zone_labels[zone.zone_id].setVisible(visible)
    
    def _show_unused_configs(self):
        """Show list of unused configs"""
        if not self.config_mapping:
            QMessageBox.information(self, "No Data", "No config mapping loaded")
            return
        
        # Get all configs that are in use
        used_configs = set()
        for zone in self.zones:
            used_configs.add(zone.num_config)
        
        # Get unused configs
        all_configs = set(self.config_mapping.keys())
        unused_configs = sorted(all_configs - used_configs)
        
        if not unused_configs:
            QMessageBox.information(
                self, "Unused Configs",
                "All configs are currently in use!"
            )
            return
        
        # Show dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Unused Configs ({len(unused_configs)} total)")
        dialog.setMinimumSize(400, 500)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        text_parts = [f"<h3>Unused Configs: {len(unused_configs)}</h3>"]
        text_parts.append("<p>These configs exist in ZombiesChooseCategories.c but are not used by any zones:</p>")
        text_parts.append("<ul>")
        for config_num in unused_configs:
            mapping = self.config_mapping[config_num]
            categories = [name for name in mapping.values() if name]
            text_parts.append(f"<li><b>Config {config_num}</b>: {len(categories)} categories</li>")
        text_parts.append("</ul>")
        
        text_edit.setHtml("".join(text_parts))
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def _show_unused_categories(self):
        """Show list of unused categories"""
        if not self.category_definitions:
            QMessageBox.information(self, "No Data", "No category definitions loaded")
            return
        
        # Get all categories that are in use by zones
        used_categories = set()
        for zone in self.zones:
            if hasattr(zone, 'categories'):
                used_categories.update(zone.categories.keys())
        
        # Get unused categories
        all_categories = set(self.category_definitions.keys())
        unused_categories = sorted(all_categories - used_categories)
        
        if not unused_categories:
            QMessageBox.information(
                self, "Unused Categories",
                "All categories are currently in use!"
            )
            return
        
        # Show dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Unused Categories ({len(unused_categories)} total)")
        dialog.setMinimumSize(500, 600)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        text_parts = [f"<h3>Unused Categories: {len(unused_categories)}</h3>"]
        text_parts.append("<p>These categories exist in ZombiesCategories.c but are not used by any active zones:</p>")
        text_parts.append("<ul>")
        for cat_name in unused_categories:
            zombies = self.category_definitions[cat_name]
            text_parts.append(f"<li><b>{cat_name}</b>: {len(zombies)} zombies</li>")
        text_parts.append("</ul>")
        
        text_edit.setHtml("".join(text_parts))
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def _show_unused_zombies(self):
        """Show list of unused zombies"""
        if not self.zombie_health:
            QMessageBox.information(
                self, "No Data",
                "Zombie health file not loaded.\n\n"
                "This feature requires PvZmoD_CustomisableZombies_Characteristics.xml\n"
                "to be loaded (optional file in File → Open Files dialog)."
            )
            return
        
        # Get all zombies that are in use by zones
        used_zombies = set()
        for zone in self.zones:
            if hasattr(zone, 'categories'):
                for zombie_list in zone.categories.values():
                    used_zombies.update(zombie_list)
        
        # Get unused zombies
        all_zombies = set(self.zombie_health.keys())
        unused_zombies = sorted(all_zombies - used_zombies)
        
        if not unused_zombies:
            QMessageBox.information(
                self, "Unused Zombies",
                "All zombie types are currently in use!"
            )
            return
        
        # Show dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Unused Zombies ({len(unused_zombies)} total)")
        dialog.setMinimumSize(500, 600)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        text_parts = [f"<h3>Unused Zombies: {len(unused_zombies)}</h3>"]
        text_parts.append("<p>These zombie types exist in the characteristics file but are not used by any active zones:</p>")
        text_parts.append("<ul>")
        for zombie_name in unused_zombies:
            health = self.zombie_health.get(zombie_name, 0)
            text_parts.append(f"<li><b>{zombie_name}</b> (Health: {health:.0f})</li>")
        text_parts.append("</ul>")
        
        text_edit.setHtml("".join(text_parts))
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About PvZmoD Zone Editor",
            "PvZmoD Zone Editor v1.0\n\n"
            "A standalone application for editing DayZ PvZmoD zombie spawn zones.\n\n"
            "Features:\n"
            "• Visual zone editing with danger color coding\n"
            "• Support for dynamic and static zones\n"
            "• Relative difficulty based on your zombie health data\n"
            "• Comprehensive filtering and analysis tools\n\n"
            "License: GNU General Public License v3.0\n"
            "This program is free software: you can redistribute it and/or modify it\n"
            "under the terms of the GNU GPL v3 as published by the Free Software Foundation.\n\n"
            "This program is distributed in the hope that it will be useful,\n"
            "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.\n\n"
            "See the GNU General Public License for more details:\n"
            "https://www.gnu.org/licenses/gpl-3.0.html"
        )
    
    def _show_user_guide(self):
        """Show user guide dialog"""
        guide = QDialog(self)
        guide.setWindowTitle("User Guide")
        guide.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # Create tabbed interface for guide sections
        from PyQt5.QtWidgets import QTabWidget
        tabs = QTabWidget()
        
        # Getting Started tab
        getting_started = QTextBrowser()
        getting_started.setOpenExternalLinks(False)
        getting_started.setHtml("""
        <h2>Getting Started</h2>
        
        <h3>First Time Setup</h3>
        <ol>
            <li>Launch the app - file dialog opens automatically</li>
            <li><b>Configure your map:</b></li>
            <ul>
                <li>Select map preset: <b>Deer Isle</b> (16384), <b>Chernarus</b> (15360), <b>Livonia</b> (12800), or <b>Custom</b></li>
                <li>World size auto-fills (editable for Custom)</li>
                <li>Image size auto-detected from your map PNG</li>
            </ul>
            <li>Browse for <b>required files</b> (marked with *):</li>
            <ul>
                <li><b>DynamicSpawnZones.c</b> - Zone coordinates and configs</li>
                <li><b>StaticSpawnDatas.c</b> - Static zones</li>
                <li><b>ZombiesChooseCategories.c</b> - Config mappings</li>
                <li><b>ZombiesCategories.c</b> - Zombie lists</li>
                <li><b>Map.png</b> - Background map (must be square!)</li>
            </ul>
            <li>Optionally add:</li>
            <ul>
                <li><b>PvZmoD_CustomisableZombies_Characteristics.xml</b> - For danger color coding</li>
            </ul>
            <li>Click "Load Files"</li>
            <li>Settings are saved - next time just click "Load Files"!</li>
        </ol>
        
        <h3>Map Configuration</h3>
        <p><b>Important:</b> Map image must be square (width = height)</p>
        <ul>
            <li>Common sizes: 2048x2048, 4096x4096</li>
            <li>World size must match your zone coordinate ranges</li>
            <li>Settings persist between sessions</li>
        </ul>
        
        <h3>Daily Workflow</h3>
        <ol>
            <li>Launch app → Dialog opens with saved paths and map config</li>
            <li>Click "Load Files"</li>
            <li>Start editing!</li>
        </ol>
        """)
        tabs.addTab(getting_started, "Getting Started")
        
        # Working with Zones tab
        working_with_zones = QTextBrowser()
        working_with_zones.setHtml("""
        <h2>Working with Zones</h2>
        
        <h3>Selecting Zones</h3>
        <ul>
            <li><b>From list:</b> Click zone in left panel → Highlights on map</li>
            <li><b>From map:</b> Click zone on map → Selects in list</li>
            <li>Both methods highlight in bright blue</li>
        </ul>
        
        <h3>Editing Config & Comment</h3>
        <ol>
            <li>Select a zone</li>
            <li>In Properties panel (right):</li>
            <ul>
                <li><b>Config dropdown:</b> Type number to jump, hover for preview</li>
                <li><b>Comment:</b> Edit description</li>
            </ul>
            <li>Click "Save Changes"</li>
            <li>Categories update automatically!</li>
        </ol>
        
        <h3>Moving/Resizing Zones</h3>
        <ol>
            <li>Select a <b>dynamic zone</b></li>
            <li>Click <b>"Move/Resize Zone"</b> button (toolbar)</li>
            <li>Button changes to "Done Editing"</li>
            <li><b>Blue handles</b> appear at corners</li>
            <li>Drag zone to move, or drag handles to resize</li>
            <li>Click <b>"Done Editing"</b> when finished</li>
            <li>Handles disappear, zone locked</li>
        </ol>
        
        <h3>Adding New Zones</h3>
        <ol>
            <li>Click <b>"Add Dynamic Zone"</b> button</li>
            <li>Click and drag on map to draw rectangle</li>
            <li>Select available zone slot (e.g., Zone049)</li>
            <li>Set config number</li>
            <li>Add comment</li>
            <li>Click OK</li>
            <li>Automatically returns to Select mode</li>
        </ol>
        
        <h3>Deleting Zones</h3>
        <p><b>Important:</b> You don't actually delete zones from the file. Instead, you set their config and coordinates to 0, which makes them "available" for reuse.</p>
        <ol>
            <li>Select the zone you want to remove</li>
            <li>Set Config to <b>0</b></li>
            <li>Click "Save Changes"</li>
            <li>Zone disappears from map</li>
            <li>Zone slot becomes available for "Add Dynamic Zone"</li>
        </ol>
        <p>The zone (e.g., Zone049) still exists in the file, but with config=0 and coordinates=0, it's treated as an empty slot ready to be reassigned.</p>
        """)
        tabs.addTab(working_with_zones, "Working with Zones")
        
        # Tips & Tricks tab
        tips = QTextBrowser()
        tips.setHtml("""
        <h2>Tips & Tricks</h2>
        
        <h3>Danger Color Coding</h3>
        <p><b>If characteristics.xml is loaded:</b> Both dynamic and static zones are color-coded based on average zombie health (danger level).</p>
        <p><b>Relative Danger Levels:</b> Colors are calculated from YOUR zombie health range (not fixed values):</p>
        <ul>
            <li><b>Green:</b> Very Low danger (Bottom 20% of health range) - Weakest zombies</li>
            <li><b>Yellow-Green:</b> Low danger (20-40% of range) - Below average</li>
            <li><b>Yellow:</b> Medium danger (40-60% of range) - Average zombies</li>
            <li><b>Orange:</b> High danger (60-80% of range) - Above average</li>
            <li><b>Red:</b> Very High danger (Top 20% of range) - Strongest zombies</li>
        </ul>
        <p><b>Visual style:</b> Dynamic zones = translucent rectangles. Static zones = solid circles with white borders (always visible on top).</p>
        <p><b>Example:</b> If your zombies range from 50-250 health, green = 50-90, yellow = 130-170, red = 210-250.</p>
        <p><b>Without characteristics.xml:</b> All zones are yellow (default).</p>
        <p><b>Overlapping zones:</b> Lower zone number takes precedence (Zone001 overrides Zone002).</p>
        
        <h3>Navigation</h3>
        <ul>
            <li><b>Zoom:</b> Mouse wheel (in/out)</li>
            <li><b>Zoom limit:</b> Can't zoom out past entire map view</li>
            <li><b>Pan:</b> Middle mouse button + drag</li>
            <li><b>Fit to view:</b> Zoom out until map fills window</li>
        </ul>
        
        <h3>Config Selection</h3>
        <ul>
            <li><b>Quick jump:</b> Click dropdown, type "60" → jumps to config 60</li>
            <li><b>Preview zombies:</b> Hover over config in dropdown</li>
            <li><b>See all zombies:</b> Click "View All Zombies" link in properties</li>
        </ul>
        
        <h3>Filtering</h3>
        <ul>
            <li><b>Filter by Config:</b> Show only zones with specific config number</li>
            <li><b>Filter by Category:</b> Show zones containing a specific category (e.g., Zombie_Type_BigTown_Low)</li>
            <li><b>Filter by Zombie Class:</b> Show zones that spawn a specific zombie (e.g., ZmbM_PatrolNormal_Autumn)</li>
            <li>Only one filter active at a time</li>
            <li>Helps when working with overlapping zones</li>
            <li>Select "None" to show all zones again</li>
        </ul>
        
        <h3>Zone Slots System</h3>
        <ul>
            <li>Zone001-Zone150 always exist in file</li>
            <li>Config = 0 means "available slot"</li>
            <li>Config > 0 means "active zone"</li>
            <li>You're assigning coordinates to slots, not creating new zones</li>
        </ul>
        
        <h3>Saving</h3>
        <ul>
            <li>Changes are only in memory until you save</li>
            <li><b>Ctrl+S</b> or File → Save Changes</li>
            <li>Automatic backup created (.backup extension)</li>
            <li>Only DynamicSpawnZones.c is modified</li>
        </ul>
        
        <h3>Keyboard Shortcuts</h3>
        <ul>
            <li><b>Ctrl+S:</b> Save changes</li>
            <li><b>Ctrl+N:</b> Add dynamic zone</li>
            <li><b>Delete:</b> Delete selected zone</li>
            <li><b>Ctrl++:</b> Zoom in</li>
            <li><b>Ctrl+-:</b> Zoom out</li>
            <li><b>F1:</b> This user guide</li>
        </ul>
        """)
        tabs.addTab(tips, "Tips & Tricks")
        
        # Troubleshooting tab
        troubleshooting = QTextBrowser()
        troubleshooting.setHtml("""
        <h2>Troubleshooting</h2>
        
        <h3>Common Issues</h3>
        
        <h4>Zones not aligned / in wrong positions</h4>
        <ul>
            <li><b>Wrong world size:</b> Verify world size matches your zone files</li>
            <li>Check zone coordinate ranges in DynamicSpawnZones.c</li>
            <li>If zones go up to 16384, world size should be 16384</li>
            <li>If zones go up to 15360, world size should be 15360</li>
            <li><b>Solution:</b> Reload with correct map preset or Custom world size</li>
        </ul>
        
        <h4>Map image won't load</h4>
        <ul>
            <li><b>Image not square:</b> Width must equal height</li>
            <li>Use square images: 2048x2048, 4096x4096, etc.</li>
            <li>Supported formats: PNG (recommended), JPG</li>
            <li><b>Solution:</b> Re-export map as square image</li>
        </ul>
        
        <h4>Categories not showing</h4>
        <ul>
            <li>Make sure you loaded both:</li>
            <ul>
                <li>ZombiesChooseCategories.c</li>
                <li>ZombiesCategories.c</li>
            </ul>
            <li>Check if config number exists in ZombiesChooseCategories.c</li>
        </ul>
        
        <h4>Can't click small zones</h4>
        <ul>
            <li>Small zones are rendered on top of large ones</li>
            <li>Try zooming in for better precision</li>
            <li>Use filter to hide other zones</li>
        </ul>
        
        <h4>"No available zone slots"</h4>
        <ul>
            <li>All 150 zone slots are assigned (config > 0)</li>
            <li>Set an existing zone's config to 0 to free it up</li>
        </ul>
        
        <h4>Changes not saving</h4>
        <ul>
            <li>Check file permissions on DynamicSpawnZones.c</li>
            <li>Make sure file isn't open in another program</li>
            <li>Check debug log for errors (see below)</li>
        </ul>
        
        <h3>Debug Log</h3>
        <p>If you encounter errors, check the debug log file:</p>
        <p><b>Windows:</b> <code>%LOCALAPPDATA%\\PvZmoD_Zone_Editor\\pvzmod_editor_debug.log</code></p>
        <p><b>Typical path:</b> <code>C:\\Users\\YourName\\AppData\\Local\\PvZmoD_Zone_Editor\\pvzmod_editor_debug.log</code></p>
        <ol>
            <li>Open the log file location shown above</li>
            <li>Look at the bottom of the file for recent errors</li>
            <li>Log shows what operation failed and why</li>
        </ol>
        
        <h3>Settings File</h3>
        <p><b>pvzmod_editor_settings.json</b> saves your file paths and map config.</p>
        <ul>
            <li>To reset: Delete the file</li>
            <li>To change paths: Browse in file dialog</li>
            <li>Auto-saved after successful load</li>
        </ul>
        
        <h3>File Backups</h3>
        <ul>
            <li>Every save creates .backup file</li>
            <li>Example: DynamicSpawnZones.c.backup</li>
            <li>To restore: Rename .backup file, remove extension</li>
        </ul>
        """)
        tabs.addTab(troubleshooting, "Troubleshooting")
        
        layout.addWidget(tabs)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(guide.accept)
        layout.addWidget(close_btn)
        
        guide.setLayout(layout)
        guide.exec_()


def main():
    """Main entry point"""
    try:
        logger.info("Starting PvZmoD Zone Editor")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Qt version: {QApplication.instance()}")
        
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        # Global exception handler
        def exception_hook(exctype, value, tb):
            logger.error("Uncaught exception!")
            logger.error(''.join(traceback.format_exception(exctype, value, tb)))
            QMessageBox.critical(
                None, "Fatal Error",
                f"An unexpected error occurred:\n\n{value}\n\nSee log file for details:\n{LOG_FILE}"
            )
            sys.__excepthook__(exctype, value, tb)
        
        sys.excepthook = exception_hook
        
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully")
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        logger.error(traceback.format_exc())
        print(f"\n\nFATAL ERROR: {e}")
        print(f"\nCheck log file for details:\n{LOG_FILE}")
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == '__main__':
    main()
