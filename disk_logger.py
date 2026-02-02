#!/usr/bin/env python3
"""
MoSMART Monitor - Disk Health Logger

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
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from pySMART import DeviceList
from smart_monitor import calculate_health_score
from config_manager import is_emergency_mode_active

# Decision engine is currently running in PASSIVE MODE.
# Output is logged only. No actions are taken based on decisions.
try:
    from decision_engine import evaluate_disk_health
    DECISION_ENGINE_AVAILABLE = True
except ImportError:
    DECISION_ENGINE_AVAILABLE = False
    print("Warning: decision_engine not available, passive monitoring disabled")

# Emergency actions module for ACTIVE mode
try:
    from emergency_actions import emergency_unmount_disk
    EMERGENCY_ACTIONS_AVAILABLE = True
except ImportError:
    EMERGENCY_ACTIONS_AVAILABLE = False

# Log directory structure: ~/.mosmart/logs/{disk_id}/YYYY-MM-DD.jsonl
LOG_DIR = Path.home() / '.mosmart' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Maximum log file size before rotation (1024 KB = 1 MB)
MAX_LOG_SIZE_KB = 1024

# In-memory tracking for periodic and change-based logging
# Structure: {disk_id: {'last_hour': int, 'reallocated': int, 'pending': int}}
_last_logged_state = {}


def get_disk_identifier(device):
    """Get unique disk identifier (model + serial)"""
    return f"{device.model}_{device.serial}".replace(' ', '_').replace('/', '-')


def get_disk_identifier_from_parts(model, serial):
    """Get unique disk identifier from model and serial parts"""
    return f"{model}_{serial}".replace(' ', '_').replace('/', '-')


def _get_smart_critical_values(device):
    """Extract Reallocated Sectors (5) and Pending Sectors (197) from device"""
    if not device.attributes:
        return None, None
    
    def get_attr_value(attr_id: int) -> int:
        attr = next((a for a in device.attributes if a and a.num == attr_id), None)
        if attr and attr.raw:
            try:
                return int(str(attr.raw).split()[0])
            except (ValueError, TypeError):
                return 0
        return 0
    
    reallocated = get_attr_value(5)   # Reallocated Sectors Count
    pending = get_attr_value(197)     # Current Pending Sector Count
    return reallocated, pending


def _should_log(device, force=False):
    """
    Determine if logging should occur based on:
    1. Force flag (manual scan)
    2. Hour has changed since last log (periodic hourly logging)
    3. Reallocated Sectors or Pending Sectors values have changed
    
    Returns: (should_log: bool, reason: str)
    """
    if force:
        return True, "manual"
    
    disk_id = get_disk_identifier(device)
    current_hour = datetime.now().hour
    reallocated, pending = _get_smart_critical_values(device)
    
    # If we can't read SMART values, only log on force (manual) or hourly
    if reallocated is None or pending is None:
        if force:
            return True, "manual"
        # Check if hour has changed (periodic logging for non-SMART disks)
        if disk_id not in _last_logged_state:
            _last_logged_state[disk_id] = {'last_hour': current_hour}
            return True, "first_scan"
        if _last_logged_state[disk_id].get('last_hour') != current_hour:
            _last_logged_state[disk_id]['last_hour'] = current_hour
            return True, "hourly"
        return False, None
    
    # Check if this is first time seeing this disk
    if disk_id not in _last_logged_state:
        _last_logged_state[disk_id] = {
            'last_hour': current_hour,
            'reallocated': reallocated,
            'pending': pending
        }
        return True, "first_scan"
    
    last_state = _last_logged_state[disk_id]
    
    # Check if hour has changed
    if last_state['last_hour'] != current_hour:
        _last_logged_state[disk_id]['last_hour'] = current_hour
        _last_logged_state[disk_id]['reallocated'] = reallocated
        _last_logged_state[disk_id]['pending'] = pending
        return True, "hourly"
    
    # Check if critical values have changed
    if (last_state['reallocated'] != reallocated or 
        last_state['pending'] != pending):
        _last_logged_state[disk_id]['reallocated'] = reallocated
        _last_logged_state[disk_id]['pending'] = pending
        return True, "smart_change"
    
    return False, None


def cleanup_old_logs(disk_dir, max_size_kb=MAX_LOG_SIZE_KB):
    """Remove oldest log files if total size exceeds max_size_kb"""
    if not disk_dir.exists():
        return
    
    # Get all log files sorted by modification time (oldest first)
    log_files = sorted(disk_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime)
    
    # Calculate total size in KB
    total_size_kb = sum(f.stat().st_size for f in log_files) / 1024
    
    # Remove oldest files until under limit
    while total_size_kb > max_size_kb and len(log_files) > 1:
        oldest_file = log_files.pop(0)
        file_size_kb = oldest_file.stat().st_size / 1024
        oldest_file.unlink()
        total_size_kb -= file_size_kb
        print(f"Removed old log: {oldest_file.name} ({file_size_kb:.1f} KB)")


def log_disk_health(device, force=False, is_usb=False, mosmart188_penalty=0, mosmart188_count=0):
    """
    Log health data for a specific disk.
    
    Args:
        device: Device object from pySMART
        force: If True, always log (manual scan). If False, only log when:
               - Hour has changed (periodic hourly logging)
               - Reallocated Sectors or Pending Sectors have changed
        is_usb: If True, marks the log entry as USB device
        mosmart188_penalty: Health penalty from mosmart188_manager (-100 to 0)
        mosmart188_count: Restart count in last 24h (for display)
    
    Returns:
        (log_file, log_entry) if logged, (None, None) if skipped
    """
    # Check if we should log
    should_log, reason = _should_log(device, force=force)
    if not should_log:
        return None, None
    
    disk_id = get_disk_identifier(device)
    disk_dir = LOG_DIR / disk_id
    disk_dir.mkdir(parents=True, exist_ok=True)
    
    # Create daily log file
    today = date.today().isoformat()
    log_file = disk_dir / f"{today}.jsonl"
    
    # Calculate health score with mosmart188 penalty and count
    health_score = calculate_health_score(device, mosmart188_penalty, mosmart188_count)
    
    # Create log entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'device_name': f"[USB] {device.name}" if is_usb else device.name,
        'model': device.model,
        'serial': device.serial,
        'capacity': device.capacity,
        'temperature': device.temperature,
        'assessment': device.assessment,
        'health_score': health_score['total'],
        'is_ssd': health_score.get('is_ssd', False),
        'is_usb': is_usb,
        'log_reason': reason,  # Track why this log entry was created
        'components': {}
    }
    
    # Add component scores
    if health_score.get('components'):
        for comp_name, comp_data in health_score['components'].items():
            log_entry['components'][comp_name] = {
                'value': comp_data['value'],
                'score': comp_data['score']
            }
    
    # Decision engine is currently running in PASSIVE MODE.
    # Output is logged only. No actions are taken based on decisions.
    if DECISION_ENGINE_AVAILABLE:
        decision = _evaluate_passive_decision(device, log_entry, disk_id, is_usb)
        if decision:
            log_entry['decision_engine'] = decision
            log_entry['decision_engine_mode'] = 'PASSIVE'
            
            # Emergency unmount in ACTIVE mode
            if decision['status'] == 'EMERGENCY' and decision.get('can_emergency_unmount', False):
                if is_emergency_mode_active():
                    # ACTIVE MODE: Attempt emergency unmount
                    if EMERGENCY_ACTIONS_AVAILABLE:
                        success = emergency_unmount_disk(device.name, disk_id, decision)
                        log_entry['emergency_unmount_attempted'] = True
                        log_entry['emergency_unmount_success'] = success
                    else:
                        # Module not available
                        log_entry['emergency_unmount_blocked_reason'] = 'MODULE_NOT_AVAILABLE'
                        print(f"⚠️  [EMERGENCY] {device.name}: ACTIVE mode enabled but emergency_actions.py not available")
                else:
                    # PASSIVE MODE: Log only
                    log_entry['emergency_unmount_blocked_reason'] = 'PASSIVE_MODE'
    
    # Append to log file (JSONL format - one JSON object per line)
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    # Cleanup old logs if total size exceeds limit
    cleanup_old_logs(disk_dir, MAX_LOG_SIZE_KB)
    
    return log_file, log_entry

def _get_previous_log_entry(disk_id):
    """
    Get the most recent log entry for a disk to support decision engine.
    
    Returns:
        dict or None: Previous log entry if found
    """
    disk_dir = LOG_DIR / disk_id
    if not disk_dir.exists():
        return None
    
    # Get all JSONL files sorted by date (newest first)
    log_files = sorted(disk_dir.glob('*.jsonl'), reverse=True)
    
    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    # Get last entry from file
                    last_line = lines[-1].strip()
                    if last_line:
                        return json.loads(last_line)
        except (json.JSONDecodeError, IOError):
            continue
    
    return None


def _evaluate_passive_decision(device, log_entry, disk_id, is_usb):
    """
    Evaluate disk health using decision engine in PASSIVE mode.
    
    Decision engine is currently running in PASSIVE MODE.
    Output is logged only. No actions are taken based on decisions.
    
    Args:
        device: pySMART device object
        log_entry: Current log entry being created
        disk_id: Disk identifier
        is_usb: Whether disk is USB connected
    
    Returns:
        dict: Decision engine output or None if evaluation fails
    """
    try:
        # Get previous log entry
        previous = _get_previous_log_entry(disk_id)
        
        # Extract current values
        current_reallocated = log_entry.get('components', {}).get('reallocated', {}).get('value', 0)
        current_pending = log_entry.get('components', {}).get('pending', {}).get('value', 0)
        current_temp = log_entry.get('temperature', 0) or 0
        current_health = log_entry.get('health_score', 100)
        
        # Extract previous values
        if previous:
            prev_reallocated = previous.get('components', {}).get('reallocated', {}).get('value', 0)
            prev_pending = previous.get('components', {}).get('pending', {}).get('value', 0)
            prev_health = previous.get('health_score', 100)
        else:
            # First scan - no previous data
            prev_reallocated = None
            prev_pending = None
            prev_health = None
        
        # Detect connection type
        connection_type = "USB" if is_usb else "INTERNAL"
        
        # Detect if system disk (check common mount points)
        is_system_disk = False
        # Note: We don't have mount point info in device object here,
        # so we default to False. This could be enhanced later.
        
        # Build decision engine input
        engine_input = {
            "reallocated_sectors": {
                "current": current_reallocated,
                "previous": prev_reallocated
            },
            "pending_sectors": {
                "current": current_pending,
                "previous": prev_pending
            },
            "temperature": current_temp,
            "health_score": current_health,
            "previous_health_score": prev_health,
            "connection_type": connection_type,
            "limited_smart": False,
            "is_system_disk": is_system_disk
        }
        
        # Get decision (PASSIVE - no actions taken)
        decision = evaluate_disk_health(engine_input)
        
        # Log decision for observation
        print(f"🔍 [PASSIVE DECISION ENGINE] {device.name}: {decision['status']} - {len(decision['reasons'])} reasons")
        
        return decision
        
    except Exception as e:
        print(f"Warning: Decision engine evaluation failed for {device.name}: {e}")
        return None

def detect_warnings(entries):
    """Detect warnings in health history (sudden drops in score)"""
    warnings = []
    
    for i in range(1, len(entries)):
        prev_score = entries[i-1].get('health_score')
        curr_score = entries[i].get('health_score')
        
        if prev_score is None or curr_score is None:
            continue
        
        # Detect significant drops (>5 points in one reading)
        drop = prev_score - curr_score
        if drop >= 5:
            warnings.append({
                'timestamp': entries[i]['timestamp'],
                'type': 'score_drop',
                'severity': 'critical' if drop >= 10 else 'warning',
                'message': f'Health score dropped {drop} points',
                'from_score': prev_score,
                'to_score': curr_score
            })
        
        # Detect new reallocated sectors
        prev_realloc = entries[i-1].get('components', {}).get('reallocated', {}).get('value', 0)
        curr_realloc = entries[i].get('components', {}).get('reallocated', {}).get('value', 0)
        if curr_realloc > prev_realloc:
            warnings.append({
                'timestamp': entries[i]['timestamp'],
                'type': 'reallocated_increase',
                'severity': 'warning',
                'message': f'New reallocated sectors: {curr_realloc - prev_realloc}',
                'from_value': prev_realloc,
                'to_value': curr_realloc
            })
    
    return warnings


def get_disk_history(model, serial, days=30):
    """Get historical data for a specific disk"""
    disk_id = f"{model}_{serial}".replace(' ', '_').replace('/', '-')
    disk_dir = LOG_DIR / disk_id
    
    if not disk_dir.exists():
        return []
    
    # Read all log files
    entries = []
    
    # Get all JSONL files in disk directory
    for log_file in sorted(disk_dir.glob('*.jsonl')):
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entries.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue
    
    # Sort entries by timestamp to ensure chronological order
    entries.sort(key=lambda x: x['timestamp'])
    
    return entries


def get_recent_warnings(model, serial, days=7):
    """Get recent warnings for a disk (last 7 days)"""
    try:
        entries = get_disk_history(model, serial, days)
        if not entries or len(entries) < 2:
            return []
        return detect_warnings(entries)
    except Exception as e:
        print(f"Error getting warnings for {model}: {e}")
        return []


def log_all_disks():
    """Log health for all detected disks (force=True for manual invocation)"""
    try:
        devlist = DeviceList()
        logged_disks = []
        
        for dev in devlist.devices:
            if dev is None:
                continue
            
            try:
                log_file, entry = log_disk_health(dev, force=True)
                if log_file and entry:
                    logged_disks.append({
                        'disk': f"{dev.model} ({dev.serial})",
                        'score': entry['health_score'],
                        'log_file': str(log_file)
                    })
            except Exception as e:
                print(f"Error logging {dev.name}: {e}")
        
        return logged_disks
    except Exception as e:
        print(f"Error scanning devices: {e}")
        return []


def main():
    """Main entry point for manual logging"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Log S.M.A.R.T. health data')
    parser.add_argument('-d', '--days', type=int, default=30,
                       help='Days of history to show (default: 30)')
    parser.add_argument('--history', action='store_true',
                       help='Show historical data')
    parser.add_argument('--model', type=str, help='Disk model for history')
    parser.add_argument('--serial', type=str, help='Disk serial for history')
    
    args = parser.parse_args()
    
    if args.history and args.model and args.serial:
        # Show history
        history = get_disk_history(args.model, args.serial, args.days)
        print(f"\nHistory for {args.model} ({args.serial}) - Last {args.days} days:")
        print(f"{'Timestamp':<25} {'Score':<10} {'Temp':<10} {'Status'}")
        print("-" * 60)
        for entry in history:
            timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            score = entry.get('health_score', 'N/A')
            temp = f"{entry.get('temperature', 'N/A')}°C"
            status = entry.get('assessment', 'N/A')
            print(f"{timestamp:<25} {score:<10} {temp:<10} {status}")
    else:
        # Log all disks
        print("Logging disk health...")
        logged = log_all_disks()
        
        print(f"\nLogged {len(logged)} disk(s):")
        for disk_info in logged:
            print(f"  • {disk_info['disk']}: Score {disk_info['score']}")
            print(f"    Log: {disk_info['log_file']}")


if __name__ == '__main__':
    main()


def log_usb_event(model, serial, device_name, event_type):
    """
    Log USB connection/disconnection event to disk's log file.
    
    Args:
        model: Disk model
        serial: Disk serial number
        device_name: Device name (e.g., 'sdh')
        event_type: 'connected', 'disconnected', or 'reconnected'
    
    Returns:
        log_file path if logged, None otherwise
    """
    if not model or not serial:
        return None
    
    disk_id = get_disk_identifier_from_parts(model, serial)
    disk_dir = LOG_DIR / disk_id
    disk_dir.mkdir(parents=True, exist_ok=True)
    
    # Create daily log file
    today = date.today().isoformat()
    log_file = disk_dir / f"{today}.jsonl"
    
    # Create USB event entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': f'usb_{event_type}',
        'device_name': device_name,
        'model': model,
        'serial': serial,
        'message': f'USB disk {event_type}',
        'is_usb_event': True
    }
    
    # Append to log file (JSONL format)
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    return log_file


def log_gdc_event_to_disk(model, serial, device_name, old_state, new_state):
    """
    Log GDC state change to disk's log file for GUI visibility.
    
    Args:
        model: Disk model
        serial: Disk serial number
        device_name: Device name (e.g., 'sdi')
        old_state: Previous GDC state
        new_state: New GDC state
    
    Returns:
        log_file path if logged, None otherwise
    """
    if not model or not serial:
        return None
    
    disk_id = get_disk_identifier_from_parts(model, serial)
    disk_dir = LOG_DIR / disk_id
    disk_dir.mkdir(parents=True, exist_ok=True)
    
    # Create daily log file
    today = date.today().isoformat()
    log_file = disk_dir / f"{today}.jsonl"
    
    # Create GDC event message
    if new_state == 'SUSPECT':
        message = '⚠️ Ghost Drive Condition SUSPECTED - Disk showing early warning signs'
    elif new_state == 'CONFIRMED':
        message = '💀 Ghost Drive Condition CONFIRMED - Disk reliability compromised'
    elif new_state == 'TERMINAL':
        message = '☠️ Ghost Drive Condition TERMINAL - Disk should be replaced immediately'
    elif new_state == 'OK' and old_state in ['SUSPECT', 'CONFIRMED', 'TERMINAL']:
        message = '✅ GDC status REVOKED - Disk recovered and delivering reliable data'
    else:
        message = f'GDC state change: {old_state} → {new_state}'
    
    # Create GDC event entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': 'gdc_state_change',
        'device_name': device_name,
        'model': model,
        'serial': serial,
        'old_state': old_state,
        'new_state': new_state,
        'message': message,
        'is_gdc_event': True
    }
    
    # Append to log file (JSONL format)
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    print(f"📝 GDC event logged to disk log: {message}")
    return log_file

def log_system_event_uncontrolled_shutdown(affected_disk_ids, timestamp=None, affected_count=None):
    """
    Log a system event 'Uncontrolled shutdown' to each affected disk's log file.

    Args:
        affected_disk_ids: Iterable of disk_id strings (model_serial format used in logs)
        timestamp: Optional datetime or ISO string; defaults to now
        affected_count: Optional int; number of affected disks for message context

    Returns:
        dict: {disk_id: log_file_path} for successfully logged disks
    """
    results = {}
    from datetime import datetime
    if timestamp is None:
        ts_iso = datetime.now().isoformat()
    else:
        if isinstance(timestamp, str):
            ts_iso = timestamp
        else:
            ts_iso = timestamp.isoformat()

    count = affected_count if affected_count is not None else (len(affected_disk_ids) if affected_disk_ids else 0)

    for disk_id in set(affected_disk_ids or []):
        try:
            disk_dir = LOG_DIR / disk_id
            disk_dir.mkdir(parents=True, exist_ok=True)
            today = date.today().isoformat()
            log_file = disk_dir / f"{today}.jsonl"

            log_entry = {
                'timestamp': ts_iso,
                'event_type': 'system_uncontrolled_shutdown',
                'message': 'Ukontrollert avslutning oppdaget',
                'affected_disks_count': count,
                'is_system_event': True,
                'note': 'Dette påvirker ikke diskens mekaniske helse.'
            }

            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

            results[disk_id] = str(log_file)
        except Exception as e:
            print(f"⚠️ Failed to log system event for {disk_id}: {e}")
            continue

    return results
