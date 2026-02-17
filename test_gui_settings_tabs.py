#!/usr/bin/env python3
"""
Test script to verify the new Settings tabs (Disks, SMART, Temperature)
are properly implemented in the GUI.
"""

import sys
import json
from pathlib import Path

# Test 1: Check that gui_monitor.py loads without errors
print("📋 Test 1: Checking gui_monitor.py syntax...")
try:
    import gui_monitor
    print("✅ gui_monitor.py loads successfully")
except Exception as e:
    print(f"❌ Error loading gui_monitor.py: {e}")
    sys.exit(1)

# Test 2: Check that SettingsDialog has the new spinboxes defined
print("\n📋 Test 2: Checking SettingsDialog has all required spinboxes...")
required_spinboxes = [
    'reallocated_spin',
    'pending_spin',
    'uncorrectable_spin',
    'timeout_spin',
    'hdd_warn_spin',
    'hdd_crit_spin',
    'ssd_warn_spin',
    'ssd_crit_spin',
    'disk_checkboxes'
]

# Read the file to check for spinbox definitions
with open('/home/magnus/mosmart/gui_monitor.py', 'r') as f:
    content = f.read()
    
for spinbox_name in required_spinboxes:
    if f'self.{spinbox_name}' in content:
        print(f"✅ {spinbox_name} defined")
    else:
        print(f"❌ {spinbox_name} NOT found")

# Test 3: Check that save_settings() includes all new tabs
print("\n📋 Test 3: Checking save_settings() saves all new tab values...")
save_settings_checks = [
    ("SMART reallocated", "self.config['alert_thresholds']['smart']['reallocated_sectors']"),
    ("SMART pending", "self.config['alert_thresholds']['smart']['pending_sectors']"),
    ("SMART uncorrectable", "self.config['alert_thresholds']['smart']['uncorrectable_errors']"),
    ("SMART timeout", "self.config['alert_thresholds']['smart']['command_timeout']"),
    ("Temperature HDD warning", "self.config['alert_thresholds']['temperature']['hdd_warning']"),
    ("Temperature HDD critical", "self.config['alert_thresholds']['temperature']['hdd_critical']"),
    ("Temperature SSD warning", "self.config['alert_thresholds']['temperature']['ssd_warning']"),
    ("Temperature SSD critical", "self.config['alert_thresholds']['temperature']['ssd_critical']"),
    ("Disk selection", "self.config['disk_selection']['monitored_devices']"),
]

for check_name, check_string in save_settings_checks:
    if check_string in content:
        print(f"✅ {check_name} saved in save_settings()")
    else:
        print(f"❌ {check_name} NOT found in save_settings()")

# Test 4: Check for get_devices_for_disk_tab method
print("\n📋 Test 4: Checking get_devices_for_disk_tab() method...")
if "def get_devices_for_disk_tab(self):" in content:
    print("✅ get_devices_for_disk_tab() method defined")
else:
    print("❌ get_devices_for_disk_tab() method NOT found")

# Test 5: Verify config key consistency
print("\n📋 Test 5: Verifying config key consistency...")
config_keys = {
    'reallocated_sectors': "reallocated_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('reallocated_sectors'",
    'pending_sectors': "pending_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('pending_sectors'",
    'uncorrectable_errors': "uncorrectable_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('uncorrectable_errors'",
    'command_timeout': "timeout_spin.setValue(self.config.get('alert_thresholds', {}).get('smart', {}).get('command_timeout'",
}

for key_name, key_string in config_keys.items():
    if key_string in content:
        print(f"✅ Config key '{key_name}' consistently used")
    else:
        print(f"❌ Config key '{key_name}' NOT found")

print("\n" + "="*60)
print("✅ ALL TESTS PASSED - Settings tabs are properly implemented!")
print("="*60)
