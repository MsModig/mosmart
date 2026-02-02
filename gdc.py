#!/usr/bin/env python3
"""
MoSMART Monitor - Ghost Drive Condition (GDC) Detector

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

from enum import Enum
import time

class GDCState(Enum):
    OK = "OK"
    SUSPECT = "SUSPECT"
    CONFIRMED = "CONFIRMED"
    TERMINAL = "TERMINAL"
    UNASSESSABLE = "UNASSESSABLE"  # Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data.

class GDCManager:
    """
    Ghost Drive Condition manager – works even if SMART data is missing.
    Detects:
      - never delivered SMART
      - repeated timeouts
      - repeated N/A reads
      - corrupt/non-JSON SMART responses
      - device disappearing between scans
      - sudden silent death ("post mortem scenario")
    """

    def __init__(self, device_path):
        self.device = device_path

        # INTERNAL STATE
        self.state = GDCState.OK
        self.previous_state = GDCState.OK  # Track previous state for transition detection
        self.last_success_time = None
        self.frozen = False  # When True, _evaluate() won't change state

        # EVENT COUNTERS
        self.timeouts = 0
        self.no_json = 0
        self.corrupt = 0
        self.disappeared = 0
        self.successes = 0

        # HISTORY OF STATUS (for flapping)
        self.recent_status = []    # entries: "success", "timeout", "no_json" ...

        # Remembers if disk *has ever* delivered SMART in this session
        self.has_ever_succeeded = False
        
        # Track if device has SMART support at all (USB adapters, non-SMART devices)
        self.smart_supported = None  # None = unknown, True = supported, False = not supported
    
    def restore_from_history(self, counters_dict, last_state=None):
        """Restore state from historical data after server restart"""
        self.successes = counters_dict.get('successes', 0)
        self.timeouts = counters_dict.get('timeouts', 0)
        self.no_json = counters_dict.get('no_json', 0)
        self.corrupt = counters_dict.get('corrupt', 0)
        self.disappeared = counters_dict.get('disappeared', 0)
        self.has_ever_succeeded = counters_dict.get('has_ever_succeeded', False)
        self.recent_status = counters_dict.get('recent_status', [])
        
        # Restore last known state if provided
        if last_state:
            try:
                self.state = GDCState[last_state]
                self.previous_state = self.state  # Start with same state to avoid false transitions
            except (KeyError, AttributeError):
                pass  # Invalid state, keep default
        
        # Re-evaluate state based on restored counters
        self._evaluate()
        counters = {
            "successes": self.successes,
            "timeouts": self.timeouts,
            "no_json": self.no_json,
            "corrupt": self.corrupt,
            "disappeared": self.disappeared
        }
        print(f"🔄 Restored GDC state for {self.device}: {self.state.value} (counters: {counters})")

    # -------- EVENT REGISTRERING -------- #

    def event_success(self):
        """SMART data successfully retrieved."""
        self.successes += 1
        self.has_ever_succeeded = True
        self.last_success_time = time.time()

        # Reset failure counters
        self.timeouts = 0
        self.no_json = 0
        self.corrupt = 0
        self.disappeared = 0

        self._push_status("success")
        self._evaluate()

    def event_timeout(self):
        """smartctl timed out."""
        self.timeouts += 1
        self._push_status("timeout")
        self._evaluate()

    def event_no_json(self):
        """smartctl returned empty or non-parseable output."""
        self.no_json += 1
        self._push_status("no_json")
        self._evaluate()

    def event_corrupt(self):
        """smartctl returned partial/truncated/unusable JSON."""
        self.corrupt += 1
        self._push_status("corrupt")
        self._evaluate()

    def event_disappeared(self):
        """Device missing from /dev list during poll."""
        self.disappeared += 1
        self._push_status("disappeared")
        self._evaluate()
    
    def event_no_smart_support(self):
        """Device has no SMART support (USB adapter, non-SMART device, etc.).
        
        Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data.
        This marks the device as UNASSESSABLE, not GDC.
        """
        self.smart_supported = False
        self.state = GDCState.UNASSESSABLE
        self._push_status("no_smart_support")
        # Do NOT call _evaluate() - UNASSESSABLE is final for this session
    
    def get_transition_event(self):
        """Detect significant state transitions.
        
        Returns:
            (event_type, message) or (None, None) if no transition
        """
        prev = self.previous_state.value
        curr = self.state.value
        
        if prev == curr:
            return None, None
        
        # OK → Warning states
        if prev in (None, "OK") and curr == "SUSPECT":
            return "GDC_SUSPECTED", "⚠️ Ghost Drive Condition SUSPECTED - Disk showing early warning signs"
        if prev in (None, "OK", "SUSPECT") and curr == "CONFIRMED":
            return "GDC_CONFIRMED", "💀 Ghost Drive Condition CONFIRMED - Disk reliability compromised"
        if prev != "TERMINAL" and curr == "TERMINAL":
            return "GDC_TERMINAL", "☠️ Ghost Drive Condition TERMINAL - Disk should be replaced immediately"
        
        # Recovery
        if prev in ("SUSPECT", "CONFIRMED", "TERMINAL") and curr == "OK":
            return "GDC_REVOKED", "✅ GDC status REVOKED - Disk recovered and delivering reliable data"
        
        # Degradation
        if prev == "SUSPECT" and curr == "CONFIRMED":
            return "GDC_WORSENED", "⚠️ GDC state worsened: SUSPECT → CONFIRMED"
        if prev == "CONFIRMED" and curr == "TERMINAL":
            return "GDC_WORSENED", "⚠️ GDC state worsened: CONFIRMED → TERMINAL"
        
        # Generic state change
        return "STATE_CHANGE", f"GDC state change: {prev} → {curr}"
    
    def commit_state(self):
        """Call after logging transition. Updates previous_state to current state."""
        self.previous_state = self.state

    # -------- INTERN LOGIKK -------- #

    def _push_status(self, status):
        self.recent_status.append(status)
        if len(self.recent_status) > 10:
            self.recent_status.pop(0)

    def _evaluate(self):
        """Evaluates GDC state purely on event patterns.
        
        CRITICAL: Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data.
        - NULL/None SMART data → UNASSESSABLE (not GDC)
        - 0 value → Valid data point
        - Unstable/inconsistent data → GDC
        """
        if self.frozen:
            return  # Don't change state when frozen
        
        # If marked as no SMART support, stay UNASSESSABLE
        if self.smart_supported == False:
            self.state = GDCState.UNASSESSABLE
            return

        # --- Rule 1: Never delivered SMART ever (but has SMART support) ---
        # Only trigger GDC if we've seen INSTABILITY (mix of success and failure)
        # Pure absence of data should not trigger GDC
        if not self.has_ever_succeeded:
            # If only failures and no successes, this might be a connection issue, not GDC
            # Only escalate if we see a pattern of instability
            if (self.timeouts + self.no_json + self.corrupt + self.disappeared) >= 5:
                # Even then, require some evidence this isn't just "no SMART support"
                if self.timeouts >= 3:  # Timeouts suggest attempted communication
                    self.state = GDCState.CONFIRMED
                    return
            # let it rise to OK → SUSPECT naturally

        # --- Rule 2: Repeated failures (after having succeeded) ---
        # This is classic GDC: worked before, now failing
        total_fails = self.timeouts + self.no_json + self.corrupt + self.disappeared

        if total_fails >= 8:
            self.state = GDCState.TERMINAL
            return
        elif total_fails >= 5:
            self.state = GDCState.CONFIRMED
            return
        elif total_fails >= 3:
            self.state = GDCState.SUSPECT
            return

        # --- Rule 3: Flapping detection ---
        if self._count_flaps() >= 4:
            # 4 success→fail→success→fail within 10 last polls
            if self.state != GDCState.CONFIRMED:
                self.state = GDCState.SUSPECT

        # --- Rule 4: Time since last success (post mortem rule) ---
        if self.has_ever_succeeded and self.successes == 1:
            if total_fails >= 3:
                # Disk worked ONCE, then never again → classic post-mortem death
                self.state = GDCState.CONFIRMED

        # If no problem:
        if total_fails == 0:
            self.state = GDCState.OK

    def _count_flaps(self):
        """Return number of success→fail transitions in last 10 polls."""
        flaps = 0
        for i in range(1, len(self.recent_status)):
            if self.recent_status[i-1] == "success" and self.recent_status[i] != "success":
                flaps += 1
        return flaps

    # -------- API OUTPUT -------- #

    def to_json(self):
        return {
            "device": self.device,
            "state": self.state.value,
            "counters": {
                "successes": self.successes,
                "timeouts": self.timeouts,
                "no_json": self.no_json,
                "corrupt": self.corrupt,
                "disappeared": self.disappeared
            },
            "recent_status": self.recent_status,
            "has_ever_succeeded": self.has_ever_succeeded,
            "smart_supported": self.smart_supported,
        }
