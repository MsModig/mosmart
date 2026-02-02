#!/usr/bin/env python3
# MoSMART Monitor
# Copyright (C) 2026 Magnus S. Modig
# Licensed under GPLv3. See LICENSE for details.

import json
from pathlib import Path
from typing import Dict, Any

# Configuration file location
CONFIG_DIR = Path.home() / '.mosmart'
CONFIG_FILE = CONFIG_DIR / 'settings.json'

# Default configuration
DEFAULT_CONFIG = {
    # General Settings
    'general': {
        'language': 'no',
        'polling_interval': 60,
        'temperature_unit': 'C'
    },
    
    # Disk Selection
    'disk_selection': {
        'monitored_devices': {},  # Device-specific enable/disable
        'ignore_removable_usb': False
    },
    
    # Health Score Alerts
    'health_alerts': {
        'score_drop_threshold': 3,
        'critical_score_limit': 40
    },
    
    # SMART Attribute Alerts
    'smart_alerts': {
        'reallocated_milestones': [5, 10, 100, 1000, 10000],
        'pending_milestones': [1, 5, 10, 50, 100],
        'uncorrectable_threshold': 1,
        'timeout_threshold': 5
    },
    
    # Temperature Alerts
    'temperature_alerts': {
        'ssd_warning': 60,
        'ssd_critical': 70,
        'hdd_warning': 50,
        'hdd_critical': 60,
        'consecutive_readings': 4,
        'alert_on_normalize': True
    },
    
    # Ghost Drive Detection
    'gdc': {
        'enabled': True,
        'failed_polls_threshold': 5
    },
    
    # Logging
    'logging': {
        'retention_size_kb': 1024,
        'rolling_logs': True,  # True = rolling, False = per-day
        'verbosity': 'info'  # 'debug', 'info', 'warning', 'error'
    },
    
    # Emergency Unmount
    'emergency_unmount': {
        'mode': 'PASSIVE',  # 'PASSIVE' (log only) or 'ACTIVE' (unmount on EMERGENCY)
        'require_confirmation': True  # Future: require manual confirmation before unmount
    },
    
    # Alert Channels (placeholders)
    'alert_channels': {
        'email': {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_username': '',
            'smtp_password': '',
            'from_email': '',
            'to_emails': [],
            'use_tls': True,
            'use_starttls': True,
            'alert_on_severity': ['critical', 'high']
        },
        'webhooks': {
            'enabled': False,
            'url': '',
            'method': 'POST',
            'headers': {},
            'alert_on_severity': ['critical', 'high']
        },
        'push': {
            'enabled': False,
            'service': 'pushover',  # 'pushover', 'ntfy', 'custom'
            'api_key': '',
            'user_key': '',
            'alert_on_severity': ['critical', 'high']
        }
    }
}


def ensure_config_dir():
    """Create config directory if it doesn't exist"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load configuration from file, return defaults if not found"""
    ensure_config_dir()
    
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Merge with defaults to add any new fields from updates
        merged = _deep_merge(DEFAULT_CONFIG.copy(), config)
        return merged
    except Exception as e:
        print(f"⚠️ Error loading config: {e}, using defaults")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file"""
    ensure_config_dir()
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Error saving config: {e}")
        return False


def get_section(section: str) -> Dict[str, Any]:
    """Get a specific configuration section"""
    config = load_config()
    return config.get(section, DEFAULT_CONFIG.get(section, {}))


def update_section(section: str, data: Dict[str, Any]) -> bool:
    """Update a specific configuration section"""
    config = load_config()
    if section in config:
        config[section].update(data)
    else:
        config[section] = data
    return save_config(config)


def restore_defaults() -> bool:
    """Restore all settings to defaults"""
    return save_config(DEFAULT_CONFIG.copy())


def export_config() -> str:
    """Export configuration as JSON string"""
    config = load_config()
    return json.dumps(config, indent=2)


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Deep merge two dictionaries, overlay takes precedence"""
    result = base.copy()
    
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


# Convenience functions for common operations
def get_language() -> str:
    """Get current language setting"""
    return get_section('general').get('language', 'no')


def get_polling_interval() -> int:
    """Get current polling interval in seconds"""
    return get_section('general').get('polling_interval', 60)


def get_temperature_unit() -> str:
    """Get temperature unit (C or F)"""
    return get_section('general').get('temperature_unit', 'C')


def is_device_monitored(device_name: str) -> bool:
    """Check if a specific device is monitored"""
    monitored = get_section('disk_selection').get('monitored_devices', {})
    return monitored.get(device_name, True)  # Default to monitored


def should_ignore_usb() -> bool:
    """Check if removable USB devices should be ignored"""
    return get_section('disk_selection').get('ignore_removable_usb', False)


def get_alert_config() -> Dict[str, Any]:
    """Get combined alert configuration for alert_engine compatibility"""
    config = load_config()
    
    return {
        'score_change_threshold': config['health_alerts']['score_drop_threshold'],
        'critical_score': config['health_alerts']['critical_score_limit'],
        'reallocated_milestones': config['smart_alerts']['reallocated_milestones'],
        'pending_milestones': config['smart_alerts']['pending_milestones'],
        'uncorrectable_threshold': config['smart_alerts']['uncorrectable_threshold'],
        'timeout_threshold': config['smart_alerts']['timeout_threshold'],
        'temperature_consecutive_readings': config['temperature_alerts']['consecutive_readings'],
        'temperature_thresholds': {
            'ssd_warning': config['temperature_alerts']['ssd_warning'],
            'ssd_critical': config['temperature_alerts']['ssd_critical'],
            'hdd_warning': config['temperature_alerts']['hdd_warning'],
            'hdd_critical': config['temperature_alerts']['hdd_critical']
        },
        'alert_on_normalize': config['temperature_alerts']['alert_on_normalize']
    }


def is_emergency_mode_active() -> bool:
    """
    Check if emergency unmount mode is ACTIVE.
    
    Returns:
        True if mode == "ACTIVE", False otherwise (including PASSIVE or config error)
    
    Safety: Defaults to PASSIVE if config is missing or corrupt.
    """
    try:
        config = load_config()
        mode = config.get('emergency_unmount', {}).get('mode', 'PASSIVE')
        return mode.upper() == 'ACTIVE'
    except Exception:
        # If ANY error reading config, default to PASSIVE
        return False


if __name__ == '__main__':
    # Test configuration
    print("Loading configuration...")
    config = load_config()
    print(json.dumps(config, indent=2))
    
    print("\nConfiguration file location:", CONFIG_FILE)
