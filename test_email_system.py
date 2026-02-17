#!/usr/bin/env python3
"""
Test script for email configuration system
Verifies that all components work together correctly
"""

import json
from pathlib import Path

# Import our modules
import config_manager
import email_notifier

# Config file location
CONFIG_FILE = Path.home() / '.mosmart' / 'settings.json'

def test_config_flow():
    """Test the complete configuration flow"""
    print("=" * 70)
    print("TESTING EMAIL CONFIGURATION SYSTEM")
    print("=" * 70)
    
    # 1. Check if settings.json exists
    config_file = Path.home() / '.mosmart' / 'settings.json'
    print(f"\n1. Checking config file: {config_file}")
    if config_file.exists():
        print(f"   ✅ File exists")
        with open(config_file) as f:
            config = json.load(f)
            print(f"   📄 Size: {config_file.stat().st_size} bytes")
    else:
        print(f"   ⚠️  File does not exist - will be created on first save")
    
    # 2. Load email config via config_manager
    print(f"\n2. Loading email config via config_manager")
    alert_channels = config_manager.get_section('alert_channels')
    email_config = alert_channels.get('email', {})
    print(f"   Enabled: {email_config.get('enabled', False)}")
    print(f"   SMTP Server: {email_config.get('smtp_server', 'N/A')}")
    print(f"   SMTP Port: {email_config.get('smtp_port', 'N/A')}")
    print(f"   Username: {email_config.get('smtp_username', '(empty)')}")
    print(f"   Password: {'(set)' if email_config.get('smtp_password') else '(empty)'}")
    print(f"   To Emails: {email_config.get('to_emails', [])}")
    print(f"   Use TLS: {email_config.get('use_tls', False)}")
    print(f"   Use STARTTLS: {email_config.get('use_starttls', False)}")
    
    # 3. Load email config via email_notifier
    print(f"\n3. Loading email config via email_notifier.load_email_config()")
    loaded_config = email_notifier.load_email_config()
    print(f"   Enabled: {loaded_config.get('enabled', False)}")
    print(f"   SMTP Server: {loaded_config.get('smtp_server', 'N/A')}")
    print(f"   SMTP Port: {loaded_config.get('smtp_port', 'N/A')}")
    
    # 4. Verify they match
    print(f"\n4. Verifying consistency")
    # Compare key values (skip to_emails list comparison)
    match = True
    for key in ['enabled', 'smtp_server', 'smtp_port', 'smtp_username', 'use_tls', 'use_starttls']:
        if email_config.get(key) != loaded_config.get(key):
            match = False
            print(f"   Mismatch on {key}: {email_config.get(key)} vs {loaded_config.get(key)}")
    
    if match:
        print(f"   ✅ Configs match!")
    
    # 5. Test save/load cycle
    print(f"\n5. Testing save/load cycle")
    test_config = {
        'enabled': True,
        'smtp_server': 'smtp.test.com',
        'smtp_port': 587,
        'smtp_username': 'test@test.com',
        'smtp_password': 'testpass123',
        'from_email': 'alerts@test.com',
        'to_emails': ['admin@test.com'],
        'use_tls': True,
        'use_starttls': True,
        'alert_on_severity': ['critical']
    }
    
    print(f"   Saving test config...")
    success = email_notifier.save_email_config(test_config)
    if success:
        print(f"   ✅ Save successful")
    else:
        print(f"   ❌ Save failed")
    
    print(f"   Loading back...")
    loaded_back = email_notifier.load_email_config()
    
    if loaded_back['smtp_server'] == 'smtp.test.com':
        print(f"   ✅ Config persisted correctly")
    else:
        print(f"   ❌ Config not persisted")
        print(f"   Expected: smtp.test.com")
        print(f"   Got: {loaded_back['smtp_server']}")
    
    # 6. Test validation
    print(f"\n6. Testing validation")
    
    # Test with disabled email
    disabled_config = test_config.copy()
    disabled_config['enabled'] = False
    result = email_notifier.test_email_config(disabled_config)
    if not result['success'] and 'deaktivert' in result['error'].lower():
        print(f"   ✅ Correctly rejects disabled email")
    else:
        print(f"   ❌ Should reject disabled email")
        print(f"   Result: {result}")
    
    # Test with missing credentials
    no_creds = test_config.copy()
    no_creds['enabled'] = True
    no_creds['smtp_username'] = ''
    result = email_notifier.test_email_config(no_creds)
    if not result['success'] and 'brukernavn' in result['error'].lower():
        print(f"   ✅ Correctly rejects missing credentials")
    else:
        print(f"   ❌ Should reject missing credentials")
        print(f"   Result: {result}")
    
    # Test with missing recipients
    no_recipients = test_config.copy()
    no_recipients['enabled'] = True
    no_recipients['to_emails'] = []
    result = email_notifier.test_email_config(no_recipients)
    if not result['success'] and 'mottaker' in result['error'].lower():
        print(f"   ✅ Correctly rejects missing recipients")
    else:
        print(f"   ❌ Should reject missing recipients")
        print(f"   Result: {result}")
    
    # 7. Test password encryption
    print(f"\n7. Testing password encryption")
    
    # Save a password
    test_password = "MySecretPassword123!"
    encrypt_test_config = {
        'enabled': True,
        'smtp_server': 'smtp.test.com',
        'smtp_port': 587,
        'smtp_username': 'test@test.com',
        'smtp_password': test_password,
        'from_email': 'test@test.com',
        'to_emails': ['admin@test.com'],
        'use_tls': True,
        'use_starttls': True,
        'alert_on_severity': ['critical']
    }
    
    email_notifier.save_email_config(encrypt_test_config)
    
    # Read directly from file to verify encryption
    with open(CONFIG_FILE) as f:
        file_data = json.load(f)
        stored_password = file_data['alert_channels']['email']['smtp_password']
    
    if stored_password != test_password:
        print(f"   ✅ Password encrypted in file (not plain text)")
        print(f"   Encrypted length: {len(stored_password)} chars")
    else:
        print(f"   ❌ Password NOT encrypted in file!")
    
    # Load and verify decryption
    loaded = email_notifier.load_email_config()
    if loaded['smtp_password'] == test_password:
        print(f"   ✅ Password decrypts correctly")
    else:
        print(f"   ❌ Password decryption failed")
        print(f"   Expected: {test_password}")
        print(f"   Got: {loaded['smtp_password']}")
    
    # Check encryption key file
    key_file = Path.home() / '.mosmart' / '.email_key'
    if key_file.exists():
        import stat
        key_perms = oct(key_file.stat().st_mode)[-3:]
        print(f"   ✅ Encryption key file exists")
        print(f"   Key file permissions: {key_perms} {'(secure)' if key_perms == '600' else '(INSECURE!)'}")
    else:
        print(f"   ❌ Encryption key file not found!")
    
    # 8. Restore original config
    print(f"\n8. Restoring original config")
    email_notifier.save_email_config(email_config)
    print(f"   ✅ Config restored")
    
    print(f"\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print(f"\n💡 To test actual email sending:")
    print(f"   1. Open settings in web UI")
    print(f"   2. Fill in all email fields")
    print(f"   3. Check 'Enable Email Notifications'")
    print(f"   4. Click 'Test E-post'")
    print(f"   5. Check server console for detailed SMTP logs")
    print()

if __name__ == '__main__':
    test_config_flow()
