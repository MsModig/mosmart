#!/usr/bin/env python3
"""
MoSMART Monitor - Alert Engine

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

import json
import time
from datetime import datetime
from pathlib import Path
from enum import Enum

# Import config manager to load settings
try:
    from config_manager import load_config
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False

# Import email notifier (optional - won't break if missing)
try:
    from email_notifier import send_alert_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("⚠️ Email notifier not available")


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    SCORE_CHANGE = "score_change"
    SCORE_CRITICAL = "score_critical"
    REALLOCATED_MILESTONE = "reallocated_milestone"
    PENDING_MILESTONE = "pending_milestone"
    TEMPERATURE_WARNING = "temperature_warning"
    TEMPERATURE_CRITICAL = "temperature_critical"
    TEMPERATURE_NORMALIZED = "temperature_normalized"
    GDC_DETECTED = "gdc_detected"
    LIFETIME_REMAINING_CRITICAL = "lifetime_remaining_critical"


# Alert configuration
# Default config (fallback if config_manager not available)
DEFAULT_ALERT_CONFIG = {
    'score_change_threshold': 3,
    'critical_score': 40,
    'reallocated_milestones': [5, 10, 100, 1000, 10000],
    'pending_milestones': [1, 5, 10, 50, 100],
    'temperature_consecutive_readings': 4,
    'temperature_thresholds': {
        'ssd': {'warning': 60, 'critical': 70},
        'hdd': {'warning': 50, 'critical': 60}
    }
}

def get_alert_config():
    """Load alert configuration from settings.json via config_manager"""
    if not CONFIG_MANAGER_AVAILABLE:
        return DEFAULT_ALERT_CONFIG
    
    try:
        settings = load_config()
        
        return {
            'score_change_threshold': settings.get('health_alerts', {}).get('score_drop_threshold', 3),
            'critical_score': settings.get('health_alerts', {}).get('critical_score_limit', 40),
            'reallocated_milestones': settings.get('smart_alerts', {}).get('reallocated_milestones', [5, 10, 100, 1000, 10000]),
            'pending_milestones': settings.get('smart_alerts', {}).get('pending_milestones', [1, 5, 10, 50, 100]),
            'temperature_consecutive_readings': settings.get('temperature_alerts', {}).get('consecutive_readings', 4),
            'temperature_thresholds': {
                'ssd': {
                    'warning': settings.get('temperature_alerts', {}).get('ssd_warning', 60),
                    'critical': settings.get('temperature_alerts', {}).get('ssd_critical', 70)
                },
                'hdd': {
                    'warning': settings.get('temperature_alerts', {}).get('hdd_warning', 50),
                    'critical': settings.get('temperature_alerts', {}).get('hdd_critical', 60)
                }
            }
        }
    except Exception as e:
        print(f"Warning: Could not load alert config from settings: {e}")
        return DEFAULT_ALERT_CONFIG

# Load config once at module level (will be refreshed on each alert check)
ALERT_CONFIG = get_alert_config()

# State directory: ~/.mosmart/alerts/
ALERT_STATE_DIR = Path.home() / '.mosmart' / 'alerts'
ALERT_STATE_DIR.mkdir(parents=True, exist_ok=True)


def get_disk_identifier(device_name, model, serial):
    """Get stable disk identifier (model_serial)"""
    if model and serial:
        return f"{model}_{serial}".replace(' ', '_').replace('/', '-')
    return device_name


def load_disk_state(disk_id):
    """Load persistent state for a disk"""
    state_file = ALERT_STATE_DIR / f"{disk_id}.json"
    
    if not state_file.exists():
        return {
            'disk_id': disk_id,
            'last_score': None,
            'last_reallocated': 0,
            'last_pending': 0,
            'alerted_reallocated_milestones': [],
            'alerted_pending_milestones': [],
            'temperature_history': [],
            'last_temperature': None,
            'last_smart_status': None,  # 'ok', 'failed', None
            'gdc_flag': False,
            'lifetime_remaining_critical_alerted': False,
            'last_update': None
        }
    
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return load_disk_state.__defaults__[0]


def save_disk_state(disk_id, state):
    """Save persistent state for a disk"""
    state_file = ALERT_STATE_DIR / f"{disk_id}.json"
    state['last_update'] = datetime.now().isoformat()
    
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        print(f"Error saving alert state for {disk_id}: {e}")


def send_alert(disk_id, alert_type, severity, metric_name, old_value, new_value, message):
    """
    Central alert dispatch function
    
    Args:
        disk_id: Disk identifier (model_serial)
        alert_type: AlertType enum value
        severity: AlertSeverity enum value
        metric_name: Name of metric that changed
        old_value: Previous value
        new_value: Current value
        message: Human-readable alert message
    """
    alert_data = {
        'timestamp': datetime.now().isoformat(),
        'disk_id': disk_id,
        'alert_type': alert_type.value,
        'severity': severity.value,
        'metric': metric_name,
        'old_value': old_value,
        'new_value': new_value,
        'message': message
    }
    
    # Log to console (later route to email/webhooks/etc)
    severity_icon = {
        AlertSeverity.INFO: 'ℹ️',
        AlertSeverity.WARNING: '⚠️',
        AlertSeverity.HIGH: '🟠',
        AlertSeverity.CRITICAL: '🔴'
    }
    
    icon = severity_icon.get(severity, '•')
    print(f"{icon} ALERT [{severity.value.upper()}] {disk_id}: {message}")
    
    # Store alert history
    alert_log = ALERT_STATE_DIR / 'alert_history.jsonl'
    try:
        with open(alert_log, 'a') as f:
            f.write(json.dumps(alert_data) + '\n')
    except IOError:
        pass
    
    # Send email notification if available
    if EMAIL_AVAILABLE:
        try:
            send_alert_email(alert_data)
        except Exception as e:
            print(f"⚠️ Failed to send email: {e}")
    
    return alert_data


def check_score_alerts(disk_id, state, current_score, is_usb=False):
    """Check for score-based alerts (with USB tolerance)"""
    alerts = []
    
    if current_score is None:
        return alerts
    
    # Reload config to get latest settings
    config = get_alert_config()
    
    # Increase threshold for USB devices (they can have unreliable SMART)
    score_threshold = config['score_change_threshold']
    if is_usb:
        score_threshold = score_threshold * 2  # Double threshold for USB devices
    
    # Score change alert
    if state['last_score'] is not None:
        score_change = abs(current_score - state['last_score'])
        
        if score_change >= score_threshold:
            direction = "dropped" if current_score < state['last_score'] else "increased"
            severity = AlertSeverity.WARNING if current_score < state['last_score'] else AlertSeverity.INFO
            
            usb_note = " [USB - may be connection-related]" if is_usb else ""
            
            alert = send_alert(
                disk_id=disk_id,
                alert_type=AlertType.SCORE_CHANGE,
                severity=severity,
                metric_name='health_score',
                old_value=state['last_score'],
                new_value=current_score,
                message=f"Health score {direction} by {score_change} points ({state['last_score']} → {current_score}){usb_note}"
            )
            alerts.append(alert)
    
    # Critical score alert (only if persistent for USB)
    if current_score < config['critical_score']:
        if state['last_score'] is None or state['last_score'] >= config['critical_score']:
            # First time dropping below critical
            # For USB: Only alert if score is VERY low
            if not is_usb or current_score < 20:
                alert = send_alert(
                    disk_id=disk_id,
                    alert_type=AlertType.SCORE_CRITICAL,
                    severity=AlertSeverity.CRITICAL,
                    metric_name='health_score',
                    old_value=state['last_score'],
                    new_value=current_score,
                    message=f"Health score critically low: {current_score} (threshold: {config['critical_score']})"
                )
                alerts.append(alert)
    
    state['last_score'] = current_score
    return alerts


def check_milestone_alerts(disk_id, state, current_reallocated, current_pending):
    """Check for sector milestone alerts"""
    alerts = []
    
    # Reload config to get latest settings
    config = get_alert_config()
    
    # Reallocated sectors
    if current_reallocated is not None:
        for milestone in config['reallocated_milestones']:
            if (current_reallocated >= milestone and 
                state['last_reallocated'] < milestone and 
                milestone not in state['alerted_reallocated_milestones']):
                
                severity = AlertSeverity.CRITICAL if milestone >= 1000 else AlertSeverity.HIGH
                
                alert = send_alert(
                    disk_id=disk_id,
                    alert_type=AlertType.REALLOCATED_MILESTONE,
                    severity=severity,
                    metric_name='reallocated_sectors',
                    old_value=state['last_reallocated'],
                    new_value=current_reallocated,
                    message=f"Reallocated sectors crossed {milestone} ({current_reallocated} sectors)"
                )
                alerts.append(alert)
                state['alerted_reallocated_milestones'].append(milestone)
        
        state['last_reallocated'] = current_reallocated
    
    # Pending sectors
    if current_pending is not None:
        for milestone in config['pending_milestones']:
            if (current_pending >= milestone and 
                state['last_pending'] < milestone and 
                milestone not in state['alerted_pending_milestones']):
                
                severity = AlertSeverity.HIGH if milestone >= 10 else AlertSeverity.WARNING
                
                alert = send_alert(
                    disk_id=disk_id,
                    alert_type=AlertType.PENDING_MILESTONE,
                    severity=severity,
                    metric_name='pending_sectors',
                    old_value=state['last_pending'],
                    new_value=current_pending,
                    message=f"Pending sectors crossed {milestone} ({current_pending} sectors)"
                )
                alerts.append(alert)
                state['alerted_pending_milestones'].append(milestone)
        
        state['last_pending'] = current_pending
    
    return alerts


def check_temperature_alerts(disk_id, state, current_temp, is_ssd):
    """Check for temperature alerts with stability logic"""
    alerts = []
    
    if current_temp is None:
        return alerts
    
    # Reload config to get latest settings
    config = get_alert_config()
    
    # Get thresholds
    disk_type = 'ssd' if is_ssd else 'hdd'
    thresholds = config['temperature_thresholds'][disk_type]
    
    # Update temperature history
    state['temperature_history'].append(current_temp)
    state['temperature_history'] = state['temperature_history'][-config['temperature_consecutive_readings']:]
    
    # Need full history to check
    if len(state['temperature_history']) < config['temperature_consecutive_readings']:
        state['last_temperature'] = current_temp
        return alerts
    
    # Check if all recent readings exceed threshold
    all_above_critical = all(t >= thresholds['critical'] for t in state['temperature_history'])
    all_above_warning = all(t >= thresholds['warning'] for t in state['temperature_history'])
    all_below_warning = all(t < thresholds['warning'] for t in state['temperature_history'])
    
    prev_temp = state['last_temperature']
    
    # Critical temperature alert
    if all_above_critical:
        if prev_temp is None or prev_temp < thresholds['critical']:
            alert = send_alert(
                disk_id=disk_id,
                alert_type=AlertType.TEMPERATURE_CRITICAL,
                severity=AlertSeverity.CRITICAL,
                metric_name='temperature',
                old_value=prev_temp,
                new_value=current_temp,
                message=f"Temperature critically high: {current_temp}°C (threshold: {thresholds['critical']}°C, {disk_type.upper()})"
            )
            alerts.append(alert)
    
    # Warning temperature alert
    elif all_above_warning:
        if prev_temp is None or prev_temp < thresholds['warning']:
            alert = send_alert(
                disk_id=disk_id,
                alert_type=AlertType.TEMPERATURE_WARNING,
                severity=AlertSeverity.WARNING,
                metric_name='temperature',
                old_value=prev_temp,
                new_value=current_temp,
                message=f"Temperature elevated: {current_temp}°C (threshold: {thresholds['warning']}°C, {disk_type.upper()})"
            )
            alerts.append(alert)
    
    # Temperature normalized
    elif all_below_warning:
        if prev_temp is not None and prev_temp >= thresholds['warning']:
            alert = send_alert(
                disk_id=disk_id,
                alert_type=AlertType.TEMPERATURE_NORMALIZED,
                severity=AlertSeverity.INFO,
                metric_name='temperature',
                old_value=prev_temp,
                new_value=current_temp,
                message=f"Temperature normalized: {current_temp}°C (was {prev_temp}°C)"
            )
            alerts.append(alert)
    
    state['last_temperature'] = current_temp
    return alerts


def check_gdc_alert(disk_id, state, is_responsive, has_smart_data):
    """Check for Ghost Drive Condition"""
    alerts = []
    
    current_status = 'ok' if (is_responsive and has_smart_data) else 'failed'
    
    # GDC condition: Previously worked, now consistently fails
    if state['last_smart_status'] == 'ok' and current_status == 'failed':
        if not state['gdc_flag']:
            alert = send_alert(
                disk_id=disk_id,
                alert_type=AlertType.GDC_DETECTED,
                severity=AlertSeverity.CRITICAL,
                metric_name='smart_status',
                old_value='ok',
                new_value='failed',
                message=f"Ghost Drive Condition detected - disk previously delivered SMART but now fails consistently"
            )
            alerts.append(alert)
            state['gdc_flag'] = True
    
    # Reset GDC flag if disk recovers
    elif current_status == 'ok' and state['gdc_flag']:
        state['gdc_flag'] = False
    
    state['last_smart_status'] = current_status
    return alerts


def check_lifetime_remaining_alert(disk_id, state, lifetime_remaining):
    """Check for SMART ID 202 lifetime remaining critical alert (<=5%)"""
    alerts = []

    if lifetime_remaining is None:
        return alerts

    if lifetime_remaining <= 5 and not state.get('lifetime_remaining_critical_alerted'):
        alert = send_alert(
            disk_id=disk_id,
            alert_type=AlertType.LIFETIME_REMAINING_CRITICAL,
            severity=AlertSeverity.CRITICAL,
            metric_name='lifetime_remaining',
            old_value=None,
            new_value=lifetime_remaining,
            message=f"Lifetime remaining critically low: {lifetime_remaining}% (SMART ID 202)"
        )
        alerts.append(alert)
        state['lifetime_remaining_critical_alerted'] = True

    return alerts


def process_disk_alerts(device_data):
    """
    Main entry point - process all alerts for a single disk
    
    Args:
        device_data: Dict with disk information from your backend
            Required keys: name, model, serial, health_score, temperature,
                          is_ssd, responsive, components (with reallocated/pending),
                          is_usb (optional)
    
    Returns:
        List of alert dicts that were triggered
    """
    # Get stable disk identifier
    disk_id = get_disk_identifier(
        device_data.get('name', 'unknown'),
        device_data.get('model'),
        device_data.get('serial')
    )
    
    # Check if USB device - reduce alert sensitivity
    is_usb = device_data.get('is_usb', False)
    
    # Load state
    state = load_disk_state(disk_id)
    
    all_alerts = []
    
    # Extract metrics
    current_score = device_data.get('health_score')
    current_temp = device_data.get('temperature')
    is_ssd = device_data.get('is_ssd', False)
    is_responsive = device_data.get('responsive', False)
    components = device_data.get('components', {})
    lifetime_remaining = device_data.get('lifetime_remaining')
    
    current_reallocated = components.get('reallocated', {}).get('value') if components else None
    current_pending = components.get('pending', {}).get('value') if components else None
    has_smart_data = current_score is not None
    
    # Run all alert checks (skip SMART value alerts for USB devices)
    all_alerts.extend(check_score_alerts(disk_id, state, current_score, is_usb=is_usb))
    if not is_usb:
        # USB devices: Skip reallocated/pending alerts (unreliable via USB)
        all_alerts.extend(check_milestone_alerts(disk_id, state, current_reallocated, current_pending))
    all_alerts.extend(check_temperature_alerts(disk_id, state, current_temp, is_ssd))
    all_alerts.extend(check_gdc_alert(disk_id, state, is_responsive, has_smart_data))
    all_alerts.extend(check_lifetime_remaining_alert(disk_id, state, lifetime_remaining))
    
    # Save updated state
    save_disk_state(disk_id, state)
    
    return all_alerts


def get_disk_alert_status(device_data):
    """
    Get current alert status for UI display
    
    Returns:
        dict with 'status' (ok/warning/high/critical/gdc) and 'icon'
    """
    disk_id = get_disk_identifier(
        device_data.get('name', 'unknown'),
        device_data.get('model'),
        device_data.get('serial')
    )
    
    state = load_disk_state(disk_id)
    
    # Check GDC
    if state.get('gdc_flag'):
        return {'status': 'gdc', 'icon': '👻', 'label_key': 'gdc_detected'}
    
    # Check score
    score = device_data.get('health_score')
    config = get_alert_config()
    if score is not None and score < config['critical_score']:
        return {'status': 'critical', 'icon': '🔴', 'label_key': 'critical'}
    
    # Check temperature
    temp = device_data.get('temperature')
    is_ssd = device_data.get('is_ssd', False)
    if temp is not None:
        disk_type = 'ssd' if is_ssd else 'hdd'
        thresholds = config['temperature_thresholds'][disk_type]
        
        if temp >= thresholds['critical']:
            return {'status': 'critical', 'icon': '🔴', 'label_key': 'critical'}
        elif temp >= thresholds['warning']:
            return {'status': 'warning', 'icon': '⚠️', 'label_key': 'warning'}
    
    # Check reallocated sectors
    components = device_data.get('components', {})
    reallocated = components.get('reallocated', {}).get('value') if components else 0
    if reallocated and reallocated >= 1000:
        return {'status': 'high', 'icon': '🟠', 'label_key': 'high_risk'}
    elif reallocated and reallocated >= 10:
        return {'status': 'warning', 'icon': '⚠️', 'label_key': 'warning'}
    
    return {'status': 'ok', 'icon': '✓', 'label_key': 'ok'}


def get_recent_alerts(hours=24):
    """Get recent alerts from history"""
    from datetime import timedelta
    
    alert_log = ALERT_STATE_DIR / 'alert_history.jsonl'
    if not alert_log.exists():
        return []
    
    cutoff = datetime.now() - timedelta(hours=hours)
    alerts = []
    
    try:
        with open(alert_log, 'r') as f:
            for line in f:
                try:
                    alert = json.loads(line.strip())
                    alert_time = datetime.fromisoformat(alert['timestamp'])
                    if alert_time >= cutoff:
                        alerts.append(alert)
                except (json.JSONDecodeError, KeyError):
                    continue
    except IOError:
        pass
    
    return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)
