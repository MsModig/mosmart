# MoSMART GUI Settings Tabs - Visual Reference

## Tab Layout

The Settings Dialog now contains 6 tabs (3 existing + 3 new):

```
┌─ ⬜ General ─┬─ 🟦 Health ─┬─ 🟥 Security ─┬─ 🟫 Disks ─┬─ 🟨 SMART ─┬─ 🟩 Temperature ─┐
│             │             │               │            │            │                 │
│ Language    │ Score drop  │ Emergency     │ ☑ sda      │ Reallocated│ HDD Warning:    │
│ en / no ▼   │ threshold   │ Unmount Mode: │   CT480... │ sectors: 5 │ 50°C [▢▢▢▢▢ 50]│
│             │ 1 [▢▢▢ 3]  │               │ ☑ sdb      │            │                 │
│ Refresh     │             │ ◉ PASSIVE     │   WDC Blue │ Pending:   │ HDD Critical:   │
│ interval    │ Critical    │ ○ ACTIVE      │ ☐ sdc      │ sectors: 1 │ 60°C [▢▢▢▢▢ 60]│
│ 60 [▢▢▢ 60] │ score:      │               │   Samsung  │            │                 │
│             │ 40 [▢▢▢ 40] │ Require       │            │ Uncorrectable
│             │             │ confirmation  │            │ errors: 1  │ SSD Warning:    │
│             │             │ ✓             │            │            │ 60°C [▢▢▢▢▢ 60]│
│             │             │               │            │ Command    │                 │
│             │             │               │            │ timeout: 5 │ SSD Critical:   │
│             │             │               │            │            │ 70°C [▢▢▢▢▢ 70]│
│                                                                                         │
│ [Save Settings]                                                  [Cancel]             │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Tab Details

### 🟫 Disks Tab
**Purpose**: Select which disks to monitor

```
┌────────────────────────────────────────┐
│ Select disks to monitor:               │
│                                        │
│ ☑ sda - CT480BX500SSD1                │
│ ☑ sdb - SEAGATE ST2000DM001           │
│ ☐ sdc - Samsung 860 EVO               │
│ ☑ sdd - WDC WD10EZEX-08M              │
│                                        │
│ [                                  ] ← Fill remaining space
└────────────────────────────────────────┘
```

**Features**:
- Checkboxes for each connected disk
- Model name displayed for identification
- Easy enable/disable without backend interaction
- Default: All disks monitored (✓)

### 🟨 SMART Tab
**Purpose**: Set thresholds for SMART attribute alerts

```
┌────────────────────────────────────────┐
│ Reallocated sectors threshold:         │
│ [▢▢▢ 5 ◀─────────────────────────────] │
│                                        │
│ Pending sectors threshold:             │
│ [▢ 1 ◀────────────────────────────────] │
│                                        │
│ Uncorrectable errors threshold:        │
│ [▢ 1 ◀────────────────────────────────] │
│                                        │
│ Command timeout threshold:             │
│ [▢▢▢ 5 ◀─────────────────────────────] │
└────────────────────────────────────────┘
```

**Thresholds**:
| Metric | Min | Max | Default |
|--------|-----|-----|---------|
| Reallocated sectors | 1 | 10,000 | 5 |
| Pending sectors | 1 | 1,000 | 1 |
| Uncorrectable errors | 1 | 100 | 1 |
| Command timeout | 1 | 100 | 5 |

### 🟩 Temperature Tab
**Purpose**: Set temperature warning and critical thresholds

```
┌────────────────────────────────────────┐
│ Temperature thresholds:                │
│                                        │
│ HDD Warning:                           │
│ [▢▢▢▢ 50°C ◀──────────────────────────] │
│                                        │
│ HDD Critical:                          │
│ [▢▢▢▢▢ 60°C ◀─────────────────────────] │
│                                        │
│ SSD Warning:                           │
│ [▢▢▢▢▢ 60°C ◀─────────────────────────] │
│                                        │
│ SSD Critical:                          │
│ [▢▢▢▢▢▢ 70°C ◀────────────────────────] │
└────────────────────────────────────────┘
```

**Ranges**:
- All values: 30-100°C
- HDD defaults: 50°C (warning), 60°C (critical)
- SSD defaults: 60°C (warning), 70°C (critical)

## Configuration Example

When you click **Save Settings**, the following JSON is written to `~/.mosmart/settings.json`:

```json
{
  "general": {
    "language": "en",
    "polling_interval": 60
  },
  "disk_selection": {
    "monitored_devices": {
      "sda": true,
      "sdb": true,
      "sdc": false,
      "sdd": true
    }
  },
  "alert_thresholds": {
    "health": {
      "score_drop": 3,
      "critical_score": 40
    },
    "smart": {
      "reallocated_sectors": 5,
      "pending_sectors": 1,
      "uncorrectable_errors": 1,
      "command_timeout": 5
    },
    "temperature": {
      "hdd_warning": 50,
      "hdd_critical": 60,
      "ssd_warning": 60,
      "ssd_critical": 70
    }
  },
  "emergency_unmount": {
    "mode": "PASSIVE",
    "require_confirmation": true
  }
}
```

## User Workflow

### Step 1: Open Settings
```
Main GUI Window
↓
[⚙️ Settings] button
↓
Settings Dialog opens (with 6 tabs)
```

### Step 2: Configure Disks
```
Click "🟫 Disks" tab
↓
Select which disks to monitor
↓
Example: Uncheck SSD if it's a system drive and you only want to monitor external drives
```

### Step 3: Configure SMART Alerts
```
Click "🟨 SMART" tab
↓
Adjust thresholds based on your preferences
↓
Example: Increase reallocated sectors threshold to 10 if you're monitoring older drives
```

### Step 4: Configure Temperature
```
Click "🟩 Temperature" tab
↓
Set warning/critical temps for your drive types
↓
Example: Lower SSD critical from 70°C to 60°C if you want more aggressive monitoring
```

### Step 5: Save
```
Click [Save Settings] button
↓
Config written to ~/.mosmart/settings.json
↓
Success message displays
↓
Settings immediately take effect in next scan
```

## Integration Points

The three new tabs integrate with:

1. **Disk Monitoring** (`smart_monitor.py`):
   - Uses `disk_selection.monitored_devices` to determine which disks to scan
   - Skips disks marked as `false`

2. **SMART Alerts** (`alert_engine.py`):
   - Uses `alert_thresholds.smart` values for threshold checking
   - Compares actual SMART values against configured thresholds

3. **Temperature Alerts** (`alert_engine.py`):
   - Uses `alert_thresholds.temperature` values
   - Applies HDD vs SSD thresholds based on drive type

## Data Synchronization

✅ **GUI ↔ WebUI Synchronization**:
- Both read from the same config file: `~/.mosmart/settings.json`
- Changes in GUI settings appear in WebUI immediately
- Changes in WebUI settings appear in GUI after reload
- No conflicts or race conditions (file-based persistence)

## Implementation Files

- **UI Definition**: [gui_monitor.py](gui_monitor.py) lines 1013-1093
- **Save Logic**: [gui_monitor.py](gui_monitor.py) lines 1178-1220
- **Config Manager**: [config_manager.py](config_manager.py)
- **Tests**: [test_gui_settings_tabs.py](test_gui_settings_tabs.py)
- **Documentation**: [GUI_SETTINGS_TABS.md](GUI_SETTINGS_TABS.md)
