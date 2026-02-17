#!/usr/bin/env python3
"""
MoSMART Desktop GUI Monitor

Copyright (C) 2026 Magnus S. Modig

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

Desktop GUI using PyQt5 with same theme and functionality as Web UI.
"""

import sys
import json
import requests
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import config_manager

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QScrollArea, QTabWidget, QDialog,
        QSpinBox, QComboBox, QCheckBox, QMessageBox, QProgressDialog,
        QGridLayout, QFormLayout, QLineEdit, QFileDialog, QTableWidget,
        QTableWidgetItem, QHeaderView, QProgressBar, QSystemTrayIcon,
        QMenu, QAction, QStatusBar, QStyleFactory, QStackedWidget
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize, QDateTime, QPointF, QSettings
    from PyQt5.QtGui import (
        QFont, QIcon, QPixmap, QColor, QPalette, QBrush,
        QLinearGradient, QPainter
    )
    from PyQt5.QtChart import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
    PYQT_AVAILABLE = True
except ImportError as e:
    print(f"❌ PyQt5 not installed: {e}")
    print("Install with: pip install PyQt5 PyQtChart requests")
    PYQT_AVAILABLE = False
    sys.exit(1)


# ===== API CONFIG MANAGER (Backend-based configuration) =====
class APIConfigManager:
    """
    Manages configuration through backend API instead of local files.
    GUI never writes directly to filesystem - all changes go through API.
    """
    
    def __init__(self, api_base='http://localhost:5000', timeout=5):
        self.api_base = api_base.rstrip('/')
        self.timeout = timeout
        self.permissions = {}
        self.config = {}
        self.fetch_permissions()
    
    def fetch_permissions(self):
        """Fetch user permissions and role from backend"""
        try:
            resp = requests.get(
                f'{self.api_base}/api/permissions',
                timeout=self.timeout
            )
            if resp.status_code == 200:
                self.permissions = resp.json()
                print(f"✓ Permissions: {self.permissions.get('role', 'unknown')} "
                      f"({self.permissions.get('username', 'unknown')})")
            else:
                print(f"⚠ Failed to fetch permissions: {resp.status_code}")
                self.permissions = {'role': 'read-only', 'username': 'unknown'}
        except Exception as e:
            print(f"⚠ Error fetching permissions: {e}")
            self.permissions = {'role': 'read-only', 'username': 'unknown'}
    
    def load_config(self):
        """Load configuration from backend API"""
        try:
            resp = requests.get(
                f'{self.api_base}/api/config',
                timeout=self.timeout
            )
            if resp.status_code == 200:
                self.config = resp.json()
                return self.config
            else:
                print(f"⚠ Failed to load config: {resp.status_code}")
                return {}
        except Exception as e:
            print(f"⚠ Error loading config from API: {e}")
            return {}
    
    def save_config(self, config):
        """Save configuration to backend API (admin only)"""
        if not self.is_admin():
            raise PermissionError(
                "Admin access required to change settings. "
                "Please run backend with sudo."
            )
        
        try:
            resp = requests.post(
                f'{self.api_base}/api/config',
                json=config,
                timeout=self.timeout
            )
            if resp.status_code == 200:
                self.config = config
                return True
            else:
                error = resp.json().get('error', f'HTTP {resp.status_code}')
                raise Exception(error)
        except Exception as e:
            print(f"⚠ Error saving config: {e}")
            raise
    
    def is_admin(self):
        """Check if current user has admin role"""
        return self.permissions.get('role') == 'admin'
    
    def is_read_only(self):
        """Check if current user is read-only"""
        return self.permissions.get('role') == 'read-only'
    
    def get_username(self):
        """Get current username"""
        return self.permissions.get('username', 'unknown')
    
    def get_role(self):
        """Get current user role"""
        return self.permissions.get('role', 'read-only')


# ===== COLOR THEME (matching Web UI) =====
class Theme:
    """Dark theme matching Web UI"""
    
    # Backgrounds
    BG_PRIMARY = "#0d1117"
    BG_SECONDARY = "#161b22"
    BG_TERTIARY = "#21262d"
    BG_HOVER = "#30363d"
    
    # Text
    TEXT_PRIMARY = "#c9d1d9"
    TEXT_SECONDARY = "#8b949e"
    TEXT_MUTED = "#6e7681"
    
    # Borders
    BORDER_COLOR = "#30363d"
    BORDER_ACTIVE = "#58a6ff"
    
    # Status
    STATUS_OK = "#278cff"
    STATUS_WARNING = "#d29922"
    STATUS_CRITICAL = "#f85149"
    STATUS_INFO = "#9b955c25"
    STATUS_GDC = "#8b949e"
    
    # Health states
    HEALTH_EXCELLENT = "#3498db"  # 95-100
    HEALTH_GOOD = "#2ecc71"       # 80-94
    HEALTH_ACCEPTABLE = "#f1c40f" # 60-79
    HEALTH_WARNING = "#e67e22"    # 40-59
    HEALTH_POOR = "#e74c3c"       # 20-39
    HEALTH_CRITICAL = "#c0392b"   # 0-19
    
    # Accent colors
    BLUE = "#58a6ff"
    ORANGE = "#ff8c42"
    RED = "#f85149"
    YELLOW = "#fbbf24"
    GREEN = "#3fb950"
    PURPLE = "#bc8cff"
    
    @staticmethod
    def get_health_color(score: Optional[int]) -> str:
        """Get color based on health score"""
        if score is None:
            return Theme.TEXT_MUTED
        if score >= 95:
            return Theme.HEALTH_EXCELLENT
        elif score >= 80:
            return Theme.HEALTH_GOOD
        elif score >= 60:
            return Theme.HEALTH_ACCEPTABLE
        elif score >= 40:
            return Theme.HEALTH_WARNING
        elif score >= 20:
            return Theme.HEALTH_POOR
        else:
            return Theme.HEALTH_CRITICAL
    
    @staticmethod
    def get_stylesheet() -> str:
        """Generate PyQt5 stylesheet matching Web UI theme"""
        return f"""
            QMainWindow, QDialog {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
            }}
            
            QWidget {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
            }}
            
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
            }}
            
            QPushButton {{
                background-color: {Theme.STATUS_OK};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            
            QPushButton:hover {{
                background-color: #4a93e5;
            }}
            
            QPushButton:pressed {{
                background-color: #2d6fb5;
            }}
            
            QPushButton#btn-warning {{
                background-color: {Theme.STATUS_WARNING};
            }}
            
            QPushButton#btn-warning:hover {{
                background-color: #e6a91a;
            }}
            
            QPushButton#btn-critical {{
                background-color: {Theme.STATUS_CRITICAL};
            }}
            
            QPushButton#btn-critical:hover {{
                background-color: #f63a2a;
            }}
            
            QScrollArea {{
                background-color: {Theme.BG_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QTabBar::tab {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                padding: 8px 20px;
                border: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QTabBar::tab:selected {{
                background-color: {Theme.BG_TERTIARY};
                border-bottom: 2px solid {Theme.STATUS_OK};
            }}
            
            QTableWidget {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
                gridline-color: {Theme.BORDER_COLOR};
            }}
            
            QTableWidget::item {{
                padding: 4px;
            }}
            
            QTableWidget::item:selected {{
                background-color: {Theme.BG_TERTIARY};
            }}
            
            QHeaderView::section {{
                background-color: {Theme.BG_TERTIARY};
                color: {Theme.TEXT_PRIMARY};
                padding: 4px;
                border: none;
                border-right: 1px solid {Theme.BORDER_COLOR};
                border-bottom: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QLineEdit {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
            }}
            
            QLineEdit:focus {{
                border: 1px solid {Theme.STATUS_OK};
            }}
            
            QComboBox {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px;
            }}
            
            QComboBox:hover {{
                border: 1px solid {Theme.STATUS_OK};
            }}
            
            QSpinBox {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px;
            }}
            
            QCheckBox {{
                color: {Theme.TEXT_PRIMARY};
                spacing: 6px;
            }}
            
            QCheckBox::indicator:unchecked {{
                background-color: {Theme.BG_SECONDARY};
                border: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {Theme.STATUS_OK};
                border: 1px solid {Theme.STATUS_OK};
            }}
            
            QProgressBar {{
                background-color: {Theme.BG_SECONDARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 4px;
                text-align: center;
                color: {Theme.TEXT_PRIMARY};
            }}
            
            QProgressBar::chunk {{
                background-color: {Theme.STATUS_OK};
            }}
            
            QMenuBar {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border-bottom: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QMenuBar::item:selected {{
                background-color: {Theme.BG_TERTIARY};
            }}
            
            QMenu {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
            }}
            
            QMenu::item:selected {{
                background-color: {Theme.BG_TERTIARY};
            }}
            
            QStatusBar {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border-top: 1px solid {Theme.BORDER_COLOR};
            }}
        """


# ===== API COMMUNICATION =====
class APIClient:
    """Handles communication with MoSMART backend"""
    
    def __init__(self, host: str = "localhost", port: int = 5000):
        self.base_url = f"http://{host}:{port}"
        self.timeout = 10
    
    def get_devices(self) -> Optional[List[Dict]]:
        """Get all devices"""
        try:
            response = requests.get(f"{self.base_url}/api/devices", timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return data.get('devices', [])
        except Exception as e:
            print(f"❌ Error fetching devices: {e}")
        return None
    
    def get_device_progressive(self) -> Optional[Dict]:
        """Get progressive scan results"""
        try:
            response = requests.get(f"{self.base_url}/api/devices/progressive", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Error fetching progressive data: {e}")
        return None
    
    def force_scan(self) -> bool:
        """Trigger a force scan"""
        try:
            response = requests.post(f"{self.base_url}/api/force-scan", timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error triggering force scan: {e}")
        return False
    
    def get_history(self, model: str, serial: str, days: int = 30) -> Optional[Dict]:
        """Get disk history"""
        try:
            response = requests.get(
                f"{self.base_url}/api/history/{model}/{serial}",
                params={'days': days},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Error fetching history: {e}")
        return None
    
    def get_alerts(self, hours: int = 24) -> Optional[List[Dict]]:
        """Get recent alerts"""
        try:
            response = requests.get(
                f"{self.base_url}/api/alerts/recent",
                params={'hours': hours},
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('alerts', [])
        except Exception as e:
            print(f"❌ Error fetching alerts: {e}")
        return None
    
    def get_settings(self) -> Optional[Dict]:
        """Get all settings"""
        try:
            response = requests.get(f"{self.base_url}/api/settings", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Error fetching settings: {e}")
        return None

    def get_languages(self) -> Optional[Dict]:
        """Get available languages"""
        try:
            response = requests.get(f"{self.base_url}/api/languages", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Error fetching languages: {e}")
        return None

    def get_language(self, lang_code: str) -> Optional[Dict]:
        """Get translations for a language"""
        try:
            response = requests.get(f"{self.base_url}/api/language/{lang_code}", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Error fetching language {lang_code}: {e}")
        return None
    
    def save_settings(self, settings: Dict) -> bool:
        """Save settings"""
        try:
            response = requests.post(
                f"{self.base_url}/api/settings",
                json=settings,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error saving settings: {e}")
        return False


# ===== BACKGROUND WORKER =====
class RefreshWorker(QThread):
    """Background thread for refreshing disk data"""
    
    data_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api: APIClient, interval: int = 60):
        super().__init__()
        self.api = api
        self.interval = interval
        self.running = True
    
    def run(self):
        """Refresh data periodically"""
        while self.running:
            try:
                data = self.api.get_device_progressive()
                if data:
                    self.data_updated.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))
            
            time.sleep(self.interval)
    
    def stop(self):
        """Stop the worker"""
        self.running = False


# ===== DEVICE CARD WIDGET =====
class DeviceCard(QWidget):
    """Visual representation of a single disk (vertical card matching WebUI)"""
    
    def __init__(self, device_data: Dict, translator, parent=None):
        super().__init__(parent)
        self.device = device_data
        self.t = translator
        self.setMaximumWidth(400)  # Fixed width for vertical cards
        self.setMinimumWidth(350)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI with vertical layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Get health score for border color
        health_score = self.device.get('health_score')
        border_color = Theme.get_health_color(health_score) if health_score is not None else Theme.BORDER_COLOR
        
        # Card container with vertical layout
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_SECONDARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        
        # === HEADER: Mountpoint + status, model, capacity (no border) ===
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        mountpoint = self.device.get('mountpoint') or self.device.get('name')
        health_state = (self.device.get('health_state') or '').lower()
        health_rating = self.device.get('health_rating')
        health_key = None
        rating_map = {
            'utmerket': 'excellent',
            'excellent': 'excellent',
            'god': 'good',
            'good': 'good',
            'akseptabel': 'acceptable',
            'acceptable': 'acceptable',
            'advarsel': 'warning',
            'warning': 'warning',
            'dårlig': 'poor',
            'poor': 'poor',
            'kritisk': 'critical',
            'critical': 'critical',
            'ukjent': 'unknown',
            'unknown': 'unknown'
        }
        
        # Backend always provides health_state - just use it directly
        if health_state:
            health_key = rating_map.get(health_state, health_state)
        else:
            # Fallback if backend doesn't provide health_state (shouldn't happen)
            health_key = 'unknown'

        top_row = QHBoxLayout()
        mount_label = QLabel(f"{mountpoint}")
        mount_label.setFont(QFont("Arial", 14, QFont.Bold))
        mount_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        top_row.addWidget(mount_label)
        top_row.addStretch()

        health_text = self.t(health_key, health_key)
        health_label = QLabel(health_text)
        health_label.setFont(QFont("Arial", 10, QFont.Bold))
        health_label.setStyleSheet(f"color: {border_color};")
        top_row.addWidget(health_label)
        header_layout.addLayout(top_row)

        if self.device.get('model'):
            model = QLabel(self.device['model'])
            model.setFont(QFont("Arial", 10))
            model.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
            model.setWordWrap(True)
            header_layout.addWidget(model)

        if self.device.get('serial'):
            serial = QLabel(self.device['serial'])
            serial.setFont(QFont("Arial", 9))
            serial.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            header_layout.addWidget(serial)

        if self.device.get('capacity'):
            capacity = QLabel(f"{self.device['capacity']}")
            capacity.setFont(QFont("Arial", 9))
            capacity.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            header_layout.addWidget(capacity)

        card_layout.addWidget(header_widget)
        
        # === PAST FAILURES WARNING (before separator) ===
        if self.device.get('past_failures'):
            past_widget = QWidget()
            past_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: {Theme.BG_TERTIARY};
                    border: 1px solid {Theme.STATUS_WARNING};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            past_layout = QVBoxLayout(past_widget)
            past_layout.setSpacing(6)
            
            # Header with warning icon
            header_row = QHBoxLayout()
            header_label = QLabel(f"⚠️ {self.t('past_failures_detected', 'Disk is OK now, but attribute(s) failed in the past')}")
            header_label.setFont(QFont("Arial", 10, QFont.Bold))
            header_label.setStyleSheet(f"color: {Theme.STATUS_WARNING};")
            header_label.setWordWrap(True)
            header_row.addWidget(header_label)
            past_layout.addLayout(header_row)
            
            # List failed attributes
            for failure in self.device['past_failures']:
                failure_row = QHBoxLayout()
                
                # Translate attribute name if it's a translation key
                attr_name = self.t(failure.get('display_name', ''), failure.get('name', ''))
                when_failed = self.t(failure.get('when_failed', ''), failure.get('when_failed', ''))
                
                attr_label = QLabel(f"• {attr_name}")
                attr_label.setFont(QFont("Arial", 9))
                attr_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
                failure_row.addWidget(attr_label)
                failure_row.addStretch()
                
                when_label = QLabel(when_failed)
                when_font = QFont("Arial", 9)
                when_font.setItalic(True)
                when_label.setFont(when_font)
                when_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
                failure_row.addWidget(when_label)
                
                past_layout.addLayout(failure_row)
            
            card_layout.addWidget(past_widget)
        
        # Separator
        separator = QLabel("")
        separator.setStyleSheet(f"border-top: 1px solid {Theme.BORDER_COLOR};")
        separator.setFixedHeight(1)
        card_layout.addWidget(separator)
        
        # === HEALTH SCORE (single bordered widget) ===
        if health_score is not None:
            health_widget = QWidget()
            health_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: {Theme.BG_TERTIARY};
                    border: 1px solid {Theme.BORDER_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            health_layout = QVBoxLayout(health_widget)
            health_layout.setSpacing(8)
            
            health_label = QLabel(f"🦉 {self.t('health_score', 'Helsescore')}")
            health_label.setFont(QFont("Arial", 12, QFont.Bold))
            health_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
            health_label.setAlignment(Qt.AlignCenter)
            health_layout.addWidget(health_label)
            
            # Health progress bar
            health_bar = QProgressBar()
            health_bar.setMinimum(0)
            health_bar.setMaximum(100)
            health_bar.setValue(health_score)
            health_bar.setTextVisible(False)
            health_bar.setFixedHeight(24)
            
            # Color based on health score
            health_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid {Theme.BORDER_COLOR};
                    border-radius: 4px;
                    background-color: {Theme.BG_PRIMARY};
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {border_color};
                    border-radius: 3px;
                }}
            """)
            health_layout.addWidget(health_bar)
            
            # Percentage text below bar
            health_percent = QLabel(f"{health_score}%")
            health_percent.setFont(QFont("Arial", 14, QFont.Bold))
            health_percent.setStyleSheet(f"color: {border_color};")
            health_percent.setAlignment(Qt.AlignCenter)
            health_layout.addWidget(health_percent)
            
            card_layout.addWidget(health_widget)
        
        # === CRITICAL SMART ATTRIBUTES (right after health score) ===
        if self.device.get('escalated_attributes'):
            critical_widget = QWidget()
            critical_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: {Theme.BG_TERTIARY};
                    border: 1px solid {Theme.BORDER_COLOR};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            critical_layout = QVBoxLayout(critical_widget)
            critical_layout.setSpacing(6)
            
            for attr in self.device['escalated_attributes']:
                attr_name = attr.get('name', '')
                attr_value = attr.get('value', '')
                
                # Determine emoji based on attribute name
                if 'reallocated' in attr_name.lower():
                    emoji = "🧱"
                elif 'pending' in attr_name.lower():
                    emoji = "⚠️"
                elif 'uncorrectable' in attr_name.lower():
                    emoji = "❌"
                else:
                    emoji = "⚠️"
                
                attr_row = QHBoxLayout()
                attr_label = QLabel(f"{emoji} {attr_name}")
                attr_label.setFont(QFont("Arial", 10, QFont.Bold))
                attr_label.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
                attr_row.addWidget(attr_label)
                attr_row.addStretch()
                
                attr_value_label = QLabel(str(attr_value))
                attr_value_label.setFont(QFont("Arial", 10, QFont.Bold))
                attr_value_label.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
                attr_row.addWidget(attr_value_label)
                
                critical_layout.addLayout(attr_row)
            
            card_layout.addWidget(critical_widget)
        
        
        # === TEMPERATURE (with sources) ===
        if self.device.get('temperature') is not None:
            temp = self.device['temperature']
            is_ssd = self.device.get('is_ssd', False)
            
            # Determine color based on SSD or HDD thresholds
            if is_ssd:
                if temp >= 75:
                    temp_color = Theme.STATUS_CRITICAL
                elif temp >= 60:
                    temp_color = Theme.STATUS_WARNING
                else:
                    temp_color = Theme.STATUS_OK
            else:
                if temp >= 60:
                    temp_color = Theme.STATUS_CRITICAL
                elif temp >= 50:
                    temp_color = Theme.STATUS_WARNING
                else:
                    temp_color = Theme.STATUS_OK
            
            temp_widget = QWidget()
            temp_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: {Theme.BG_TERTIARY};
                    border: 1px solid {Theme.BORDER_COLOR};
                    border-radius: 6px;
                    padding: 12px;
                }}
            """)
            temp_layout = QVBoxLayout(temp_widget)
            temp_layout.setSpacing(6)
            
            # Current temperature (label left, value right)
            temp_header = QHBoxLayout()
            temp_label = QLabel(f"🌡 {self.t('temperature', 'Temperature')}")
            temp_label.setFont(QFont("Arial", 12, QFont.Bold))
            temp_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
            temp_header.addWidget(temp_label)
            temp_header.addStretch()
            
            temp_value = QLabel(f"{temp}°C")
            temp_value.setFont(QFont("Arial", 16, QFont.Bold))
            temp_value.setStyleSheet(f"color: {temp_color};")
            temp_header.addWidget(temp_value)
            temp_layout.addLayout(temp_header)
            
            # Temperature sources (small, muted)
            if self.device.get('mosmart194') is not None:
                mosmart194_label = QLabel(f"mosmart194, {self.t('max', 'max')}: {self.device['mosmart194']}°C")
                mosmart194_label.setFont(QFont("Arial", 8))
                mosmart194_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
                temp_layout.addWidget(mosmart194_label)
            
            if self.device.get('max_temperature') is not None:
                smart194_label = QLabel(f"SMART ID 194, {self.t('max', 'max')}: {self.device['max_temperature']}°C")
                smart194_label.setFont(QFont("Arial", 8))
                smart194_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
                temp_layout.addWidget(smart194_label)
            
            card_layout.addWidget(temp_widget)
        
        # === POWER ON HOURS (single bordered widget) ===
        if self.device.get('power_on_formatted'):
            poh_widget = QWidget()
            poh_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: {Theme.BG_TERTIARY};
                    border: 1px solid {Theme.BORDER_COLOR};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            poh_layout = QHBoxLayout(poh_widget)
            poh_layout.setContentsMargins(0, 0, 0, 0)
            poh_label = QLabel(f"⏱ {self.t('power_on_hours', 'Power On Hours')}")
            poh_label.setFont(QFont("Arial", 10, QFont.Bold))
            poh_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
            poh_layout.addWidget(poh_label)
            poh_layout.addStretch()
            poh_value = QLabel(self.device['power_on_formatted'])
            poh_value.setFont(QFont("Arial", 10))
            poh_value.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
            poh_layout.addWidget(poh_value)
            card_layout.addWidget(poh_widget)

        # === SSD/HDD USAGE PANEL ===
        if self.device.get('is_ssd'):
            if self.device.get('total_bytes_written') is not None:
                ssd_widget = QWidget()
                ssd_widget.setStyleSheet(f"""
                    QWidget {{
                        background-color: {Theme.BG_TERTIARY};
                        border: 1px solid {Theme.BORDER_COLOR};
                        border-radius: 6px;
                        padding: 10px;
                    }}
                """)
                ssd_layout = QVBoxLayout(ssd_widget)
                ssd_layout.setSpacing(4)
                
                # Title and value on same line (like Power On Hours)
                ssd_header = QHBoxLayout()
                ssd_title = QLabel(f"💾 {self.t('total_bytes_written', 'Skrevet data')}")
                ssd_title.setFont(QFont("Arial", 10, QFont.Bold))
                ssd_title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
                ssd_header.addWidget(ssd_title)
                ssd_header.addStretch()
                
                ssd_value = QLabel(self.format_bytes(self.device['total_bytes_written']))
                ssd_value.setFont(QFont("Arial", 10))
                ssd_value.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
                ssd_header.addWidget(ssd_value)
                ssd_layout.addLayout(ssd_header)
                
                lifetime_remaining = self.device.get('lifetime_remaining')
                if lifetime_remaining is not None:
                    if lifetime_remaining > 10:
                        warn_color = Theme.STATUS_WARNING if lifetime_remaining < 20 else Theme.TEXT_SECONDARY
                        lifetime_label = QLabel(f"⚠️ {self.t('lifetime_remaining', 'Gjenstående bruk')}: {lifetime_remaining}%")
                        lifetime_label.setFont(QFont("Arial", 9, QFont.Bold))
                        lifetime_label.setStyleSheet(f"color: {warn_color};")
                        ssd_layout.addWidget(lifetime_label)
                    else:
                        lifetime_label = QLabel(f"⚠️ {self.t('lifetime_remaining', 'Gjenstående bruk')}: {lifetime_remaining}%")
                        lifetime_label.setFont(QFont("Arial", 9, QFont.Bold))
                        lifetime_label.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
                        ssd_layout.addWidget(lifetime_label)
                        near_end = QLabel(self.t('lifetime_remaining_near_end', 'Nær endt levetid'))
                        near_end.setFont(QFont("Arial", 8))
                        near_end.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
                        ssd_layout.addWidget(near_end)
                        if lifetime_remaining <= 5:
                            replace_soon = QLabel(self.t('lifetime_remaining_replace_soon', 'Bytt snart'))
                            replace_soon.setFont(QFont("Arial", 8))
                            replace_soon.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
                            ssd_layout.addWidget(replace_soon)
                
                card_layout.addWidget(ssd_widget)
        else:
            if self.device.get('power_cycle_count') is not None:
                hdd_widget = QWidget()
                hdd_widget.setStyleSheet(f"""
                    QWidget {{
                        background-color: {Theme.BG_TERTIARY};
                        border: 1px solid {Theme.BORDER_COLOR};
                        border-radius: 6px;
                        padding: 10px;
                    }}
                """)
                hdd_layout = QVBoxLayout(hdd_widget)
                hdd_layout.setSpacing(4)
                
                hdd_title = QLabel(f"🔄 {self.t('power_on_cycles', 'Power Cycles')}")
                hdd_title.setFont(QFont("Arial", 10, QFont.Bold))
                hdd_title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
                hdd_layout.addWidget(hdd_title)
                
                hdd_value = QLabel(f"{self.device['power_cycle_count']}")
                hdd_value.setFont(QFont("Arial", 14, QFont.Bold))
                hdd_value.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
                hdd_layout.addWidget(hdd_value)
                
                card_layout.addWidget(hdd_widget)
        
        card_layout.addStretch()
        layout.addWidget(card)

    def format_bytes(self, bytes_value: Optional[int]) -> str:
        """Format bytes to human readable string"""
        if bytes_value is None or bytes_value == 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        value = float(bytes_value)
        unit_index = 0
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024.0
            unit_index += 1
        return f"{value:.1f} {units[unit_index]}"
    
    def update_device(self, device_data: Dict):
        """Update device data"""
        self.device = device_data
        # Clear layout and recreate
        for i in reversed(range(self.layout().count())):
            self.layout().itemAt(i).widget().setParent(None)
        self.init_ui()


# ===== SETTINGS DIALOG =====
class SettingsDialog(QDialog):
    """Settings dialog with grid-based tab navigation"""
    
    def __init__(self, parent, t_func):
        super().__init__(parent)
        self.t = t_func
        
        # Use API config manager instead of local file access
        self.api_config = APIConfigManager()
        self.config = self.api_config.load_config()
        self.current_tab = 0
        self.settings = QSettings("MoSMART", "SettingsDialog")
        self.init_ui()
        self.restore_geometry()
    
    def init_ui(self):
        self.setWindowTitle(self.t('settings', 'Settings'))
        self.setMinimumSize(850, 700)
        
        layout = QVBoxLayout(self)
        
        # Tab navigation grid (3x2 layout)
        nav_layout = QGridLayout()
        nav_layout.setSpacing(10)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        
        # Define tabs with emoji, label, and index
        self.tabs_info = [
            (0, "⬜", self.t('general_settings', 'General')),
            (1, "🟦", self.t('health_alerts', 'Health')),
            (2, "🟥", self.t('security_settings', 'Security')),
            (3, "🟫", self.t('disk_selection', 'Disks')),
            (4, "🟨", self.t('smart_alerts', 'SMART')),
            (5, "🟩", self.t('temp_alerts', 'Temperature')),
            (6, "⬛", self.t('gdc_settings', 'GDC')),
            (7, "🟧", self.t('logging_settings', 'Logging')),
            (8, "🟪", self.t('notification_channels', 'Notifications')),
        ]
        
        self.tab_buttons = {}
        for idx, emoji, label in self.tabs_info:
            row = idx // 3
            col = idx % 3
            
            btn = QPushButton(f"{emoji}\n{label}")
            btn.setMinimumHeight(47)
            btn.setFont(QFont("Arial", 11, QFont.Bold))
            btn.clicked.connect(lambda checked=False, i=idx: self.show_tab(i))
            
            self.tab_buttons[idx] = btn
            nav_layout.addWidget(btn, row, col)
        
        # Stacked widget for tab content
        self.stacked_widget = QStackedWidget()
        
        # Create tab widgets
        tabs = {}
        
        # General tab (index 0)
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(['en', 'no'])
        current_lang = self.config.get('general', {}).get('language', 'en')
        self.language_combo.setCurrentText(current_lang)
        general_layout.addRow(self.t('language', 'Language:'), self.language_combo)
        
        self.polling_spin = QSpinBox()
        self.polling_spin.setRange(10, 300)
        self.polling_spin.setValue(self.config.get('general', {}).get('polling_interval', 60))
        self.polling_spin.setSuffix(" " + self.t('seconds', 'seconds'))
        general_layout.addRow(self.t('refresh_interval', 'Refresh interval:'), self.polling_spin)
        
        tabs[0] = general_tab
        self.stacked_widget.addWidget(general_tab)
        
        # Health tab (index 1)
        health_tab = QWidget()
        health_layout = QFormLayout(health_tab)
        
        self.score_drop_spin = QSpinBox()
        self.score_drop_spin.setRange(1, 50)
        self.score_drop_spin.setValue(self.config.get('alert_thresholds', {}).get('health', {}).get('score_drop', 3))
        health_layout.addRow(self.t('score_drop_threshold', 'Score drop threshold:'), self.score_drop_spin)
        
        self.critical_score_spin = QSpinBox()
        self.critical_score_spin.setRange(0, 100)
        self.critical_score_spin.setValue(self.config.get('alert_thresholds', {}).get('health', {}).get('critical_score', 40))
        health_layout.addRow(self.t('critical_score_limit', 'Critical score limit:'), self.critical_score_spin)
        
        tabs[1] = health_tab
        self.stacked_widget.addWidget(health_tab)
        
        # Security tab (index 2)
        security_tab = QWidget()
        security_layout = QVBoxLayout(security_tab)
        
        security_title = QLabel(f"🛡️ {self.t('security_settings', 'Security Settings')}")
        security_title.setFont(QFont("Arial", 12, QFont.Bold))
        security_layout.addWidget(security_title)
        
        # Emergency unmount section
        unmount_section = QWidget()
        unmount_section.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_TERTIARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 6px;
                padding: 15px;
            }}
        """)
        unmount_layout = QVBoxLayout(unmount_section)
        
        unmount_title = QLabel(self.t('emergency_unmount_title', 'Emergency Unmount'))
        unmount_title.setFont(QFont("Arial", 11, QFont.Bold))
        unmount_layout.addWidget(unmount_title)
        
        warning_label = QLabel(f"⚠️ {self.t('emergency_unmount_warning', 'This can automatically remove critically failing disks from the system. Only use if you understand the consequences.')}")
        warning_label.setWordWrap(True)
        warning_label.setMinimumHeight(60)
        warning_label.setStyleSheet(f"color: {Theme.STATUS_WARNING}; padding: 10px; background-color: rgba(255, 193, 7, 0.1); border-radius: 4px;")
        unmount_layout.addWidget(warning_label)
        
        self.emergency_unmount_check = QCheckBox(self.t('enable_emergency_unmount', 'Enable Emergency Unmount (ACTIVE mode)'))
        current_mode = self.config.get('emergency_unmount', {}).get('mode', 'PASSIVE')
        self.emergency_unmount_check.setChecked(current_mode == 'ACTIVE')
        self.emergency_unmount_check.setFont(QFont("Arial", 10, QFont.Bold))
        unmount_layout.addWidget(self.emergency_unmount_check)
        
        unmount_desc = QLabel(self.t('emergency_unmount_description', 'When enabled, the system will automatically unmount disks that reach EMERGENCY status.'))
        unmount_desc.setWordWrap(True)
        unmount_desc.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt;")
        unmount_layout.addWidget(unmount_desc)
        
        # Status indicator
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 10, 0, 10)
        status_label = QLabel(f"{self.t('current_status', 'Status:')}")
        status_label.setFont(QFont("Arial", 10, QFont.Bold))
        status_layout.addWidget(status_label)
        
        self.status_badge = QLabel("PASSIVE")
        self.status_badge.setMinimumHeight(30)
        self.update_status_badge()
        status_layout.addWidget(self.status_badge)
        status_layout.addStretch()
        unmount_layout.addWidget(status_widget)
        
        # Protection info
        protection_label = QLabel(f"<b>{self.t('protection_guarantees', 'Protection:')}</b>")
        protection_label.setMinimumHeight(25)
        unmount_layout.addWidget(protection_label)
        
        protection_list = QLabel(
            f"✅ {self.t('protection_1', 'Never unmount critical paths: /, /boot, /home, /usr, /var')}<br>"
            f"✅ {self.t('protection_2', '30 minute cooldown between attempts per disk')}<br>"
            f"✅ {self.t('protection_3', 'Only when status = EMERGENCY and can emergency unmount = true')}<br>"
            f"✅ {self.t('protection_4', 'Full logging before/during/after unmount')}<br>"
            f"✅ {self.t('protection_5', 'Default to PASSIVE on config error')}"
        )
        protection_list.setWordWrap(True)
        protection_list.setMinimumHeight(100)
        protection_list.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 9pt; padding: 5px;")
        unmount_layout.addWidget(protection_list)
        
        # Test button
        test_btn = QPushButton(f"🧪 {self.t('test_emergency_unmount', 'Test Emergency Unmount')}")
        test_btn.clicked.connect(self.test_emergency_unmount)
        test_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.STATUS_WARNING};
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e6a91a;
            }}
        """)
        unmount_layout.addWidget(test_btn)
        
        security_layout.addWidget(unmount_section)
        security_layout.addStretch()
        tabs[2] = security_tab
        self.stacked_widget.addWidget(security_tab)
        
        # Disks tab (index 3)
        disks_tab = QWidget()
        disks_layout = QVBoxLayout(disks_tab)
        
        disks_label = QLabel(self.t('disk_selection', 'Select disks to monitor:'))
        disks_label.setFont(QFont("Arial", 10, QFont.Bold))
        disks_layout.addWidget(disks_label)
        
        # Get list of available disks from API
        devices_response = self.get_devices_for_disk_tab()
        self.disk_checkboxes = {}
        monitored = self.config.get('disk_selection', {}).get('monitored_devices', {})
        
        for device in devices_response:
            device_name = device.get('name', 'Unknown')
            model = device.get('model', 'Unknown')
            is_monitored = monitored.get(device_name, True)
            
            checkbox = QCheckBox(f"{device_name} - {model}")
            checkbox.setChecked(is_monitored)
            self.disk_checkboxes[device_name] = checkbox
            disks_layout.addWidget(checkbox)
        
        disks_layout.addStretch()
        tabs[3] = disks_tab
        self.stacked_widget.addWidget(disks_tab)
        
        # SMART tab (index 4)
        smart_tab = QWidget()
        smart_layout = QFormLayout(smart_tab)
        
        self.reallocated_spin = QSpinBox()
        self.reallocated_spin.setRange(1, 10000)
        self.reallocated_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('reallocated_sectors', 5))
        smart_layout.addRow(self.t('reallocated_threshold', 'Reallocated sectors threshold:'), self.reallocated_spin)
        
        self.pending_spin = QSpinBox()
        self.pending_spin.setRange(1, 1000)
        self.pending_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('pending_sectors', 1))
        smart_layout.addRow(self.t('pending_threshold', 'Pending sectors threshold:'), self.pending_spin)
        
        self.uncorrectable_spin = QSpinBox()
        self.uncorrectable_spin.setRange(1, 100)
        self.uncorrectable_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('uncorrectable_errors', 1))
        smart_layout.addRow(self.t('uncorrectable_threshold', 'Uncorrectable errors threshold:'), self.uncorrectable_spin)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 100)
        self.timeout_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('command_timeout', 5))
        smart_layout.addRow(self.t('timeout_threshold', 'Command timeout threshold:'), self.timeout_spin)
        
        smart_layout.addRow(QLabel(""))  # Spacer
        smart_layout.addRow(QLabel(""))  # Spacer
        tabs[4] = smart_tab
        self.stacked_widget.addWidget(smart_tab)
        
        # Temperature tab (index 5)
        temp_tab = QWidget()
        temp_layout = QFormLayout(temp_tab)
        
        temp_label = QLabel(self.t('temperature_thresholds', 'Temperature thresholds:'))
        temp_label.setFont(QFont("Arial", 10, QFont.Bold))
        temp_layout.addRow(temp_label)
        
        self.hdd_warn_spin = QSpinBox()
        self.hdd_warn_spin.setRange(30, 100)
        self.hdd_warn_spin.setValue(self.config.get('alert_thresholds', {}).get('temperature', {}).get('hdd_warning', 50))
        self.hdd_warn_spin.setSuffix("°C")
        temp_layout.addRow(self.t('hdd_warning', 'HDD Warning:'), self.hdd_warn_spin)
        
        self.hdd_crit_spin = QSpinBox()
        self.hdd_crit_spin.setRange(30, 100)
        self.hdd_crit_spin.setValue(self.config.get('alert_thresholds', {}).get('temperature', {}).get('hdd_critical', 60))
        self.hdd_crit_spin.setSuffix("°C")
        temp_layout.addRow(self.t('hdd_critical', 'HDD Critical:'), self.hdd_crit_spin)
        
        self.ssd_warn_spin = QSpinBox()
        self.ssd_warn_spin.setRange(30, 100)
        self.ssd_warn_spin.setValue(self.config.get('alert_thresholds', {}).get('temperature', {}).get('ssd_warning', 60))
        self.ssd_warn_spin.setSuffix("°C")
        temp_layout.addRow(self.t('ssd_warning', 'SSD Warning:'), self.ssd_warn_spin)
        
        self.ssd_crit_spin = QSpinBox()
        self.ssd_crit_spin.setRange(30, 100)
        self.ssd_crit_spin.setValue(self.config.get('alert_thresholds', {}).get('temperature', {}).get('ssd_critical', 70))
        self.ssd_crit_spin.setSuffix("°C")
        temp_layout.addRow(self.t('ssd_critical', 'SSD Critical:'), self.ssd_crit_spin)
        
        temp_layout.addRow(QLabel(""))  # Spacer
        tabs[5] = temp_tab
        self.stacked_widget.addWidget(temp_tab)
        
        # GDC tab (index 6)
        gdc_tab = QWidget()
        gdc_layout = QFormLayout(gdc_tab)
        
        gdc_title = QLabel(self.t('gdc_settings_title', 'Ghost Drive Condition Settings'))
        gdc_title.setFont(QFont("Arial", 11, QFont.Bold))
        gdc_layout.addRow(gdc_title)
        
        self.gdc_timeout_spin = QSpinBox()
        self.gdc_timeout_spin.setRange(1, 60)
        self.gdc_timeout_spin.setValue(self.config.get('gdc', {}).get('timeout_threshold', 5))
        self.gdc_timeout_spin.setSuffix(" " + self.t('seconds', 'seconds'))
        gdc_layout.addRow(self.t('gdc_timeout', 'Timeout threshold:'), self.gdc_timeout_spin)
        
        self.gdc_max_retries_spin = QSpinBox()
        self.gdc_max_retries_spin.setRange(1, 20)
        self.gdc_max_retries_spin.setValue(self.config.get('gdc', {}).get('max_retries', 3))
        gdc_layout.addRow(self.t('gdc_max_retries', 'Max retries:'), self.gdc_max_retries_spin)
        
        self.gdc_persist_check = QCheckBox(self.t('gdc_persist_state', 'Persist GDC state across restarts'))
        self.gdc_persist_check.setChecked(self.config.get('gdc', {}).get('persist_state', True))
        gdc_layout.addRow(self.gdc_persist_check)
        
        gdc_layout.addRow(QLabel(""))  # Spacer
        tabs[6] = gdc_tab
        self.stacked_widget.addWidget(gdc_tab)
        
        # Logging tab (index 7)
        logging_tab = QWidget()
        logging_layout = QFormLayout(logging_tab)
        
        logging_title = QLabel(self.t('logging_settings_title', 'Logging Settings'))
        logging_title.setFont(QFont("Arial", 11, QFont.Bold))
        logging_layout.addRow(logging_title)
        
        # Log retention size (KB)
        self.log_retention_spin = QSpinBox()
        self.log_retention_spin.setRange(100, 10240)
        self.log_retention_spin.setValue(self.config.get('logging', {}).get('retention_size_kb', 1024))
        self.log_retention_spin.setSuffix(" KB")
        logging_layout.addRow(self.t('retention_size', 'Log retention (KB):'), self.log_retention_spin)
        
        # Rolling logs checkbox
        self.rolling_logs_check = QCheckBox(self.t('rolling_logs', 'Rolling logs'))
        self.rolling_logs_check.setChecked(self.config.get('logging', {}).get('rolling_logs', True))
        logging_layout.addRow(self.rolling_logs_check)
        
        # Verbosity combo
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(['debug', 'info', 'warning', 'error'])
        current_verbosity = self.config.get('logging', {}).get('verbosity', 'info')
        self.verbosity_combo.setCurrentText(current_verbosity)
        logging_layout.addRow(self.t('verbosity', 'Verbosity:'), self.verbosity_combo)
        
        logging_layout.addRow(QLabel(""))  # Spacer
        tabs[7] = logging_tab
        self.stacked_widget.addWidget(logging_tab)
        
        # Notifications tab (index 8)
        notifications_tab = QWidget()
        notifications_layout = QVBoxLayout(notifications_tab)
        
        notif_title = QLabel(f"📧 {self.t('email_notifications', 'Email Notifications')}")
        notif_title.setFont(QFont("Arial", 12, QFont.Bold))
        notifications_layout.addWidget(notif_title)
        
        # Email section
        email_section = QWidget()
        email_section.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_TERTIARY};
                border: 1px solid {Theme.BORDER_COLOR};
                border-radius: 6px;
                padding: 15px;
            }}
        """)
        email_layout = QFormLayout(email_section)
        
        # Get email config from alert_channels.email
        email_cfg = self.config.get('alert_channels', {}).get('email', {})
        
        self.email_enabled_check = QCheckBox(self.t('enable_email_alerts', 'Enable email alerts'))
        self.email_enabled_check.setChecked(email_cfg.get('enabled', False))
        self.email_enabled_check.setFont(QFont("Arial", 10, QFont.Bold))
        email_layout.addRow(self.email_enabled_check)
        
        self.smtp_server_input = QLineEdit()
        self.smtp_server_input.setText(email_cfg.get('smtp_server', ''))
        self.smtp_server_input.setPlaceholderText('smtp.example.com')
        email_layout.addRow(self.t('smtp_server', 'SMTP Server:'), self.smtp_server_input)
        
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(email_cfg.get('smtp_port', 587))
        email_layout.addRow(self.t('smtp_port', 'SMTP Port:'), self.smtp_port_spin)
        
        self.smtp_tls_check = QCheckBox(self.t('use_tls', 'Use TLS/STARTTLS'))
        self.smtp_tls_check.setChecked(email_cfg.get('use_tls', True))
        email_layout.addRow(self.smtp_tls_check)
        
        self.smtp_user_input = QLineEdit()
        self.smtp_user_input.setText(email_cfg.get('smtp_username', ''))
        self.smtp_user_input.setPlaceholderText('user@example.com')
        email_layout.addRow(self.t('smtp_username', 'Username:'), self.smtp_user_input)
        
        self.smtp_pass_input = QLineEdit()
        self.smtp_pass_input.setEchoMode(QLineEdit.Password)
        # Never populate password field - user must enter new one to change
        # self.smtp_pass_input.setText(email_cfg.get('smtp_password', ''))
        self.smtp_pass_input.setPlaceholderText('(leave blank to keep existing)')
        email_layout.addRow(self.t('smtp_password', 'Password:'), self.smtp_pass_input)
        
        self.email_from_input = QLineEdit()
        self.email_from_input.setText(email_cfg.get('from_email', ''))
        self.email_from_input.setPlaceholderText('alerts@example.com')
        email_layout.addRow(self.t('from_address', 'From address:'), self.email_from_input)
        
        self.email_to_input = QLineEdit()
        to_emails = email_cfg.get('to_emails', [])
        self.email_to_input.setText(', '.join(to_emails) if isinstance(to_emails, list) else str(to_emails))
        self.email_to_input.setPlaceholderText('admin@example.com, user@example.com')
        email_layout.addRow(self.t('to_addresses', 'To addresses:'), self.email_to_input)
        
        # Test email button
        test_email_btn = QPushButton(f"📧 {self.t('test_email', 'Send Test Email')}")
        test_email_btn.clicked.connect(self.test_email_settings)
        test_email_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.STATUS_OK};
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #27ae60;
            }}
        """)
        email_layout.addRow(test_email_btn)
        
        notifications_layout.addWidget(email_section)
        notifications_layout.addStretch()
        tabs[8] = notifications_tab
        self.stacked_widget.addWidget(notifications_tab)
        
        # Connect signal
        self.emergency_unmount_check.stateChanged.connect(self.update_status_badge)
        
        # Add navigation grid and stacked widget to main layout
        layout.addLayout(nav_layout, 0)
        layout.addWidget(self.stacked_widget, 1)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Show role/permission info
        role_label = QLabel()
        if self.api_config.is_admin():
            role_label.setText(f"👤 {self.api_config.get_username()} (ADMIN)")
            role_label.setStyleSheet(f"color: {Theme.STATUS_OK}; font-weight: bold;")
        else:
            role_label.setText(f"👤 {self.api_config.get_username()} (read-only)")
            role_label.setStyleSheet(f"color: {Theme.STATUS_WARNING}; font-weight: bold;")
        button_layout.addWidget(role_label)
        button_layout.addStretch()
        
        save_btn = QPushButton(self.t('save_all', 'Save All Settings'))
        save_btn.clicked.connect(self.save_settings)
        
        # Disable save button if not admin
        if not self.api_config.is_admin():
            save_btn.setEnabled(False)
            save_btn.setToolTip('Admin access required. Please run backend with sudo.')
        
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.STATUS_OK};
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover:!disabled {{
                background-color: #27ae60;
            }}
            QPushButton:disabled {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_MUTED};
            }}
        """)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton(self.t('cancel', 'Cancel'))
        cancel_btn.clicked.connect(self.on_cancel)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_TERTIARY};
            }}
        """)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Disable all input controls if user is not admin
        if not self.api_config.is_admin():
            self._disable_readonly_controls()
        
        # Show first tab by default
        self.show_tab(0)
    
    def _disable_readonly_controls(self):
        """Disable all input controls for read-only users"""
        # General tab
        if hasattr(self, 'language_combo'):
            self.language_combo.setEnabled(False)
        if hasattr(self, 'polling_spin'):
            self.polling_spin.setEnabled(False)
        
        # Health tab
        if hasattr(self, 'score_drop_spin'):
            self.score_drop_spin.setEnabled(False)
        if hasattr(self, 'critical_score_spin'):
            self.critical_score_spin.setEnabled(False)
        
        # Security tab (Emergency unmount)
        if hasattr(self, 'emergency_unmount_check'):
            self.emergency_unmount_check.setEnabled(False)
        
        # Disks tab - disable all disk checkboxes
        if hasattr(self, 'disk_checkboxes'):
            for checkbox in self.disk_checkboxes.values():
                checkbox.setEnabled(False)
        
        # SMART tab - all thresholds
        if hasattr(self, 'reallocated_spin'):
            self.reallocated_spin.setEnabled(False)
        if hasattr(self, 'pending_spin'):
            self.pending_spin.setEnabled(False)
        if hasattr(self, 'uncorrectable_spin'):
            self.uncorrectable_spin.setEnabled(False)
        if hasattr(self, 'timeout_spin'):
            self.timeout_spin.setEnabled(False)
        
        # Temperature tab - all spinboxes
        if hasattr(self, 'temp_hdd_spin'):
            self.temp_hdd_spin.setEnabled(False)
        if hasattr(self, 'temp_hdd_crit_spin'):
            self.temp_hdd_crit_spin.setEnabled(False)
        if hasattr(self, 'temp_ssd_spin'):
            self.temp_ssd_spin.setEnabled(False)
        if hasattr(self, 'temp_ssd_crit_spin'):
            self.temp_ssd_crit_spin.setEnabled(False)
        
        # GDC tab
        if hasattr(self, 'gdc_timeout_spin'):
            self.gdc_timeout_spin.setEnabled(False)
        if hasattr(self, 'gdc_max_retries_spin'):
            self.gdc_max_retries_spin.setEnabled(False)
        if hasattr(self, 'gdc_persist_check'):
            self.gdc_persist_check.setEnabled(False)
        
        # Logging tab
        if hasattr(self, 'log_retention_spin'):
            self.log_retention_spin.setEnabled(False)
        if hasattr(self, 'rolling_logs_check'):
            self.rolling_logs_check.setEnabled(False)
        if hasattr(self, 'verbosity_combo'):
            self.verbosity_combo.setEnabled(False)
        
        # Notifications tab
        if hasattr(self, 'email_enabled_check'):
            self.email_enabled_check.setEnabled(False)
        if hasattr(self, 'smtp_server_input'):
            self.smtp_server_input.setEnabled(False)
        if hasattr(self, 'smtp_port_spin'):
            self.smtp_port_spin.setEnabled(False)
        if hasattr(self, 'smtp_tls_check'):
            self.smtp_tls_check.setEnabled(False)
        if hasattr(self, 'smtp_user_input'):
            self.smtp_user_input.setEnabled(False)
        if hasattr(self, 'smtp_pass_input'):
            self.smtp_pass_input.setEnabled(False)
        if hasattr(self, 'email_from_input'):
            self.email_from_input.setEnabled(False)
        if hasattr(self, 'email_to_input'):
            self.email_to_input.setEnabled(False)
    
    def update_status_badge(self):
        """Update the status badge based on checkbox state"""
        is_active = self.emergency_unmount_check.isChecked()
        
        if is_active:
            self.status_badge.setText("ACTIVE")
            self.status_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {Theme.STATUS_CRITICAL};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
            """)
        else:
            self.status_badge.setText("PASSIVE (safe - logging only)")
            self.status_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {Theme.STATUS_OK};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
            """)
    
    def show_tab(self, tab_index):
        """Switch to the specified tab"""
        self.current_tab = tab_index
        self.stacked_widget.setCurrentIndex(tab_index)
        
        # Update button styles - highlight current tab
        for idx, btn in self.tab_buttons.items():
            if idx == tab_index:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Theme.STATUS_OK};
                        color: white;
                        padding: 8px;
                        border-radius: 4px;
                        font-weight: bold;
                        border: 2px solid {Theme.TEXT_PRIMARY};
                    }}
                    QPushButton:hover {{
                        background-color: #27ae60;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Theme.BG_SECONDARY};
                        color: {Theme.TEXT_PRIMARY};
                        padding: 8px;
                        border-radius: 4px;
                        border: 1px solid {Theme.BORDER_COLOR};
                    }}
                    QPushButton:hover {{
                        background-color: {Theme.BG_TERTIARY};
                    }}
                """)
    
    def get_devices_for_disk_tab(self):
        """Get list of devices from API"""
        try:
            response = requests.get('http://localhost:5000/api/devices', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('devices', [])
        except Exception as e:
            print(f"Error getting devices: {e}")
        return []
    
    def save_settings(self):
        """Save all settings to backend API"""
        # Check if user has admin permissions
        if not self.api_config.is_admin():
            QMessageBox.warning(
                self,
                self.t('permission_denied', 'Permission Denied'),
                self.t('admin_required', 
                       'Admin access required to change settings.\n\n'
                       'Please run the backend with sudo:\n'
                       'sudo /path/to/mosmart-venv/bin/python3 web_monitor.py')
            )
            return
        
        # Update config dictionary
        if 'general' not in self.config:
            self.config['general'] = {}
        self.config['general']['language'] = self.language_combo.currentText()
        self.config['general']['polling_interval'] = self.polling_spin.value()
        
        if 'disk_selection' not in self.config:
            self.config['disk_selection'] = {}
        if 'monitored_devices' not in self.config['disk_selection']:
            self.config['disk_selection']['monitored_devices'] = {}
        
        # Save disk selection
        for device_name, checkbox in self.disk_checkboxes.items():
            self.config['disk_selection']['monitored_devices'][device_name] = checkbox.isChecked()
        
        if 'alert_thresholds' not in self.config:
            self.config['alert_thresholds'] = {}
        
        # Save SMART thresholds
        if 'smart' not in self.config['alert_thresholds']:
            self.config['alert_thresholds']['smart'] = {}
        self.config['alert_thresholds']['smart']['reallocated_sectors'] = self.reallocated_spin.value()
        self.config['alert_thresholds']['smart']['pending_sectors'] = self.pending_spin.value()
        self.config['alert_thresholds']['smart']['uncorrectable_errors'] = self.uncorrectable_spin.value()
        self.config['alert_thresholds']['smart']['command_timeout'] = self.timeout_spin.value()
        
        # Save Temperature thresholds
        if 'temperature' not in self.config['alert_thresholds']:
            self.config['alert_thresholds']['temperature'] = {}
        self.config['alert_thresholds']['temperature']['hdd_warning'] = self.hdd_warn_spin.value()
        self.config['alert_thresholds']['temperature']['hdd_critical'] = self.hdd_crit_spin.value()
        self.config['alert_thresholds']['temperature']['ssd_warning'] = self.ssd_warn_spin.value()
        self.config['alert_thresholds']['temperature']['ssd_critical'] = self.ssd_crit_spin.value()
        
        # Save health thresholds
        if 'health' not in self.config['alert_thresholds']:
            self.config['alert_thresholds']['health'] = {}
        self.config['alert_thresholds']['health']['score_drop'] = self.score_drop_spin.value()
        self.config['alert_thresholds']['health']['critical_score'] = self.critical_score_spin.value()
        
        if 'emergency_unmount' not in self.config:
            self.config['emergency_unmount'] = {}
        self.config['emergency_unmount']['mode'] = 'ACTIVE' if self.emergency_unmount_check.isChecked() else 'PASSIVE'
        self.config['emergency_unmount']['require_confirmation'] = True
        
        # Save GDC settings
        if 'gdc' not in self.config:
            self.config['gdc'] = {}
        self.config['gdc']['timeout_threshold'] = self.gdc_timeout_spin.value()
        self.config['gdc']['max_retries'] = self.gdc_max_retries_spin.value()
        self.config['gdc']['persist_state'] = self.gdc_persist_check.isChecked()
        
        # Save Logging settings
        if 'logging' not in self.config:
            self.config['logging'] = {}
        self.config['logging']['retention_size_kb'] = self.log_retention_spin.value()
        self.config['logging']['rolling_logs'] = self.rolling_logs_check.isChecked()
        self.config['logging']['verbosity'] = self.verbosity_combo.currentText()
        
        # Save Email settings to alert_channels.email
        if 'alert_channels' not in self.config:
            self.config['alert_channels'] = {}
        if 'email' not in self.config['alert_channels']:
            self.config['alert_channels']['email'] = {}
        
        self.config['alert_channels']['email']['enabled'] = self.email_enabled_check.isChecked()
        self.config['alert_channels']['email']['smtp_server'] = self.smtp_server_input.text()
        self.config['alert_channels']['email']['smtp_port'] = self.smtp_port_spin.value()
        self.config['alert_channels']['email']['use_tls'] = self.smtp_tls_check.isChecked()
        self.config['alert_channels']['email']['smtp_username'] = self.smtp_user_input.text()
        
        # Handle password - only update if user entered a new one
        password = self.smtp_pass_input.text()
        if password:
            self.config['alert_channels']['email']['smtp_password'] = password
        # else: preserve existing password (don't overwrite with empty string)
        
        self.config['alert_channels']['email']['from_email'] = self.email_from_input.text()
        # Parse comma-separated email addresses
        to_emails = [addr.strip() for addr in self.email_to_input.text().split(',') if addr.strip()]
        self.config['alert_channels']['email']['to_emails'] = to_emails
        
        # Save to backend API
        try:
            self.api_config.save_config(self.config)
            QMessageBox.information(
                self, 
                self.t('success', 'Success'),
                self.t('settings_saved', 'Settings saved successfully. Some changes may require restart.')
            )
            # Save geometry before closing
            self.settings.setValue("geometry", self.saveGeometry())
            self.accept()
        except PermissionError as e:
            QMessageBox.warning(self, self.t('permission_denied', 'Permission Denied'), str(e))
        except Exception as e:
            QMessageBox.critical(self, self.t('error', 'Error'), f'Failed to save settings: {str(e)}')
    
    def restore_geometry(self):
        """Restore dialog size from last session"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
    
    def on_cancel(self):
        """Handle cancel button - save geometry before closing"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.reject()
    
    def test_email_settings(self):
        """Test email settings by sending a test email"""
        try:
            # Prepare test email data
            test_data = {
                'smtp_server': self.smtp_server_input.text(),
                'smtp_port': self.smtp_port_spin.value(),
                'use_tls': self.smtp_tls_check.isChecked(),
                'smtp_username': self.smtp_user_input.text(),
                'smtp_password': self.smtp_pass_input.text(),
                'from_address': self.email_from_input.text(),
                'to_addresses': [addr.strip() for addr in self.email_to_input.text().split(',') if addr.strip()]
            }
            
            # Send test request to backend
            response = requests.post('http://localhost:5000/api/test-email', json=test_data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                QMessageBox.information(
                    self,
                    self.t('success', 'Success'),
                    f"✅ {self.t('test_email_sent', 'Test email sent successfully!')}\n\n{result.get('message', '')}"
                )
            else:
                error_msg = response.json().get('error', f'HTTP {response.status_code}')
                QMessageBox.warning(
                    self,
                    self.t('error', 'Error'),
                    f"❌ {self.t('test_email_failed', 'Failed to send test email')}:\n{error_msg}"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                self.t('error', 'Error'),
                f"❌ {self.t('test_email_error', 'Error testing email settings')}:\n{str(e)}"
            )
    
    def test_emergency_unmount(self):
        """Test emergency unmount - shows what would be unmounted without actually unmounting"""
        try:
            response = requests.get('http://localhost:5000/api/emergency-unmount/test', timeout=10)
            if response.status_code == 200:
                result = response.json()
                
                # Build message
                msg = f"{self.t('test_emergency_title', 'Emergency Unmount Test Results')}\\n\\n"
                
                if result.get('would_unmount'):
                    msg += f"⚠️ {self.t('would_unmount', 'The following disks would be unmounted:')}\\n\\n"
                    for disk in result['would_unmount']:
                        msg += f"  • {disk.get('device', 'Unknown')} - {disk.get('mountpoint', 'N/A')}\\n"
                        msg += f"    {self.t('reason', 'Reason')}: {disk.get('reason', 'N/A')}\\n\\n"
                else:
                    msg += f"✅ {self.t('no_disks_unmount', 'No disks would be unmounted at this time.')}\\n\\n"
                
                if result.get('protected'):
                    msg += f"\\n🛡️ {self.t('protected_disks', 'Protected disks (never unmounted):')}\\n"
                    for disk in result['protected']:
                        msg += f"  • {disk}\\n"
                
                QMessageBox.information(
                    self,
                    self.t('test_results', 'Test Results'),
                    msg
                )
            else:
                QMessageBox.warning(
                    self,
                    self.t('error', 'Error'),
                    f"{self.t('test_failed', 'Test failed')}: HTTP {response.status_code}"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                self.t('error', 'Error'),
                f"{self.t('test_error', 'Error running test')}: {str(e)}"
            )
    
    def open_documentation(self):
        """Open documentation URL in browser"""
        import webbrowser
        url = "https://modigs-datahjelp.no/artikler/mosmart-en.html"
        
        # Use language-specific URL if Norwegian
        if hasattr(self, 'language') and self.language == 'no':
            url = "https://modigs-datahjelp.no/artikler/mosmart.html"
        
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.t('error', 'Error'),
                f"{self.t('open_browser_failed', 'Failed to open browser')}: {str(e)}"
            )
    
    def closeEvent(self, event):
        """Save dialog size when closing"""
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


# ===== MAIN WINDOW =====
class MoSMARTGUI(QMainWindow):
    """Main desktop GUI window"""
    
    def __init__(self):
        super().__init__()
        self.api = APIClient()
        self.devices = []
        self.device_cards = {}
        self.refresh_worker = None
        self.refresh_interval = 60
        self.translations = {}
        self.language = 'en'
        self.columns = 3
        self.emergency_mode = 'PASSIVE'  # Track emergency unmount mode
        
        self.setWindowTitle("MoSMART Monitor - Desktop GUI")
        self.setWindowIcon(QIcon())
        self.restore_window_geometry()
        
        # Set theme
        QApplication.instance().setStyle(QStyleFactory.create('Fusion'))
        QApplication.instance().setPalette(self.create_palette())
        QApplication.instance().setStyleSheet(Theme.get_stylesheet())
        
        self.load_translations()
        self.init_ui()
        self.init_backend()
        self.refresh_data()
        self.start_auto_refresh()

    def restore_window_geometry(self):
        """Restore window size/position from last session"""
        settings = QSettings("MoSMART", "MoSMARTGUI")
        geometry = settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 1400, 900)

    def t(self, key: str, default: str = "") -> str:
        """Translate key using loaded translations"""
        if key in self.translations:
            return self.translations[key]
        return default or key

    def load_translations(self):
        """Load translations based on backend settings"""
        settings = self.api.get_settings() or {}
        general = settings.get('general', {})
        self.language = general.get('language', 'en') or 'en'

        # Always load English as fallback
        en_data = self.api.get_language('en') or {}
        self.translations = en_data.get('translations', {}) if isinstance(en_data, dict) else {}

        if self.language != 'en':
            lang_data = self.api.get_language(self.language) or {}
            lang_translations = lang_data.get('translations', {}) if isinstance(lang_data, dict) else {}
            # Overlay language-specific translations on top of English
            self.translations.update(lang_translations)

    def apply_translations(self):
        """Apply translations to static UI elements"""
        self.setWindowTitle(self.t('app_title', 'MoSMART Monitor - Desktop GUI'))
        self.title.setText(self.t('app_tagline', 'System Status Overview'))
        self.btn_refresh.setText(f"🔄 {self.t('refresh_now', 'Refresh')}")
        self.btn_force_scan.setText(f"⚡ {self.t('force_scan', 'Force Scan')}")
        self.btn_settings.setText(f"⚙️ {self.t('settings', 'Settings')}")
        self.tabs.setTabText(0, f"📊 {self.t('devices', 'Devices')}")
        self.tabs.setTabText(1, f"⚠️ {self.t('alerts', 'Alerts')}")
        self.tabs.setTabText(2, f"ℹ️ {self.t('about', 'About')}")
        self.statusBar().showMessage(self.t('ready', 'Ready'))

    def create_logo_label(self, filename: str, height: int = 48) -> QLabel:
        """Create a QLabel with a logo pixmap"""
        label = QLabel()
        path = Path(__file__).parent / 'static' / filename
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaledToHeight(height, Qt.SmoothTransformation))
        return label
    
    def create_palette(self) -> QPalette:
        """Create dark palette"""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(Theme.BG_PRIMARY))
        palette.setColor(QPalette.WindowText, QColor(Theme.TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(Theme.BG_SECONDARY))
        palette.setColor(QPalette.AlternateBase, QColor(Theme.BG_TERTIARY))
        palette.setColor(QPalette.ToolTipBase, QColor(Theme.BG_SECONDARY))
        palette.setColor(QPalette.ToolTipText, QColor(Theme.TEXT_PRIMARY))
        palette.setColor(QPalette.Text, QColor(Theme.TEXT_PRIMARY))
        palette.setColor(QPalette.Button, QColor(Theme.BG_SECONDARY))
        palette.setColor(QPalette.ButtonText, QColor(Theme.TEXT_PRIMARY))
        palette.setColor(QPalette.BrightText, QColor(Theme.TEXT_PRIMARY))
        palette.setColor(QPalette.Link, QColor(Theme.BLUE))
        palette.setColor(QPalette.Highlight, QColor(Theme.STATUS_OK))
        palette.setColor(QPalette.HighlightedText, QColor(Theme.BG_PRIMARY))
        return palette
    
    def init_ui(self):
        """Initialize user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()

        header_content = QWidget()
        header_content_layout = QHBoxLayout(header_content)
        header_content_layout.setContentsMargins(0, 0, 0, 0)
        header_content_layout.setSpacing(12)

        left_logo = self.create_logo_label('mosmart-logo.png', height=48)
        right_logo = self.create_logo_label('logo_top.png', height=48)

        self.title = QLabel(self.t('app_tagline', 'System Status Overview'))
        self.title.setFont(QFont("Arial", 16, QFont.Bold))
        self.title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        self.title.setAlignment(Qt.AlignCenter)

        header_content_layout.addWidget(left_logo)
        header_content_layout.addWidget(self.title)
        header_content_layout.addWidget(right_logo)

        header_layout.addWidget(header_content)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Buttons row under header
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.btn_refresh = QPushButton(f"🔄 {self.t('refresh_now', 'Refresh')}")
        self.btn_refresh.clicked.connect(self.refresh_data)
        buttons_layout.addWidget(self.btn_refresh)

        self.btn_force_scan = QPushButton(f"⚡ {self.t('force_scan', 'Force Scan')}")
        self.btn_force_scan.setObjectName("btn-warning")
        self.btn_force_scan.clicked.connect(self.force_scan)
        buttons_layout.addWidget(self.btn_force_scan)

        self.btn_settings = QPushButton(f"⚙️ {self.t('settings', 'Settings')}")
        self.btn_settings.clicked.connect(self.open_settings)
        buttons_layout.addWidget(self.btn_settings)

        buttons_layout.addStretch()
        
        # Emergency unmount status indicator
        self.emergency_status_widget = QWidget()
        emergency_layout = QHBoxLayout(self.emergency_status_widget)
        emergency_layout.setContentsMargins(0, 0, 0, 0)
        emergency_layout.setSpacing(8)
        
        self.emergency_status_dot = QLabel("●")
        self.emergency_status_dot.setFont(QFont("Arial", 12))
        emergency_layout.addWidget(self.emergency_status_dot)
        
        self.emergency_status_label = QLabel()
        self.emergency_status_label.setFont(QFont("Arial", 9, QFont.Bold))
        emergency_layout.addWidget(self.emergency_status_label)
        
        self.update_emergency_status()
        buttons_layout.addWidget(self.emergency_status_widget)
        
        main_layout.addLayout(buttons_layout)
        
        # Tab widget for different views
        self.tabs = QTabWidget()
        
        # Devices tab
        self.devices_tab = QWidget()
        self.init_devices_tab()
        self.tabs.addTab(self.devices_tab, f"📊 {self.t('devices', 'Devices')}")
        
        # Alerts tab
        self.alerts_tab = QWidget()
        self.init_alerts_tab()
        self.tabs.addTab(self.alerts_tab, f"⚠️ {self.t('alerts', 'Alerts')}")
        
        # About tab
        self.about_tab = QWidget()
        self.init_about_tab()
        self.tabs.addTab(self.about_tab, f"ℹ️ {self.t('about', 'About')}")
        
        main_layout.addWidget(self.tabs)
        
        # Status bar
        self.statusBar().showMessage(self.t('ready', 'Ready'))
    
    def init_devices_tab(self):
        """Initialize devices tab with grid layout"""
        layout = QVBoxLayout(self.devices_tab)
        
        # Scroll area for device cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background-color: {Theme.BG_PRIMARY};")
        
        self.devices_container = QWidget()
        # Use grid layout for card arrangement (like WebUI)
        self.devices_layout = QGridLayout(self.devices_container)
        self.devices_layout.setSpacing(16)
        self.devices_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        scroll.setWidget(self.devices_container)
        layout.addWidget(scroll)
    
    def init_alerts_tab(self):
        """Initialize alerts tab"""
        layout = QVBoxLayout(self.alerts_tab)
        
        # Alerts table
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(4)
        self.alerts_table.setHorizontalHeaderLabels([
            self.t('device', 'Device'),
            self.t('message', 'Message'),
            self.t('severity', 'Severity'),
            self.t('time', 'Time')
        ])
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.alerts_table)
        
        # Refresh button
        btn_refresh_alerts = QPushButton(self.t('refresh_alerts', 'Refresh Alerts'))
        btn_refresh_alerts.clicked.connect(self.refresh_alerts)
        layout.addWidget(btn_refresh_alerts)
    
    def init_about_tab(self):
        """Initialize about tab"""
        layout = QVBoxLayout(self.about_tab)
        
        about_text = QLabel("""
        <b>MoSMART Monitor - Desktop GUI</b><br><br>
        A powerful S.M.A.R.T. monitoring software<br><br>
        <b>Version:</b> 0.9.3 (Desktop)<br>
        <b>Backend:</b> Web API on port 5000<br><br>
        <b>Copyright (C) 2026 Magnus S. Modig</b><br><br>
        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.<br><br>
        <b>Features:</b><br>
        • Real-time disk monitoring<br>
        • S.M.A.R.T. attribute tracking<br>
        • Health score calculation<br>
        • Temperature monitoring<br>
        • Ghost Drive Condition detection<br>
        • Emergency unmount capability<br>
        • Multi-language support<br><br>
        <b>Made by:</b> <a href="mailto:kontakt@modigs-datahjelp.no">Modigs Datahjelp</a>
        """)
        about_text.setWordWrap(True)
        layout.addWidget(about_text)
        
        # Documentation button
        docs_btn = QPushButton(f"📖 {self.t('view_documentation', 'View Documentation')}")
        docs_btn.clicked.connect(self.open_documentation)
        docs_btn.setFixedWidth(250)
        docs_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.STATUS_OK};
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: #27ae60;
            }}
        """)
        layout.addWidget(docs_btn)
        layout.addStretch()
    
    def init_backend(self):
        """Initialize background refresh worker"""
        self.refresh_worker = RefreshWorker(self.api, self.refresh_interval)
        self.refresh_worker.data_updated.connect(self.on_data_updated)
        self.refresh_worker.error_occurred.connect(self.on_error)
        self.refresh_worker.start()
    
    def refresh_data(self):
        """Fetch and display devices"""
        devices = self.api.get_devices()
        if devices:
            self.devices = devices
            self.render_devices()
            last_updated = self.t('last_updated', 'Last updated')
            devices_label = self.t('devices', 'devices')
            self.statusBar().showMessage(f"{last_updated}: {datetime.now().strftime('%H:%M:%S')} - {len(devices)} {devices_label}")
    
    def render_devices(self):
        """Render device cards in grid layout (like WebUI)"""
        # Clear existing cards
        while self.devices_layout.count():
            item = self.devices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.device_cards.clear()
        
        # Add device cards to grid (responsive columns)
        container_width = self.devices_container.width() if self.devices_container else self.width()
        card_width = 380
        spacing = self.devices_layout.spacing() if self.devices_layout else 16
        columns = max(1, (container_width + spacing) // (card_width + spacing))
        self.columns = columns
        for idx, device in enumerate(self.devices):
            card = DeviceCard(device, self.t)
            self.device_cards[device['name']] = card
            row = idx // columns
            col = idx % columns
            self.devices_layout.addWidget(card, row, col)
    
    def refresh_alerts(self):
        """Refresh alerts table"""
        alerts = self.api.get_alerts()
        if alerts:
            self.alerts_table.setRowCount(len(alerts))
            for row, alert in enumerate(alerts):
                self.alerts_table.setItem(row, 0, QTableWidgetItem(alert.get('device_name', 'Unknown')))
                self.alerts_table.setItem(row, 1, QTableWidgetItem(alert.get('message', '')))
                self.alerts_table.setItem(row, 2, QTableWidgetItem(alert.get('severity', 'INFO')))
                self.alerts_table.setItem(row, 3, QTableWidgetItem(alert.get('timestamp', '')))
    
    def force_scan(self):
        """Trigger force scan"""
        self.btn_force_scan.setEnabled(False)
        result = self.api.force_scan()
        if result:
            QMessageBox.information(self, self.t('success', 'Success'), self.t('force_scan_started', 'Force scan started!'))
        else:
            QMessageBox.warning(self, self.t('error', 'Error'), self.t('force_scan_failed', 'Failed to start force scan.'))
        self.btn_force_scan.setEnabled(True)
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self, self.t)
        if dialog.exec_() == QDialog.Accepted:
            # Reload translations and emergency status after settings changes
            self.load_translations()
            self.apply_translations()
            self.update_emergency_status()
            self.render_devices()
    
    def open_documentation(self):
        """Open documentation URL in browser"""
        import webbrowser
        url = "https://modigs-datahjelp.no/artikler/mosmart-en.html"
        
        # Use language-specific URL if Norwegian
        if self.language == 'no':
            url = "https://modigs-datahjelp.no/saker/mosmart.html"
        
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.t('error', 'Error'),
                f"{self.t('open_browser_failed', 'Failed to open browser')}: {str(e)}"
            )
    
    def update_emergency_status(self):
        """Update emergency unmount status indicator"""
        settings = self.api.get_settings() or {}
        self.emergency_mode = settings.get('emergency_unmount', {}).get('mode', 'PASSIVE')
        
        if self.emergency_mode == 'ACTIVE':
            self.emergency_status_dot.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
            self.emergency_status_label.setText(self.t('emergency_active', 'Emergency Unmount: ACTIVE'))
            self.emergency_status_label.setStyleSheet(f"color: {Theme.STATUS_CRITICAL};")
        else:
            self.emergency_status_dot.setStyleSheet(f"color: {Theme.STATUS_OK};")
            self.emergency_status_label.setText(self.t('emergency_passive', 'Emergency Unmount: OFF'))
            self.emergency_status_label.setStyleSheet(f"color: {Theme.STATUS_OK};")
    
    def start_auto_refresh(self):
        """Start auto-refresh timer"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(self.refresh_interval * 1000)
    
    def on_data_updated(self, data: dict):
        """Handle data update from worker"""
        devices = data.get('devices', [])
        if devices:
            self.devices = devices
            self.render_devices()
    
    def on_error(self, error: str):
        """Handle error from worker"""
        print(f"⚠️ Backend error: {error}")
        self.statusBar().showMessage(f"Error: {error}")
    
    def closeEvent(self, event):
        """Clean up on close"""
        if self.refresh_worker:
            self.refresh_worker.stop()
        settings = QSettings("MoSMART", "MoSMARTGUI")
        settings.setValue("window_geometry", self.saveGeometry())
        event.accept()

    def resizeEvent(self, event):
        """Reflow grid on resize"""
        super().resizeEvent(event)
        # Re-render only if column count would change
        container_width = self.devices_container.width() if self.devices_container else self.width()
        card_width = 380
        spacing = self.devices_layout.spacing() if self.devices_layout else 16
        new_columns = max(1, (container_width + spacing) // (card_width + spacing))
        if new_columns != self.columns:
            self.render_devices()


# ===== MAIN ENTRY POINT =====
def main():
    """Main entry point"""
    if not PYQT_AVAILABLE:
        print("❌ PyQt5 is required for the GUI. Install with:")
        print("pip install PyQt5 PyQtChart requests")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    window = MoSMARTGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
