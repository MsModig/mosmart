#!/usr/bin/env python3
"""
MoSMART Monitor - Disk Health Decision Engine

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

This module provides a deterministic decision engine that evaluates disk health
metrics and returns structured recommendations without performing any actions.
"""

from enum import Enum
from typing import Dict, List, Optional, Any


class Status(Enum):
    """Decision status levels"""
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"
    
    def __ge__(self, other):
        order = [Status.OK, Status.WARNING, Status.CRITICAL, Status.EMERGENCY]
        return order.index(self) >= order.index(other)
    
    def __gt__(self, other):
        order = [Status.OK, Status.WARNING, Status.CRITICAL, Status.EMERGENCY]
        return order.index(self) > order.index(other)


class ConnectionType(Enum):
    """Disk connection types"""
    INTERNAL = "INTERNAL"
    USB = "USB"


# Thresholds - clearly defined in one place
THRESHOLDS = {
    'reallocated_sectors': {
        'absolute_warning': 5,
        'absolute_critical': 50,
        'absolute_emergency': 500,
        'delta_warning': 1,
        'delta_critical': 10,
        'delta_emergency': 100
    },
    'pending_sectors': {
        'absolute_warning': 1,
        'absolute_critical': 50,
        'delta_critical': 1
    }
}


def evaluate_reallocated_sectors(current: int, previous: Optional[int], is_usb: bool) -> Dict[str, Any]:
    """
    Evaluate reallocated sectors metric.
    
    Returns:
        dict with keys: severity, is_increasing, message
    """
    multiplier = 2 if is_usb else 1
    
    result = {
        'severity': Status.OK,
        'is_increasing': False,
        'message': ""
    }
    
    # Check if increasing
    if previous is not None:
        delta = current - previous
        if delta > 0:
            result['is_increasing'] = True
    
    # === DELTA-BASED EVALUATION (if baseline exists) ===
    if previous is not None:
        delta = current - previous
        
        if delta >= THRESHOLDS['reallocated_sectors']['delta_emergency'] * multiplier:
            result['severity'] = Status.EMERGENCY
            result['message'] = f"Reallocated sectors increased rapidly by {delta} ({previous} → {current})"
            return result
        
        if delta >= THRESHOLDS['reallocated_sectors']['delta_critical'] * multiplier:
            result['severity'] = Status.CRITICAL
            result['message'] = f"Reallocated sectors increased by {delta} ({previous} → {current})"
            return result
        
        if delta >= THRESHOLDS['reallocated_sectors']['delta_warning']:
            result['severity'] = Status.WARNING
            result['message'] = f"Reallocated sectors increased by {delta} ({previous} → {current})"
            return result
    
    # === ABSOLUTE VALUE EVALUATION ===
    if current >= THRESHOLDS['reallocated_sectors']['absolute_emergency'] * multiplier:
        result['severity'] = Status.EMERGENCY
        result['message'] = f"Reallocated sectors critically high: {current}"
        return result
    
    if current >= THRESHOLDS['reallocated_sectors']['absolute_critical'] * multiplier:
        result['severity'] = Status.CRITICAL
        result['message'] = f"Reallocated sectors high: {current}"
        return result
    
    if current >= THRESHOLDS['reallocated_sectors']['absolute_warning'] * multiplier:
        result['severity'] = Status.WARNING
        result['message'] = f"Reallocated sectors detected: {current}"
        return result
    
    return result


def evaluate_pending_sectors(current: int, previous: Optional[int], is_usb: bool) -> Dict[str, Any]:
    """
    Evaluate pending sectors metric.
    
    Returns:
        dict with keys: severity, is_increasing, message
    """
    multiplier = 2 if is_usb else 1
    
    result = {
        'severity': Status.OK,
        'is_increasing': False,
        'message': ""
    }
    
    if current == 0:
        return result
    
    # Any pending sectors = at least WARNING
    result['severity'] = Status.WARNING
    result['message'] = f"Pending sectors detected: {current}"
    
    # Check if increasing
    if previous is not None and previous != 0:
        delta = current - previous
        if delta > 0:
            result['is_increasing'] = True
            result['severity'] = Status.CRITICAL
            result['message'] = f"Pending sectors increasing ({previous} → {current})"
    
    # High absolute value
    if current >= THRESHOLDS['pending_sectors']['absolute_critical'] * multiplier:
        result['severity'] = Status.CRITICAL
        result['message'] = f"Pending sectors critically high: {current}"
    
    return result


def evaluate_temperature(temp: Optional[int]) -> Dict[str, Any]:
    """
    Evaluate temperature metric.
    
    Returns:
        dict with keys: severity, message
    """
    result = {
        'severity': Status.OK,
        'message': ""
    }
    
    if temp is None:
        return result
    
    if temp >= 65:
        result['severity'] = Status.EMERGENCY
        result['message'] = f"Temperature critical: {temp}°C (≥65°C)"
    elif temp >= 60:
        result['severity'] = Status.CRITICAL
        result['message'] = f"Temperature high: {temp}°C (≥60°C)"
    elif temp >= 50:
        result['severity'] = Status.WARNING
        result['message'] = f"Temperature elevated: {temp}°C (≥50°C)"
    
    return result


def count_at_level(severities: List[Status], level: Status) -> int:
    """Count how many severities are at or above the given level"""
    return sum(1 for s in severities if s >= level)


def evaluate_disk_health(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure decision engine that evaluates disk health and returns recommendations.
    
    Args:
        input_data: Dictionary containing:
            - reallocated_sectors: {'current': int, 'previous': int|None}
            - pending_sectors: {'current': int, 'previous': int|None}
            - temperature: int|None
            - health_score: int|None
            - previous_health_score: int|None
            - connection_type: 'INTERNAL' or 'USB'
            - limited_smart: bool
            - is_system_disk: bool
    
    Returns:
        Decision dictionary with:
            - status: Status enum value
            - reasons: List of explanation strings
            - recommended_actions: List of action strings
            - can_emergency_unmount: bool
            - notes: List of note strings
    """
    # Extract input
    current_realloc = input_data['reallocated_sectors']['current']
    prev_realloc = input_data['reallocated_sectors'].get('previous')
    current_pending = input_data['pending_sectors']['current']
    prev_pending = input_data['pending_sectors'].get('previous')
    temperature = input_data.get('temperature')
    health_score = input_data.get('health_score')
    prev_health_score = input_data.get('previous_health_score')
    is_usb = input_data.get('connection_type', 'INTERNAL') == 'USB'
    limited_smart = input_data.get('limited_smart', False)
    is_system_disk = input_data.get('is_system_disk', False)
    
    # Initialize decision object
    decision = {
        'status': Status.OK,
        'reasons': [],
        'recommended_actions': [],
        'can_emergency_unmount': False,
        'notes': []
    }
    
    # Apply USB reliability note
    if is_usb:
        decision['notes'].append("USB connection: SMART data may be unreliable")
    
    if limited_smart:
        decision['notes'].append("Limited SMART support detected")
    
    # === METRIC EVALUATION (EXCLUDING HEALTH SCORE) ===
    
    realloc_result = evaluate_reallocated_sectors(current_realloc, prev_realloc, is_usb)
    pending_result = evaluate_pending_sectors(current_pending, prev_pending, is_usb)
    temp_result = evaluate_temperature(temperature)
    
    # === SEVERITY AGGREGATION (HEALTH SCORE EXCLUDED) ===
    
    smart_severities = [
        realloc_result['severity'],
        pending_result['severity'],
        temp_result['severity']
    ]
    
    # Determine overall status (highest severity wins)
    decision['status'] = max(smart_severities)
    
    # === EXPLICIT EMERGENCY COMBINATION RULE ===
    
    # If BOTH reallocated AND pending are increasing, escalate to EMERGENCY
    if realloc_result['is_increasing'] and pending_result['is_increasing']:
        if realloc_result['severity'] >= Status.CRITICAL or pending_result['severity'] >= Status.CRITICAL:
            decision['status'] = Status.EMERGENCY
            decision['reasons'].append("EMERGENCY: Both reallocated and pending sectors increasing")
    
    # === EMERGENCY VALIDATION ===
    
    # Ensure EMERGENCY requires at least 2 concurrent severe signals
    if decision['status'] == Status.EMERGENCY:
        emergency_count = count_at_level(smart_severities, Status.EMERGENCY)
        
        # Require either:
        # - 2+ EMERGENCY signals, OR
        # - The explicit combination rule triggered
        combination_rule_triggered = (realloc_result['is_increasing'] and 
                                     pending_result['is_increasing'])
        
        if emergency_count < 2 and not combination_rule_triggered:
            decision['status'] = Status.CRITICAL
            decision['reasons'].append("Single emergency signal - downgraded to CRITICAL")
    
    # === POPULATE REASONS (SMART METRICS) ===
    
    if realloc_result['severity'] >= Status.WARNING and realloc_result['message']:
        decision['reasons'].append(realloc_result['message'])
    
    if pending_result['severity'] >= Status.WARNING and pending_result['message']:
        decision['reasons'].append(pending_result['message'])
    
    if temp_result['severity'] >= Status.WARNING and temp_result['message']:
        decision['reasons'].append(temp_result['message'])
    
    # === HEALTH SCORE CONTEXT (AFTER STATUS DETERMINED) ===
    
    # Health score adds context but does NOT change status
    if health_score is not None and prev_health_score is not None:
        score_drop = prev_health_score - health_score
        threshold = 3 * (2 if is_usb else 1)
        
        if score_drop > threshold:
            decision['reasons'].append(f"Health score dropped {score_drop} points (informational)")
    
    # === RECOMMENDED ACTIONS ===
    
    if decision['status'] == Status.WARNING:
        decision['recommended_actions'].append("Monitor disk closely")
        decision['recommended_actions'].append("Schedule backup if not recent")
    
    if decision['status'] == Status.CRITICAL:
        decision['recommended_actions'].append("**BACKUP IMMEDIATELY**")
        decision['recommended_actions'].append("Plan disk replacement")
        if temp_result['severity'] == Status.CRITICAL:
            decision['recommended_actions'].append("Improve cooling immediately")
    
    if decision['status'] == Status.EMERGENCY:
        decision['recommended_actions'].append("**BACKUP IN PROGRESS OR DISK FAILURE IMMINENT**")
        decision['recommended_actions'].append("Replace disk urgently")
        
        # ONLY recommend unmount if NOT system disk
        if not is_system_disk:
            decision['recommended_actions'].append("Emergency unmount recommended")
    
    # === EMERGENCY UNMOUNT ELIGIBILITY ===
    
    if decision['status'] == Status.EMERGENCY:
        if is_system_disk:
            decision['can_emergency_unmount'] = False
            decision['notes'].append("System disk – emergency unmount not permitted")
        else:
            if not is_usb:
                # Internal disk: Allow emergency unmount
                decision['can_emergency_unmount'] = True
            else:
                # USB disk: Future opt-in required
                decision['can_emergency_unmount'] = False
                decision['notes'].append("USB emergency unmount requires opt-in (future feature)")
    
    # Convert status enum to string for JSON serialization
    decision['status'] = decision['status'].value
    
    return decision
