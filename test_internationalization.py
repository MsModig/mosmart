#!/usr/bin/env python3
"""
Test script to verify internationalization implementation.
Checks that all translation keys used in main_new.js exist in translations.json.
"""

import json
import re
import sys

def load_translations():
    """Load translations.json"""
    with open('translations.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_translation_keys_from_js():
    """Extract all App.t() and this.t() calls from main_new.js"""
    with open('static/main_new.js', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all this.t('key') and App.t('key') calls
    pattern = r'(?:this|App)\.t\([\'"]([^\'"]+)[\'"]\)'
    matches = re.findall(pattern, content)
    
    return set(matches)

def main():
    print("=== Internationalization Test ===\n")
    
    # Load translations
    translations = load_translations()
    norwegian_keys = set(translations.get('no', {}).keys())
    english_keys = set(translations.get('en', {}).keys())
    
    # Extract keys used in JS
    js_keys = extract_translation_keys_from_js()
    
    # New keys from recent implementation
    new_keys = {
        'usb_smart_warning',
        'gdc_identity_preserved',
        'period_24h',
        'period_week',
        'period_month',
        'print_button',
        'download_txt_last100',
        'download_full_log',
        'download_full_warning',
        'loading_history',
        'no_history_available',
        'could_not_load_history',
        'no_log_file',
        'no_log_found',
        'could_not_load_full_log',
        'could_not_load_log',
        'time_years',
        'time_days',
        'time_hours',
        'no_log_data_24h',
        'no_log_data_week',
        'no_log_data_month',
        'report_generated',
        'device_not_found'
    }
    
    print(f"📊 Statistics:")
    print(f"  - Norwegian translation keys: {len(norwegian_keys)}")
    print(f"  - English translation keys: {len(english_keys)}")
    print(f"  - Keys used in main_new.js: {len(js_keys)}")
    print(f"  - New keys from implementation: {len(new_keys)}")
    print()
    
    # Check 1: All new keys exist in both languages
    print("✓ Check 1: New keys exist in translations.json")
    missing_no = new_keys - norwegian_keys
    missing_en = new_keys - english_keys
    
    if missing_no:
        print(f"  ❌ Missing from Norwegian: {missing_no}")
    else:
        print(f"  ✅ All {len(new_keys)} new keys present in Norwegian")
    
    if missing_en:
        print(f"  ❌ Missing from English: {missing_en}")
    else:
        print(f"  ✅ All {len(new_keys)} new keys present in English")
    print()
    
    # Check 2: All keys used in JS exist in translations
    print("✓ Check 2: JS keys exist in translations.json")
    missing_no_js = js_keys - norwegian_keys
    missing_en_js = js_keys - english_keys
    
    if missing_no_js:
        print(f"  ❌ Used in JS but missing from Norwegian: {missing_no_js}")
    else:
        print(f"  ✅ All JS keys present in Norwegian")
    
    if missing_en_js:
        print(f"  ❌ Used in JS but missing from English: {missing_en_js}")
    else:
        print(f"  ✅ All JS keys present in English")
    print()
    
    # Check 3: Norwegian and English have same keys
    print("✓ Check 3: Norwegian and English have matching keys")
    only_no = norwegian_keys - english_keys
    only_en = english_keys - norwegian_keys
    
    if only_no:
        print(f"  ⚠️  Only in Norwegian: {only_no}")
    if only_en:
        print(f"  ⚠️  Only in English: {only_en}")
    if not only_no and not only_en:
        print(f"  ✅ Perfect match: {len(norwegian_keys)} keys in both languages")
    print()
    
    # Check 4: Verify specific critical translations
    print("✓ Check 4: Critical translations are correct")
    critical_checks = [
        ('usb_smart_warning', 'no', 'USB: SMART-data'),
        ('usb_smart_warning', 'en', 'USB: SMART data'),
        ('report_generated', 'no', 'Rapport generert'),
        ('report_generated', 'en', 'Report generated'),
        ('period_week', 'no', 'Uke'),
        ('period_week', 'en', 'Week'),
    ]
    
    all_correct = True
    for key, lang, expected_substring in critical_checks:
        value = translations.get(lang, {}).get(key, '')
        if expected_substring in value:
            print(f"  ✅ {lang}/{key}: '{value}'")
        else:
            print(f"  ❌ {lang}/{key}: Expected '{expected_substring}' in '{value}'")
            all_correct = False
    print()
    
    # Final verdict
    print("=" * 50)
    if (not missing_no and not missing_en and 
        not missing_no_js and not missing_en_js and 
        not only_no and not only_en and all_correct):
        print("✅ SUCCESS: Internationalization implementation is complete!")
        print()
        print("Next steps:")
        print("1. Restart web_monitor.py: sudo systemctl restart mosmart")
        print("2. Test language switching in dashboard settings")
        print("3. Verify all 27 new strings change language correctly")
        return 0
    else:
        print("❌ FAILED: Some issues found")
        return 1

if __name__ == '__main__':
    sys.exit(main())
