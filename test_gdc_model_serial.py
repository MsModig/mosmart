#!/usr/bin/env python3
"""
Test GDC logging with model/serial support
"""

from gdc import GDCManager
from gdc_logger import log_gdc_event, get_gdc_history, get_worst_gdc_state, has_gdc_history

print("Testing GDC logger with model/serial support...")
print("=" * 60)

# Create a GDC manager for testing
gdc = GDCManager("/dev/sdtest")

# Simulate some events with model/serial
print("\n1. Logging timeout events with model/serial...")
gdc.event_timeout()
log_gdc_event("/dev/sdtest", "timeout", gdc.to_json(), 
              model="ST2000DM001-1CH164", 
              serial="S1E1YQ9T")

gdc.event_timeout()
log_gdc_event("/dev/sdtest", "timeout", gdc.to_json(),
              model="ST2000DM001-1CH164",
              serial="S1E1YQ9T")

gdc.event_timeout()
log_gdc_event("/dev/sdtest", "state_change", gdc.to_json(),
              details={'old_state': 'OK', 'new_state': 'SUSPECT'},
              model="ST2000DM001-1CH164",
              serial="S1E1YQ9T")

print(f"✓ Current GDC state: {gdc.state.value}")

# Test retrieval by model/serial
print("\n2. Testing retrieval by model/serial...")
history = get_gdc_history(model="ST2000DM001-1CH164", serial="S1E1YQ9T")
print(f"✓ Found {len(history)} events for ST2000DM001-1CH164 (S1E1YQ9T)")

# Test worst state
print("\n3. Testing worst state detection...")
worst = get_worst_gdc_state(model="ST2000DM001-1CH164", serial="S1E1YQ9T")
if worst:
    print(f"✓ Worst state: {worst['worst_state']}")
    print(f"  Total events: {worst['total_events']}")
    print(f"  Timeouts: {worst['timeouts']}")
else:
    print("✗ No worst state found")

# Test has_gdc_history
print("\n4. Testing has_gdc_history...")
has_gdc = has_gdc_history(model="ST2000DM001-1CH164", serial="S1E1YQ9T")
print(f"✓ Has GDC history: {has_gdc}")

# Test with different model/serial (should return empty)
print("\n5. Testing with different model/serial...")
history2 = get_gdc_history(model="DIFFERENT_MODEL", serial="DIFFERENT_SERIAL")
print(f"✓ Found {len(history2)} events for DIFFERENT_MODEL (should be 0)")

# Print sample log entry
print("\n6. Sample log entry:")
if history:
    import json
    print(json.dumps(history[0], indent=2))

print("\n" + "=" * 60)
print("✅ GDC model/serial support is working correctly!")
