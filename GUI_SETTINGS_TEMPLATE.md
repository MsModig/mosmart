# GUI Settings Tabs - Implementation Template

## Quick Guide for Adding New Settings Tabs

To add a new settings tab to the SettingsDialog, follow this template pattern.

### 1. Create Tab in `init_ui()` Method

```python
# Your Tab
your_tab = QWidget()
your_layout = QFormLayout(your_tab)  # or QVBoxLayout for complex layouts

# Add label (optional)
your_label = QLabel(self.t('your_label_key', 'Your Label:'))
your_label.setFont(QFont("Arial", 10, QFont.Bold))
your_layout.addRow(your_label)

# Add controls (spinbox, checkbox, combo, etc.)
self.your_spinbox = QSpinBox()
self.your_spinbox.setRange(1, 100)
self.your_spinbox.setValue(self.config.get('your_section', {}).get('your_key', 10))
your_layout.addRow(self.t('label_key', 'Label:'), self.your_spinbox)

# Add stretch if needed
if isinstance(your_layout, QVBoxLayout):
    your_layout.addStretch()

# Add to tabs
tabs.addTab(your_tab, f"🟫 {self.t('tab_label_key', 'Tab Label')}")
```

### 2. Update `save_settings()` Method

```python
# Initialize config section if needed
if 'your_section' not in self.config:
    self.config['your_section'] = {}

# Save values
self.config['your_section']['your_key'] = self.your_spinbox.value()
```

### 3. Configuration Structure

Config follows nested pattern:
```json
{
  "section_name": {
    "key_name": value
  }
}
```

**Common Sections**:
- `general` - Application settings
- `disk_selection` - Disk monitoring options
- `alert_thresholds` - Alert and warning thresholds
  - `.health` - Health score thresholds
  - `.smart` - SMART attribute thresholds
  - `.temperature` - Temperature thresholds
- `emergency_unmount` - Emergency actions

### 4. Control Types and Patterns

#### QSpinBox (Integer Input)
```python
self.my_spin = QSpinBox()
self.my_spin.setRange(1, 100)
self.my_spin.setValue(self.config.get('section', {}).get('key', 50))
self.my_spin.setSuffix(" suffix")  # Optional: °C, seconds, %, etc.
value = self.my_spin.value()  # Save: use .value()
```

#### QCheckBox (Boolean Input)
```python
self.my_check = QCheckBox("Label text")
self.my_check.setChecked(self.config.get('section', {}).get('key', True))
is_checked = self.my_check.isChecked()  # Save: use .isChecked()
```

#### QComboBox (Selection)
```python
self.my_combo = QComboBox()
self.my_combo.addItems(['option1', 'option2', 'option3'])
self.my_combo.setCurrentText(self.config.get('section', {}).get('key', 'option1'))
selected = self.my_combo.currentText()  # Save: use .currentText()
```

#### QLineEdit (Text Input)
```python
self.my_text = QLineEdit()
self.my_text.setText(self.config.get('section', {}).get('key', ''))
text = self.my_text.text()  # Save: use .text()
```

### 5. Tab Icon and Color Conventions

Use emoji for visual identification:
- ⬜ **General** - System settings
- 🟦 **Health** - Health score settings
- 🟥 **Security** - Emergency/safety features
- 🟫 **Disks** - Disk selection
- 🟨 **SMART** - SMART attribute settings
- 🟩 **Temperature** - Temperature settings
- 🟧 **GDC** - Ghost Drive Condition
- 📋 **Logging** - Log settings
- 📧 **Alerts** - Alert configuration

### 6. Translation Keys

Always use translation keys for user-visible strings:
```python
self.t('translation_key', 'Default English Text')
```

Common keys:
- `general_settings` → "General"
- `health_alerts` → "Health"
- `security_settings` → "Security"
- `disk_selection` → "Disks"
- `smart_alerts` → "SMART"
- `temp_alerts` → "Temperature"

### 7. Example: Adding a New "GDC" Tab

```python
# In init_ui(), after Temperature tab:

# GDC tab
gdc_tab = QWidget()
gdc_layout = QFormLayout(gdc_tab)

self.gdc_enabled_check = QCheckBox("Enable GDC Detection")
self.gdc_enabled_check.setChecked(self.config.get('gdc', {}).get('enabled', True))
gdc_layout.addRow(self.gdc_enabled_check)

self.gdc_threshold_spin = QSpinBox()
self.gdc_threshold_spin.setRange(1, 10)
self.gdc_threshold_spin.setValue(self.config.get('gdc', {}).get('threshold', 5))
gdc_layout.addRow(self.t('gdc_threshold', 'GDC Threshold:'), self.gdc_threshold_spin)

tabs.addTab(gdc_tab, f"🟧 {self.t('gdc_settings', 'GDC')}")

# In save_settings():
if 'gdc' not in self.config:
    self.config['gdc'] = {}
self.config['gdc']['enabled'] = self.gdc_enabled_check.isChecked()
self.config['gdc']['threshold'] = self.gdc_threshold_spin.value()
```

### 8. Testing Your Tab

After implementing:
1. Syntax check:
   ```bash
   python3 -m py_compile gui_monitor.py
   ```

2. Run GUI (with sudo for config access):
   ```bash
   sudo /home/magnus/mosmart/.venv-gui/bin/python3 gui_monitor.py
   ```

3. Verify:
   - Tab appears in Settings dialog
   - Controls load with config values
   - Changing values and clicking Save works
   - Config file updated with new values

### 9. Full Checklist

- [ ] Tab UI created in `init_ui()` with all controls
- [ ] Controls load config values with `.get()` and defaults
- [ ] Save logic added to `save_settings()` method
- [ ] Config section properly nested (check JSON structure)
- [ ] Translation keys used for all user-visible text
- [ ] Emoji icon added to tab label
- [ ] Control ranges/limits set appropriately
- [ ] Units/suffixes added (°C, seconds, etc.)
- [ ] Syntax check passes: `python3 -m py_compile gui_monitor.py`
- [ ] GUI runs without errors: `sudo python3 gui_monitor.py`
- [ ] Settings dialog opens to new tab
- [ ] Values load and save correctly
- [ ] Config file updated correctly
- [ ] WebUI reads same config values

### 10. Debugging

**Values not loading?**
- Check config section/key names match exactly
- Verify `.get()` defaults match actual config structure
- Run: `sudo python3 -c "import config_manager; import json; print(json.dumps(config_manager.load_config(), indent=2))"`

**Values not saving?**
- Ensure save logic added to `save_settings()` method
- Check `.value()` or `.isChecked()` used correctly
- Verify config dictionary structure before `save_config()`

**GUI crashes?**
- Check syntax: `python3 -m py_compile gui_monitor.py`
- Check imports at top of file
- Review error message carefully

**Translation not working?**
- Verify `self.t()` method exists (it does)
- Check key name in translations.json
- Use fallback text if key missing
