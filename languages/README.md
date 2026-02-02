# Language Files for MoSMART Monitor

## Adding a New Language

To add support for a new language, follow these steps:

### Step 1: Copy the Template

```bash
cp template.lang your_language.lang
```

For example:
- `german.lang`
- `french.lang`
- `spanish.lang`
- `japanese.lang`

### Step 2: Edit the File

Open your new `.lang` file and update these fields:

1. **language_name**: The name in the native language (e.g., "Deutsch", "Français", "日本語")
2. **language_code**: ISO 639-1 two-letter code (e.g., "de", "fr", "ja")
3. **translations**: Translate each value (see example below)

#### Example (German):
```json
{
    "language_name": "Deutsch",
    "language_code": "de",
    "translations": {
        "refresh_now": "Jetzt aktualisieren",
        "force_scan": "Scan erzwingen",
        "settings": "Einstellungen",
        ...
    }
}
```

### Step 3: Test Your Translation

1. **Save** your `.lang` file in the `languages/` directory
2. **Restart** the MoSMART server (if running):
   ```bash
   sudo pkill -f "web_monitor.py"
   sudo ./venv/bin/python3 web_monitor.py
   ```
3. **Open** the web interface at `http://localhost:5000`
4. **Go to** Settings ⚙️ → General Settings
5. **Select** your language from the dropdown
6. **Verify** all text is translated correctly

### Translation Tips

- **Be consistent**: Use the same terminology throughout
- **Keep it concise**: Some labels appear in buttons or small spaces
- **Test thoroughly**: Check all tabs in Settings, all buttons, all modals
- **Technical terms**: Some terms like "SMART", "GDC", "SSD", "HDD" are typically not translated
- **Units**: Keep temperature units (°C), time units (seconds, hours) in their common form
- **Punctuation**: Include colons (:) at the end of labels where present in English/Norwegian

### Complete Translation Keys

See `english.lang` for the complete list of all 66 translation keys with their English values. All keys must be present in your translation file.

### File Format

- **Format**: JSON (JavaScript Object Notation)
- **Encoding**: UTF-8 (supports all international characters)
- **Structure**: Object with `language_name`, `language_code`, and `translations`
- **Naming**: `<language_in_english>.lang` (lowercase)

### Current Languages

- 🇳🇴 **Norwegian** (no) - `norwegian.lang`
- 🇬🇧 **English** (en) - `english.lang`

### Contributing

If you create a quality translation, please consider contributing it back:
1. Test thoroughly
2. Create a pull request or send the file to the project maintainer
3. Include your name/handle for credit in the documentation

### Troubleshooting

**Language doesn't appear in dropdown:**
- Check JSON syntax is valid (use JSONLint.com)
- Verify file is named `*.lang`
- Restart the server
- Check browser console for errors (F12)

**Text not translating:**
- Verify `language_code` matches what's shown in dropdown
- Clear browser cache (Ctrl+Shift+R)
- Check all translation keys are present (compare with `template.lang`)

**Special characters broken:**
- Ensure file is saved as UTF-8 encoding
- Use proper JSON escaping for quotes: `\"`

---

**Auto-detection:** The system automatically scans this directory for `*.lang` files on startup. No code changes needed!

