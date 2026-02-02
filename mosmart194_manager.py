#!/usr/bin/env python3
"""
mosmart194 - Software-tracked Maximum Temperature Observer

Tracks the highest observed temperature per disk across all scans.
Persistent storage per disk ID (model_serial).

Purpose:
- Supplements SMART ID 194 max temp (which not all disks support)
- Provides user with historical max temp during ownership
- Never resets (preserves history)
"""

import json
from pathlib import Path
from typing import Optional


# Storage directory
STATE_DIR = Path.home() / '.mosmart' / 'mosmart194_state'
STATE_DIR.mkdir(parents=True, exist_ok=True)


class Mosmart194State:
    """Persistent state for a single disk's observed max temperature"""
    
    def __init__(self, disk_id: str):
        self.disk_id = disk_id
        self.max_temp = None  # Highest observed temperature
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'disk_id': self.disk_id,
            'max_temp': self.max_temp
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Mosmart194State':
        """Deserialize from JSON"""
        state = cls(data['disk_id'])
        state.max_temp = data.get('max_temp')
        return state


class Mosmart194Manager:
    """Manages mosmart194 (observed max temp) for all disks"""
    
    def __init__(self):
        self.states = {}
        self._load_all_states()
    
    def _get_state_file(self, disk_id: str) -> Path:
        """Get state file path for a disk"""
        safe_id = disk_id.replace('/', '-').replace(' ', '_')
        return STATE_DIR / f"{safe_id}.json"
    
    def _load_all_states(self):
        """Load all persisted states"""
        for state_file in STATE_DIR.glob('*.json'):
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    state = Mosmart194State.from_dict(data)
                    self.states[state.disk_id] = state
            except Exception as e:
                print(f"⚠️ Failed to load mosmart194 state from {state_file}: {e}")
    
    def _save_state(self, disk_id: str):
        """Persist state for a disk"""
        if disk_id not in self.states:
            return
        
        state_file = self._get_state_file(disk_id)
        try:
            with open(state_file, 'w') as f:
                json.dump(self.states[disk_id].to_dict(), f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save mosmart194 state for {disk_id}: {e}")
    
    def get_state(self, disk_id: str) -> Mosmart194State:
        """Get or create state for a disk"""
        if disk_id not in self.states:
            self.states[disk_id] = Mosmart194State(disk_id)
        return self.states[disk_id]
    
    def update_temperature(self, disk_id: str, current_temp: Optional[int]):
        """
        Update observed max temperature if current temp is higher.
        
        Args:
            disk_id: Unique disk identifier (model_serial)
            current_temp: Current temperature reading (°C)
        """
        if current_temp is None:
            return
        
        state = self.get_state(disk_id)
        
        # Initialize on first observation
        if state.max_temp is None:
            state.max_temp = current_temp
            self._save_state(disk_id)
            print(f"🌡 mosmart194: {disk_id} initialized at {current_temp}°C")
            return
        
        # Update if current is higher
        if current_temp > state.max_temp:
            old_max = state.max_temp
            state.max_temp = current_temp
            self._save_state(disk_id)
            print(f"🌡 mosmart194: {disk_id} new max: {old_max}°C → {current_temp}°C")
    
    def get_max_temp(self, disk_id: str) -> Optional[int]:
        """Get observed max temperature for a disk"""
        state = self.get_state(disk_id)
        return state.max_temp


# Global manager instance
_manager = None

def get_manager() -> Mosmart194Manager:
    """Get global mosmart194 manager instance"""
    global _manager
    if _manager is None:
        _manager = Mosmart194Manager()
    return _manager
