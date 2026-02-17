#!/usr/bin/env python3
"""
Test language fallback mechanism.
Creates a test German language file with missing keys to verify fallback to English.
"""

import json
from pathlib import Path

# Load English translations as base
with open('languages/english.lang', 'r', encoding='utf-8') as f:
    english = json.load(f)

# Create German file with only SOME translations (simulate incomplete translation)
german = {
    "language_name": "Deutsch",
    "language_flag": "🇩🇪",
    "language_code": "de",
    "translations": {
        # Only translate a few keys - rest should fallback to English
        "refresh_now": "Jetzt aktualisieren",
        "force_scan": "Scan erzwingen",
        "settings": "Einstellungen",
        "about": "Über",
        "health_score": "Gesundheitsbewertung",
        "temperature": "Temperatur",
        "ok": "OK",
        "warning": "Warnung",
        "critical": "Kritisch"
        # Missing: time_years, time_days, time_hours, etc. - should fallback to English
    }
}

# Save test German file
german_path = Path('languages/german.lang')
with open(german_path, 'w', encoding='utf-8') as f:
    json.dump(german, f, indent=4, ensure_ascii=False)

print("✅ Created test German language file with only 9 translations")
print(f"   English has {len(english['translations'])} translations")
print(f"   German has {len(german['translations'])} translations")
print(f"   Missing: {len(english['translations']) - len(german['translations'])} keys")
print()
print("🔍 Keys that should fallback to English:")
missing_keys = set(english['translations'].keys()) - set(german['translations'].keys())
for i, key in enumerate(sorted(missing_keys)[:10], 1):
    print(f"   {i}. {key}: '{english['translations'][key]}'")
if len(missing_keys) > 10:
    print(f"   ... and {len(missing_keys) - 10} more")
print()
print("📝 To test:")
print("   1. Restart mosmart: sudo systemctl restart mosmart")
print("   2. Open dashboard, go to Settings")
print("   3. Change language to 'Deutsch'")
print("   4. Check that time units show 'Years, Days, Hours' (English fallback)")
print("   5. Check that buttons show German: 'Jetzt aktualisieren', 'Einstellungen'")
