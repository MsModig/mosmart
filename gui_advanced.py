#!/usr/bin/env python3
"""
MoSMART Desktop GUI Advanced Features

Extended GUI with charts, detailed views, and full feature parity with Web UI.
"""

import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QListWidget, QListWidgetItem, QSplitter, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QCalendarWidget
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont
from gui_monitor import Theme, APIClient


# ===== DETAIL VIEW DIALOG =====
class DeviceDetailDialog(QDialog):
    """Detailed view for a single device"""
    
    def __init__(self, device: dict, api: APIClient, parent=None):
        super().__init__(parent)
        self.device = device
        self.api = api
        self.setWindowTitle(f"Device Details - {device['name']}")
        self.setGeometry(100, 100, 1000, 700)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Create splitter for navigation
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - navigation
        left_widget = QTreeWidget()
        left_widget.setHeaderLabels(["Device Information"])
        left_widget.setMinimumWidth(200)
        
        # Add tree items
        root = QTreeWidgetItem(left_widget, [f"📊 {self.device['name']}"])
        
        overview = QTreeWidgetItem(root, ["Overview"])
        health = QTreeWidgetItem(root, ["Health Analysis"])
        attributes = QTreeWidgetItem(root, ["SMART Attributes"])
        history = QTreeWidgetItem(root, ["History"])
        errors = QTreeWidgetItem(root, ["Errors & Warnings"])
        
        left_widget.expandAll()
        left_widget.itemClicked.connect(self.on_item_selected)
        
        splitter.addWidget(left_widget)
        
        # Right panel - content
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        self.content_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_COLOR};
                padding: 16px;
            }}
        """)
        splitter.addWidget(self.content_area)
        
        splitter.setSizes([250, 750])
        layout.addWidget(splitter)
        
        # Load overview by default
        self.show_overview()
    
    def on_item_selected(self, item, column):
        """Handle item selection"""
        text = item.text(0)
        
        if "Overview" in text:
            self.show_overview()
        elif "Health Analysis" in text:
            self.show_health()
        elif "SMART Attributes" in text:
            self.show_attributes()
        elif "History" in text:
            self.show_history()
        elif "Errors & Warnings" in text:
            self.show_errors()
    
    def show_overview(self):
        """Show device overview"""
        html = f"""
        <h2>📊 {self.device['name']}</h2>
        
        <h3>Basic Information</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: {Theme.BG_TERTIARY};">
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR}; width: 30%;"><b>Model</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{self.device.get('model', 'Unknown')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Serial</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{self.device.get('serial', 'Unknown')}</td>
            </tr>
            <tr style="background-color: {Theme.BG_TERTIARY};">
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Capacity</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{self.device.get('capacity', 'Unknown')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Interface</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{self.device.get('interface', 'Unknown')}</td>
            </tr>
            <tr style="background-color: {Theme.BG_TERTIARY};">
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Type</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{'SSD' if self.device.get('is_ssd') else 'HDD'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Status</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">
                    {'✅ Online' if self.device.get('responsive') else '⚠️ Offline'}
                </td>
            </tr>
        </table>
        
        <h3>Usage Statistics</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: {Theme.BG_TERTIARY};">
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Power On Hours</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{self.device.get('power_on_formatted', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Temperature</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">
                    {self.device.get('temperature', 'N/A')}°C
                </td>
            </tr>
            <tr style="background-color: {Theme.BG_TERTIARY};">
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};"><b>Power Cycles</b></td>
                <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">
                    {self.device.get('power_cycle_count', 'N/A')}
                </td>
            </tr>
        </table>
        """
        self.content_area.setHtml(html)
    
    def show_health(self):
        """Show health analysis"""
        score = self.device.get('health_score', 0)
        state = self.device.get('health_state', 'unknown')
        
        if score >= 95:
            assessment = "EXCELLENT - Disk is in perfect condition"
            color = Theme.HEALTH_EXCELLENT
        elif score >= 80:
            assessment = "GOOD - Disk is working properly"
            color = Theme.HEALTH_GOOD
        elif score >= 60:
            assessment = "ACCEPTABLE - Monitor for changes"
            color = Theme.HEALTH_ACCEPTABLE
        elif score >= 40:
            assessment = "WARNING - Plan for replacement soon"
            color = Theme.HEALTH_WARNING
        elif score >= 20:
            assessment = "POOR - Replacement recommended"
            color = Theme.HEALTH_POOR
        else:
            assessment = "CRITICAL - Immediate action required"
            color = Theme.HEALTH_CRITICAL
        
        html = f"""
        <h2>🦉 Health Analysis</h2>
        
        <div style="background-color: {Theme.BG_TERTIARY}; padding: 16px; border-radius: 8px; border-left: 4px solid {color};">
            <h3 style="color: {color}; margin-top: 0;">Health Score: {score}/100</h3>
            <p style="font-size: 16px; margin: 8px 0;"><b>{assessment}</b></p>
        </div>
        
        <h3>Component Scores</h3>
        """
        
        components = self.device.get('components', {})
        for component, data in components.items():
            if data:
                value = data.get('value', 0)
                comp_score = data.get('score', 0)
                html += f"""
                <div style="background-color: {Theme.BG_SECONDARY}; padding: 12px; margin: 8px 0; border-radius: 4px;">
                    <strong>{component.upper()}</strong><br>
                    Value: {value} | Score: {comp_score}/100
                </div>
                """
        
        self.content_area.setHtml(html)
    
    def show_attributes(self):
        """Show SMART attributes"""
        html = f"""
        <h2>🔧 SMART Attributes</h2>
        
        <h3>Critical Attributes</h3>
        """
        
        escalated = self.device.get('escalated_attributes', [])
        if escalated:
            for attr in escalated:
                html += f"""
                <div style="background-color: {Theme.STATUS_CRITICAL}20; padding: 12px; margin: 8px 0; border-left: 4px solid {Theme.STATUS_CRITICAL}; border-radius: 4px;">
                    <strong>{attr['name'].upper()}</strong><br>
                    Value: {attr['value']} | Severity: {attr['severity']}
                </div>
                """
        else:
            html += "<p>No critical attributes detected</p>"
        
        html += "<h3>Past Failures</h3>"
        past_failures = self.device.get('past_failures', [])
        if past_failures:
            for failure in past_failures:
                html += f"""
                <div style="background-color: {Theme.STATUS_WARNING}20; padding: 12px; margin: 8px 0; border-left: 4px solid {Theme.STATUS_WARNING}; border-radius: 4px;">
                    <strong>{failure['name']}</strong><br>
                    When Failed: {failure.get('when_failed', 'Unknown')}<br>
                    Current Value: {failure.get('current_value', 'N/A')} | Threshold: {failure.get('threshold', 'N/A')}
                </div>
                """
        else:
            html += "<p>No past failures detected</p>"
        
        self.content_area.setHtml(html)
    
    def show_history(self):
        """Show historical data"""
        html = f"""
        <h2>📈 Health History</h2>
        
        <p>Fetching historical data...</p>
        """
        
        # Fetch history from API
        history = self.api.get_history(
            self.device.get('model', 'Unknown'),
            self.device.get('serial', 'Unknown'),
            days=30
        )
        
        if history and history.get('history'):
            html = f"""
            <h2>📈 Health History (Last 30 Days)</h2>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background-color: {Theme.BG_TERTIARY};">
                    <th style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR}; text-align: left;">Date</th>
                    <th style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR}; text-align: left;">Health Score</th>
                    <th style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR}; text-align: left;">Temperature</th>
                    <th style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR}; text-align: left;">Assessment</th>
                </tr>
            """
            
            for entry in history['history'][-30:]:  # Last 30 entries
                timestamp = entry.get('timestamp', 'N/A')
                score = entry.get('health_score', 'N/A')
                temp = entry.get('temperature', 'N/A')
                assessment = entry.get('assessment', 'N/A')
                
                html += f"""
                <tr style="background-color: {Theme.BG_SECONDARY};">
                    <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{timestamp}</td>
                    <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{score}</td>
                    <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{temp}°C</td>
                    <td style="padding: 8px; border: 1px solid {Theme.BORDER_COLOR};">{assessment}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html = "<h2>📈 Health History</h2><p>No historical data available</p>"
        
        self.content_area.setHtml(html)
    
    def show_errors(self):
        """Show errors and warnings"""
        html = f"""
        <h2>⚠️ Errors & Warnings</h2>
        """
        
        warnings = self.device.get('escalated_attributes', [])
        
        if warnings:
            html += "<h3>Active Warnings</h3>"
            for warning in warnings:
                severity_color = Theme.STATUS_CRITICAL if warning['severity'] == 'critical' else Theme.STATUS_WARNING
                html += f"""
                <div style="background-color: {severity_color}20; padding: 12px; margin: 8px 0; border-left: 4px solid {severity_color}; border-radius: 4px;">
                    <strong>{warning['name']}</strong><br>
                    Value: {warning['value']} | Severity: {warning['severity'].upper()}
                </div>
                """
        else:
            html += "<p>No active warnings</p>"
        
        past_failures = self.device.get('past_failures', [])
        if past_failures:
            html += "<h3>Past Failures</h3>"
            for failure in past_failures:
                html += f"""
                <div style="background-color: {Theme.STATUS_WARNING}20; padding: 12px; margin: 8px 0; border-left: 4px solid {Theme.STATUS_WARNING}; border-radius: 4px;">
                    <strong>{failure['name']}</strong> - {failure.get('when_failed', 'Unknown')}
                </div>
                """
        
        self.content_area.setHtml(html)


# ===== HISTORY VIEWER DIALOG =====
class HistoryViewerDialog(QDialog):
    """View disk health history"""
    
    def __init__(self, model: str, serial: str, api: APIClient, parent=None):
        super().__init__(parent)
        self.model = model
        self.serial = serial
        self.api = api
        self.setWindowTitle(f"History - {model} {serial}")
        self.setGeometry(100, 100, 900, 600)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Date range selector
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Show last:"))
        
        days_combo = QComboBox()
        days_combo.addItems(["7 days", "30 days", "90 days", "All"])
        days_combo.currentTextChanged.connect(self.on_days_changed)
        controls.addWidget(days_combo)
        
        controls.addStretch()
        
        layout.addLayout(controls)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Health Score", "Temperature", "Reallocated", "Status"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.history_table)
        
        self.load_history(30)
    
    def load_history(self, days: int):
        """Load history data"""
        history = self.api.get_history(self.model, self.serial, days)
        
        if history and history.get('history'):
            entries = history['history']
            self.history_table.setRowCount(len(entries))
            
            for row, entry in enumerate(entries):
                self.history_table.setItem(row, 0, QTableWidgetItem(entry.get('timestamp', 'N/A')))
                self.history_table.setItem(row, 1, QTableWidgetItem(str(entry.get('health_score', 'N/A'))))
                self.history_table.setItem(row, 2, QTableWidgetItem(f"{entry.get('temperature', 'N/A')}°C"))
                
                components = entry.get('components', {})
                reallocated = components.get('reallocated', {}).get('value', 0)
                self.history_table.setItem(row, 3, QTableWidgetItem(str(reallocated)))
                self.history_table.setItem(row, 4, QTableWidgetItem(entry.get('assessment', 'N/A')))
    
    def on_days_changed(self, text: str):
        """Handle days selection change"""
        if "7" in text:
            self.load_history(7)
        elif "30" in text:
            self.load_history(30)
        elif "90" in text:
            self.load_history(90)
        else:
            self.load_history(365)


if __name__ == '__main__':
    # This module is imported by gui_monitor.py
    pass
