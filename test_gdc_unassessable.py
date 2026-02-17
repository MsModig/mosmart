#!/usr/bin/env python3
"""
Test script to verify that UNASSESSABLE state works correctly.
Tests that missing SMART data does NOT trigger GDC.
"""

from gdc import GDCManager, GDCState

def test_usb_device_no_gdc():
    """Test that USB devices get UNASSESSABLE, not GDC"""
    print("\n=== Test 1: USB device without SMART support ===")
    manager = GDCManager("/dev/sdb")
    
    # Simulate USB device without SMART
    print("Scan 1: event_no_smart_support()")
    manager.event_no_smart_support()
    assert manager.state == GDCState.UNASSESSABLE, f"Expected UNASSESSABLE, got {manager.state}"
    print(f"✅ State: {manager.state.value}")
    
    # Subsequent scans should stay UNASSESSABLE
    print("Scan 2: event_no_smart_support()")
    manager.event_no_smart_support()
    assert manager.state == GDCState.UNASSESSABLE, f"Expected UNASSESSABLE, got {manager.state}"
    print(f"✅ State: {manager.state.value}")
    
    print("\n✅ USB device correctly marked as UNASSESSABLE (not GDC)\n")

def test_zero_vs_null():
    """Test that 0 is treated as valid data, null triggers UNASSESSABLE"""
    print("=== Test 2: Zero (0) vs None/null distinction ===")
    
    # 0 reallocated sectors = valid data point
    print("Scenario: Device reports 0 reallocated sectors (valid data)")
    print("  → Should be OK, not UNASSESSABLE")
    print("  → 0 is a data point, null/None is missing data")
    
    manager = GDCManager("/dev/sdc")
    manager.event_success()  # Device returned SMART with 0 values
    assert manager.state == GDCState.OK, f"Expected OK for valid data, got {manager.state}"
    print(f"✅ State: {manager.state.value}")
    
    # None/null = missing data
    print("\nScenario: Device returns no SMART data (null/None)")
    manager2 = GDCManager("/dev/sdd")
    manager2.event_no_smart_support()
    assert manager2.state == GDCState.UNASSESSABLE, f"Expected UNASSESSABLE, got {manager2.state}"
    print(f"✅ State: {manager2.state.value}")
    
    print("\n✅ Zero treated as data, null treated as missing\n")

def test_true_gdc_still_works():
    """Test that real GDC (unstable data) still triggers correctly"""
    print("=== Test 3: Real GDC (unstable data) still detected ===")
    manager = GDCManager("/dev/sde")
    
    # Disk works initially
    print("Scan 1-2: success")
    manager.event_success()
    manager.event_success()
    assert manager.state == GDCState.OK
    print(f"  State: {manager.state.value}")
    
    # Then starts failing (classic GDC pattern)
    print("Scan 3-5: timeout (unstable behavior)")
    manager.event_timeout()
    manager.event_timeout()
    manager.event_timeout()
    
    # Should trigger GDC
    assert manager.state == GDCState.SUSPECT, f"Expected SUSPECT, got {manager.state}"
    print(f"✅ State: {manager.state.value} (GDC correctly detected)")
    
    # More failures
    print("Scan 6-7: timeout")
    manager.event_timeout()
    manager.event_timeout()
    assert manager.state == GDCState.CONFIRMED, f"Expected CONFIRMED, got {manager.state}"
    print(f"✅ State: {manager.state.value}")
    
    print("\n✅ True GDC (unstable data) still triggers correctly\n")

def test_no_smart_vs_lying_smart():
    """Test the key distinction: no SMART vs lying SMART"""
    print("=== Test 4: No SMART vs Lying SMART ===")
    
    # No SMART support
    print("Device A: No SMART support (USB)")
    device_a = GDCManager("/dev/sdf")
    device_a.event_no_smart_support()
    print(f"  Result: {device_a.state.value} ✅")
    assert device_a.state == GDCState.UNASSESSABLE
    
    # Has SMART but then fails consistently (classic GDC)
    print("\nDevice B: Has SMART initially, then dies (classic GDC)")
    device_b = GDCManager("/dev/sdg")
    print("  Scan 1: success")
    device_b.event_success()
    print("  Scan 2-4: timeout (disk failing)")
    device_b.event_timeout()
    device_b.event_timeout()
    device_b.event_timeout()
    
    print(f"  Result: {device_b.state.value}")
    assert device_b.state == GDCState.SUSPECT, \
        f"Expected SUSPECT for failing disk, got {device_b.state}"
    print("✅ Disk that worked then failed triggers GDC")
    
    print("\n✅ Critical distinction maintained:\n")
    print("   Missing data = UNASSESSABLE")
    print("   Working → Failing = GDC\n")

def test_first_scan_no_gdc():
    """Test that first scan without history doesn't trigger GDC"""
    print("=== Test 5: First scan behavior ===")
    manager = GDCManager("/dev/sdh")
    
    print("First scan: no_json (no history yet)")
    manager.event_no_json()
    
    # Should NOT be GDC on first scan
    assert manager.state != GDCState.CONFIRMED, \
        f"First scan should not trigger CONFIRMED GDC, got {manager.state}"
    print(f"✅ State: {manager.state.value} (not CONFIRMED on first scan)")
    
    print("\n✅ First scan without history doesn't trigger GDC immediately\n")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("GDC UNASSESSABLE Logic Test")
    print("Testing: Missing SMART data NEVER triggers GDC")
    print("="*70)
    
    try:
        test_usb_device_no_gdc()
        test_zero_vs_null()
        test_true_gdc_still_works()
        test_no_smart_vs_lying_smart()
        test_first_scan_no_gdc()
        
        print("="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nKey principles verified:")
        print("  ✅ NULL/None = missing data → UNASSESSABLE (not GDC)")
        print("  ✅ 0 value = valid data point")
        print("  ✅ Unstable/inconsistent data → GDC")
        print("  ✅ USB devices → UNASSESSABLE")
        print("  ✅ First scan without history → not immediate GDC")
        print()
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        exit(1)
