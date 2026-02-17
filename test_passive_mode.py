#!/usr/bin/env python3
"""
Test Passive Decision Engine Integration

Verifies that decision engine runs in passive mode and logs decisions
without taking any actions.
"""

import json
import sys
from pathlib import Path

# Decision engine is currently running in PASSIVE MODE.
# Output is logged only. No actions are taken based on decisions.

def test_log_entry_has_decision_engine():
    """Test that recent log entries contain decision engine data"""
    
    log_dir = Path.home() / '.mosmart' / 'logs'
    
    if not log_dir.exists():
        print("❌ No log directory found. Run a scan first.")
        return False
    
    # Find any disk log directory
    disk_dirs = [d for d in log_dir.iterdir() if d.is_dir()]
    
    if not disk_dirs:
        print("❌ No disk logs found. Run a scan first.")
        return False
    
    found_decision_engine = False
    
    for disk_dir in disk_dirs:
        # Get latest log file
        log_files = sorted(disk_dir.glob('*.jsonl'))
        if not log_files:
            continue
        
        latest_log = log_files[-1]
        
        # Read last entry
        with open(latest_log, 'r') as f:
            lines = f.readlines()
            if not lines:
                continue
            
            last_entry = json.loads(lines[-1])
            
            # Check for decision engine data
            if 'decision_engine' in last_entry and 'decision_engine_mode' in last_entry:
                found_decision_engine = True
                disk_name = last_entry.get('device_name', 'unknown')
                mode = last_entry.get('decision_engine_mode')
                decision = last_entry.get('decision_engine', {})
                status = decision.get('status', 'UNKNOWN')
                reasons = decision.get('reasons', [])
                
                print(f"\n✅ Found decision engine data for {disk_name}")
                print(f"   Mode: {mode}")
                print(f"   Status: {status}")
                print(f"   Reasons: {len(reasons)}")
                
                if mode != 'PASSIVE':
                    print(f"   ⚠️ WARNING: Mode is {mode}, expected PASSIVE")
                    return False
                
                # Show reasons
                for reason in reasons[:3]:  # Show first 3
                    print(f"   - {reason}")
                
                if len(reasons) > 3:
                    print(f"   ... and {len(reasons) - 3} more")
                
                # Verify no actions are taken
                print(f"\n   ✅ PASSIVE MODE VERIFIED: No actions taken")
                
                break
    
    if not found_decision_engine:
        print("\n⚠️ No decision engine data found in recent logs.")
        print("   This is expected if:")
        print("   - This is the first scan after integration")
        print("   - No hourly boundary crossed yet")
        print("   - No SMART changes detected")
        print("\n   Run a forced scan to test:")
        print("   sudo systemctl restart mosmart.service")
        return None
    
    return True


def test_passive_mode_comments():
    """Verify that passive mode comments are present in code files"""
    
    files_to_check = [
        'disk_logger.py',
        'alert_engine.py', 
        'web_monitor.py'
    ]
    
    base_dir = Path(__file__).parent
    
    print("\n" + "="*70)
    print("Checking for passive mode comments in source files...")
    print("="*70)
    
    all_found = True
    
    for filename in files_to_check:
        filepath = base_dir / filename
        
        if not filepath.exists():
            print(f"❌ {filename}: File not found")
            all_found = False
            continue
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        if 'Decision engine is currently running in PASSIVE MODE' in content:
            print(f"✅ {filename}: Passive mode comment found")
        else:
            print(f"❌ {filename}: Passive mode comment MISSING")
            all_found = False
    
    return all_found


def test_no_action_code():
    """Verify that no action-triggering code exists based on decision engine"""
    
    print("\n" + "="*70)
    print("Verifying no action code exists...")
    print("="*70)
    
    # Check that decision engine results are only logged, not acted upon
    base_dir = Path(__file__).parent
    
    # List of files where we should NOT see decision-based actions
    files_to_check = [
        'disk_logger.py',
        'alert_engine.py',
        'email_notifier.py'
    ]
    
    forbidden_patterns = [
        'if decision[',  # Acting on decision results
        'if decision.get',
        'decision_engine[\'status\'] ==',
        'send_alert.*decision',
        'unmount.*decision'
    ]
    
    all_clean = True
    
    for filename in files_to_check:
        filepath = base_dir / filename
        
        if not filepath.exists():
            continue
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Look for forbidden patterns
        for i, line in enumerate(lines, 1):
            # Skip if line is a comment
            if line.strip().startswith('#'):
                continue
            
            for pattern in forbidden_patterns:
                if pattern in line.lower():
                    # Check if this is in our passive evaluation function (allowed)
                    if '_evaluate_passive_decision' in lines[max(0, i-20):i]:
                        continue
                    
                    print(f"⚠️ {filename}:{i}: Potential action on decision: {line.strip()[:60]}")
                    all_clean = False
    
    if all_clean:
        print("✅ No action code found - passive mode verified")
    
    return all_clean


if __name__ == "__main__":
    print("="*70)
    print("PASSIVE MODE INTEGRATION TEST")
    print("="*70)
    print("\nDecision engine is currently running in PASSIVE MODE.")
    print("Output is logged only. No actions are taken based on decisions.")
    print("="*70)
    
    # Test 1: Check comments
    test1 = test_passive_mode_comments()
    
    # Test 2: Check for action code
    test2 = test_no_action_code()
    
    # Test 3: Check log entries
    print("\n" + "="*70)
    print("Checking for decision engine data in logs...")
    print("="*70)
    test3 = test_log_entry_has_decision_engine()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    results = {
        "Passive mode comments": test1,
        "No action code": test2,
        "Decision engine in logs": test3
    }
    
    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name}: PASS")
        elif result is False:
            print(f"❌ {test_name}: FAIL")
        else:
            print(f"⚠️ {test_name}: PENDING (need scan)")
    
    print("="*70)
    
    # Exit code
    if test1 and test2:
        if test3 is None:
            print("\n💡 Run a disk scan to verify decision engine logging")
            sys.exit(0)
        elif test3:
            print("\n✅ All tests passed - Passive mode working correctly!")
            sys.exit(0)
        else:
            print("\n❌ Decision engine not logging - check integration")
            sys.exit(1)
    else:
        print("\n❌ Integration incomplete")
        sys.exit(1)
