#!/usr/bin/env python3
# MoSMART Monitor
# Copyright (C) 2026 Magnus S. Modig
# Licensed under GPLv3. See LICENSE for details.

import json
import os
from datetime import datetime
from pathlib import Path

# GDC log directory
# Use /var/lib/mosmart/gdc when running as root (systemd service)
# Use ~/.mosmart/gdc when running as regular user
if os.getuid() == 0:
    # Running as root (systemd service or sudo)
    GDC_DIR = Path('/var/lib/mosmart/gdc')
else:
    # Running as regular user
    GDC_DIR = Path.home() / '.mosmart' / 'gdc'

GDC_DIR.mkdir(parents=True, exist_ok=True)

# Global GDC history file
GDC_HISTORY_FILE = GDC_DIR / 'gdc_history.jsonl'


def log_gdc_event(device_path, event_type, gdc_state, details=None, model=None, serial=None):
    """
    Log GDC state changes to persistent storage
    
    Args:
        device_path: Device path (e.g., '/dev/sdb')
        event_type: 'state_change', 'timeout', 'success', 'disappeared'
        gdc_state: Current GDC state dict from GDCManager.to_json()
        details: Optional additional details
        model: Disk model (e.g., 'ST2000DM001-1CH164')
        serial: Disk serial number (e.g., 'S1E1YQ9T')
    """
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        'timestamp': timestamp,
        'device': device_path,
        'event_type': event_type,
        'state': gdc_state['state'],
        'counters': gdc_state['counters'],
        'has_ever_succeeded': gdc_state.get('has_ever_succeeded', False),
        'recent_status': gdc_state.get('recent_status', [])
    }
    
    # Add model/serial if available
    if model:
        log_entry['model'] = model
    if serial:
        log_entry['serial'] = serial
    
    if details:
        log_entry['details'] = details
    
    # Append to history file
    with open(GDC_HISTORY_FILE, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')


def get_gdc_history(device_path=None, model=None, serial=None, days=30):
    """
    Get GDC history for a device or all devices
    
    Args:
        device_path: Optional device path to filter by
        model: Optional disk model to filter by
        serial: Optional disk serial to filter by
        days: Number of days of history to retrieve
    
    Returns:
        List of GDC events
    """
    if not GDC_HISTORY_FILE.exists():
        return []
    
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    history = []
    with open(GDC_HISTORY_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entry_date = datetime.fromisoformat(entry['timestamp'])
                
                # Filter by date
                if entry_date < cutoff_date:
                    continue
                
                # Filter by device if specified
                if device_path and entry['device'] != device_path:
                    continue
                
                # Filter by model/serial if specified
                if model and entry.get('model') != model:
                    continue
                if serial and entry.get('serial') != serial:
                    continue
                
                history.append(entry)
            except (json.JSONDecodeError, KeyError):
                continue
    
    return history


def get_worst_gdc_state(device_path=None, model=None, serial=None):
    """
    Get the worst GDC state ever recorded for a device
    
    Args:
        device_path: Optional device path
        model: Optional disk model
        serial: Optional disk serial
    
    Returns:
        dict with 'worst_state', 'first_seen', 'last_seen', 'total_events'
        or None if no GDC history exists
    """
    history = get_gdc_history(device_path, model, serial, days=30)  # Last 30 days
    
    if not history:
        return None
    
    # State severity ranking
    state_severity = {
        'OK': 0,
        'SUSPECT': 1,
        'CONFIRMED': 2,
        'TERMINAL': 3
    }
    
    worst_state = 'OK'
    worst_severity = 0
    first_seen = None
    last_seen = None
    total_events = len(history)
    
    # Count event types
    timeouts = 0
    successes = 0
    
    for entry in history:
        state = entry.get('state', 'OK')
        severity = state_severity.get(state, 0)
        
        if severity > worst_severity:
            worst_state = state
            worst_severity = severity
        
        # Count event types
        event_type = entry.get('event_type', '')
        if event_type == 'timeout':
            timeouts += 1
        elif event_type in ['success']:
            successes += 1
        
        timestamp = entry['timestamp']
        if first_seen is None or timestamp < first_seen:
            first_seen = timestamp
        if last_seen is None or timestamp > last_seen:
            last_seen = timestamp
    
    # If worst_state is still OK but we have many timeouts, upgrade it
    if worst_state == 'OK' and timeouts >= 5:
        worst_state = 'CONFIRMED'
    elif worst_state == 'OK' and timeouts >= 3:
        worst_state = 'SUSPECT'
    
    return {
        'worst_state': worst_state,
        'first_seen': first_seen,
        'last_seen': last_seen,
        'total_events': total_events,
        'timeouts': timeouts,
        'successes': successes
    }


def has_gdc_history(device_path=None, model=None, serial=None):
    """
    Check if device has any GDC events (SUSPECT or worse) in history
    
    Args:
        device_path: Optional device path
        model: Optional disk model
        serial: Optional disk serial
    
    Returns:
        True if device has been flagged with GDC before
    """
    history = get_gdc_history(device_path, model, serial)
    
    for entry in history:
        if entry['state'] in ['SUSPECT', 'CONFIRMED', 'TERMINAL']:
            return True
    
    return False


def cleanup_old_gdc_logs(days=365):
    """Remove GDC history older than specified days"""
    if not GDC_HISTORY_FILE.exists():
        return
    
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Read all entries
    entries = []
    with open(GDC_HISTORY_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entry_date = datetime.fromisoformat(entry['timestamp'])
                
                if entry_date >= cutoff_date:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError):
                continue
    
    # Rewrite file with filtered entries
    with open(GDC_HISTORY_FILE, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')
    
    print(f"GDC cleanup: Kept {len(entries)} recent events")


def restore_gdc_state_from_history(device_path, model=None, serial=None):
    """
    Restore GDC state machine counters from history
    Used to restore state after server restart
    
    Args:
        device_path: Device path
        model: Optional disk model
        serial: Optional disk serial
    
    Returns:
        dict with counters and has_ever_succeeded flag, or None
    """
    history = get_gdc_history(device_path, model, serial, days=7)  # Last 7 days
    
    if not history:
        return None
    
    # Count events
    timeouts = 0
    successes = 0
    no_json = 0
    corrupt = 0
    disappeared = 0
    has_ever_succeeded = False
    recent_status = []
    
    for entry in history:
        event_type = entry.get('event_type', '')
        
        if event_type == 'timeout':
            timeouts += 1
            recent_status.append('timeout')
        elif event_type == 'success':
            successes += 1
            has_ever_succeeded = True
            recent_status.append('success')
        elif event_type == 'no_json':
            no_json += 1
            recent_status.append('no_json')
        elif event_type == 'corrupt':
            corrupt += 1
            recent_status.append('corrupt')
        elif event_type == 'disappeared':
            disappeared += 1
            recent_status.append('disappeared')
    
    return {
        'timeouts': timeouts,
        'successes': successes,
        'no_json': no_json,
        'corrupt': corrupt,
        'disappeared': disappeared,
        'has_ever_succeeded': has_ever_succeeded or entry.get('has_ever_succeeded', False),
        'recent_status': recent_status[-10:]  # Last 10
    }
