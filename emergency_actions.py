#!/usr/bin/env python3
# MoSMART Monitor
# Copyright (C) 2026 Magnus S. Modig
# Licensed under GPLv3. See LICENSE for details.

import subprocess
import time
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime, timedelta


# Cooldown tracking: prevent repeated unmount attempts
_unmount_attempts = {}  # {disk_id: timestamp}
UNMOUNT_COOLDOWN_MINUTES = 30


def get_mount_info(device_name: str) -> Optional[str]:
    """
    Get mountpoint for a device using /proc/self/mounts.
    
    Args:
        device_name: Device name (e.g., 'sda', 'sdb1')
    
    Returns:
        Mountpoint path or None if not mounted
    """
    try:
        with open('/proc/self/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    device = parts[0]
                    mountpoint = parts[1]
                    
                    # Match /dev/{device_name}
                    if device == f'/dev/{device_name}':
                        return mountpoint
        return None
    except Exception as e:
        print(f"❌ [MOUNT-INFO] Error reading mounts: {e}")
        return None


def is_critical_mountpoint(mountpoint: str) -> bool:
    """
    Check if mountpoint is critical system path.
    
    Critical paths that should NEVER be unmounted:
    - / (root)
    - /boot (including /boot/efi, /boot/grub)
    - /home
    - /usr
    - /var
    
    Args:
        mountpoint: Mount point path
    
    Returns:
        True if critical, False otherwise
    """
    critical_paths = ['/', '/boot', '/home', '/usr', '/var']
    
    # Exact match
    if mountpoint in critical_paths:
        return True
    
    # Check if mountpoint is a subdirectory of a critical path
    # e.g., /boot/efi is under /boot
    for critical in critical_paths:
        if mountpoint.startswith(critical + '/'):
            return True
    
    return False


def is_in_cooldown(disk_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check if disk is in unmount cooldown period.
    
    Args:
        disk_id: Disk identifier
    
    Returns:
        (in_cooldown: bool, reason: Optional[str])
    """
    if disk_id not in _unmount_attempts:
        return (False, None)
    
    last_attempt = _unmount_attempts[disk_id]
    elapsed = datetime.now() - last_attempt
    cooldown_remaining = timedelta(minutes=UNMOUNT_COOLDOWN_MINUTES) - elapsed
    
    if cooldown_remaining.total_seconds() > 0:
        minutes_left = int(cooldown_remaining.total_seconds() / 60)
        return (True, f"Cooldown active: {minutes_left} minutes remaining")
    
    return (False, None)


def validate_unmount_conditions(device_name: str, disk_id: str, decision: dict) -> Tuple[bool, str]:
    """
    Validate ALL conditions before unmount.
    
    Validation checks:
    1. Decision status is EMERGENCY
    2. can_emergency_unmount is True
    3. Device is mounted
    4. Mountpoint is not critical system path
    5. Not in cooldown period
    
    Args:
        device_name: Device name (e.g., 'sda')
        disk_id: Disk identifier
        decision: Decision engine output
    
    Returns:
        (can_proceed: bool, reason: str)
    """
    # Check 1: Emergency status
    if decision.get('status') != 'EMERGENCY':
        return (False, f"Status is {decision.get('status')}, not EMERGENCY")
    
    # Check 2: Unmount permission
    if not decision.get('can_emergency_unmount', False):
        return (False, "can_emergency_unmount is False")
    
    # Check 3: Cooldown
    in_cooldown, cooldown_reason = is_in_cooldown(disk_id)
    if in_cooldown:
        return (False, cooldown_reason)
    
    # Check 4: Device is mounted
    mountpoint = get_mount_info(device_name)
    if not mountpoint:
        return (False, "Device is not mounted")
    
    # Check 5: Not critical system path
    if is_critical_mountpoint(mountpoint):
        return (False, f"Critical system mountpoint: {mountpoint}")
    
    return (True, f"All checks passed - mountpoint: {mountpoint}")


def _execute_unmount(mountpoint: str, device_name: str) -> Tuple[bool, str]:
    """
    Execute umount command with timeout.
    
    Tries mountpoint first, falls back to device if needed.
    
    Args:
        mountpoint: Mount point path
        device_name: Device name (fallback)
    
    Returns:
        (success: bool, output: str)
    """
    # Try unmounting by mountpoint first (preferred)
    try:
        result = subprocess.run(
            ['umount', mountpoint],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return (True, f"Unmounted {mountpoint}")
        
        # If mountpoint unmount failed, try device as fallback
        print(f"⚠️ [UNMOUNT] Mountpoint unmount failed, trying device...")
        
        result = subprocess.run(
            ['umount', f'/dev/{device_name}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return (True, f"Unmounted /dev/{device_name}")
        
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return (False, f"Unmount failed: {error_msg}")
        
    except subprocess.TimeoutExpired:
        return (False, "Unmount timeout after 10s")
    except Exception as e:
        return (False, f"Unmount exception: {str(e)}")


def emergency_unmount_disk(device_name: str, disk_id: str, decision: dict) -> bool:
    """
    Perform emergency unmount with full safety checks.
    
    This function does NOT check config - caller must verify emergency mode is active.
    
    Pre-conditions (validated internally):
    - Decision status == EMERGENCY
    - can_emergency_unmount == True
    - Device is mounted
    - Mountpoint is not critical system path
    - Not in cooldown period
    
    Args:
        device_name: Device name (e.g., 'sda')
        disk_id: Disk identifier
        decision: Decision engine output
    
    Returns:
        True if unmounted successfully, False otherwise
    
    Logs:
        - Before unmount (WARNING)
        - After successful unmount (CRITICAL)
        - On error (ERROR)
    """
    # Validate all conditions
    can_proceed, reason = validate_unmount_conditions(device_name, disk_id, decision)
    
    if not can_proceed:
        print(f"🚫 [UNMOUNT-BLOCKED] {device_name}: {reason}")
        return False
    
    # Get mountpoint (we validated it exists above)
    mountpoint = get_mount_info(device_name)
    
    # Log BEFORE unmount (WARNING)
    reasons_str = ', '.join(decision.get('reasons', []))
    print(f"⚠️  [EMERGENCY] {device_name}: Preparing emergency unmount")
    print(f"    Mountpoint: {mountpoint}")
    print(f"    Reasons: {reasons_str}")
    
    # Execute unmount
    print(f"🔓 [UNMOUNT] {device_name}: Executing umount {mountpoint}...")
    
    success, output = _execute_unmount(mountpoint, device_name)
    
    if success:
        # Record successful unmount attempt
        _unmount_attempts[disk_id] = datetime.now()
        
        # Log SUCCESS (CRITICAL)
        print(f"✅ [UNMOUNT] {device_name}: Successfully unmounted")
        print(f"    Output: {output}")
        print(f"🚨 [CRITICAL] {device_name}: Disk removed from system - EMERGENCY state")
        print(f"    Cooldown: {UNMOUNT_COOLDOWN_MINUTES} minutes until next unmount attempt allowed")
        
        return True
    else:
        # Log FAILURE (ERROR)
        print(f"❌ [UNMOUNT-FAILED] {device_name}: Unmount failed")
        print(f"    Error: {output}")
        
        # Still record attempt to prevent spam
        _unmount_attempts[disk_id] = datetime.now()
        
        return False
