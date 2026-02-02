#!/usr/bin/env python3
"""
mosmart188 - Virtual SMART Attribute for Disk Instability Detection

This module implements a persistent, time-based disk restart/instability tracker
that behaves like a virtual SMART attribute with memory.

Key features:
- Persistent across disconnects (stored per disk ID, not device path)
- Time-based sliding windows (60s, 5min, 24h)
- Asymmetric: fast degradation, slow recovery
- Lock mechanism: prevents health improvement during instability
- Robust against random cable blips
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


# Storage directory for mosmart188 state
STATE_DIR = Path.home() / '.mosmart' / 'mosmart188_state'
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Time windows for restart tracking (seconds)
WINDOW_SHORT = 60        # 1 minute
WINDOW_MEDIUM = 300      # 5 minutes
WINDOW_LONG = 86400      # 24 hours

# Lock thresholds (restarts within time period triggers lock)
LOCK_THRESHOLD_SHORT = 3   # 3 restarts in 60s → lock
LOCK_THRESHOLD_MEDIUM = 5  # 5 restarts in 5min → lock
LOCK_THRESHOLD_LONG = 10   # 10 restarts in 24h → lock

# Lock release: no restarts for this duration
LOCK_RELEASE_DURATION = 1800  # 30 minutes of stability

# USB connect grace period: ignore restarts for 10s after first detection
# Prevents false positives when USB disk connects (not ready for SMART yet)
USB_CONNECT_GRACE_PERIOD = 10  # 10 seconds

# Command Timeout (SMART ID 188) handling
RECENT_BOOT_GRACE_SECONDS = 3600  # 1 hour after boot
SHORT_UPTIME_THRESHOLD = 7200     # 2 hours uptime
POWER_EVENT_GRACE_SECONDS = 7200  # 2 hours after uncontrolled shutdown
REBOOT_TIME_DRIFT_SECONDS = 300   # 5 minutes drift to detect reboot
COMMAND_TIMEOUT_STABLE_WINDOW = 72 * 3600  # 72 hours

# Penalty escalation for stable Command Timeout increases
COMMAND_TIMEOUT_PENALTY_TABLE = {
    0: 0,
    1: -1,
    2: -2,
    3: -3,
    4: -5,
    5: -7,
    6: -9,
    7: -12,
    8: -15,
    9: -18,
    10: -20
}

# Health penalty table (restarts in last 24h → penalty points)
HEALTH_PENALTY_TABLE = {
    0: 0,
    1: 0,
    2: 0,
    3: 0,
    4: -5,
    5: -10,
    6: -15,
    7: -20,
    8: -25,
    9: -30,
    10: -40,
    11: -50,
    12: -55,
    13: -60,
    14: -65,
    15: -70,
    16: -100,  # Terminal
}


class Mosmart188State:
    """
    Represents the persistent state of mosmart188 for a single disk.
    
    Data structure:
        disk_id: Unique identifier (model_serial)
        last_seen: Last time disk was scanned (timestamp)
        mosmart188_score: Current health penalty (-100 to 0)
        mosmart188_lock: If True, health cannot improve
        lock_since: Timestamp when lock was activated
        restart_events: List of timestamped restart events
        last_power_cycles: Last known power cycle count (for jump detection)
        last_id193: Last known Load_Cycle_Count (for jump detection)
    """
    
    def __init__(self, disk_id: str):
        self.disk_id = disk_id
        self.first_seen = time.time()  # Track initial detection for USB grace period
        self.last_seen = time.time()
        self.last_disconnect_time = None  # Track USB disconnects for reconnect classification
        self.mosmart188_score = 0
        self.mosmart188_lock = False
        self.lock_since = None
        self.restart_events = []  # [{"timestamp": float, "reason": str, "source": str, "category": str}, ...]
        self.last_power_cycles = None
        self.last_id193 = None
        self.last_id188 = None
        self.last_boot_time = None
        self.command_timeout_events = []  # [{"timestamp": float, "delta": int, "category": str}, ...]
    
    def to_dict(self) -> dict:
        """Serialize state to dictionary for JSON storage"""
        return {
            'disk_id': self.disk_id,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'last_disconnect_time': self.last_disconnect_time,
            'mosmart188_score': self.mosmart188_score,
            'mosmart188_lock': self.mosmart188_lock,
            'lock_since': self.lock_since,
            'restart_events': self.restart_events,
            'last_power_cycles': self.last_power_cycles,
            'last_id193': self.last_id193,
            'last_id188': self.last_id188,
            'last_boot_time': self.last_boot_time,
            'command_timeout_events': self.command_timeout_events,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Mosmart188State':
        """Deserialize state from dictionary"""
        state = cls(data['disk_id'])
        state.first_seen = data.get('first_seen', time.time())  # Backward compatible: default to now
        state.last_seen = data.get('last_seen', time.time())
        state.last_disconnect_time = data.get('last_disconnect_time')  # None if not present
        state.mosmart188_score = data.get('mosmart188_score', 0)
        state.mosmart188_lock = data.get('mosmart188_lock', False)
        state.lock_since = data.get('lock_since')
        state.restart_events = data.get('restart_events', [])
        state.last_power_cycles = data.get('last_power_cycles')
        state.last_id193 = data.get('last_id193')
        state.last_id188 = data.get('last_id188')
        state.last_boot_time = data.get('last_boot_time')
        state.command_timeout_events = data.get('command_timeout_events', [])
        return state


class Mosmart188Manager:
    """
    Manages mosmart188 state for all disks with persistent storage.
    
    Responsibilities:
    - Track restart events with timestamps
    - Maintain time-based sliding windows
    - Implement lock mechanism
    - Calculate health penalties
    - Persist state across restarts
    """
    
    def __init__(self):
        self.states: Dict[str, Mosmart188State] = {}
        self._load_all_states()
        # Track recent FAULT restarts across disks for system event detection
        self._recent_fault_events: List[Dict[str, float]] = []  # [{'disk_id': str, 'timestamp': float}]
        self._last_system_event: Optional[Dict[str, any]] = None
        self._system_event_cooldown_until: float = 0.0
    
    def _get_state_file(self, disk_id: str) -> Path:
        """Get the state file path for a disk"""
        # Sanitize disk_id for filename
        safe_id = disk_id.replace('/', '-').replace(' ', '_')
        return STATE_DIR / f"{safe_id}.json"
    
    def _load_all_states(self):
        """Load all persisted states from disk"""
        for state_file in STATE_DIR.glob('*.json'):
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    state = Mosmart188State.from_dict(data)
                    self.states[state.disk_id] = state
            except Exception as e:
                print(f"⚠️ Failed to load mosmart188 state from {state_file}: {e}")
    
    def _save_state(self, disk_id: str):
        """Persist state for a specific disk"""
        if disk_id not in self.states:
            return
        
        state_file = self._get_state_file(disk_id)
        try:
            with open(state_file, 'w') as f:
                json.dump(self.states[disk_id].to_dict(), f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save mosmart188 state for {disk_id}: {e}")
    
    def get_state(self, disk_id: str) -> Mosmart188State:
        """Get or create state for a disk"""
        if disk_id not in self.states:
            self.states[disk_id] = Mosmart188State(disk_id)
        return self.states[disk_id]
    
    def _cleanup_old_events(self, state: Mosmart188State):
        """Remove restart events older than 24h"""
        cutoff = time.time() - WINDOW_LONG
        state.restart_events = [
            event for event in state.restart_events
            if event['timestamp'] > cutoff
        ]

        timeout_cutoff = time.time() - COMMAND_TIMEOUT_STABLE_WINDOW
        state.command_timeout_events = [
            event for event in state.command_timeout_events
            if event['timestamp'] > timeout_cutoff
        ]

    def _count_command_timeout_events(self, state: Mosmart188State, category: Optional[str] = 'STABLE') -> int:
        """Count command timeout events within window, optionally filtered by category"""
        cutoff = time.time() - COMMAND_TIMEOUT_STABLE_WINDOW
        if category is None:
            return sum(1 for event in state.command_timeout_events if event['timestamp'] > cutoff)
        return sum(
            1 for event in state.command_timeout_events
            if event['timestamp'] > cutoff
            and event.get('category') == category
        )

    def _calculate_command_timeout_penalty(self, state: Mosmart188State) -> int:
        """Calculate penalty from stable SMART ID 188 increases"""
        stable_count = self._count_command_timeout_events(state, category='STABLE')
        if stable_count >= 10:
            return COMMAND_TIMEOUT_PENALTY_TABLE[10]
        return COMMAND_TIMEOUT_PENALTY_TABLE.get(stable_count, 0)

    def _cleanup_recent_fault_events(self):
        """Prune recent fault events list to last 60 seconds only"""
        cutoff = time.time() - 60
        self._recent_fault_events = [e for e in self._recent_fault_events if e['timestamp'] > cutoff]

    def _register_recent_fault_event(self, disk_id: str, ts: float):
        """Register a recent FAULT restart for cluster detection"""
        self._recent_fault_events.append({'disk_id': disk_id, 'timestamp': ts})
        self._cleanup_recent_fault_events()
        self._detect_uncontrolled_shutdown_cluster(ts)

    def _detect_uncontrolled_shutdown_cluster(self, reference_ts: float):
        """
        Detect if multiple disks had FAULT restarts within ±30s around reference_ts.
        If detected (>=2 disks), record a system event: 'uncontrolled_shutdown'.
        Applies a 2-minute cooldown to avoid duplicate events.
        """
        # Cooldown to prevent duplicate event logging
        now = time.time()
        if now < self._system_event_cooldown_until:
            return

        # Window: last 30 seconds relative to reference_ts (future events will also be caught by later calls)
        window_start = reference_ts - 30
        window_end = reference_ts + 30
        affected = set()
        for e in self._recent_fault_events:
            if window_start <= e['timestamp'] <= window_end:
                affected.add(e['disk_id'])

        if len(affected) >= 2:
            # Record system event
            event = {
                'type': 'uncontrolled_shutdown',
                'timestamp': reference_ts,
                'affected_disk_ids': sorted(list(affected)),
                'affected_count': len(affected),
                'message_no': 'Ukontrollert avslutning oppdaget',
                'note_no': 'Dette påvirker ikke diskens mekaniske helse.',
                'message_en': 'Uncontrolled shutdown detected',
                'note_en': "This does not affect the disk's mechanical health."
            }
            self._last_system_event = event
            # 2-minute cooldown to avoid spamming
            self._system_event_cooldown_until = now + 120
            print(f"⚠️ Systemhendelse: Ukontrollert avslutning oppdaget – påvirkede disker: {len(affected)}")

    def get_last_system_event(self) -> Optional[Dict[str, any]]:
        """Return the last detected system event if any"""
        return self._last_system_event
    
    def _count_restarts_in_window(self, state: Mosmart188State, window_seconds: float, category: str = 'FAULT') -> int:
        """Count restart events within a time window, filtered by category"""
        cutoff = time.time() - window_seconds
        if category is None:
            # Count all restarts
            return sum(1 for event in state.restart_events if event['timestamp'] > cutoff)
        else:
            # Count only specified category (backward compatible: old events default to FAULT)
            return sum(
                1 for event in state.restart_events
                if event['timestamp'] > cutoff
                and event.get('category', 'FAULT') == category
            )
    
    def _should_activate_lock(self, state: Mosmart188State) -> bool:
        """Check if lock should be activated based on restart patterns"""
        short_count = self._count_restarts_in_window(state, WINDOW_SHORT)
        medium_count = self._count_restarts_in_window(state, WINDOW_MEDIUM)
        long_count = self._count_restarts_in_window(state, WINDOW_LONG)
        
        return (
            short_count >= LOCK_THRESHOLD_SHORT or
            medium_count >= LOCK_THRESHOLD_MEDIUM or
            long_count >= LOCK_THRESHOLD_LONG
        )
    
    def _should_release_lock(self, state: Mosmart188State) -> bool:
        """Check if lock should be released (no restarts for LOCK_RELEASE_DURATION)"""
        if not state.restart_events:
            return True
        
        last_restart = max(event['timestamp'] for event in state.restart_events)
        time_since_last_restart = time.time() - last_restart
        
        return time_since_last_restart >= LOCK_RELEASE_DURATION
    
    def _should_escalate_transient_to_fault(self, disk_id: str, source: str, state: Mosmart188State) -> bool:
        """
        Check if TRANSIENT pattern indicates real problem.
        
        Escalation triggers:
        - >5 TRANSIENT events in 60s (spam)
        - Same source ≥3 times in 5 min (repeated pattern)
        """
        # Count recent TRANSIENT events
        cutoff_short = time.time() - 60
        transient_count_60s = sum(
            1 for e in state.restart_events
            if e['timestamp'] > cutoff_short 
            and e.get('category') == 'TRANSIENT'
        )
        
        if transient_count_60s >= 5:
            return True  # Spam → escalate
        
        # Check for repeated pattern (same source)
        cutoff_medium = time.time() - 300
        same_source_count = sum(
            1 for e in state.restart_events
            if e['timestamp'] > cutoff_medium
            and e.get('source') == source
            and e.get('category') == 'TRANSIENT'
        )
        
        if same_source_count >= 3:
            return True  # Pattern → escalate
        
        return False
    
    def _classify_restart(self, disk_id: str, source: str, reason: str, state: Mosmart188State) -> str:
        """
        Classify restart as FAULT, TRANSIENT, or EXPECTED.
        
        EXPECTED: Known benign events (USB disconnect, shutdown)
        TRANSIENT: Enumeration glitches, rapid reconnects (rate-limited)
        FAULT: Real disk problems
        """
        # EXPECTED: Explicit disconnect/shutdown
        if source in ['usb_disconnect', 'user_initiated', 'shutdown', 'cable_disconnect']:
            return 'EXPECTED'
        
        # Check for TRANSIENT escalation FIRST (before classifying as TRANSIENT)
        if self._should_escalate_transient_to_fault(disk_id, source, state):
            return 'FAULT'
        
        # TRANSIENT: Rapid reconnect (disk disappeared <60s ago)
        if state.last_disconnect_time:
            reconnect_gap = time.time() - state.last_disconnect_time
            if reconnect_gap < 60:
                # Check if this is a single power cycle jump (not multiple crashes)
                if source == 'power_cycle_jump' and 'Power Cycles +1' in reason:
                    return 'TRANSIENT'
                # SMART exception shortly after reconnect
                if source == 'smart_exception' and reconnect_gap < 30:
                    return 'TRANSIENT'
        
        # TRANSIENT: SMART exception in extended grace period (10-30s after first_seen)
        if source == 'smart_exception':
            time_since_first = time.time() - state.first_seen
            if 10 < time_since_first < 30:
                return 'TRANSIENT'
        
        # Default: FAULT
        return 'FAULT'
    
    def _calculate_health_penalty(self, state: Mosmart188State) -> int:
        """
        Calculate health penalty based on restarts in last 24h.
        
        Uses asymmetric scoring:
        - Fast degradation: each new restart immediately impacts health
        - Slow recovery: health only improves after sustained stability
        
        Returns: Penalty points (-100 to 0)
        """
        restarts_24h = self._count_restarts_in_window(state, WINDOW_LONG)
        
        # Use penalty table, cap at 16+ restarts
        if restarts_24h >= 16:
            penalty = HEALTH_PENALTY_TABLE[16]
        else:
            penalty = HEALTH_PENALTY_TABLE.get(restarts_24h, 0)
        
        command_timeout_penalty = self._calculate_command_timeout_penalty(state)
        penalty = penalty + command_timeout_penalty
        penalty = max(-100, min(0, penalty))

        # If locked, cannot improve (only degrade or stay same)
        if state.mosmart188_lock:
            if penalty < state.mosmart188_score:
                # New penalty is worse (more negative) → allow degradation
                return penalty
            else:
                # New penalty is better → keep old worse score
                return state.mosmart188_score
        else:
            # Not locked → allow both improvement and degradation
            # But improvement is slow (gradual healing)
            if penalty > state.mosmart188_score:
                # Penalty improving (less negative)
                # Allow 10% improvement per scan (slow recovery)
                improvement = int((penalty - state.mosmart188_score) * 0.1)
                if improvement == 0 and penalty != state.mosmart188_score:
                    improvement = 1  # Minimum 1 point improvement
                new_score = state.mosmart188_score + improvement
                return min(new_score, penalty)  # Don't overshoot
            else:
                # Penalty degrading → immediate full degradation
                return penalty
    
    def register_restart(self, disk_id: str, reason: str, source: str):
        """
        Register a restart/instability event.
        
        Args:
            disk_id: Unique disk identifier (model_serial)
            reason: Human-readable reason (e.g., "Power Cycles +1")
            source: Detection source (e.g., "smart_interrupt", "usb_disconnect")
        """
        state = self.get_state(disk_id)
        
        # USB connect grace period: ignore SMART failures in first 10s after detection
        # USB disks aren't ready for SMART immediately after connection
        time_since_first_seen = time.time() - state.first_seen
        if time_since_first_seen < USB_CONNECT_GRACE_PERIOD:
            print(f"⏳ mosmart188: Ignoring restart for {disk_id} (grace period: {time_since_first_seen:.1f}s / {USB_CONNECT_GRACE_PERIOD}s)")
            print(f"   Reason: {reason} (source: {source})")
            return  # Don't register this restart
        
        # Classify restart
        category = self._classify_restart(disk_id, source, reason, state)
        
        # Add restart event with category
        event = {
            'timestamp': time.time(),
            'reason': reason,
            'source': source,
            'category': category
        }
        state.restart_events.append(event)
        
        # Cleanup old events (>24h)
        self._cleanup_old_events(state)
        
        # Only FAULT restarts affect lock and penalty
        if category != 'FAULT':
            # Update last_seen and persist (but don't affect health)
            state.last_seen = time.time()
            self._save_state(disk_id)
            print(f"🟡 {disk_id}: Restart classified as {category} (not affecting health)")
            print(f"   Reason: {reason} (source: {source})")
            return  # Early exit - skip lock/penalty logic
        
        # Track recent FAULT restart for system event detection
        self._register_recent_fault_event(disk_id, event['timestamp'])

        # FAULT restart: update lock state
        if self._should_activate_lock(state):
            if not state.mosmart188_lock:
                print(f"🔒 mosmart188 lock ACTIVATED for {disk_id}: instability detected")
                state.mosmart188_lock = True
                state.lock_since = time.time()
        
        # Recalculate health penalty (fast degradation)
        state.mosmart188_score = self._calculate_health_penalty(state)
        
        # Update last_seen
        state.last_seen = time.time()
        
        # Persist state
        self._save_state(disk_id)
        
        # Log event
        restarts_24h = self._count_restarts_in_window(state, WINDOW_LONG)
        print(f"📡 {disk_id}: mosmart188 restart detected ({source}): {reason}")
        print(f"   Restarts: 60s={self._count_restarts_in_window(state, WINDOW_SHORT)}, "
              f"5m={self._count_restarts_in_window(state, WINDOW_MEDIUM)}, "
              f"24h={restarts_24h}, penalty={state.mosmart188_score}, locked={state.mosmart188_lock}")
    
    def register_success(self, disk_id: str, power_cycles: Optional[int] = None, id193: Optional[int] = None):
        """
        Register a successful scan (no restart detected).
        
        Checks for abnormal jumps in power_cycles or ID193 and registers as restart if detected.
        Updates lock state if stability period met.
        
        Args:
            disk_id: Unique disk identifier
            power_cycles: Current power cycle count from SMART
            id193: Current Load_Cycle_Count from SMART ID 193
        """
        state = self.get_state(disk_id)
        
        # Check for abnormal jumps in SMART attributes
        restart_detected = False
        
        # Power cycle jump detection
        if power_cycles is not None and state.last_power_cycles is not None:
            jump = power_cycles - state.last_power_cycles
            if jump > 0:
                # Power cycle increased → disk restarted
                # Check grace period: USB reconnects cause legitimate power cycle jumps
                time_since_first_seen = time.time() - state.first_seen
                if time_since_first_seen < USB_CONNECT_GRACE_PERIOD:
                    print(f"⏳ mosmart188: Ignoring Power Cycles +{jump} for {disk_id} (grace period: {time_since_first_seen:.1f}s / {USB_CONNECT_GRACE_PERIOD}s)")
                else:
                    self.register_restart(disk_id, f"Power Cycles +{jump}", "power_cycle_jump")
                    restart_detected = True
        
        # ID193 (Load_Cycle_Count) jump detection
        if id193 is not None and state.last_id193 is not None:
            jump = id193 - state.last_id193
            # Abnormal jump: >100 in one scan interval (typical scans are 60s)
            if jump > 100:
                # Check grace period: USB reconnects may cause ID193 jumps too
                time_since_first_seen = time.time() - state.first_seen
                if time_since_first_seen < USB_CONNECT_GRACE_PERIOD:
                    print(f"⏳ mosmart188: Ignoring Load_Cycle_Count +{jump} for {disk_id} (grace period: {time_since_first_seen:.1f}s / {USB_CONNECT_GRACE_PERIOD}s)")
                else:
                    self.register_restart(disk_id, f"Load_Cycle_Count +{jump}", "id193_jump")
                    restart_detected = True
        
        # Update last known values
        if power_cycles is not None:
            state.last_power_cycles = power_cycles
        if id193 is not None:
            state.last_id193 = id193
        
        # If no restart detected, update state
        if not restart_detected:
            # Cleanup old events
            self._cleanup_old_events(state)
            
            # Check if lock should be released
            if state.mosmart188_lock and self._should_release_lock(state):
                print(f"🔓 mosmart188 lock RELEASED for {disk_id}: stability period met")
                state.mosmart188_lock = False
                state.lock_since = None
            
            # Recalculate health penalty (slow recovery)
            state.mosmart188_score = self._calculate_health_penalty(state)
            
            # Update last_seen
            state.last_seen = time.time()
            
            # Persist state
            self._save_state(disk_id)

    def register_command_timeout(self, disk_id: str, current_value: int, uptime_seconds: Optional[float] = None,
                                 boot_time: Optional[float] = None, system_event_ts: Optional[float] = None):
        """Register SMART ID 188 (Command Timeout) value and classify increases"""
        state = self.get_state(disk_id)
        now = time.time()

        if current_value is None:
            return

        # Initialize tracking
        if state.last_id188 is None:
            state.last_id188 = current_value
            if boot_time is not None:
                state.last_boot_time = boot_time
            self._save_state(disk_id)
            return

        delta = current_value - state.last_id188
        state.last_id188 = current_value

        reboot_detected = False
        if boot_time is not None and state.last_boot_time is not None:
            if abs(boot_time - state.last_boot_time) > REBOOT_TIME_DRIFT_SECONDS:
                reboot_detected = True
        if boot_time is not None:
            state.last_boot_time = boot_time

        if delta <= 0:
            self._save_state(disk_id)
            return

        recent_boot = uptime_seconds is not None and uptime_seconds < RECENT_BOOT_GRACE_SECONDS
        short_uptime = uptime_seconds is not None and uptime_seconds < SHORT_UPTIME_THRESHOLD
        recent_power_event = system_event_ts is not None and (now - system_event_ts) < POWER_EVENT_GRACE_SECONDS

        power_related = reboot_detected or recent_boot or short_uptime or recent_power_event

        category = 'POWER' if power_related else 'STABLE'
        state.command_timeout_events.append({
            'timestamp': now,
            'delta': delta,
            'category': category
        })
        self._cleanup_old_events(state)

        # Only stable increases affect penalty
        state.mosmart188_score = self._calculate_health_penalty(state)
        state.last_seen = now
        self._save_state(disk_id)

        if power_related:
            print(f"🟡 {disk_id}: ID 188 increased by {delta} (power-related, no health impact)")
        else:
            stable_count = self._count_command_timeout_events(state, category='STABLE')
            print(f"🟠 {disk_id}: ID 188 increased by {delta} (stable event #{stable_count})")
    
    def get_health_penalty(self, disk_id: str) -> int:
        """Get current health penalty for a disk (-100 to 0)"""
        state = self.get_state(disk_id)
        return state.mosmart188_score
    
    def get_restart_count_24h(self, disk_id: str) -> int:
        """Get restart count in last 24 hours"""
        state = self.get_state(disk_id)
        return self._count_restarts_in_window(state, WINDOW_LONG)
    
    def is_locked(self, disk_id: str) -> bool:
        """Check if disk is in locked state (health cannot improve)"""
        state = self.get_state(disk_id)
        return state.mosmart188_lock
    
    def get_summary(self, disk_id: str) -> dict:
        """Get complete summary of mosmart188 state for a disk"""
        state = self.get_state(disk_id)
        
        return {
            'disk_id': disk_id,
            'health_penalty': state.mosmart188_score,
            'restarts_60s': self._count_restarts_in_window(state, WINDOW_SHORT),
            'restarts_5m': self._count_restarts_in_window(state, WINDOW_MEDIUM),
            'restarts_24h': self._count_restarts_in_window(state, WINDOW_LONG),
            'locked': state.mosmart188_lock,
            'lock_since': state.lock_since,
            'last_seen': state.last_seen,
            'total_events': len(state.restart_events),
        }


# Global manager instance
_manager = None

def get_manager() -> Mosmart188Manager:
    """Get global mosmart188 manager instance"""
    global _manager
    if _manager is None:
        _manager = Mosmart188Manager()
    return _manager
