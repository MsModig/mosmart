#!/usr/bin/env python3
"""
MoSMART Monitor - Web Dashboard

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

Decision engine is currently running in PASSIVE MODE.
Output is logged only. No actions are taken based on decisions.
"""

import sys
import argparse
import json
import os
import platform
import time
import threading
import subprocess
from typing import Optional
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from smart_monitor import SMARTMonitor, calculate_health_score, format_health_rating, detect_ghost_drive_condition
from pySMART import DeviceList
import disk_logger
from disk_logger import log_disk_health, get_disk_history, get_recent_warnings, log_gdc_event_to_disk, LOG_DIR
from gdc import GDCManager, GDCState
import gdc_logger
from gdc_logger import log_gdc_event, get_worst_gdc_state, has_gdc_history, restore_gdc_state_from_history
from device_lifecycle_logger import DeviceLifecycleLogger
from mosmart188_manager import get_manager as get_mosmart188_manager
from mosmart194_manager import get_manager as get_mosmart194_manager
import alert_engine
from alert_engine import process_disk_alerts, get_disk_alert_status
import email_notifier
from email_notifier import load_email_config, save_email_config, test_email_config
import config_manager
from config_manager import load_config, save_config, get_section, update_section, restore_defaults, export_config

app = Flask(__name__)
CORS(app)

# Load translations
TRANSLATIONS_FILE = Path(__file__).parent / 'translations.json'
with open(TRANSLATIONS_FILE, 'r', encoding='utf-8') as f:
    TRANSLATIONS = json.load(f)

# WebUI enable/disable middleware - check before each request
@app.before_request
def check_webui_enabled():
    """Check if WebUI is enabled before handling request"""
    config_data = load_config()
    if not config_data.get('general', {}).get('enable_webui', True):
        return jsonify({
            'error': 'WebUI is currently disabled',
            'message': 'The web interface has been turned off. Use the GUI or API to re-enable it.'
        }), 503

# Load translations
TRANSLATIONS_FILE = Path(__file__).parent / 'translations.json'
with open(TRANSLATIONS_FILE, 'r', encoding='utf-8') as f:
    TRANSLATIONS = json.load(f)

# Configuration
config = {
    'port': 5000,
    'refresh_interval': 60,  # seconds
    'monitored_devices': {},  # {device_name: True/False}
    'language': 'en',  # default language
    'enable_logging': True,  # enable automatic health logging
    'max_log_size_kb': 1024  # maximum log size per disk in KB
}

# Service start time (for uptime tracking in API)
service_start_time = time.time()

def format_power_on_time_localized(hours: int, language: str) -> str:
    """
    Convert power-on hours to a human-readable, localized format.
    - For < 24 hours: Show decimal hours (e.g., "17.8 hours")
    - For ≥ 24 hours: Show years, months, days, hours breakdown
    """
    if hours is None:
        return 'N/A'

    units_by_lang = {
        'no': {
            'years': 'år',
            'months': 'md',
            'days': 'd',
            'hours': 't',
            'hours_full': 'timer',
            'total_hours': 'timer totalt'
        },
        'en': {
            'years': 'years',
            'months': 'mo',
            'days': 'd',
            'hours': 'h',
            'hours_full': 'hours',
            'total_hours': 'total hours'
        }
    }
    units = units_by_lang.get(language, units_by_lang['en'])

    if hours < 24:
        return f"{hours:.1f} {units['hours_full']}"

    years = hours // 8760  # 365 * 24
    remaining = hours % 8760
    months = remaining // 730  # ~30.4 * 24
    remaining = remaining % 730
    days = remaining // 24
    remaining_hours = remaining % 24

    parts = []
    if years > 0:
        parts.append(f"{years} {units['years']}")
    if months > 0:
        parts.append(f"{months} {units['months']}")
    if days > 0 or (years == 0 and months == 0):
        parts.append(f"{days} {units['days']}")
    if remaining_hours > 0 or len(parts) == 0:
        parts.append(f"{remaining_hours} {units['hours']}")

    return ", ".join(parts) + f" ({hours:,} {units['total_hours']})"

# Cache for warnings to avoid repeated filesystem scans
warnings_cache = {}
warnings_cache_time = {}
WARNINGS_CACHE_DURATION = 300  # 5 minutes in seconds

# Cache for device data to avoid blocking UI on slow scans
device_cache = {}
device_cache_time = {}
DEVICE_CACHE_DURATION = 60  # 1 minute - show cached data while rescanning

# Track retry attempts per device
device_retry_state = {}  # {device_name: {'attempt': 1, 'last_try': timestamp}}

# Track timeout history for GDC detection
timeout_history = {}  # {device_name: [timestamps of timeouts]}

# GDC managers per device
gdc_managers = {}  # {device_name: GDCManager instance}

# Device registry to track which disk is at which device path
# Structure: {device_name: {'model': str, 'serial': str, 'disk_id': str}}
device_registry = {}

# Device lifecycle logger
lifecycle_logger = DeviceLifecycleLogger()

# Track devices seen in previous scan (for disappearance detection)
previous_scan_devices = set()  # Set of device_names from last scan

def _parse_smartctl_json_fallback(device_name):
    """
    Fallback parser for disks that pySMART can't handle (e.g., IDE via USB).
    Directly parses smartctl JSON output.
    
    Returns:
        tuple: (device_info, has_smart_capability)
            device_info: dict with device data or None if parsing failed
            has_smart_capability: True (has SMART), False (no SMART), None (unknown)
    """
    try:
        # First, check if SMART is enabled - if not, enable it
        check_result = subprocess.run(
            ['smartctl', '-i', f'/dev/{device_name}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        has_smart_capability = 'SMART support is: Available' in check_result.stdout
        smart_disabled = has_smart_capability and 'SMART support is: Disabled' in check_result.stdout
        
        if smart_disabled:
            print(f"⚠️ {device_name}: SMART capable but disabled, attempting enable (3 retries)...")
            
            # Retry up to 3 times
            for attempt in range(3):
                enable_result = subprocess.run(
                    ['smartctl', '-s', 'on', f'/dev/{device_name}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # Verify if enabled
                verify_result = subprocess.run(
                    ['smartctl', '-i', f'/dev/{device_name}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if 'SMART support is: Enabled' in verify_result.stdout:
                    print(f"✅ {device_name}: SMART enabled on attempt {attempt + 1}")
                    break
            else:
                # All 3 attempts failed
                print(f"❌ {device_name}: SMART enable failed after 3 attempts")
                return (None, True)  # Has capability but couldn't enable
        
        # Now read SMART data
        result = subprocess.run(
            ['smartctl', '-a', f'/dev/{device_name}', '-j'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        data = json.loads(result.stdout)
        
        # Extract basic info
        device_info = {
            'model': data.get('model_name') or data.get('model_family'),
            'serial': data.get('serial_number'),
            'capacity': f"{data.get('user_capacity', {}).get('bytes', 0) / 1e9:.1f} GB" if data.get('user_capacity') else None,
            'interface': 'USB' if 'USB' in data.get('device', {}).get('info_name', '') else data.get('device', {}).get('protocol'),
            'assessment': 'PASSED' if data.get('smart_status', {}).get('passed') else 'FAILED',
            'temperature': None,
            'power_on_hours': None,
            'power_cycle_count': None,
            'attributes': {}
        }
        
        # Parse SMART attributes
        attrs_table = data.get('ata_smart_attributes', {}).get('table', [])
        for attr in attrs_table:
            attr_id = attr.get('id')
            attr_name = attr.get('name')
            raw_value = attr.get('raw', {}).get('value', 0)
            
            # Temperature (ID 194)
            if attr_id == 194:
                # Try to extract numeric temp from string like "23 (Min/Max 15/58)"
                temp_str = attr.get('raw', {}).get('string', '0')
                try:
                    device_info['temperature'] = int(temp_str.split()[0])
                except (ValueError, IndexError):
                    pass
            
            # Power-on hours (ID 9) - handle both hours and seconds
            elif attr_id == 9:
                # Check if attribute name indicates seconds instead of hours
                if attr_name and 'Second' in attr_name:
                    # Power_On_Seconds - convert to hours
                    # Some disks report in "Xh+Ym+Zs" format, use raw value (total seconds)
                    hours = raw_value // 3600 if raw_value < 4294967295 else 0
                    device_info['power_on_hours'] = hours
                    print(f"🕐 {device_name}: Power_On_Seconds detected: {raw_value} seconds = {hours} hours")
                else:
                    # Power_On_Hours - use directly
                    device_info['power_on_hours'] = raw_value if raw_value < 4294967295 else 0
                    print(f"🕐 {device_name}: Power_On_Hours: {raw_value} hours")
            
            # Power cycles (ID 12)
            elif attr_id == 12:
                device_info['power_cycle_count'] = raw_value
            
            # Store for SMART parsing
            device_info['attributes'][attr_id] = {
                'name': attr_name,
                'value': attr.get('value'),
                'raw': raw_value
            }
        
        print(f"✅ Fallback parser success for {device_name}: {device_info['model']} ({device_info['serial']})")
        return (device_info, has_smart_capability)
        
    except subprocess.TimeoutExpired as e:
        print(f"❌ Fallback parser timeout for {device_name}: {e}")
        # Register timeout event in GDC manager
        if device_name not in gdc_managers:
            initialize_gdc_for_device(device_name, None, None)
        gdc_managers[device_name].event_timeout()
        print(f"⏱️ {device_name}: Registered TIMEOUT with GDC manager (fallback parser)")


def get_system_uptime_seconds() -> Optional[float]:
    """Return system uptime in seconds (float)"""
    try:
        with open('/proc/uptime', 'r') as f:
            return float(f.read().split()[0])
    except Exception:
        return None
        return (None, None)  # Unknown capability
    except Exception as e:
        print(f"❌ Fallback parser failed for {device_name}: {e}")
        return (None, None)  # Unknown capability

def detect_gdc_from_timeout_pattern(device_name):
    """
    Detect GDC based on timeout patterns alone.
    Repeated timeouts on the same device indicate possible GDC.
    """
    if device_name not in timeout_history:
        return None
    
    timeouts = timeout_history[device_name]
    if len(timeouts) < 2:
        return None
    
    # Check if device has timed out multiple times
    if len(timeouts) >= 3:
        return {
            'has_gdc': True,
            'confidence': 'medium',
            'indicators': [
                f'Repeated timeouts: {len(timeouts)} consecutive failures',
                'Disk consistently unresponsive - typical GDC behavior',
                'Likely Seagate with Ghost Drive Condition'
            ]
        }
    elif len(timeouts) >= 2:
        return {
            'has_gdc': True,
            'confidence': 'low',
            'indicators': [
                f'Multiple timeouts detected: {len(timeouts)}',
                'Slow response pattern suggests potential GDC'
            ]
        }
    
    return None

# Shared state for parallel scanning
scan_status = {'in_progress': False, 'start_time': 0}
scan_results = {}  # {device_name: device_data} - stores results as they come in
scan_lock = threading.Lock()  # Thread-safe access to scan_results
scan_results_placeholder_time = {}  # {device_name: timestamp} - track when placeholder was set
PLACEHOLDER_TIMEOUT_SECONDS = 30  # Alert if device in placeholder state >30s

# Track if current scan is a force scan (for logging behavior)
is_force_scan = False

# Background scanner control
background_scanner_running = False
background_scanner_thread = None

# Track connected USB disks for connection/disconnection logging
last_connected_usb_disks = set()

# Track last logged system event to avoid duplicate logs
last_logged_system_event_ts = 0.0


def log_gdc_transition_if_changed(device_name, device_data):
    """
    Check for GDC state transitions and log to both GDC history and disk log.
    Call this AFTER event_*() has been called and _evaluate() has run.
    
    Returns: True if transition logged, False otherwise
    """
    if device_name not in gdc_managers:
        return False
    
    manager = gdc_managers[device_name]
    event_type, message = manager.get_transition_event()
    
    if not event_type:
        return False  # No transition
    
    old_state = manager.previous_state.value
    new_state = manager.state.value
    model = device_data.get('model')
    serial = device_data.get('serial')
    
    # Log to GDC history (existing system)
    log_gdc_event(
        f"/dev/{device_name}",
        'state_change',
        manager.to_json(),
        {'old_state': old_state, 'new_state': new_state, 'event': event_type},
        model=model,
        serial=serial
    )
    
    # Log to disk log (for GUI visibility)
    if model and serial:
        log_gdc_event_to_disk(model, serial, device_name, old_state, new_state)
    
    print(f"📝 GDC transition: {device_name} {old_state} → {new_state} ({event_type})")
    
    # Commit the state change
    manager.commit_state()
    
    return True


def set_scan_result_placeholder(device_name):
    """
    Safely set placeholder for a device in scan_results.
    Thread-safe with timestamp tracking for timeout detection.
    """
    global scan_results, scan_results_placeholder_time
    
    with scan_lock:
        scan_results[device_name] = {
            'name': device_name,
            'responsive': None,
            'model': '⏳ Scanning...',
            'serial': None,
            'capacity': None,
            'interface': None,
            'temperature': None,
            'power_on_hours': None,
            'power_on_formatted': 'N/A',
            'health_score': None,
            'is_ssd': False,
            'components': None,
            'is_monitored': config['monitored_devices'].get(device_name, True),
            'has_warnings': False,
            'latest_warning': None
        }
        scan_results_placeholder_time[device_name] = time.time()


def update_scan_result(device_name, device_data):
    """
    Safely update scan_result with real data (not placeholder).
    Thread-safe with atomic update.
    Ensures placeholder is never restored after real data.
    """
    global scan_results, scan_results_placeholder_time
    
    with scan_lock:
        # Only update if:
        # 1. Device not in results yet, OR
        # 2. Device is in placeholder state (model == "⏳ Scanning...")
        if device_name not in scan_results or scan_results[device_name].get('model') == '⏳ Scanning...':
            scan_results[device_name] = device_data
            # Clear placeholder time since we now have real data
            scan_results_placeholder_time.pop(device_name, None)
        else:
            # Device already has real data, don't overwrite
            # This prevents race conditions where old data overwrites new
            print(f"⚠️  {device_name}: Already has real data, skipping update (collision protection)")


def get_scan_result(device_name):
    """
    Safely get scan_result for a device.
    Thread-safe read.
    """
    global scan_results
    
    with scan_lock:
        return scan_results.get(device_name)


def get_all_scan_results():
    """
    Safely get all scan results as a copy.
    Thread-safe read.
    Returns list of device results.
    """
    global scan_results
    
    with scan_lock:
        return list(scan_results.values())


def check_stuck_devices():
    """
    Check for devices stuck in placeholder state and log warnings.
    Call periodically to detect scanning hangs.
    """
    global scan_results, scan_results_placeholder_time
    
    current_time = time.time()
    stuck_devices = []
    
    with scan_lock:
        for device_name, placeholder_time in list(scan_results_placeholder_time.items()):
            elapsed = current_time - placeholder_time
            if elapsed > PLACEHOLDER_TIMEOUT_SECONDS:
                stuck_devices.append((device_name, elapsed))
    
    # Log stuck devices (outside lock to avoid deadlock)
    for device_name, elapsed in stuck_devices:
        print(f"⚠️  WATCHDOG: {device_name} stuck in placeholder for {elapsed:.0f}s - possible scan hang!")
        
        # Log to system (but don't keep repeating same warning)
        lifecycle_logger.log_stuck_device(device_name, elapsed)


def initialize_gdc_for_device(device_name, model=None, serial=None):
    """
    Initialize GDC manager for device. Load state from history if available.
    MUST be called BEFORE scanning device to restore persistent state.
    
    Args:
        device_name: Device name (e.g., 'sda')
        model: Optional disk model (will try to get from registry if not provided)
        serial: Optional disk serial (will try to get from registry if not provided)
    
    Returns:
        dict with:
            - skip_scan: True if CONFIRMED/TERMINAL GDC (no point scanning)
            - display_status: String for GUI display
            - gdc_state: Current GDC state value
            - manager: GDCManager instance
    """
    global gdc_managers
    
    # Try to get model/serial from registry if not provided
    if not model or not serial:
        if device_name in device_registry:
            reg = device_registry[device_name]
            model = model or reg.get('model')
            serial = serial or reg.get('serial')
    
    # If still no model/serial, try quick identity check NOW (before restore)
    if not model or not serial:
        try:
            print(f"🔍 {device_name}: Quick identity check for GDC restore...")
            from pySMART import Device
            quick_dev = Device(device_name)
            if quick_dev and quick_dev.model and quick_dev.serial:
                model = quick_dev.model
                serial = quick_dev.serial
                print(f"   ✓ Identity: {model} ({serial})")
            else:
                print(f"   ⚠️ Could not get identity via pySMART")
        except Exception as e:
            print(f"   ⚠️ Quick identity check failed: {e}")
    
    # Load historical GDC state from logs
    from gdc_logger import restore_gdc_state_from_history, get_gdc_history
    historical_state = restore_gdc_state_from_history(
        device_path=f"/dev/{device_name}",
        model=model,
        serial=serial
    )
    
    # Create GDC manager
    manager = GDCManager(f"/dev/{device_name}")
    
    # Restore state from history if available
    if historical_state:
        # CRITICAL: Verify disk identity matches history if we have model/serial
        history = get_gdc_history(device_path=f"/dev/{device_name}", model=model, serial=serial, days=7)
        
        if history and model and serial:
            # Check if history is for THIS disk or a different disk at same path
            history_model = history[-1].get('model')
            history_serial = history[-1].get('serial')
            
            if history_model and history_serial:
                if history_model != model or history_serial != serial:
                    # DISK SWAP DETECTED - different disk at same path!
                    print(f"🔄 DISK SWAP on {device_name}:")
                    print(f"   History: {history_model} ({history_serial})")
                    print(f"   Current: {model} ({serial})")
                    print(f"   ❌ NOT restoring GDC state - wrong disk!")
                    historical_state = None  # Don't restore wrong disk's state
        
        if historical_state:
            last_state = None
            if history:
                # Get most recent state
                last_state = history[-1].get('state', 'OK')
            
            # Restore counters and state
            manager.restore_from_history(historical_state, last_state=last_state)
            print(f"🔄 GDC state restored for {device_name}: {manager.state.value} (from history)")
        else:
            print(f"🆕 No GDC history for {device_name}, starting fresh")
    else:
        print(f"🆕 No GDC history for {device_name}, starting fresh")
    
    # Store manager
    gdc_managers[device_name] = manager
    
    # Determine display status and skip behavior
    current_state = manager.state.value
    skip_scan = current_state in ['CONFIRMED', 'TERMINAL']
    
    if current_state == 'TERMINAL':
        display_status = f'☠️ GDC TERMINAL'
    elif current_state == 'CONFIRMED':
        display_status = f'💀 GDC CONFIRMED'
    elif current_state == 'SUSPECT':
        display_status = f'⚠️ GDC SUSPECT'
    else:
        display_status = None  # Normal status
    
    return {
        'skip_scan': skip_scan,
        'display_status': display_status,
        'gdc_state': current_state,
        'manager': manager
    }


def background_scanner():
    """
    Background thread that scans disks periodically for automatic logging.
    Runs independently of GUI - ensures hourly logging and change detection.
    """
    global background_scanner_running, is_force_scan
    
    print("🔄 Background scanner started - will scan every 60 seconds for automatic logging")
    
    while background_scanner_running:
        try:
            # Wait 60 seconds before next scan
            time.sleep(60)
            
            if not background_scanner_running:
                break
            
            # Only scan if not already scanning
            if not scan_status.get('in_progress', False):
                print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Background scan starting...")
                is_force_scan = False  # Ensure automatic logging mode
                scan_all_devices_progressive()
                print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Background scan complete")
            
            # Check for stuck devices (run watchdog every 60s)
            check_stuck_devices()
            
        except Exception as e:
            print(f"❌ Background scanner error: {e}")
            import traceback
            traceback.print_exc()
    
    print("🔄 Background scanner stopped")

def get_system_info():
    """Get system information"""
    return {
        'os': platform.system(),
        'platform': platform.platform(),
        'hostname': platform.node()
    }

def get_disk_info_fallback(device_name):
    """
    Fallback method to get disk information when SMART is not available.
    Uses udisksctl and lsblk to retrieve basic disk information.
    Returns dict with model, serial, capacity, or None if failed.
    """
    try:
        import subprocess
        import json
        
        info = {
            'model': None,
            'serial': None,
            'capacity': None,
            'method': 'fallback'
        }
        
        # Try udisksctl first (most reliable for USB)
        try:
            result = subprocess.run(
                ['udisksctl', 'info', '-b', f'/dev/{device_name}'],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                output = result.stdout
                # Parse udisksctl output
                for line in output.split('\n'):
                    if 'Model:' in line:
                        info['model'] = line.split('Model:')[1].strip()
                    elif 'Serial:' in line:
                        serial = line.split('Serial:')[1].strip()
                        if serial and serial != '':
                            info['serial'] = serial
                    elif 'Size:' in line:
                        # Convert bytes to human readable
                        try:
                            size_bytes = int(line.split('Size:')[1].strip().split()[0])
                            # Convert to GB/TB
                            if size_bytes >= 1e12:
                                info['capacity'] = f"{size_bytes / 1e12:.1f} TB"
                            else:
                                info['capacity'] = f"{size_bytes / 1e9:.1f} GB"
                        except:
                            pass
        except Exception as e:
            print(f"⚠️ udisksctl failed for {device_name}: {e}")
        
        # Fallback to lsblk if udisksctl didn't work
        if not info['model'] or not info['capacity']:
            try:
                result = subprocess.run(
                    ['lsblk', '-J', '-o', 'NAME,MODEL,SERIAL,SIZE', f'/dev/{device_name}'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if data.get('blockdevices') and len(data['blockdevices']) > 0:
                        dev = data['blockdevices'][0]
                        if not info['model'] and dev.get('model'):
                            info['model'] = dev['model'].strip()
                        if not info['serial'] and dev.get('serial'):
                            info['serial'] = dev['serial'].strip()
                        if not info['capacity'] and dev.get('size'):
                            info['capacity'] = dev['size']
            except Exception as e:
                print(f"⚠️ lsblk failed for {device_name}: {e}")
        
        # Return info if we got at least something
        if info['model'] or info['serial'] or info['capacity']:
            print(f"ℹ️ {device_name}: Fallback info retrieved - Model: {info['model']}, Serial: {info['serial']}, Capacity: {info['capacity']}")
            return info
        
        return None
        
    except Exception as e:
        print(f"⚠️ Disk info fallback failed for {device_name}: {e}")
        return None

def get_max_temperature_from_smart(dev):
    """
    Get the maximum temperature from SMART attribute 194's raw value.
    Parses format like "28 (Min/Max 0/62)" to extract max temp (62).
    
    Args:
        dev: pySMART Device object
    
    Returns:
        Maximum temperature (int) or None if not available
    """
    try:
        if not dev or not hasattr(dev, 'attributes') or not dev.attributes:
            return None
        
        # Find temperature attribute (ID 194)
        temp_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 194), None)
        
        if temp_attr and hasattr(temp_attr, 'raw'):
            raw_str = str(temp_attr.raw)
            
            # Parse "28 (Min/Max 0/62)" format
            # Strategy: Split on "/" and take the last part, then remove ")"
            if '/' in raw_str:
                try:
                    # Split on "/" and get last part
                    parts = raw_str.split('/')
                    last_part = parts[-1]  # e.g., "62)"
                    
                    # Remove any closing parenthesis and whitespace
                    max_str = last_part.replace(')', '').strip()
                    
                    # Parse to int
                    max_temp = int(max_str)
                    return max_temp
                except (ValueError, IndexError) as e:
                    # Parsing failed - raw value doesn't have expected format
                    pass
            
            # No Min/Max format - can't determine historical max
            return None
        
        return None
    except Exception as e:
        print(f"Error getting max temperature from SMART: {e}")
        return None

def is_usb_device(device_name):
    """
    Check if a device is connected via USB by checking transport type.
    Returns True for USB devices, False otherwise.
    """
    try:
        import subprocess
        result = subprocess.run(
            ['lsblk', '-n', '-o', 'TRAN', f'/dev/{device_name}'],
            capture_output=True,
            text=True,
            timeout=2
        )
        transport = result.stdout.strip()
        return transport == 'usb'
    except Exception as e:
        print(f"⚠️ Could not detect USB status for {device_name}: {e}")
        return False

def _scan_single_device(device_name):
    """Scan a single device synchronously"""
    global is_force_scan  # Declare at top of function
    print(f"🔧 Scanning {device_name}...")
    
    # mosmart188 manager (global)
    mosmart_mgr = get_mosmart188_manager()
    disk_id = None
    uptime_seconds = get_system_uptime_seconds()
    boot_time = time.time() - uptime_seconds if uptime_seconds is not None else None
    system_event = mosmart_mgr.get_last_system_event()
    system_event_ts = None
    if system_event and system_event.get('type') == 'uncontrolled_shutdown':
        system_event_ts = system_event.get('timestamp')
    
    try:
        from pySMART import Device
        from config_manager import load_config
        
        print(f"🔧 {device_name}: Imports OK")
        
        # Load config
        worker_config = load_config()
        language = worker_config.get('general', {}).get('language', config.get('language', 'en'))
        
        print(f"🔧 {device_name}: Creating Device object...")
        dev = Device(device_name)
        print(f"🔧 {device_name}: Device created, responsive={dev is not None and dev.assessment is not None}")
        
        # Detect if USB device
        is_usb = is_usb_device(device_name)
        if is_usb:
            print(f"🔌 {device_name}: Detected as USB device")
        
        device_data = {
            'name': device_name,
            'responsive': dev is not None and dev.assessment is not None,
            'model': None,
            'serial': None,
            'capacity': None,
            'interface': None,
            'temperature': None,
            'power_on_hours': None,
            'power_on_formatted': 'N/A',
            'total_bytes_written': None,
            'lifetime_remaining': None,
            'health_score': None,
            'health_rating': 'N/A',
            'is_ssd': False,
            'is_usb': is_usb,
            'components': None,
            'is_monitored': worker_config.get('monitored_devices', {}).get(device_name, True),
            'has_warnings': False,
            'latest_warning': None,
            'scan_status': 'success'  # For GDC tracking
        }
        
        # Try fallback parser if pySMART failed to get basic info
        if dev is None or dev.assessment is None or dev.model is None:
            print(f"⚠️ {device_name}: pySMART failed, trying fallback parser... (dev={dev is not None}, assessment={dev.assessment if dev else None}, model={dev.model if dev else None})")
            
            fallback_data, has_smart = _parse_smartctl_json_fallback(device_name)
            
            if fallback_data:
                print(f"✅ {device_name}: Fallback parser succeeded!")
                
                # Get model/serial to create disk_id for tracker
                model = fallback_data['model'] or 'Unknown'
                serial = fallback_data['serial'] or 'Unknown'
                disk_id = f"{model}_{serial}"
                
                # Initialize tracker and register error (pySMART failed)
                smart_tracker = get_smart_read_manager().get_tracker(disk_id, device_name)
                smart_tracker.register_error(reason="pySMART_failed")
                
                # Extract SMART attributes for mechanical failure detection
                power_cycles = fallback_data.get('power_cycle_count')
                id192_value = fallback_data.get('attributes', {}).get(192, {}).get('raw')
                id193_value = fallback_data.get('attributes', {}).get(193, {}).get('raw')
                
                # Check for abnormal SMART attribute changes
                if device_name == 'sdi':
                    print(f"🔍 [FALLBACK] Checking attributes for sdi: power_cycles={power_cycles}, id192={id192_value}, id193={id193_value}")
                smart_tracker.check_smart_attributes(
                    power_cycles=power_cycles,
                    id192=id192_value,
                    id193=id193_value
                )
                get_smart_read_manager().save()
                
                device_data['model'] = model
                device_data['serial'] = serial
                device_data['capacity'] = fallback_data['capacity'] or 'Unknown'
                device_data['interface'] = fallback_data['interface'] or 'Unknown'
                device_data['assessment'] = fallback_data['assessment']
                device_data['temperature'] = fallback_data['temperature']
                device_data['power_on_hours'] = fallback_data['power_on_hours']
                device_data['responsive'] = True
                
                print(f"📊 {device_name}: Applying fallback data - power_on_hours={fallback_data['power_on_hours']}")
                
                if fallback_data['power_on_hours']:
                    device_data['power_on_formatted'] = format_power_on_time_localized(fallback_data['power_on_hours'], language)
                    print(f"📊 {device_name}: Formatted power_on_time: {device_data['power_on_formatted']}")
                else:
                    print(f"⚠️ {device_name}: No power_on_hours in fallback data!")
                
                if fallback_data['power_cycle_count']:
                    device_data['power_cycle_count'] = fallback_data['power_cycle_count']

                # SMART ID 202 - Lifetime Remaining (handle Percent_Used conversion)
                lifetime_attr = fallback_data.get('attributes', {}).get(202)
                if lifetime_attr and lifetime_attr.get('raw') is not None:
                    try:
                        raw_value = int(lifetime_attr.get('raw'))
                        if raw_value >= 4294967295:
                            raw_value = 0

                        attr_name = (lifetime_attr.get('name') or '').lower()
                        if 'percent_used' in attr_name:
                            lifetime_remaining = 100 - raw_value
                        else:
                            lifetime_remaining = raw_value

                        device_data['lifetime_remaining'] = max(0, min(100, lifetime_remaining))
                    except (ValueError, TypeError):
                        pass
                
                # Parse SMART attributes for health calculation
                device_data['fallback_attributes'] = fallback_data['attributes']

                # SMART ID 188 - Command Timeout (fallback)
                timeout_attr = fallback_data.get('attributes', {}).get(188)
                if timeout_attr and timeout_attr.get('raw') is not None and disk_id:
                    try:
                        mosmart_mgr.register_command_timeout(
                            disk_id,
                            int(timeout_attr.get('raw')),
                            uptime_seconds=uptime_seconds,
                            boot_time=boot_time,
                            system_event_ts=system_event_ts
                        )
                    except (ValueError, TypeError):
                        pass
            elif has_smart is True:
                # SMART_CAPABLE_BUT_DISABLED: Has SMART capability but couldn't enable after 3 retries
                print(f"🔴 {device_name}: SMART capable but unavailable after 3 enable attempts - triggering GDC event")
                
                # Initialize GDC manager if needed
                if device_name not in gdc_managers:
                    initialize_gdc_for_device(device_name, device_data.get('model'), device_data.get('serial'))
                
                # Trigger GDC event for SMART unavailable
                gdc_managers[device_name].event_no_smart_support()
                
                # Log the GDC event
                log_gdc_event(
                    device_path=f"/dev/{device_name}",
                    event_type="smart_unavailable",
                    state=gdc_managers[device_name].state.value,
                    counters=gdc_managers[device_name].to_json()['counters'],
                    model=device_data.get('model'),
                    serial=device_data.get('serial')
                )
                log_gdc_transition_if_changed(device_name, device_data)
            elif has_smart is False:
                # NO_SMART_CAPABILITY: Disk doesn't support SMART (e.g., 1990s disk)
                print(f"ℹ️ {device_name}: No SMART capability - this is normal for old disks (pre-2000s)")
                # Do NOT trigger GDC event - this is expected behavior
            # else: has_smart is None → unknown state, ignore
        
        if dev is not None and dev.assessment is not None:
            if device_name == 'sdi':
                print(f"🔍 sdi: dev.assessment={dev.assessment}, entering normal SMART block")
            # Get model/serial to create disk_id
            model = dev.model or 'Unknown'
            serial = dev.serial or 'Unknown'
            disk_id = f"{model}_{serial}"
            
            if device_name == 'sdi':  # Debug for sdi
                print(f"🔍 sdi: Entering SMART processing block, disk_id={disk_id}")
            
            # Get mosmart188 manager
            mosmart_mgr = get_mosmart188_manager()
            
            # Extract critical SMART attributes for mechanical failure detection
            power_cycles = None
            id192_value = None  # Emergency Retract Count
            id193_value = None  # Load Cycle Count
            
            if dev.attributes:
                # Get power cycle count (ID 12)
                power_cycle_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 12), None)
                if power_cycle_attr:
                    try:
                        power_cycles = int(power_cycle_attr.raw)
                    except (ValueError, TypeError):
                        pass
                
                # Get ID 192 (Emergency Retract Count)
                id192_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 192), None)
                if id192_attr:
                    try:
                        id192_value = int(id192_attr.raw)
                    except (ValueError, TypeError):
                        pass
                
                # Get ID 193 (Load Cycle Count)
                id193_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 193), None)
                if id193_attr:
                    try:
                        id193_value = int(id193_attr.raw)
                    except (ValueError, TypeError):
                        pass

                # SMART ID 188 - Command Timeout
                timeout_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 188), None)
                if timeout_attr and timeout_attr.raw:
                    try:
                        mosmart_mgr.register_command_timeout(
                            disk_id,
                            int(str(timeout_attr.raw).split()[0]),
                            uptime_seconds=uptime_seconds,
                            boot_time=boot_time,
                            system_event_ts=system_event_ts
                        )
                    except (ValueError, TypeError):
                        pass
            
            # Register successful SMART read with mosmart188 manager
            # This will detect abnormal jumps in power_cycles and id193
            if device_name == 'sdi':
                print(f"🔍 Registering success for sdi: power_cycles={power_cycles}, id193={id193_value}")
            mosmart_mgr.register_success(disk_id, power_cycles=power_cycles, id193=id193_value)
            
            device_data['model'] = model
            device_data['serial'] = serial
            device_data['capacity'] = dev.capacity or 'Unknown'
            device_data['interface'] = dev.interface or 'Unknown'
            device_data['assessment'] = dev.assessment
            
            # Track current temperature
            current_temp = None
            if hasattr(dev, 'temperature') and dev.temperature is not None:
                device_data['temperature'] = dev.temperature
                current_temp = dev.temperature
            
            # Update mosmart194 (observed max temp)
            mosmart194_mgr = get_mosmart194_manager()
            mosmart194_mgr.update_temperature(disk_id, current_temp)
            device_data['mosmart194'] = mosmart194_mgr.get_max_temp(disk_id)
            
            if dev.attributes:
                power_on_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 9), None)
                if power_on_attr:
                    try:
                        raw_str = str(power_on_attr.raw).strip()
                        # Check if attribute name indicates seconds instead of hours
                        if hasattr(power_on_attr, 'name') and power_on_attr.name and 'Second' in power_on_attr.name:
                            # Power_On_Seconds - handle different formats
                            if 'h+' in raw_str and 'm+' in raw_str and 's' in raw_str:
                                # Format: "0h+17m+48s" - parse the format
                                import re
                                match = re.match(r'(\d+)h\+(\d+)m\+(\d+)s', raw_str)
                                if match:
                                    hours = int(match.group(1))
                                    minutes = int(match.group(2))
                                    seconds = int(match.group(3))
                                    total_seconds = hours * 3600 + minutes * 60 + seconds
                                    hours_calculated = total_seconds // 3600
                                    device_data['power_on_hours'] = hours_calculated
                                    device_data['power_on_formatted'] = format_power_on_time_localized(hours_calculated, language)
                                    print(f"🕐 {device_name}: Power_On_Seconds (pySMART): {raw_str} = {hours_calculated} hours")
                            else:
                                # Plain number - assume it's seconds
                                seconds = int(raw_str.split()[0])
                                hours_calculated = seconds // 3600
                                device_data['power_on_hours'] = hours_calculated
                                device_data['power_on_formatted'] = format_power_on_time_localized(hours_calculated, language)
                                print(f"🕐 {device_name}: Power_On_Seconds (pySMART): {seconds}s = {hours_calculated} hours")
                        else:
                            # Power_On_Hours - use directly
                            hours = int(str(power_on_attr.raw).split()[0])
                            device_data['power_on_hours'] = hours
                            device_data['power_on_formatted'] = format_power_on_time_localized(hours, language)
                            print(f"🕐 {device_name}: Power_On_Hours (pySMART): {hours} hours")
                    except (ValueError, TypeError, AttributeError) as e:
                        print(f"⚠️ {device_name}: Failed to parse power_on_hours: {e}")
                        pass
                
                # If pySMART couldn't get power_on_hours, try fallback parser
                if 'power_on_hours' not in device_data or device_data['power_on_hours'] is None:
                    print(f"⚠️ {device_name}: pySMART couldn't get power_on_hours, trying fallback...")
                    fallback_data, _ = _parse_smartctl_json_fallback(device_name)
                    if fallback_data and fallback_data.get('power_on_hours') is not None:
                        device_data['power_on_hours'] = fallback_data['power_on_hours']
                        device_data['power_on_formatted'] = format_power_on_time_localized(fallback_data['power_on_hours'], language)
                        print(f"✅ {device_name}: Got power_on_hours from fallback: {fallback_data['power_on_hours']} hours")
                
                # Get power cycle count (ID 12)
                power_cycle_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 12), None)
                if power_cycle_attr:
                    try:
                        device_data['power_cycle_count'] = int(power_cycle_attr.raw)
                    except (ValueError, TypeError):
                        pass
                
                # Get total bytes written (for SSDs)
                # Attribute 241: Total LBAs Written (multiply by 512 bytes)
                # Attribute 247: Host Program Page Count (depends on page size, often 4KB or 8KB)
                bytes_written_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num in [241, 247]), None)
                if bytes_written_attr:
                    try:
                        raw_value = int(bytes_written_attr.raw)
                        # Attribute 247 is typically in pages (assume 4KB pages for Crucial SSDs)
                        if bytes_written_attr.num == 247:
                            device_data['total_bytes_written'] = raw_value * 4096  # 4KB per page
                        # Attribute 241 is in LBAs (512 bytes per LBA)
                        elif bytes_written_attr.num == 241:
                            device_data['total_bytes_written'] = raw_value * 512
                    except (ValueError, TypeError):
                        pass

                # SMART ID 202 - Lifetime Remaining (handle Percent_Used conversion)
                lifetime_attr = next((a for a in dev.attributes if a and hasattr(a, 'num') and a.num == 202), None)
                if lifetime_attr and lifetime_attr.raw:
                    try:
                        raw_value = int(str(lifetime_attr.raw).split()[0])
                        if raw_value >= 4294967295:
                            raw_value = 0

                        attr_name = (lifetime_attr.name or '').lower()
                        if 'percent_used' in attr_name:
                            lifetime_remaining = 100 - raw_value
                        else:
                            lifetime_remaining = raw_value

                        device_data['lifetime_remaining'] = max(0, min(100, lifetime_remaining))
                    except (ValueError, TypeError):
                        pass
                
                # Check for attributes that failed in the past
                # Map SMART attribute names to translation keys
                attr_name_map = {
                    'Temperature_Celsius': 'attr_temperature',
                    'Airflow_Temperature_Cel': 'attr_temperature',
                    'Reallocated_Sector_Ct': 'attr_reallocated_sectors',
                    'Reallocate_NAND_Blk_Cnt': 'attr_reallocated_sectors',
                    'Current_Pending_Sector': 'attr_pending_sectors',
                    'Current_Pending_ECC_Cnt': 'attr_pending_sectors',
                    'Offline_Uncorrectable': 'attr_uncorrectable_sectors',
                    'Reported_Uncorrect': 'attr_uncorrectable_sectors',
                    'UDMA_CRC_Error_Count': 'attr_crc_errors',
                    'Command_Timeout': 'attr_command_timeout',
                    'Power_On_Hours': 'attr_power_on_hours',
                    'Power_Cycle_Count': 'attr_power_cycles',
                    'Spin_Retry_Count': 'attr_spin_retry',
                    'End-to-End_Error': 'attr_e2e_error',
                    'Raw_Read_Error_Rate': 'attr_read_error_rate',
                    'Seek_Error_Rate': 'attr_seek_error_rate'
                }
                
                failed_attrs = []
                for attr in dev.attributes:
                    if attr and hasattr(attr, 'when_failed') and attr.when_failed:
                        # Check if when_failed indicates past failure
                        if attr.when_failed not in ['Never', '-', '']:
                            # Use mapped translation key if available, otherwise raw name
                            display_name = attr_name_map.get(attr.name, attr.name)
                            failed_attrs.append({
                                'id': attr.num,
                                'name': attr.name,
                                'display_name': display_name,
                                'when_failed': attr.when_failed,
                                'current_value': attr.value,
                                'threshold': attr.thresh
                            })
                
                if failed_attrs:
                    device_data['past_failures'] = failed_attrs
            
            # Get mosmart188 data for health calculation
            mosmart188_penalty = mosmart_mgr.get_health_penalty(disk_id)
            mosmart188_count = mosmart_mgr.get_restart_count_24h(disk_id)
            
            health_score = calculate_health_score(dev, mosmart188_penalty, mosmart188_count)
            if health_score['total'] is not None:
                device_data['health_score'] = health_score['total']
                device_data['health_rating'] = format_health_rating(health_score['total'])
                device_data['is_ssd'] = health_score.get('is_ssd', False)
                device_data['components'] = health_score['components']
                
                # Detect Ghost Drive Condition
                gdc_info = detect_ghost_drive_condition(dev, health_score['components'])
                device_data['gdc'] = gdc_info
                # === BACKEND AUTHORITY: Escalation & Health State ===
                
                # Derive health state from score (backend decides, frontend displays)
                score = health_score['total']
                if score >= 95:
                    device_data['health_state'] = 'excellent'  # 95-100: Blue
                elif score >= 80:
                    device_data['health_state'] = 'good'       # 80-94: Green
                elif score >= 60:
                    device_data['health_state'] = 'acceptable' # 60-79: Yellow
                elif score >= 40:
                    device_data['health_state'] = 'warning'    # 40-59: Orange
                elif score >= 20:
                    device_data['health_state'] = 'poor'       # 20-39: Red
                elif score >= 0:
                    device_data['health_state'] = 'critical'   # 0-19: Red (darker)
                else:
                    device_data['health_state'] = 'dead'       # <0: Dead/Zombie
                
                # Check for escalated attributes (backend authority - frontend must not infer)
                escalated = []
                components = health_score.get('components', {})
                
                # Reallocated sectors: escalate if > 0
                if components.get('reallocated', {}).get('value', 0) > 0:
                    realloc_val = components['reallocated']['value']
                    escalated.append({
                        'name': 'reallocated_sectors',
                        'value': realloc_val,
                        'severity': 'critical' if realloc_val > 100 else 'warning'
                    })
                
                # Pending sectors: escalate if > 0
                if components.get('pending', {}).get('value', 0) > 0:
                    pending_val = components['pending']['value']
                    escalated.append({
                        'name': 'pending_sectors',
                        'value': pending_val,
                        'severity': 'critical' if pending_val > 50 else 'warning'
                    })
                
                # Uncorrectable errors: escalate if > 0 (always critical - data loss)
                if components.get('uncorrectable', {}).get('value', 0) > 0:
                    escalated.append({
                        'name': 'uncorrectable_errors',
                        'value': components['uncorrectable']['value'],
                        'severity': 'critical'
                    })
                
                device_data['escalated_attributes'] = escalated
            else:
                # No health score - set unknown state
                device_data['health_state'] = 'unknown'
                device_data['escalated_attributes'] = []
            
            # Get maximum temperature from SMART attribute 194 (worst value)
            max_temp = get_max_temperature_from_smart(dev)
            if max_temp is not None:
                device_data['max_temperature'] = max_temp
            
            # Log disk health to history file (even if health_score is None)
            try:
                log_disk_health(dev, force=is_force_scan, is_usb=is_usb, 
                              mosmart188_penalty=mosmart188_penalty, mosmart188_count=mosmart188_count)
            except Exception as log_err:
                print(f"Warning: Could not log health for {device_name}: {log_err}")
        
        # If we have fallback attributes, calculate health from those
        elif device_data.get('fallback_attributes'):
            print(f"📊 {device_name}: Calculating health from fallback attributes...")
            # Create a minimal Device-like object for health calculation
            class FallbackDevice:
                def __init__(self, attrs_dict, assessment, model, serial, temp, capacity):
                    self.model = model
                    self.serial = serial
                    self.assessment = assessment
                    self.temperature = temp
                    self.capacity = capacity
                    self.attributes = []
                    
                    # Create attribute objects
                    for attr_id, attr_data in attrs_dict.items():
                        attr = type('obj', (object,), {
                            'num': attr_id,
                            'name': attr_data['name'],
                            'raw': attr_data['raw']
                        })()
                        self.attributes.append(attr)
            
            fallback_dev = FallbackDevice(
                device_data['fallback_attributes'],
                device_data['assessment'],
                device_data['model'],
                device_data['serial'],
                device_data['temperature'],
                device_data['capacity']
            )
            
            # Get mosmart188 data for health calculation
            mosmart188_penalty = mosmart_mgr.get_health_penalty(disk_id) if disk_id else 0
            mosmart188_count = mosmart_mgr.get_restart_count_24h(disk_id) if disk_id else 0
            
            health_score = calculate_health_score(fallback_dev, mosmart188_penalty, mosmart188_count)
            if health_score['total'] is not None:
                device_data['health_score'] = health_score['total']
                device_data['health_rating'] = format_health_rating(health_score['total'])
                device_data['is_ssd'] = health_score.get('is_ssd', False)
                device_data['components'] = health_score['components']
                print(f"✅ {device_name}: Health score from fallback: {health_score['total']}")
                
                # === BACKEND AUTHORITY: Escalation & Health State (Fallback Path) ===
                
                # Derive health state (matching documentation)
                score = health_score['total']
                if score >= 95:
                    device_data['health_state'] = 'excellent'  # 95-100: Blue
                elif score >= 80:
                    device_data['health_state'] = 'good'       # 80-94: Green
                elif score >= 60:
                    device_data['health_state'] = 'acceptable' # 60-79: Yellow
                elif score >= 40:
                    device_data['health_state'] = 'warning'    # 40-59: Orange
                elif score >= 20:
                    device_data['health_state'] = 'poor'       # 20-39: Red
                elif score >= 0:
                    device_data['health_state'] = 'critical'   # 0-19: Red (darker)
                else:
                    device_data['health_state'] = 'dead'       # <0: Dead/Zombie
                
                # Check for escalated attributes
                escalated = []
                components = health_score.get('components', {})
                
                if components.get('reallocated', {}).get('value', 0) > 0:
                    realloc_val = components['reallocated']['value']
                    escalated.append({
                        'name': 'reallocated_sectors',
                        'value': realloc_val,
                        'severity': 'critical' if realloc_val > 100 else 'warning'
                    })
                
                if components.get('pending', {}).get('value', 0) > 0:
                    pending_val = components['pending']['value']
                    escalated.append({
                        'name': 'pending_sectors',
                        'value': pending_val,
                        'severity': 'critical' if pending_val > 50 else 'warning'
                    })
                
                if components.get('uncorrectable', {}).get('value', 0) > 0:
                    escalated.append({
                        'name': 'uncorrectable_errors',
                        'value': components['uncorrectable']['value'],
                        'severity': 'critical'
                    })
                
                device_data['escalated_attributes'] = escalated
            else:
                device_data['health_state'] = 'unknown'
                device_data['escalated_attributes'] = []
            
            # Log fallback device health
            try:
                # Add name attribute for logging
                fallback_dev.name = device_name
                log_disk_health(fallback_dev, force=is_force_scan, is_usb=is_usb, 
                              mosmart188_penalty=mosmart188_penalty, mosmart188_count=mosmart188_count)
            except Exception as log_err:
                print(f"Warning: Could not log health for fallback device {device_name}: {log_err}")
        
        else:
            # SMART not available - try fallback methods for basic disk info
            print(f"ℹ️ {device_name}: SMART not available, trying fallback methods...")
            fallback_info = get_disk_info_fallback(device_name)
            if fallback_info:
                device_data['model'] = fallback_info.get('model') or 'Unknown'
                device_data['serial'] = fallback_info.get('serial') or 'Unknown'
                device_data['capacity'] = fallback_info.get('capacity') or 'Unknown'
                device_data['smart_unavailable'] = True  # Flag to show warning in UI
                device_data['health_state'] = 'unknown'  # No SMART = unknown state
                device_data['escalated_attributes'] = []  # No SMART = no escalations
                print(f"✅ {device_name}: Basic info retrieved via fallback (SMART unavailable)")
                
                # Log basic info even without SMART data
                if fallback_info.get('model') and fallback_info.get('serial'):
                    try:
                        # Create minimal device object for logging
                        class MinimalDevice:
                            def __init__(self, model, serial, capacity):
                                self.model = model
                                self.serial = serial
                                self.capacity = capacity
                                self.name = device_name
                                self.temperature = None
                                self.assessment = None
                                self.attributes = None
                        
                        minimal_dev = MinimalDevice(
                            fallback_info.get('model'),
                            fallback_info.get('serial'),
                            fallback_info.get('capacity')
                        )
                        # No SMART = no mosmart188 errors (count is 0)
                        log_disk_health(minimal_dev, force=is_force_scan, is_usb=is_usb, mosmart188_count=0)
                        print(f"📝 {device_name}: Logged basic info (no SMART data available)")
                    except Exception as log_err:
                        print(f"Warning: Could not log basic info for {device_name}: {log_err}")
        
        # Add mosmart188 data to response (always, even if disk_id unknown)
        from datetime import datetime
        if disk_id:
            mosmart_summary = mosmart_mgr.get_summary(disk_id)
            device_data['mosmart188'] = {
                'count': mosmart_summary['restarts_24h'],
                'severity': 'critical' if mosmart_summary['restarts_24h'] > 10 else 'warning' if mosmart_summary['restarts_24h'] > 5 else 'ok',
                'should_escalate': mosmart_summary['restarts_24h'] > 5,
                'locked': mosmart_summary['locked'],
                'health_penalty': mosmart_summary['health_penalty'],
                'restarts_60s': mosmart_summary['restarts_60s'],
                'restarts_5m': mosmart_summary['restarts_5m'],
                'restarts_24h': mosmart_summary['restarts_24h'],
            }
            
            # Add to escalated_attributes if > 5 restarts in 24h
            if mosmart_summary['restarts_24h'] > 5 and 'escalated_attributes' in device_data:
                device_data['escalated_attributes'].append({
                    'name': 'mosmart188',
                    'value': mosmart_summary['restarts_24h'],
                    'severity': 'critical' if mosmart_summary['restarts_24h'] > 10 else 'warning',
                    'locked': mosmart_summary['locked']
                })
        else:
            # Unknown disk_id - no mosmart188 data
            device_data['mosmart188'] = {
                'count': 0,
                'severity': 'ok',
                'should_escalate': False,
                'locked': False,
                'health_penalty': 0,
                'restarts_60s': 0,
                'restarts_5m': 0,
                'restarts_24h': 0,
            }
        
        print(f"✅ {device_name}: Scan complete, returning data")
        return device_data
        
    except Exception as e:
        print(f"❌ {device_name}: EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to get disk_id if we don't have it yet (for mosmart188 tracking)
        if disk_id is None:
            # Try quick fallback to get model/serial
            try:
                from pySMART import Device
                quick_dev = Device(device_name)
                if quick_dev and quick_dev.model and quick_dev.serial:
                    disk_id = f"{quick_dev.model}_{quick_dev.serial}"
            except:
                # Ultimate fallback: use device_name as disk_id
                disk_id = f"unknown_{device_name}"
        
        # Register SMART read error with mosmart188 manager
        if disk_id:
            mosmart_mgr.register_restart(disk_id, "SMART read exception", "smart_exception")
        
        # Return error data on exception
        try:
            from config_manager import load_config
            worker_config = load_config()
        except:
            worker_config = {'monitored_devices': {}}
        
        error_data = {
            'name': device_name,
            'responsive': False,
            'model': None,
            'serial': None,
            'capacity': None,
            'interface': None,
            'temperature': None,
            'power_on_hours': None,
            'power_on_formatted': 'N/A',
            'health_score': None,
            'health_rating': 'N/A',
            'is_ssd': False,
            'components': None,
            'is_monitored': worker_config.get('monitored_devices', {}).get(device_name, True),
            'has_warnings': False,
            'latest_warning': None,
            'scan_status': 'error',  # For GDC tracking
            'mosmart188': {
                'count': mosmart_mgr.get_restart_count_24h(disk_id) if disk_id else 0,
                'severity': 'critical' if (disk_id and mosmart_mgr.get_restart_count_24h(disk_id) > 10) else 'warning' if (disk_id and mosmart_mgr.get_restart_count_24h(disk_id) > 5) else 'ok',
                'should_escalate': disk_id and mosmart_mgr.get_restart_count_24h(disk_id) > 5,
                'locked': mosmart_mgr.is_locked(disk_id) if disk_id else False,
                'health_penalty': mosmart_mgr.get_health_penalty(disk_id) if disk_id else 0,
                'restarts_24h': mosmart_mgr.get_restart_count_24h(disk_id) if disk_id else 0,
            }
        }
        print(f"❌ {device_name}: Returning error data")
        return error_data


def scan_all_devices_progressive():
    """Scan all devices in parallel and store results progressively"""
    global scan_results, scan_status, last_connected_usb_disks
    import subprocess
    
    scan_status['in_progress'] = True
    scan_status['start_time'] = time.time()
    scan_results = {}
    
    # Use lsblk to find actual disk devices (exclude USB/removable)
    try:
        result = subprocess.run(
            ['lsblk', '-d', '-n', '-b', '-o', 'NAME,TYPE,SIZE,HOTPLUG,TRAN'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        device_names = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 4:
                    name, dtype, size = parts[0], parts[1], parts[2]
                    # Include all disk types with non-zero size (including USB)
                    if dtype == 'disk' and name.startswith('sd') and int(size) > 0:
                        device_names.append(name)
        
        # Detect USB disk connections/disconnections
        current_usb_disks = set()
        for device_name in device_names:
            if is_usb_device(device_name):
                current_usb_disks.add(device_name)
        
        # Log newly connected USB disks
        newly_connected = current_usb_disks - last_connected_usb_disks
        for device in newly_connected:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"🔌 [{timestamp}] USB disk connected: {device}")
            # Log to disk's individual log file
            if device in device_registry:
                reg = device_registry[device]
                if reg.get('model') and reg.get('serial'):
                    disk_logger.log_usb_event(reg['model'], reg['serial'], device, 'connected')
        
        # Log disconnected USB disks
        disconnected = last_connected_usb_disks - current_usb_disks
        for device in disconnected:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"🔌 [{timestamp}] USB disk disconnected: {device}")
            # Log to disk's individual log file
            if device in device_registry:
                reg = device_registry[device]
                if reg.get('model') and reg.get('serial'):
                    disk_logger.log_usb_event(reg['model'], reg['serial'], device, 'disconnected')
        
        # Update tracking set
        last_connected_usb_disks = current_usb_disks
        
        # Cleanup phantom devices: Remove scan_results and device_registry entries
        # for devices that no longer exist (e.g., disconnected USB disks with GDC state)
        with scan_lock:
            phantom_devices = set(scan_results.keys()) - set(device_names)
            if phantom_devices:
                print(f"🧹 Cleaning up phantom devices: {phantom_devices}")
                for phantom in phantom_devices:
                    del scan_results[phantom]
                    print(f"   ✓ Removed {phantom} from scan_results")
        
        # Also cleanup device_registry for non-existent devices
        phantom_registry = set(device_registry.keys()) - set(device_names)
        if phantom_registry:
            print(f"🧹 Cleaning up phantom registry entries: {phantom_registry}")
            for phantom in phantom_registry:
                del device_registry[phantom]
                print(f"   ✓ Removed {phantom} from device_registry")
        
        print(f"⚡ Progressive scan starting: {device_names}")
    except Exception as e:
        print(f"Error getting device list: {e}")
        scan_status['in_progress'] = False
        return
    
    current_time = time.time()
    
    # Initialize GDC managers for all devices (restore from history if available)
    gdc_info_cache = {}  # Cache GDC info for later use
    for device_name in device_names:
        if device_name not in gdc_managers:
            # Initialize GDC manager and restore state from history
            gdc_info = initialize_gdc_for_device(device_name)
            gdc_info_cache[device_name] = gdc_info
        else:
            # Manager exists - just get current state
            manager = gdc_managers[device_name]
            current_state = manager.state.value
            skip_scan = current_state in ['CONFIRMED', 'TERMINAL']
            
            if current_state == 'TERMINAL':
                display_status = f'☠️ GDC TERMINAL'
            elif current_state == 'CONFIRMED':
                display_status = f'💀 GDC CONFIRMED'
            elif current_state == 'SUSPECT':
                display_status = f'⚠️ GDC SUSPECT'
            else:
                display_status = None
            
            gdc_info_cache[device_name] = {
                'skip_scan': skip_scan,
                'display_status': display_status,
                'gdc_state': current_state,
                'manager': manager
            }
            print(f"📊 GDC manager exists for {device_name}: {current_state} (timeouts: {manager.timeouts}, successes: {manager.successes})")
    
    # Launch all scans in parallel
    for device_name in device_names:
        # Get GDC info from cache
        gdc_info = gdc_info_cache.get(device_name, {})
        skip_scan = gdc_info.get('skip_scan', False)
        gdc_state = gdc_info.get('gdc_state', 'OK')
        display_status = gdc_info.get('display_status')
        
        # Check if device is CONFIRMED or TERMINAL GDC - skip scanning if so
        if skip_scan:
            print(f"⏭️  Skipping {device_name}: GDC state is {gdc_state} - no point scanning")
            
            # Quick identity check for GDC disks (model/serial only, no full SMART scan)
            # This allows detecting disk swaps and preserving log access
            try:
                print(f"🔍 Attempting quick identity check for GDC disk {device_name}...")
                
                # Try pySMART first
                from pySMART import Device
                quick_dev = Device(f'/dev/{device_name}')
                model = quick_dev.model if quick_dev else None
                serial = quick_dev.serial if quick_dev else None
                
                # Fallback to lsblk for USB devices (JMicron bridges don't pass SMART)
                if not model or not serial:
                    print(f"   pySMART returned None, trying lsblk...")
                    import subprocess
                    result = subprocess.run(
                        ['lsblk', '-n', '-o', 'MODEL,SERIAL', f'/dev/{device_name}'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        parts = result.stdout.strip().split()
                        if len(parts) >= 2:
                            model = parts[0]
                            serial = parts[1]
                            print(f"   lsblk found: Model={model}, Serial={serial}")
                
                if model and serial:
                    current_disk_id = f"{model}_{serial}"
                    
                    # Check for disk swap
                    if device_name in device_registry:
                        old_disk_id = device_registry[device_name]['disk_id']
                        if old_disk_id != current_disk_id:
                            print(f"🔄 DISK SWAP detected on GDC device {device_name}:")
                            print(f"   Old: {device_registry[device_name]['model']} ({device_registry[device_name]['serial']})")
                            print(f"   New: {model} ({serial})")
                            # Reset GDC manager for new disk
                            initialize_gdc_for_device(device_name, model, serial)
                            print(f"   ✓ GDC manager reset for new disk")
                    
                    # Update registry with current identity
                    device_registry[device_name] = {
                        'model': model,
                        'serial': serial,
                        'disk_id': current_disk_id,
                        'interface': quick_dev.interface if (quick_dev and hasattr(quick_dev, 'interface')) else None
                    }
                    print(f"📋 Identity updated for GDC disk {device_name}: {model} ({serial})")
                else:
                    print(f"   Could not determine model/serial for {device_name}")
            except Exception as e:
                print(f"⚠️ Could not read identity for GDC disk {device_name}: {e}")
            
            # Preserve last known disk identity from device_registry
            # This ensures historical logs remain accessible even after GDC
            preserved_model = None
            preserved_serial = None
            preserved_interface = None
            
            if device_name in device_registry:
                preserved_model = device_registry[device_name].get('model')
                preserved_serial = device_registry[device_name].get('serial')
                preserved_interface = device_registry[device_name].get('interface')
                print(f"📋 Preserving identity for {device_name}: {preserved_model} ({preserved_serial})")
            
            # Add GDC placeholder result with full state info
            gdc_state_json = gdc_managers[device_name].to_json()
            gdc_worst = get_worst_gdc_state(
                device_path=f"/dev/{device_name}",
                model=preserved_model,
                serial=preserved_serial
            )
            gdc_history = None
            if gdc_worst:
                gdc_history = {
                    'worst_state': gdc_worst['worst_state'],
                    'total_events': gdc_worst['total_events']
                }
            
            with scan_lock:
                scan_results[device_name] = {
                    'name': device_name,
                    'responsive': False,
                    'model': preserved_model,  # Preserve original model
                    'serial': preserved_serial,  # Preserve original serial
                    'capacity': None,
                    'interface': preserved_interface,  # Preserve original interface
                    'temperature': None,
                    'power_on_hours': None,
                    'power_on_formatted': 'N/A',
                    'health_score': 0,
                    'is_ssd': False,
                    'components': None,
                    'is_monitored': config['monitored_devices'].get(device_name, True),
                    'has_warnings': True,
                    'latest_warning': f'Ghost Drive Condition: {gdc_state}',
                    'gdc_info': gdc_state_json,
                    'gdc_state': gdc_state_json,
                    'gdc_history': gdc_history,
                    'is_usb': is_usb_device(device_name),
                    'display_status': display_status  # Use centralized display status
                }
            continue  # Skip to next device
        
        # Add placeholder for scanning device
        set_scan_result_placeholder(device_name)
        
        # Determine timeout
        if device_name not in device_retry_state:
            device_retry_state[device_name] = {'attempt': 1, 'last_try': 0}
        
        retry_state = device_retry_state[device_name]
        timeout_options = [5, 15, 30, 55]
        
        if current_time - retry_state['last_try'] > 120:
            retry_state['attempt'] = 1
        
        attempt = min(retry_state['attempt'], len(timeout_options))
        timeout = timeout_options[attempt - 1]
        
        # Scan device synchronously
        print(f"⚡ Scanning {device_name} ({timeout}s timeout)...")
        start_time = time.time()
        
        # Call scan function directly - no multiprocessing
        try:
            device_data = _scan_single_device(device_name)
            elapsed = time.time() - start_time
            print(f"📥 {device_name}: Scan completed in {elapsed:.1f}s")
            
            # Check for abnormally slow SMART response (healthy disks: <5s, warning: >10s)
            if elapsed > 10.0:
                print(f"⚠️ {device_name}: SLOW SMART RESPONSE - {elapsed:.1f}s (healthy disks: <5s)")
                if device_data:
                    device_data['slow_smart_response'] = {
                        'detected': True,
                        'response_time': round(elapsed, 1),
                        'threshold': 10.0
                    }
            
            if device_data:
                
                # Check if device changed at this path (disk swap detection)
                if device_data.get('model') and device_data.get('serial'):
                    current_disk_id = f"{device_data['model']}_{device_data['serial']}"
                    if device_name in device_registry:
                        old_disk_id = device_registry[device_name]['disk_id']
                        if old_disk_id != current_disk_id:
                            old_model = device_registry[device_name]['model']
                            old_serial = device_registry[device_name]['serial']
                            print(f"🔄 DISK SWAP detected on {device_name}:")
                            print(f"   Old: {old_model} ({old_serial})")
                            print(f"   New: {device_data['model']} ({device_data['serial']})")
                            
                            # Reset GDC manager for new disk
                            initialize_gdc_for_device(device_name, model, serial)
                            print(f"   ✓ GDC manager reset for new disk")
                    
                    # Update registry with identity information for GDC preservation
                    device_registry[device_name] = {
                        'model': device_data['model'],
                        'serial': device_data['serial'],
                        'disk_id': current_disk_id,
                        'interface': device_data.get('interface')  # Store interface for GDC preservation
                    }
                
                # GDC manager should already exist (created at scan start)
                if device_name not in gdc_managers:
                    print(f"⚠️ WARNING: GDC manager missing for {device_name}, creating now")
                    initialize_gdc_for_device(device_name, device_data.get('model'), device_data.get('serial'))
                
                # Register event with GDC manager
                if device_data.get('responsive', False):
                        print(f"✅ {device_name}: Registering SUCCESS with GDC manager")
                        old_state = gdc_managers[device_name].state.value
                        gdc_managers[device_name].event_success()
                        new_state = gdc_managers[device_name].state.value
                        
                        # Log state change
                        if old_state != new_state:
                            log_gdc_event(f"/dev/{device_name}", 'state_change', 
                                        gdc_managers[device_name].to_json(),
                                        {'old_state': old_state, 'new_state': new_state},
                                        model=device_data.get('model'),
                                        serial=device_data.get('serial'))
                            log_gdc_event_to_disk(
                                device_data.get('model'),
                                device_data.get('serial'),
                                device_name,
                                old_state,
                                new_state
                            )
                            print(f"📝 GDC state change logged: {old_state} → {new_state}")
                
                elif device_data.get('scan_status') == 'error':
                        print(f"❌ {device_name}: Registering CORRUPT with GDC manager")
                        if device_name not in gdc_managers:
                            initialize_gdc_for_device(device_name, device_data.get('model'), device_data.get('serial'))
                        gdc_managers[device_name].event_corrupt()
                        log_gdc_transition_if_changed(device_name, device_data)
                
                else:
                        # Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data.
                        # Only mark as no SMART support if we explicitly detected no SMART capability (has_smart=False)
                        # Don't assume USB devices lack SMART - many USB adapters pass through SMART data
                        # Timeouts are handled separately by event_timeout()
                        
                        has_model = device_data.get('model') not in [None, 'Unknown', '⏳ Scanning...']
                        has_serial = device_data.get('serial') not in [None, 'Unknown']
                        
                        # Only mark as no SMART support if we have no identity AND no health score
                        # (Complete absence of data, not just timeout/failure)
                        if not has_model and not has_serial and device_data.get('health_score') is None:
                            print(f"ℹ️  {device_name}: No SMART support detected (no identity, no health data)")
                            gdc_managers[device_name].event_no_smart_support()
                            
                            # Log event
                            log_gdc_event(f"/dev/{device_name}", 'no_smart_support',
                                        gdc_managers[device_name].to_json(),
                                        model=device_data.get('model'),
                                        serial=device_data.get('serial'))
                            log_gdc_transition_if_changed(device_name, device_data)
                        else:
                            # Device should have SMART but data is missing - possible GDC
                            print(f"⚠️ {device_name}: Registering NO_JSON with GDC manager")
                            gdc_managers[device_name].event_no_json()
                            
                            # Log event
                            log_gdc_event(f"/dev/{device_name}", 'no_json',
                                        gdc_managers[device_name].to_json(),
                                        model=device_data.get('model'),
                                        serial=device_data.get('serial'))
                            log_gdc_transition_if_changed(device_name, device_data)
                
                # Add GDC state to device data
                gdc_state_json = gdc_managers[device_name].to_json()
                device_data['gdc_state'] = gdc_state_json
                
                # Add GDC history if exists
                gdc_worst = get_worst_gdc_state(
                    device_path=f"/dev/{device_name}",
                    model=device_data.get('model'),
                    serial=device_data.get('serial')
                )
                if gdc_worst:
                    device_data['gdc_history'] = gdc_worst
                
                print(f"📊 {device_name} GDC state: {gdc_state_json['state']} (counters: {gdc_state_json['counters']})")
                
                # Process alerts for this disk
                triggered_alerts = process_disk_alerts(device_data)
                if triggered_alerts:
                    print(f"🔔 {device_name}: {len(triggered_alerts)} alert(s) triggered")
                
                # Add alert status to device data
                alert_status = get_disk_alert_status(device_data)
                device_data['alert_status'] = alert_status
                
                # Add is_monitored status from config
                device_data['is_monitored'] = config['monitored_devices'].get(device_name, True)
                
                print(f"📊 {device_name} GDC state: {gdc_state_json['state']} (counters: {gdc_state_json['counters']})")
                
                update_scan_result(device_name, device_data)  # Thread-safe atomic update
                device_cache[device_name] = device_data
                device_cache_time[device_name] = current_time
                device_retry_state[device_name]['attempt'] = 1
                
                print(f"✓ {device_name}: {device_data.get('model', 'Unknown')} - Score {device_data.get('health_score', 'N/A')} ({elapsed:.1f}s)")
            else:
                # No data returned - treat as error
                print(f"⚠️ {device_name}: Scan returned no data")
                
        except Exception as scan_error:
            elapsed = time.time() - start_time
            print(f"❌ {device_name}: Scan exception after {elapsed:.1f}s: {scan_error}")
            
            # Check if it's a timeout (elapsed > timeout)
            if elapsed > timeout:
                print(f"⏱️ {device_name}: Scan timeout detected")
                # Timeout handling - track with GDC
                if device_name not in gdc_managers:
                    print(f"⚠️ WARNING: GDC manager missing for {device_name} on timeout, creating now")
                    initialize_gdc_for_device(device_name)
                
                print(f"⏱️ {device_name}: Registering TIMEOUT with GDC manager")
                gdc_managers[device_name].event_timeout()
                
                # Log timeout event
                # Try to get model/serial from registry
                model = device_registry.get(device_name, {}).get('model')
                serial = device_registry.get(device_name, {}).get('serial')
                
                log_gdc_event(f"/dev/{device_name}", 'timeout',
                            gdc_managers[device_name].to_json(),
                            model=model,
                            serial=serial)
                
                # Log state change if occurred  
                device_data_for_transition = {'model': model, 'serial': serial}
                log_gdc_transition_if_changed(device_name, device_data_for_transition)
                
                if device_name not in timeout_history:
                    timeout_history[device_name] = []
                timeout_history[device_name].append(time.time())
                timeout_history[device_name] = timeout_history[device_name][-10:]  # Keep last 10
                
                # Check for GDC based on timeout pattern
                gdc_from_timeout = detect_gdc_from_timeout_pattern(device_name)
                
                # Get GDC state from manager
                gdc_state_json = gdc_managers[device_name].to_json()
                print(f"📊 {device_name} GDC state after timeout: {gdc_state_json['state']} (counters: {gdc_state_json['counters']})")
                
                print(f"⏱️  {device_name}: Timeout after {timeout}s")
                
                # Use cached or timeout message
                if device_name in device_cache:
                    timeout_device = device_cache[device_name].copy()
                    if gdc_from_timeout:
                        timeout_device['gdc'] = gdc_from_timeout
                    timeout_device['gdc_state'] = gdc_state_json
                    
                    # Add GDC history
                    model = device_registry.get(device_name, {}).get('model')
                    serial = device_registry.get(device_name, {}).get('serial')
                    gdc_worst = get_worst_gdc_state(
                        device_path=f"/dev/{device_name}",
                        model=model,
                        serial=serial
                    )
                    if gdc_worst:
                        timeout_device['gdc_history'] = gdc_worst
                    
                    update_scan_result(device_name, timeout_device)  # Thread-safe atomic update
                else:
                    model = device_registry.get(device_name, {}).get('model')
                    serial = device_registry.get(device_name, {}).get('serial')
                    gdc_worst = get_worst_gdc_state(
                        device_path=f"/dev/{device_name}",
                        model=model,
                        serial=serial
                    )
                    
                    with scan_lock:
                        scan_results[device_name] = {
                            'name': device_name,
                            'responsive': False,
                            'model': f'⏱️ Timeout ({timeout}s)',
                            'serial': 'N/A',
                            'capacity': None,
                            'interface': None,
                            'temperature': None,
                            'power_on_hours': None,
                            'power_on_formatted': 'N/A',
                            'health_score': None,
                            'is_ssd': False,
                        'components': None,
                        'is_monitored': config['monitored_devices'].get(device_name, True),
                        'has_warnings': False,
                        'latest_warning': None,
                        'gdc': gdc_from_timeout,
                        'gdc_state': gdc_state_json,
                        'gdc_history': gdc_worst
                    }
                
                if device_retry_state[device_name]['attempt'] < len(timeout_options):
                    device_retry_state[device_name]['attempt'] += 1
            else:
                # Generic error - not timeout
                print(f"⚠️ {device_name}: Error during scan (not timeout)")
    
    # === Device Lifecycle Tracking ===
    # Track which devices we saw in this scan
    global previous_scan_devices
    current_scan_devices = set(scan_results.keys())
    
    # Detect disappeared devices
    if previous_scan_devices:
        disappeared_devices = previous_scan_devices - current_scan_devices
        
        for device_name in disappeared_devices:
            if device_name in device_registry:
                reg = device_registry[device_name]
                model = reg.get('model', 'Unknown')
                serial = reg.get('serial', 'Unknown')
                disk_id = reg.get('disk_id', f'{model}_{serial}')
                
                # Get last known state from device_cache
                last_health = None
                last_gdc_state = 'UNKNOWN'
                is_usb = reg.get('interface', '').upper() == 'USB'
                
                if device_name in device_cache:
                    last_health = device_cache[device_name].get('health_score')
                    last_gdc_info = device_cache[device_name].get('gdc_info', {})
                    last_gdc_state = last_gdc_info.get('state', 'UNKNOWN')
                
                if device_name in gdc_managers:
                    last_gdc_state = gdc_managers[device_name].state.value
                
                # Intelligent classification
                severity = 'UNKNOWN'
                reason = []
                
                # USB + healthy = probably normal disconnect
                if is_usb and last_gdc_state in ['OK', 'UNKNOWN'] and (last_health is None or last_health > 70):
                    severity = 'LOW'
                    reason.append(f'USB device with good health ({last_health or "N/A"}/100)')
                    lifecycle_logger.log_device_removed(
                        disk_id, model, serial,
                        last_state=f'USB disconnect - Health: {last_health or "N/A"}, GDC: {last_gdc_state}'
                    )
                    
                    # Track disconnect time in mosmart188 state for reconnect classification
                    if disk_id:
                        state = mosmart_mgr.get_state(disk_id)
                        state.last_disconnect_time = time.time()
                        mosmart_mgr._save_state(disk_id)
                    
                    print(f"🔌 Device disconnected (normal): {model} ({serial}) - Health: {last_health or 'N/A'}")
                
                # Internal SATA disappeared = suspicious
                elif not is_usb:
                    severity = 'HIGH'
                    reason.append(f'Internal SATA disappeared unexpectedly')
                    reason.append(f'Last health: {last_health or "unknown"}, GDC: {last_gdc_state}')
                    lifecycle_logger._log_event(
                        'DEVICE_SUSPICIOUS_REMOVAL',
                        disk_id, model, serial,
                        {
                            'last_health': last_health,
                            'last_gdc_state': last_gdc_state,
                            'interface': 'SATA',
                            'reason': ', '.join(reason),
                            'message': f'⚠️ SUSPICIOUS: Internal SATA disk disappeared - {model} ({serial})'
                        }
                    )
                    print(f"🚨 SUSPICIOUS REMOVAL: {model} ({serial}) - Health: {last_health or 'N/A'}, GDC: {last_gdc_state}")
                
                # GDC disk or poor health = possible failure
                elif last_gdc_state in ['CONFIRMED', 'TERMINAL'] or (last_health is not None and last_health < 40):
                    severity = 'MEDIUM'
                    reason.append(f'GDC: {last_gdc_state}, Health: {last_health or "unknown"}')
                    lifecycle_logger._log_event(
                        'DEVICE_POSSIBLE_FAILURE',
                        disk_id, model, serial,
                        {
                            'last_health': last_health,
                            'last_gdc_state': last_gdc_state,
                            'interface': 'USB' if is_usb else 'SATA',
                            'reason': ', '.join(reason),
                            'message': f'⚠️ Possible failure: {model} ({serial}) - GDC: {last_gdc_state}, Health: {last_health or "N/A"}'
                        }
                    )
                    print(f"⚠️ POSSIBLE FAILURE: {model} ({serial}) - Health: {last_health or 'N/A'}, GDC: {last_gdc_state}")
                
                # USB with GDC SUSPECT = unclear
                else:
                    severity = 'MEDIUM'
                    lifecycle_logger._log_event(
                        'DEVICE_POSSIBLE_FAILURE',
                        disk_id, model, serial,
                        {
                            'last_health': last_health,
                            'last_gdc_state': last_gdc_state,
                            'interface': 'USB',
                            'reason': 'USB device with suspicious state',
                            'message': f'USB device disappeared: {model} ({serial}) - Health: {last_health or "N/A"}, GDC: {last_gdc_state}'
                        }
                    )
                    print(f"⚠️ USB disappeared: {model} ({serial}) - Health: {last_health or 'N/A'}, GDC: {last_gdc_state}")
    
    # Detect reconnected devices (devices that came back)
    if previous_scan_devices:
        reconnected_devices = current_scan_devices - previous_scan_devices
        
        for device_name in reconnected_devices:
            if device_name in device_registry:
                reg = device_registry[device_name]
                model = reg.get('model', 'Unknown')
                serial = reg.get('serial', 'Unknown')
                disk_id = reg.get('disk_id', f'{model}_{serial}')
                device_path = f"/dev/{device_name}"
                is_usb = reg.get('interface', '').upper() == 'USB'
                
                # Log to lifecycle logger
                lifecycle_logger.log_device_reconnected(
                    disk_id, model, serial, device_path
                )
                
                # Also log to disk health log (like disconnection events)
                if is_usb:
                    from disk_logger import log_usb_event
                    log_usb_event(model, serial, device_name, 'reconnected')
                
                print(f"🔌 Device reconnected: {model} ({serial}) at {device_path}")
    
    # Update previous_scan_devices for next scan
    previous_scan_devices = current_scan_devices
    # === End Lifecycle Tracking ===
    
    total_time = time.time() - scan_status['start_time']
    print(f"⚡ Progressive scan complete: {len(scan_results)} devices in {total_time:.1f}s")
    scan_status['in_progress'] = False

    # After scan, check for uncontrolled shutdown system event via mosmart188
    try:
        mosmart_mgr = get_mosmart188_manager()
        system_event = mosmart_mgr.get_last_system_event()
        global last_logged_system_event_ts
        if system_event and system_event.get('type') == 'uncontrolled_shutdown':
            event_ts = system_event.get('timestamp', time.time())
            if (event_ts or 0) > last_logged_system_event_ts:
                # Log to per-disk logs for visibility
                affected_ids = system_event.get('affected_disk_ids', [])
                affected_count = system_event.get('affected_count', len(affected_ids))
                from disk_logger import log_system_event_uncontrolled_shutdown
                log_system_event_uncontrolled_shutdown(affected_ids, timestamp=datetime.fromtimestamp(event_ts), affected_count=affected_count)
                # Expose in API response cache
                scan_status['last_system_event'] = {
                    'type': 'uncontrolled_shutdown',
                    'timestamp': datetime.fromtimestamp(event_ts).isoformat(),
                    'affected_count': affected_count,
                    'message': 'Ukontrollert avslutning oppdaget'
                }
                # Update last logged to avoid duplicates
                last_logged_system_event_ts = event_ts
                print(f"📝 System event logged: Uncontrolled shutdown (affected={affected_count})")
    except Exception as e:
        print(f"⚠️ Failed to process system event: {e}")


def scan_all_devices():
    """Scan all devices in parallel with adaptive timeout"""
    import subprocess
    
    # Use lsblk to find actual disk devices (including USB)
    try:
        result = subprocess.run(
            ['lsblk', '-d', '-n', '-b', '-o', 'NAME,TYPE,SIZE,HOTPLUG,TRAN'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # Filter for disk type with non-zero size (including USB)
        device_names = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 4:
                    name, dtype, size = parts[0], parts[1], parts[2]
                    # Include all disk types with non-zero size (including USB)
                    if dtype == 'disk' and name.startswith('sd') and int(size) > 0:
                        device_names.append(name)
        
        print(f"Found {len(device_names)} actual disk devices: {device_names}")
    except Exception as e:
        print(f"Error getting device list with lsblk: {e}")
        import glob
        device_paths = glob.glob('/dev/sd[a-c]')
        device_names = [p.split('/')[-1] for p in device_paths]
    
    current_time = time.time()
    devices_info = []
    
    # Launch all scans in parallel
    processes = {}
    queues = {}
    timeouts = {}
    
    for device_name in device_names:
        # Check if device is CONFIRMED or TERMINAL GDC - skip scanning
        if device_name in gdc_managers:
            gdc_state = gdc_managers[device_name].state.value
            if gdc_state in ['CONFIRMED', 'TERMINAL']:
                print(f"⏭️  Skipping {device_name}: GDC state is {gdc_state} - no point scanning")
                
                # Quick identity check for GDC disks (model/serial only, no full SMART scan)
                try:
                    from pySMART import Device
                    quick_dev = Device(f'/dev/{device_name}')
                    model = quick_dev.model if quick_dev else None
                    serial = quick_dev.serial if quick_dev else None
                    
                    # Fallback to lsblk for USB devices (JMicron bridges don't pass SMART)
                    if not model or not serial:
                        import subprocess
                        result = subprocess.run(
                            ['lsblk', '-n', '-o', 'MODEL,SERIAL', f'/dev/{device_name}'],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            parts = result.stdout.strip().split()
                            if len(parts) >= 2:
                                model = parts[0]
                                serial = parts[1]
                    
                    if model and serial:
                        current_disk_id = f"{model}_{serial}"
                        
                        # Check for disk swap
                        if device_name in device_registry:
                            old_disk_id = device_registry[device_name]['disk_id']
                            if old_disk_id != current_disk_id:
                                print(f"🔄 DISK SWAP detected on GDC device {device_name}:")
                                print(f"   Old: {device_registry[device_name]['model']} ({device_registry[device_name]['serial']})")
                                print(f"   New: {model} ({serial})")
                                # Reset GDC manager for new disk
                                initialize_gdc_for_device(device_name, model, serial)
                                print(f"   ✓ GDC manager reset for new disk")
                        
                        # Update registry with current identity
                        device_registry[device_name] = {
                            'model': model,
                            'serial': serial,
                            'disk_id': current_disk_id,
                            'interface': quick_dev.interface if (quick_dev and hasattr(quick_dev, 'interface')) else None
                        }
                        print(f"📋 Identity updated for GDC disk {device_name}: {model} ({serial})")
                except Exception as e:
                    print(f"⚠️ Could not read identity for GDC disk {device_name}: {e}")
                
                # Preserve last known disk identity from device_registry
                preserved_model = None
                preserved_serial = None
                preserved_interface = None
                preserved_disk_id = None
                
                if device_name in device_registry:
                    preserved_model = device_registry[device_name].get('model')
                    preserved_serial = device_registry[device_name].get('serial')
                    preserved_interface = device_registry[device_name].get('interface')
                    preserved_disk_id = device_registry[device_name].get('disk_id')
                    print(f"📋 Preserving identity for {device_name}: {preserved_model} ({preserved_serial})")
                
                # Get SMART read tracker for GDC device (use disk_id if available)
                if preserved_disk_id:
                    gdc_smart_tracker = get_smart_read_manager().get_tracker(preserved_disk_id, device_name)
                else:
                    # Fallback to device_name if no disk_id
                    gdc_smart_tracker = get_smart_read_manager().get_tracker(f"unknown_{device_name}", device_name)
                
                devices_info.append({
                    'name': device_name,
                    'responsive': False,
                    'model': preserved_model,  # Preserve original model
                    'serial': preserved_serial,  # Preserve original serial
                    'capacity': None,
                    'interface': preserved_interface,  # Preserve original interface
                    'temperature': None,
                    'power_on_hours': None,
                    'power_on_formatted': 'N/A',
                    'health_score': 0,
                    'is_ssd': False,
                    'components': None,
                    'is_monitored': config['monitored_devices'].get(device_name, True),
                    'has_warnings': True,
                    'latest_warning': f'Ghost Drive Condition: {gdc_state}',
                    'gdc_info': gdc_managers[device_name].to_json(),
                    'display_status': f'💀 GDC {gdc_state}',  # Separate display status for UI
                    'mosmart188': {
                        'count': gdc_smart_tracker.get_error_count(),
                        'severity': gdc_smart_tracker.get_severity(),
                        'should_escalate': gdc_smart_tracker.should_escalate(),
                        'last_error': datetime.fromtimestamp(gdc_smart_tracker.last_error_time).isoformat() if gdc_smart_tracker.last_error_time else None,
                        'last_success': datetime.fromtimestamp(gdc_smart_tracker.last_success_time).isoformat() if gdc_smart_tracker.last_success_time else None,
                        'last_error_reason': gdc_smart_tracker.last_error_reason
                    }
                })
                continue  # Skip to next device
        
        # Check if we have fresh cached data
        if (device_name in device_cache and 
            device_name in device_cache_time and
            current_time - device_cache_time[device_name] < DEVICE_CACHE_DURATION):
            print(f"Using cached data for {device_name}")
            devices_info.append(device_cache[device_name])
            continue
        
        # Determine timeout based on retry state
        if device_name not in device_retry_state:
            device_retry_state[device_name] = {'attempt': 1, 'last_try': 0}
        
        retry_state = device_retry_state[device_name]
        timeout_options = [5, 15, 30, 55]
        
        # Only increment attempt if enough time has passed
        if current_time - retry_state['last_try'] > 120:
            retry_state['attempt'] = 1
        
        attempt = min(retry_state['attempt'], len(timeout_options))
        timeout = timeout_options[attempt - 1]
        
        # Store timeout for this device
        timeouts[device_name] = timeout
        
        if attempt == 1:
            print(f"⚡ Starting scan of {device_name} (timeout: {timeout}s)")
        else:
            print(f"⚡ Retry scan of {device_name} (attempt {attempt}, timeout: {timeout}s)")
    
    # Scan all devices sequentially
    scan_start = time.time()
    max_wait = 60  # Maximum total wait time
    
    for device_name in device_names:
        # Skip if already scanned (cached or GDC)
        if device_name in [d['name'] for d in devices_info]:
            continue
            
        timeout = timeouts.get(device_name, 5)
        retry_state = device_retry_state.get(device_name, {'attempt': 1, 'last_try': 0})
        retry_state['last_try'] = current_time
        
        try:
            # Scan device directly
            device_data = _scan_single_device(device_name)
            elapsed_time = time.time() - scan_start
            
            if device_data and device_data.get('responsive'):
                print(f"✓ {device_name}: {device_data.get('model', 'Unknown')} - Score {device_data.get('health_score', 'N/A')} ({elapsed_time:.1f}s)")
                
                # Cache successful result
                device_cache[device_name] = device_data
                device_cache_time[device_name] = current_time
                retry_state['attempt'] = 1
                
                devices_info.append(device_data)
            else:
                # Scan returned error data
                print(f"⚠️ {device_name}: Scan completed but device not responsive")
                devices_info.append(device_data if device_data else {
                    'name': device_name,
                    'responsive': False,
                    'model': '❌ Error',
                    'serial': 'N/A'
                })
                
        except Exception as e:
            print(f"❌ {device_name}: Scan exception: {e}")
            import traceback
            traceback.print_exc()
            
            # Escalate retry for next time
            if retry_state['attempt'] < len(timeout_options):
                retry_state['attempt'] += 1
                print(f"   Next attempt will use {timeout_options[retry_state['attempt']-1]}s timeout")
            
            # Use cached data if available
            if device_name in device_cache:
                print(f"   Using cached data for {device_name}")
                devices_info.append(device_cache[device_name])
            else:
                # Get SMART read tracker for error fallback (try to get disk_id from registry)
                error_disk_id = None
                if device_name in device_registry:
                    error_disk_id = device_registry[device_name].get('disk_id')
                
                if error_disk_id:
                    error_smart_tracker = get_smart_read_manager().get_tracker(error_disk_id, device_name)
                else:
                    # Fallback: use device_name
                    error_smart_tracker = get_smart_read_manager().get_tracker(f"unknown_{device_name}", device_name)
                
                devices_info.append({
                    'name': device_name,
                    'responsive': False,
                    'model': f'❌ Error - Retrying...',
                    'serial': 'N/A',
                    'capacity': None,
                    'interface': None,
                    'temperature': None,
                    'power_on_hours': None,
                    'power_on_formatted': 'N/A',
                    'health_score': None,
                    'health_rating': 'N/A',
                    'is_ssd': False,
                    'components': None,
                    'is_monitored': config['monitored_devices'].get(device_name, True),
                    'has_warnings': False,
                    'latest_warning': None,
                    'mosmart188': {
                        'count': error_smart_tracker.get_error_count(),
                        'severity': error_smart_tracker.get_severity(),
                        'should_escalate': error_smart_tracker.should_escalate(),
                        'last_error': datetime.fromtimestamp(error_smart_tracker.last_error_time).isoformat() if error_smart_tracker.last_error_time else None,
                        'last_success': datetime.fromtimestamp(error_smart_tracker.last_success_time).isoformat() if error_smart_tracker.last_success_time else None,
                        'last_error_reason': error_smart_tracker.last_error_reason
                    }
                })
    
    total_time = time.time() - scan_start
    print(f"⚡ Sequential scan complete: {len(devices_info)} devices in {total_time:.1f}s")
    return devices_info

def get_documentation_file(language):
    """Get the appropriate documentation file for the given language"""
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try language-specific documentation
    candidate = f"documentation-{language}.md"
    candidate_path = os.path.join(base_dir, candidate)
    
    # Special case for Norwegian
    if language == 'no':
        candidate = "dokumentasjon-no.md"
        candidate_path = os.path.join(base_dir, candidate)
    
    # Check if file exists
    if os.path.exists(candidate_path):
        return "/" + candidate
    else:
        # Fallback to English
        return "/documentation-en.md"

@app.route('/')
def index():
    """Main dashboard page"""
    lang = config.get('language', 'en')
    temp_unit = config.get('temperature_unit', 'C')
    documentation_link = get_documentation_file(lang)
    
    return render_template('dashboard.html', 
                         port=config['port'],
                         refresh_interval=config['refresh_interval'],
                         language=lang,
                         documentation_link=documentation_link,
                         temperature_unit=temp_unit,
                         translations=TRANSLATIONS)

@app.route('/README.md')
def readme():
    """Serve the README file"""
    return send_file('README.md', mimetype='text/markdown')

@app.route('/dokumentasjon-no.md')
def dokumentasjon_no():
    """Serve the Norwegian documentation"""
    return send_file('dokumentasjon-no.md', mimetype='text/plain; charset=utf-8')

@app.route('/documentation-en.md')
def documentation_en():
    """Serve the English documentation"""
    import os
    if os.path.exists('documentation-en.md'):
        return send_file('documentation-en.md', mimetype='text/plain; charset=utf-8')
    else:
        return "English documentation not yet available", 404

@app.route('/EMERGENCY_UNMOUNT_IMPLEMENTATION.md')
def emergency_unmount_docs():
    """Serve the Emergency Unmount documentation"""
    import os
    if os.path.exists('EMERGENCY_UNMOUNT_IMPLEMENTATION.md'):
        return send_file('EMERGENCY_UNMOUNT_IMPLEMENTATION.md', mimetype='text/plain; charset=utf-8')
    else:
        return "Emergency Unmount documentation not found", 404

@app.route('/api/translations')
def api_translations():
    """API endpoint to get all translations"""
    return jsonify(TRANSLATIONS)

@app.route('/api/permissions')
def api_permissions():
    """
    Get user permissions and role.
    
    Current Implementation (Phase 3):
    - Always returns "admin" since backend runs as root
    - Endpoint ready for Phase 4 when auth is implemented
    
    Future (Phase 4): Will check auth tokens/socket credentials
    - "admin" - Full access via authenticated admin users
    - "read-only" - View-only access via regular users
    """
    try:
        # Get username from environment
        # SUDO_USER set when running with sudo, USER otherwise
        username = os.environ.get('SUDO_USER')
        if not username:
            username = os.environ.get('USER', 'unknown')
        
        # Phase 3: Backend always admin (runs as root with sudo)
        # Phase 4: Will implement proper auth checking
        is_admin = True  # TODO: Implement proper auth in Phase 4
        
        return jsonify({
            'role': 'admin' if is_admin else 'read-only',
            'username': username,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error getting permissions: {e}")
        return jsonify({'error': str(e), 'role': 'read-only'}), 500

@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration (read-only)"""
    try:
        config_data = load_config()
        return jsonify(config_data)
    except Exception as e:
        print(f"Error loading config: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def api_set_config():
    """
    Update configuration (admin only).
    Requires root/sudo access.
    """
    try:
        # Check permissions
        if os.getuid() != 0:
            return jsonify({
                'error': 'Admin access required. Please run backend with sudo.',
                'role': 'read-only'
            }), 403
        
        # Get new config
        new_config = request.get_json()
        if not new_config:
            return jsonify({'error': 'No configuration provided'}), 400
        
        # Save config
        save_config(new_config)
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error saving config: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices')
def api_devices():
    """API endpoint to get all devices"""
    devices = scan_all_devices()
    return jsonify({
        'devices': devices,
        'timestamp': datetime.now().isoformat(),
        'system': get_system_info(),
        'config': {
            'refresh_interval': config['refresh_interval']
        }
    })

@app.route('/api/devices/progressive')
def api_devices_progressive():
    """API endpoint that returns current scan results (including partial)"""
    
    # Get current results using thread-safe function
    devices = get_all_scan_results()
    
    return jsonify({
        'devices': devices,
        'timestamp': datetime.now().isoformat(),
        'scanning': scan_status.get('in_progress', False),
        'scan_start': scan_status.get('start_time', 0),
        'system_event': scan_status.get('last_system_event')
    })

@app.route('/api/scan/start', methods=['POST'])
def api_scan_start():
    """Start a new scan in background"""
    import threading
    
    def background_scan():
        scan_all_devices_progressive()
    
    if not scan_status.get('in_progress', False):
        scan_status['in_progress'] = True
        scan_status['start_time'] = time.time()
        thread = threading.Thread(target=background_scan)
        thread.daemon = True
        thread.start()
        return jsonify({'status': 'started'})
    else:
        return jsonify({'status': 'already_running'})

@app.route('/api/force-scan', methods=['POST'])
def api_force_scan():
    """Force scan all devices including GDC - temporarily disables GDC skip"""
    global gdc_managers
    
    print("\n" + "="*80)
    print("🔨 FORCE SCAN endpoint called!")
    print(f"🔍 gdc_managers object ID: {id(gdc_managers)}")
    print(f"🔍 gdc_managers contains {len(gdc_managers)} devices: {list(gdc_managers.keys())}")
    for device_name, manager in gdc_managers.items():
        print(f"  📊 {device_name}: state={manager.state.value}, timeouts={manager.timeouts}, successes={manager.successes}")
    print("="*80 + "\n")
    
    def force_scan_worker():
        """Scan all devices without GDC skip optimization"""
        global gdc_managers, is_force_scan
        
        print("🔨 FORCE SCAN worker starting...")
        print(f"🔍 WORKER: gdc_managers object ID: {id(gdc_managers)}")
        print(f"🔍 WORKER: gdc_managers contains {len(gdc_managers)} devices")
        
        # Set force scan flag so logging happens for all devices
        is_force_scan = True
        
        # Temporarily store GDC states
        saved_states = {}
        for device_name, manager in gdc_managers.items():
            saved_states[device_name] = manager.state
        
        # Temporarily set all to OK to force scanning
        print("🔨 FORCE SCAN: Temporarily disabling GDC skip for all devices")
        from gdc import GDCState
        print(f"🔍 GDCState.OK = {GDCState.OK}")
        for device_name, manager in gdc_managers.items():
            before_state = manager.state.value
            manager.frozen = True  # FREEZE state changes during force scan
            manager.state = GDCState.OK
            after_state = manager.state.value
            print(f"  🔧 {device_name}: {before_state} → {after_state} (verified: {manager.state == GDCState.OK}, frozen: {manager.frozen})")
        
        # Run scan
        print("🔨 FORCE SCAN: Launching scan_all_devices_progressive()...")
        start_time = time.time()
        scan_all_devices_progressive()
        scan_time = time.time() - start_time
        print(f"🔨 FORCE SCAN: Scan completed in {scan_time:.1f}s")
        
        # Verify states after scan
        print("🔍 States after scan:")
        for device_name, manager in gdc_managers.items():
            print(f"  📊 {device_name}: {manager.state.value}")
        
        # Restore GDC states
        print("🔨 FORCE SCAN: Restoring GDC states")
        for device_name, original_state in saved_states.items():
            if device_name in gdc_managers:
                gdc_managers[device_name].state = original_state
                gdc_managers[device_name].frozen = False  # UNFREEZE after restore
                after = gdc_managers[device_name].state.value
                print(f"  🔧 {device_name}: Restored to {original_state.value}, unfrozen")
                
                # Check for transition and log if needed
                if device_name in scan_results:
                    log_gdc_transition_if_changed(device_name, scan_results[device_name])
                
                # Update scan_results to show GDC state if restored to CONFIRMED/TERMINAL
                if after in ['CONFIRMED', 'TERMINAL'] and device_name in scan_results:
                    gdc_json = gdc_managers[device_name].to_json()
                    # Preserve identity from device_registry
                    with scan_lock:
                        if device_name in device_registry:
                            scan_results[device_name]['model'] = device_registry[device_name].get('model')
                            scan_results[device_name]['serial'] = device_registry[device_name].get('serial')
                            scan_results[device_name]['interface'] = device_registry[device_name].get('interface')
                        scan_results[device_name]['display_status'] = f'💀 GDC {after}'
                        scan_results[device_name]['responsive'] = False
                        scan_results[device_name]['health_score'] = 0
                        scan_results[device_name]['has_warnings'] = True
                        scan_results[device_name]['latest_warning'] = f'Ghost Drive Condition: {after}'
                        scan_results[device_name]['gdc_info'] = gdc_json
                        scan_results[device_name]['gdc_state'] = gdc_json  # Viktig! Frontend bruker gdc_state
                    print(f"    📝 Updated scan_results for {device_name} to show GDC state: {after}")
            else:
                print(f"  ⚠️ {device_name}: NOT FOUND in gdc_managers!")
        
        # Reset force scan flag
        is_force_scan = False
        
        print(f"🔨 FORCE SCAN worker returning scan_time={scan_time:.1f}s")
        return scan_time
    
    if scan_status.get('in_progress', False):
        print("🔨 FORCE SCAN: Scan already in progress - aborting")
        print(f"🔍 scan_status = {scan_status}")
        return jsonify({
            'status': 'error',
            'message': 'En skanning pågår allerede'
        }), 409
    
    print("🔨 FORCE SCAN: Setting scan_status to in_progress")
    print(f"🔍 scan_status BEFORE: {scan_status}")
    scan_status['in_progress'] = True
    scan_status['start_time'] = time.time()
    print(f"🔍 scan_status AFTER: {scan_status}")
    
    try:
        print("🔨 FORCE SCAN: Calling force_scan_worker()")
        scan_time = force_scan_worker()
        print(f"🔨 FORCE SCAN: Worker completed in {scan_time:.1f}s")
        print(f"🔍 scan_results contains {len(scan_results)} devices")
        for device_name, result in scan_results.items():
            print(f"  📊 {device_name}: model={result.get('model')}, health_score={result.get('health_score')}")
        return jsonify({
            'status': 'success',
            'scanned': len(scan_results),
            'time': f'{scan_time:.1f}'
        })
    except Exception as e:
        import traceback
        print(f"❌ Force scan error: {e}")
        print(f"❌ Traceback:\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        print("🔨 FORCE SCAN: Cleanup - setting scan_status to not in_progress")
        scan_status['in_progress'] = False
        print(f"🔍 Final scan_status: {scan_status}")
        print("="*80 + "\n")

@app.route('/api/device/<device_name>')
def api_device_detail(device_name):
    """API endpoint to get detailed info for a specific device"""
    devices = scan_all_devices()
    device = next((d for d in devices if d['name'] == device_name), None)
    
    if device:
        return jsonify(device)
    else:
        return jsonify({'error': 'Device not found'}), 404

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """API endpoint to get or update configuration"""
    if request.method == 'POST':
        data = request.get_json()
        
        # Track if we need to update settings.json
        settings_changed = False
        current_settings = load_config()
        
        if 'refresh_interval' in data:
            new_interval = max(10, int(data['refresh_interval']))
            config['refresh_interval'] = new_interval
            # Save to settings.json
            current_settings.setdefault('general', {})['polling_interval'] = new_interval
            settings_changed = True
        
        if 'monitored_devices' in data:
            config['monitored_devices'] = data['monitored_devices']
        
        if 'language' in data:
            # Accept any language code (will be validated by frontend)
            config['language'] = data['language']
            # Save to settings.json
            current_settings.setdefault('general', {})['language'] = data['language']
            settings_changed = True
        
        if 'enable_logging' in data:
            config['enable_logging'] = bool(data['enable_logging'])
        
        if 'max_log_size_kb' in data:
            new_size = int(data['max_log_size_kb'])
            if 100 <= new_size <= 10240:
                config['max_log_size_kb'] = new_size
                # Update the logger's MAX_LOG_SIZE_KB
                disk_logger.MAX_LOG_SIZE_KB = new_size
        
        # Save to settings.json if anything changed
        if settings_changed:
            save_config(current_settings)
            print(f"💾 Updated settings.json via /api/config")
        
        return jsonify({'status': 'success', 'config': config})
    else:
        return jsonify(config)


@app.route('/api/alerts/recent')
def api_recent_alerts():
    """Get recent alerts"""
    hours = request.args.get('hours', 24, type=int)
    alerts = alert_engine.get_recent_alerts(hours)
    return jsonify({'alerts': alerts, 'count': len(alerts)})


@app.route('/api/alerts/config', methods=['GET', 'POST'])
def api_alert_config():
    """Get or update alert configuration"""
    if request.method == 'POST':
        data = request.json
        
        if 'score_change_threshold' in data:
            alert_engine.ALERT_CONFIG['score_change_threshold'] = int(data['score_change_threshold'])
        if 'critical_score' in data:
            alert_engine.ALERT_CONFIG['critical_score'] = int(data['critical_score'])
        if 'temperature_consecutive_readings' in data:
            alert_engine.ALERT_CONFIG['temperature_consecutive_readings'] = int(data['temperature_consecutive_readings'])
        
        return jsonify({'status': 'success', 'config': alert_engine.ALERT_CONFIG})
    else:
        return jsonify(alert_engine.ALERT_CONFIG)


@app.route('/api/history/<model>/<serial>')
def api_history(model, serial):
    """Get historical data for a specific disk"""
    days = request.args.get('days', 30, type=int)
    history = get_disk_history(model, serial, days)
    warnings = get_recent_warnings(model, serial, days)
    return jsonify({
        'history': history,
        'warnings': warnings,
        'days': days
    })

@app.route('/api/languages')
def api_languages():
    """Get list of available languages"""
    import glob
    languages = []
    lang_dir = Path(__file__).parent / 'languages'
    
    if lang_dir.exists():
        for lang_file in sorted(lang_dir.glob('*.lang')):
            # Skip template file
            if lang_file.name == 'template.lang':
                continue
                
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    lang_data = json.load(f)
                    # Also skip files with placeholder values
                    if lang_data['language_code'] == 'xx' or lang_data['language_name'] == 'LANGUAGE_NAME_NATIVE':
                        continue
                    languages.append({
                        'code': lang_data['language_code'],
                        'name': lang_data['language_name'],
                        'flag': lang_data.get('language_flag', ''),
                        'file': lang_file.name
                    })
            except Exception as e:
                print(f"Error loading language file {lang_file}: {e}")
    
    return jsonify({'languages': languages})

@app.route('/api/language/<lang_code>')
def api_language(lang_code):
    """Get translations for a specific language"""
    lang_dir = Path(__file__).parent / 'languages'
    
    # Find language file by code
    for lang_file in lang_dir.glob('*.lang'):
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                lang_data = json.load(f)
                if lang_data['language_code'] == lang_code:
                    return jsonify(lang_data)
        except Exception as e:
            print(f"Error loading language file {lang_file}: {e}")
    
    return jsonify({'error': 'Language not found'}), 404

@app.route('/api/history/<model>/<serial>/export')
def export_history(model, serial):
    """Export historical data as CSV"""
    import csv
    from io import StringIO
    from flask import make_response
    
    days = request.args.get('days', default=365, type=int)
    history = get_disk_history(model, serial, days)
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Timestamp', 'Health Score', 'Assessment', 'Temperature',
        'Reallocated Sectors', 'Reallocated Score',
        'Pending Sectors', 'Pending Score',
        'Uncorrectable Errors', 'Uncorrectable Score',
        'Timeout Errors', 'Timeout Score',
        'Power On Hours', 'Age Score',
        'Temperature Score'
    ])
    
    # Data rows
    for entry in history:
        comp = entry.get('components', {})
        writer.writerow([
            entry.get('timestamp', ''),
            entry.get('health_score', ''),
            entry.get('assessment', ''),
            entry.get('temperature', ''),
            comp.get('reallocated', {}).get('value', ''),
            comp.get('reallocated', {}).get('score', ''),
            comp.get('pending', {}).get('value', ''),
            comp.get('pending', {}).get('score', ''),
            comp.get('uncorrectable', {}).get('value', ''),
            comp.get('uncorrectable', {}).get('score', ''),
            comp.get('timeout', {}).get('value', ''),
            comp.get('timeout', {}).get('score', ''),
            comp.get('age', {}).get('value', ''),
            comp.get('age', {}).get('score', ''),
            comp.get('temperature', {}).get('score', '')
        ])
    
    # Return as downloadable file
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={model}_{serial}_health.csv'
    
    return response

@app.route('/api/toggle/<device_name>', methods=['POST'])
def api_toggle_device(device_name):
    """Toggle monitoring for a specific device"""
    # Load current settings
    settings = config_manager.load_config()
    
    # Get current state from disk_selection.monitored_devices
    disk_selection = settings.get('disk_selection', {})
    monitored_devices = disk_selection.get('monitored_devices', {})
    
    # Toggle the state
    current_state = monitored_devices.get(device_name, True)
    monitored_devices[device_name] = not current_state
    
    # Update settings
    disk_selection['monitored_devices'] = monitored_devices
    settings['disk_selection'] = disk_selection
    
    # Save to file
    config_manager.save_config(settings)
    
    # Update in-memory config as well
    config['monitored_devices'][device_name] = monitored_devices[device_name]
    
    # CRITICAL: Also update device_cache so progressive endpoint returns correct value
    if device_name in device_cache:
        device_cache[device_name]['is_monitored'] = monitored_devices[device_name]
    
    return jsonify({
        'device': device_name,
        'is_monitored': monitored_devices[device_name]
    })

@app.route('/api/email/config', methods=['GET', 'POST'])
def api_email_config():
    """Get or update email notification configuration - uses config_manager"""
    if request.method == 'GET':
        config = load_email_config()
        # Don't send password to frontend (for security)
        if 'smtp_password' in config:
            config['smtp_password'] = '***' if config['smtp_password'] else ''
        return jsonify(config)
    else:
        # POST - update config via save_email_config (uses config_manager)
        new_config = request.json
        
        # If password is '***', don't update it (keep existing)
        if new_config.get('smtp_password') == '***':
            existing_config = load_email_config()
            new_config['smtp_password'] = existing_config.get('smtp_password', '')
        
        save_email_config(new_config)
        return jsonify({'status': 'success', 'message': 'Email configuration saved'})

@app.route('/api/email/test', methods=['POST'])
def api_email_test():
    """Send a test email - loads config from config_manager"""
    # Load config from config_manager (via load_email_config which now uses config_manager)
    config = load_email_config()
    
    print(f"📧 Test email requested")
    print(f"   Enabled: {config.get('enabled')}")
    print(f"   SMTP Server: {config.get('smtp_server')}:{config.get('smtp_port')}")
    print(f"   Username: {config.get('smtp_username')}")
    print(f"   To: {config.get('to_emails')}")
    
    result = test_email_config(config)
    
    if result.get('success'):
        return jsonify({'status': 'success', 'message': result.get('message', 'Test email sent successfully')})
    else:
        return jsonify({'status': 'error', 'message': result.get('error', 'Failed to send test email')}), 500

@app.route('/api/test-email', methods=['POST'])
def api_test_email_alias():
    """Alias for /api/email/test - for frontend compatibility"""
    return api_email_test()

def get_external_health():
    """
    Get comprehensive system health and disk information.
    
    Backend function independent of WebUI/Flask that provides health data.
    Can be called from:
    - Web API endpoint (/api/external/health)
    - CLI tools
    - Other external services
    - Background tasks
    
    Returns:
        dict: System status with disk health data, warnings, and GDC states
    """
    global service_start_time
    
    # Scan all devices
    scan_error = None
    try:
        devices = scan_all_devices()
    except Exception as e:
        print(f"❌ External health scan failed: {e}")
        devices = []
        scan_error = str(e)
    
    # Get recent warnings from alert engine
    warnings = []
    # Note: get_recent_warnings() requires model and serial per disk,
    # so we skip generic warnings collection for now.
    # Device-specific warnings are included in the disks array.
    
    # Extract GDC states for all devices
    gdc_states = {}
    try:
        for device_name, manager in gdc_managers.items():
            gdc_states[device_name] = {
                'state': manager.state.value,
                'timeouts': manager.timeouts,
                'successes': manager.successes,
                'confidence': manager.confidence
            }
    except Exception as e:
        print(f"⚠️ Could not build GDC states: {e}")
    
    # Build simplified disk array
    disks_simplified = []
    for device in devices:
        disk_info = {
            'name': device.get('name'),
            'model': device.get('model'),
            'serial': device.get('serial'),
            'capacity': device.get('capacity'),
            'health_score': device.get('health_score', 0),
            'health_rating': device.get('health_rating', 'UNKNOWN'),
            'temperature': device.get('temperature'),
            'power_on_hours': device.get('power_on_hours'),
            'interface': device.get('interface'),
            'responsive': device.get('responsive', True),
            'has_warnings': device.get('has_warnings', False),
            'gdc_state': gdc_states.get(device.get('name'), {}).get('state', 'OK')
        }
        
        # Add critical SMART attributes
        attributes = device.get('attributes', {})
        disk_info['smart_critical'] = {
            'reallocated_sectors': attributes.get('5', {}).get('raw', 0),
            'pending_sectors': attributes.get('197', {}).get('raw', 0),
            'uncorrectable_errors': attributes.get('198', {}).get('raw', 0),
            'power_cycle_count': attributes.get('12', {}).get('raw', 0)
        }
        
        disks_simplified.append(disk_info)
    
    # Calculate uptime
    try:
        uptime_seconds = int(time.time() - service_start_time)
    except Exception:
        uptime_seconds = 0
    
    health_data = {
        'installed': True,
        'version': '0.9.3',
        'service': 'MoSMART',
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': uptime_seconds,
        'system': get_system_info(),
        'disks': disks_simplified,
        'disk_count': len(disks_simplified),
        'warnings': warnings,
        'warning_count': len(warnings),
        'gdc_states': gdc_states,
        'scan_error': scan_error,
        'api_endpoints': {
            'full_devices': '/api/devices',
            'device_detail': '/api/device/<device_name>',
            'device_history': '/api/history/<model>/<serial>',
            'force_scan': '/api/force-scan (POST)',
            'external_health': '/api/external/health'
        }
    }
    
    return health_data

@app.route('/api/external/health')
def api_external_health():
    """
    External Health Check Endpoint
    
    Provides comprehensive system status and disk information for external tools.
    This endpoint is generic and not tied to any specific external application.
    
    Can be used by:
    - Disk wiping tools (MoWIPE)
    - System monitoring dashboards
    - Third-party health checkers
    - Any external service that needs disk health data
    
    Example usage:
        curl -s http://localhost:5000/api/external/health | jq .
    
    Returns:
        JSON object with:
        - installed: true/false (always true if reachable)
        - version: MoSMART version string
        - timestamp: ISO 8601 timestamp
        - uptime: Service uptime in seconds
        - system: System information (OS, hostname, etc.)
        - disks: Array of disk objects with health data
        - warnings: Array of current warnings/alerts
        - gdc_states: Ghost Drive Condition states for all disks
    """
    health_data = get_external_health()
    return jsonify(health_data)

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """Get all settings"""
    return jsonify(load_config())

@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    """Save all settings"""
    global config
    new_config = request.json
    
    print(f"💾 Saving settings...")
    print(f"   Received config keys: {list(new_config.keys())}")
    if 'general' in new_config:
        print(f"   General: {new_config['general']}")
    if 'alert_channels' in new_config and 'email' in new_config['alert_channels']:
        email_cfg = new_config['alert_channels']['email']
        print(f"   Email enabled: {email_cfg.get('enabled')}")
        print(f"   Email server: {email_cfg.get('smtp_server')}")
        print(f"   Email user: {email_cfg.get('smtp_username')}")
       # print(f"   Email password length: {len(email_cfg.get('smtp_password', ''))}")
        pw = email_cfg.get('smtp_password')
        print(f"   Email password length: {len(pw) if isinstance(pw, str) else 'UNCHANGED'}")
    
    # Special handling for email config - must encrypt password
    email_saved = False
    if 'alert_channels' in new_config and 'email' in new_config['alert_channels']:
        email_cfg = new_config['alert_channels']['email']
        # Save email config separately (handles encryption)
        email_saved = save_email_config(email_cfg)
        print(f"   Email config save: {'✅ SUCCESS' if email_saved else '❌ FAILED'}")
        
    
    # Load current config to merge
    current_config = load_config()
    
    # Update current config with new values (this preserves encrypted email)
    for section, values in new_config.items():
        if section == 'alert_channels':
            # Special handling - merge alert_channels but skip email (already saved)
            if section not in current_config:
                current_config[section] = {}
            for key, value in values.items():
                if key != 'email':  # Don't overwrite email - it's already saved
                    current_config[section][key] = value
        else:
            # Normal section - just replace
            current_config[section] = values
    

    
    # Save merged config to file
    success = save_config(current_config)
    print(f"   Merged config save: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    # Update global config variables for immediate effect
    if success and 'general' in current_config:
        if 'polling_interval' in current_config['general']:
            config['refresh_interval'] = current_config['general']['polling_interval']
            print(f"   Updated refresh_interval: {config['refresh_interval']}s")
        if 'language' in current_config['general']:
            config['language'] = current_config['general']['language']
        if 'temperature_unit' in current_config['general']:
            config['temperature_unit'] = current_config['general']['temperature_unit']
    
    if success:
        return jsonify({'status': 'success', 'message': 'All settings saved'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to save settings'}), 500

@app.route('/api/settings/section/<section>', methods=['GET', 'POST'])
def api_settings_section(section):
    """Get or update a specific settings section"""
    if request.method == 'GET':
        return jsonify(get_section(section))
    else:
        # POST - update section
        data = request.json
        success = update_section(section, data)
        if success:
            return jsonify({'status': 'success', 'message': f'{section} settings saved'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save settings'}), 500

@app.route('/api/settings/restore-defaults', methods=['POST'])
def api_restore_defaults():
    """Restore all settings to defaults"""
    success = restore_defaults()
    if success:
        return jsonify({'status': 'success', 'message': 'Settings restored to defaults'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to restore defaults'}), 500

@app.route('/api/settings/export', methods=['GET'])
def api_export_settings():
    """Export settings as JSON"""
    from flask import make_response
    
    config_json = export_config()
    response = make_response(config_json)
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=mosmart_settings.json'
    return response

@app.route('/api/emergency-unmount/test', methods=['GET'])
def api_test_emergency_unmount():
    """Test emergency unmount system - validation and simulation only"""
    try:
        # Import emergency modules
        try:
            from emergency_actions import validate_unmount_conditions, get_mount_info, is_critical_mountpoint
            emergency_available = True
        except ImportError:
            emergency_available = False
        
        from config_manager import is_emergency_mode_active
        import shutil
        
        # Validation checks
        validation = {
            'emergency_module': emergency_available,
            'umount_command': shutil.which('umount') is not None,
            'current_mode': 'ACTIVE' if is_emergency_mode_active() else 'PASSIVE',
            'sudo_access': os.geteuid() == 0
        }
        
        # Simulate decisions for current disks
        simulation = []
        
        if emergency_available:
            # Get devices from current scan results
            devices = scan_all_devices()
            
            for device in devices:
                device_name = device['name']
                
                # Check both whole disk and common partitions
                partitions_to_check = [device_name]
                
                # Add common partition numbers (1-9)
                for i in range(1, 10):
                    partitions_to_check.append(f"{device_name}{i}")
                
                found_mount = False
                
                for part in partitions_to_check:
                    # Get mount info for this partition
                    mountpoint = get_mount_info(part)
                    
                    if mountpoint:
                        found_mount = True
                        is_critical = is_critical_mountpoint(mountpoint)
                        
                        # Simulate EMERGENCY decision
                        simulated_decision = {
                            'status': 'EMERGENCY',
                            'can_emergency_unmount': not is_critical
                        }
                        
                        can_proceed, reason = validate_unmount_conditions(part, f'test_{part}', simulated_decision)
                        
                        simulation.append({
                            'device': f"{device_name} ({part})",
                            'model': device.get('model', 'Unknown'),
                            'mountpoint': mountpoint,
                            'is_critical': is_critical,
                            'would_unmount': can_proceed,
                            'reason': reason
                        })
                
                # If no partition was mounted, show whole disk as not mounted
                if not found_mount:
                    simulation.append({
                        'device': device_name,
                        'model': device.get('model', 'Unknown'),
                        'mountpoint': None,
                        'is_critical': False,
                        'would_unmount': False,
                        'reason': 'Not mounted'
                    })
        
        return jsonify({
            'status': 'success',
            'validation': validation,
            'simulation': simulation
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/logs/export', methods=['GET'])
def api_export_logs():
    """Export all log files as a ZIP archive"""
    import zipfile
    from io import BytesIO
    from flask import send_file
    
    log_dir = LOG_DIR.parent  # Go up one level to include all disk logs
    
    # Create in-memory ZIP
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add all log files
        for log_file in log_dir.rglob('*.jsonl'):
            arcname = str(log_file.relative_to(log_dir))
            zf.write(log_file, arcname)
        
        for log_file in log_dir.rglob('*.json'):
            if log_file.name != 'settings.json':  # Don't export settings
                arcname = str(log_file.relative_to(log_dir))
                zf.write(log_file, arcname)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='mosmart_logs.zip'
    )

@app.route('/api/device/<device_name>/label-data')
def api_device_label_data(device_name):
    """Get formatted data for disk label printing"""
    try:
        # Find device in current scan results
        device_data = None
        for name, data in scan_results.items():
            if name == device_name:
                device_data = data
                break
        
        if not device_data:
            return jsonify({'status': 'error', 'message': 'Device not found'}), 404
        
        # Get SMART attribute 194 max temp from device_data (already extracted)
        smart_max_temp = device_data.get('max_temperature')
        
        # Get mosmart194 observed max temperature
        mosmart194_max = device_data.get('mosmart194')
        
        # Get mosmart194 average temperature
        avg_temp = None
        try:
            mosmart194_mgr = get_mosmart194_manager()
            if mosmart194_mgr and hasattr(mosmart194_mgr, 'get_statistics'):
                stats = mosmart194_mgr.get_statistics(device_name)
                if stats:
                    avg_temp = stats.get('average_temperature')
        except:
            pass
        
        # Build label data
        label_data = {
            'device_name': device_name,
            'model': device_data.get('model', 'Unknown'),
            'serial': device_data.get('serial', 'Unknown'),
            'health_score': device_data.get('health_score', 0),
            'health_rating': device_data.get('health_rating', 'Unknown'),
            'temperature': device_data.get('temperature'),
            'avg_temperature': avg_temp,
            'smart_max_temperature': smart_max_temp,
            'mosmart194_max_temperature': mosmart194_max,
            'power_on_hours': device_data.get('power_on_hours', 0),
            'total_bytes_written': device_data.get('total_bytes_written'),
            'power_cycles': device_data.get('power_cycle_count', 0),
            'reallocated_sectors': device_data.get('components', {}).get('reallocated', {}).get('value', 0),
            'pending_sectors': device_data.get('components', {}).get('pending', {}).get('value', 0),
            'uncorrectable_errors': device_data.get('components', {}).get('uncorrectable', {}).get('value', 0),
            'mosmart188': device_data.get('mosmart188', {}).get('count', 0),
            'past_failures': device_data.get('past_failures', []),
            'date': datetime.now().strftime('%d.%m.%Y'),
            'is_ssd': device_data.get('is_ssd', False)
        }
        
        return jsonify(label_data)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/logs/all')
def api_list_all_logs():
    """List all available disk logs (for disconnected/GDC disks)"""
    log_base_dir = LOG_DIR
    
    if not log_base_dir.exists():
        return jsonify({'disks': []})
    
    disks = []
    for disk_dir in log_base_dir.iterdir():
        if disk_dir.is_dir():
            # Get log files
            log_files = list(disk_dir.glob('*.jsonl'))
            if not log_files:
                continue
            
            # Read latest entry to get disk info
            latest_log = sorted(log_files, reverse=True)[0]
            latest_entry = None
            try:
                with open(latest_log, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        latest_entry = json.loads(lines[-1])
            except Exception as e:
                print(f"Error reading {latest_log}: {e}")
                continue
            
            if latest_entry:
                model = latest_entry.get('model', 'Unknown')
                serial = latest_entry.get('serial', 'Unknown')
                
                # Check for GDC history using model/serial
                has_gdc = False
                gdc_state = None
                try:
                    if model and serial and model != 'Unknown' and serial != 'Unknown':
                        gdc_worst = get_worst_gdc_state(model=model, serial=serial)
                        if gdc_worst:
                            worst_state = gdc_worst.get('worst_state', 'OK')
                            if worst_state in ['SUSPECT', 'CONFIRMED', 'TERMINAL']:
                                has_gdc = True
                                gdc_state = worst_state
                except Exception as e:
                    print(f"Error checking GDC for {model}_{serial}: {e}")
                
                disks.append({
                    'disk_id': disk_dir.name,
                    'model': model,
                    'serial': serial,
                    'last_seen': latest_entry.get('timestamp', 'Unknown'),
                    'last_health_score': latest_entry.get('health_score'),
                    'log_count': len(log_files),
                    'total_entries': sum(1 for f in log_files for _ in open(f)),
                    'has_gdc': has_gdc,
                    'gdc_state': gdc_state
                })
    
    # Sort by last_seen (most recent first)
    disks.sort(key=lambda x: x['last_seen'], reverse=True)
    
    return jsonify({'disks': disks})

@app.route('/api/logs/<model>/<serial>')
def api_view_disk_log(model, serial):
    """View raw log files for a specific disk"""
    # Create disk_id same way as disk_logger does
    disk_id = f"{model}_{serial}".replace(' ', '_').replace('/', '-')
    log_dir = LOG_DIR / disk_id
    
    if not log_dir.exists():
        return jsonify({'error': 'No logs found for this disk'}), 404
    
    # Get all log files sorted by date (oldest first for chronological reading)
    log_files = sorted(log_dir.glob('*.jsonl'), reverse=False)
    
    if not log_files:
        return jsonify({'error': 'No log entries found'}), 404
    
    # Read all log entries
    all_entries = []
    for log_file in log_files[-30:]:  # Last 30 days (from oldest to newest)
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        all_entries.append(json.loads(line))
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
    
    return jsonify({
        'disk_id': disk_id,
        'log_count': len(all_entries),
        'entries': all_entries[-100:]  # Last 100 entries
    })

@app.route('/api/logs-full/<model>/<serial>')
def api_view_disk_log_full(model, serial):
    """View FULL log files for a specific disk (all entries)"""
    # Create disk_id same way as disk_logger does
    disk_id = f"{model}_{serial}".replace(' ', '_').replace('/', '-')
    log_dir = LOG_DIR / disk_id
    
    if not log_dir.exists():
        return jsonify({'error': 'No logs found for this disk'}), 404
    
    # Get all log files sorted by date (newest first)
    log_files = sorted(log_dir.glob('*.jsonl'), reverse=True)
    
    if not log_files:
        return jsonify({'error': 'No log entries found'}), 404
    
    # Read ALL log entries (no limit)
    all_entries = []
    for log_file in log_files:  # ALL files
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        all_entries.append(json.loads(line))
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
    
    return jsonify({
        'disk_id': disk_id,
        'log_count': len(all_entries),
        'entries': all_entries  # ALL entries
    })

def main():
    parser = argparse.ArgumentParser(
        description='S.M.A.R.T. Web Monitor - Web dashboard for disk monitoring'
    )
    
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=5000,
        help='Port to run web server on (default: 5000)'
    )
    
    parser.add_argument(
        '-r', '--refresh',
        type=int,
        default=60,
        help='Auto-refresh interval in seconds (default: 60)'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    
    parser.add_argument(
        '-l', '--language',
        type=str,
        default='en',
        choices=['en', 'no'],
        help='Interface language (default: en)'
    )
    
    parser.add_argument(
        '--check-health',
        action='store_true',
        help='Check and display external health status (no WebUI)'
    )
    
    parser.add_argument(
        '--no-logging',
        action='store_true',
        help='Disable automatic health logging'
    )
    
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Run in development mode (Flask dev server)'
    )
    
    args = parser.parse_args()
    
    # Handle --check-health flag (CLI only, no WebUI)
    if args.check_health:
        health_data = get_external_health()
        print(json.dumps(health_data, indent=2))
        sys.exit(0)
    
    # Load saved settings from config_manager
    saved_config = load_config()
    
    # Check if WebUI is enabled at startup
    webui_enabled = saved_config.get('general', {}).get('enable_webui', True)
    
    # Apply command-line args (override saved settings)
    config['port'] = args.port
    config['refresh_interval'] = saved_config.get('general', {}).get('polling_interval', args.refresh)
    config['language'] = saved_config.get('general', {}).get('language', args.language)
    config['temperature_unit'] = saved_config.get('general', {}).get('temperature_unit', 'C')
    config['enable_logging'] = not args.no_logging
    
    # Load monitored devices from settings
    config['monitored_devices'] = saved_config.get('disk_selection', {}).get('monitored_devices', {})
    
    print(f"Starting S.M.A.R.T. Web Monitor...")
    if webui_enabled:
        print(f"Dashboard: http://{args.host}:{args.port}")
    else:
        print(f"⚠️  WebUI is DISABLED - Dashboard not available")
    print(f"Auto-refresh: {config['refresh_interval']} seconds")
    
    # Start background scanner thread for automatic logging
    global background_scanner_running, background_scanner_thread
    background_scanner_running = True
    background_scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    background_scanner_thread.start()
    print(f"✓ Background scanner enabled (hourly logging + change detection)")
    
    print(f"Press Ctrl+C to stop")
    
    # Run with elevated privileges warning
    if platform.system() != 'Windows' and os.geteuid() != 0:
        print("\n⚠️  Warning: Not running as root. S.M.A.R.T. data may not be accessible.")
        print("   Run with: sudo python3 web_monitor.py\n")
    
    # Only start WebUI if enabled
    if not webui_enabled:
        print("🛑 WebUI disabled. MoSMART running in background mode only.")
        # Keep process alive but don't start web server
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            background_scanner_running = False
            print("\n✓ MoSMART stopped")
            sys.exit(0)
    
    if args.dev:
        # Development server
        print("⚠️  Running Flask development server (--dev mode)")
        app.run(host=args.host, port=args.port, debug=True)
    else:
        # Production server with waitress
        try:
            from waitress import serve
            print("✓ Running production server (waitress)")
            serve(app, host=args.host, port=args.port)
        except ImportError:
            print("⚠️  waitress not installed, falling back to Flask dev server")
            print("   Install with: pip install waitress")
            app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main()
