#!/usr/bin/env python3
"""
Device Lifecycle Logger - Tracks device appearance/disappearance events
Logs device additions, removals, and path changes without breaking existing logic
"""

from datetime import datetime
from pathlib import Path
import json
from typing import Optional

class DeviceLifecycleLogger:
    """
    Logs device lifecycle events:
    - Device first detected
    - Device removed
    - Device reappeared
    - USB device connected/disconnected
    - Device path changed
    """
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path.home() / '.mosmart' / 'device_events'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'lifecycle.jsonl'
    
    def _log_event(self, event_type: str, device_id: str, model: str, serial: str, details: dict = None):
        """Write a lifecycle event to the log"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'device_id': device_id,
            'model': model,
            'serial': serial,
            'details': details or {}
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            print(f"Error logging lifecycle event: {e}")
    
    def log_device_added(self, device_id: str, model: str, serial: str, device_path: str, is_usb: bool = False):
        """Log when a new device is detected"""
        self._log_event(
            'DEVICE_ADDED',
            device_id,
            model,
            serial,
            {
                'device_path': device_path,
                'is_usb': is_usb,
                'message': f"New device detected: {model} {serial} at {device_path}"
            }
        )
    
    def log_device_removed(self, device_id: str, model: str, serial: str, last_state: str = None):
        """Log when a device is no longer detected"""
        self._log_event(
            'DEVICE_REMOVED',
            device_id,
            model,
            serial,
            {
                'last_state': last_state,
                'message': f"Device removed: {model} {serial} — last known state was {last_state or 'unknown'}"
            }
        )
    
    def log_usb_disconnected(self, device_id: str, model: str, serial: str):
        """Log USB device disconnection (normal behavior, not an error)"""
        self._log_event(
            'USB_DISCONNECTED',
            device_id,
            model,
            serial,
            {
                'message': f"USB disconnected: {model} {serial}"
            }
        )
    
    def log_device_reconnected(self, device_id: str, model: str, serial: str, device_path: str, was_missing_for: str = None, previous_removal_reason: str = None):
        """Log when a previously removed device comes back"""
        details = {
            'device_path': device_path,
            'message': f"Device reconnected: {model} {serial}"
        }
        if was_missing_for:
            details['was_missing_for'] = was_missing_for
        if previous_removal_reason:
            details['previous_removal_reason'] = previous_removal_reason
            details['message'] += f" (was: {previous_removal_reason})"
        
        self._log_event(
            'DEVICE_RECONNECTED',
            device_id,
            model,
            serial,
            details
        )
    
    def log_device_path_changed(self, device_id: str, model: str, serial: str, old_path: str, new_path: str):
        """Log when a device changes /dev path"""
        self._log_event(
            'PATH_CHANGED',
            device_id,
            model,
            serial,
            {
                'old_path': old_path,
                'new_path': new_path,
                'message': f"Device path changed: {model} {serial} moved from {old_path} to {new_path}"
            }
        )
    
    def log_device_replaced(self, old_device_id: str, new_device_id: str, device_path: str, old_model: str, old_serial: str, new_model: str, new_serial: str):
        """Log when a different device appears on the same /dev path"""
        self._log_event(
            'DEVICE_REPLACED',
            new_device_id,
            new_model,
            new_serial,
            {
                'old_device_id': old_device_id,
                'old_model': old_model,
                'old_serial': old_serial,
                'device_path': device_path,
                'message': f"New device detected on {device_path}: {new_model} {new_serial} (replaced previous device {old_model} {old_serial})"
            }
        )
    
    def log_gdc_confirmed(self, device_id: str, model: str, serial: str, timeout_count: int):
        """Log when GDC (Ghost Drive Condition) is confirmed"""
        self._log_event(
            'GDC_CONFIRMED',
            device_id,
            model,
            serial,
            {
                'timeout_count': timeout_count,
                'message': f"GDC confirmed for {model} {serial} after {timeout_count} failed attempts"
            }
        )
    
    def log_stuck_device(self, device_name: str, elapsed_seconds: float):
        """Log when a device appears stuck in placeholder state"""
        self._log_event(
            'DEVICE_STUCK',
            device_name,
            'Unknown',
            'Unknown',
            {
                'device_name': device_name,
                'elapsed_seconds': round(elapsed_seconds, 1),
                'message': f"Watchdog: Device {device_name} stuck in placeholder state for {elapsed_seconds:.0f}s - possible scan hang"
            }
        )
    
    def get_recent_events(self, limit: int = 100) -> list:
        """Get recent lifecycle events"""
        events = []
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    for line in f:
                        try:
                            events.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"Error reading lifecycle log: {e}")
        
        return events[-limit:] if events else []
