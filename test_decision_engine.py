#!/usr/bin/env python3
"""
Test suite for Disk Health Decision Engine
Demonstrates the engine with various scenarios
"""

from decision_engine import evaluate_disk_health
import json


def print_decision(scenario_name, decision):
    """Pretty print a decision"""
    print(f"\n{'=' * 70}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 70}")
    print(f"Status: {decision['status']}")
    print(f"\nReasons:")
    for reason in decision['reasons']:
        print(f"  • {reason}")
    print(f"\nRecommended Actions:")
    for action in decision['recommended_actions']:
        print(f"  • {action}")
    print(f"\nCan Emergency Unmount: {decision['can_emergency_unmount']}")
    if decision['notes']:
        print(f"\nNotes:")
        for note in decision['notes']:
            print(f"  ℹ️  {note}")
    print()


# Scenario 1: Internal HDD with Increasing Reallocated Sectors
print("\n" + "🧪 TEST SUITE: Disk Health Decision Engine".center(70))

scenario1 = {
    "reallocated_sectors": {"current": 15, "previous": 5},
    "pending_sectors": {"current": 0, "previous": 0},
    "temperature": 42,
    "health_score": 94,
    "previous_health_score": 97,
    "connection_type": "INTERNAL",
    "limited_smart": False,
    "is_system_disk": False
}

decision1 = evaluate_disk_health(scenario1)
print_decision("Internal HDD - Moderate Reallocated Increase", decision1)


# Scenario 2: USB Disk with Critical Temperature + Pending Sectors
scenario2 = {
    "reallocated_sectors": {"current": 8, "previous": 8},
    "pending_sectors": {"current": 3, "previous": 0},
    "temperature": 61,
    "health_score": 78,
    "previous_health_score": 85,
    "connection_type": "USB",
    "limited_smart": False,
    "is_system_disk": False
}

decision2 = evaluate_disk_health(scenario2)
print_decision("USB Disk - High Temp + Pending Sectors", decision2)


# Scenario 3: Internal System Disk - EMERGENCY (Combination Rule)
scenario3 = {
    "reallocated_sectors": {"current": 250, "previous": 50},
    "pending_sectors": {"current": 12, "previous": 3},
    "temperature": 58,
    "health_score": 35,
    "previous_health_score": 42,
    "connection_type": "INTERNAL",
    "limited_smart": False,
    "is_system_disk": True
}

decision3 = evaluate_disk_health(scenario3)
print_decision("System Disk - EMERGENCY (Both Increasing)", decision3)


# Scenario 4: Non-system disk - EMERGENCY with unmount allowed
scenario4 = {
    "reallocated_sectors": {"current": 600, "previous": 200},
    "pending_sectors": {"current": 25, "previous": 5},
    "temperature": 55,
    "health_score": 25,
    "previous_health_score": 45,
    "connection_type": "INTERNAL",
    "limited_smart": False,
    "is_system_disk": False
}

decision4 = evaluate_disk_health(scenario4)
print_decision("Data Disk - EMERGENCY with Unmount Eligible", decision4)


# Scenario 5: High temperature alone
scenario5 = {
    "reallocated_sectors": {"current": 0, "previous": 0},
    "pending_sectors": {"current": 0, "previous": 0},
    "temperature": 66,
    "health_score": 95,
    "previous_health_score": 96,
    "connection_type": "INTERNAL",
    "limited_smart": False,
    "is_system_disk": False
}

decision5 = evaluate_disk_health(scenario5)
print_decision("Temperature EMERGENCY (Single Signal - Downgraded)", decision5)


# Scenario 6: First scan with high absolute reallocated sectors
scenario6 = {
    "reallocated_sectors": {"current": 120, "previous": None},
    "pending_sectors": {"current": 0, "previous": None},
    "temperature": 45,
    "health_score": 75,
    "previous_health_score": None,
    "connection_type": "INTERNAL",
    "limited_smart": False,
    "is_system_disk": False
}

decision6 = evaluate_disk_health(scenario6)
print_decision("First Scan - High Absolute Reallocated", decision6)


# Scenario 7: Health score drop (should NOT affect status)
scenario7 = {
    "reallocated_sectors": {"current": 0, "previous": 0},
    "pending_sectors": {"current": 0, "previous": 0},
    "temperature": 40,
    "health_score": 85,
    "previous_health_score": 95,
    "connection_type": "INTERNAL",
    "limited_smart": False,
    "is_system_disk": False
}

decision7 = evaluate_disk_health(scenario7)
print_decision("Health Score Drop Only (Status Should Be OK)", decision7)


print("=" * 70)
print("✅ All test scenarios completed successfully")
print("=" * 70)
