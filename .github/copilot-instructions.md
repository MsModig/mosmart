# Python S.M.A.R.T. Monitor Project

## Project Overview
This is a Python-based tool for reading and interpreting S.M.A.R.T. (Self-Monitoring, Analysis and Reporting Technology) data from hard drives on Linux systems.

## Key Features
- Scan and display all available storage devices
- Read detailed S.M.A.R.T. attributes
- Detect potential health issues
- Monitor disk temperature
- Display critical parameters
- Web-based dashboard for real-time monitoring
- Ghost Drive Condition (GDC) detection for failing drives (all brands)
- Smart periodic logging with change detection
- Email alerting system
- Multi-language support (Norwegian/English)
- **Emergency Unmount** - Automatic disk removal on EMERGENCY status (PASSIVE/ACTIVE modes)

## Technical Stack
- Python 3.7+
- pySMART library for S.M.A.R.T. data access
- smartmontools (system dependency)
- Flask for web interface
- waitress for production server

## Project Structure
- `smart_monitor.py` - Main S.M.A.R.T. monitoring and health score calculation
- `web_monitor.py` - Flask web application with dashboard
- `disk_logger.py` - Smart logging with periodic and change-based triggers
- `decision_engine.py` - Pure decision logic for disk health evaluation
- `emergency_actions.py` - **Emergency unmount execution with safety checks**
- `gdc.py` - GDCManager class for detecting failing drives (all brands)
- `gdc_logger.py` - Ghost Drive Condition logging
- `smart_monitor.py::detect_ghost_drive_condition()` - Seagate-specific GDC detection
- `alert_engine.py` & `email_notifier.py` - Alert system with email notifications
- `config_manager.py` - Configuration management
- `device_lifecycle_logger.py` - Track disk connection/disconnection events
- `requirements.txt` - Python dependencies
- `setup.py` - Package installation configuration
- `README.md` - User documentation in Norwegian
- `PASSIVE_MODE_README.md` - Documentation for decision engine passive mode
- `PASSIVE_MODE_IMPLEMENTATION.md` - Implementation summary and test results
- `EMERGENCY_UNMOUNT_IMPLEMENTATION.md` - **Emergency unmount documentation**
- `templates/` - HTML templates for web dashboard
- `static/` - CSS and JavaScript for web interface

## Development Notes
- Requires root/sudo access to read S.M.A.R.T. data
- Uses pySMART wrapper around smartctl command
- Monitors critical attributes: reallocated sectors, uncorrectable errors, temperature

## Development Environment Setup

### Pre-configured Virtual Environment

A virtual environment has been set up at `/home/magnus/mosmart-venv` with all dependencies installed.

**Using the pre-configured venv:**
```bash
# Run web interface
sudo /home/magnus/mosmart-venv/bin/python3 web_monitor.py

# Check health (no WebUI needed)
sudo /home/magnus/mosmart-venv/bin/python3 web_monitor.py --check-health

# Run tests
/home/magnus/mosmart-venv/bin/python3 test_passive_mode.py
```

### Creating a Fresh Virtual Environment

If you need a new venv:
```bash
python3 -m venv /path/to/new-venv
/path/to/new-venv/bin/pip install -r requirements.txt

# Or activate for development
source /path/to/new-venv/bin/activate
pip install -r requirements.txt
```

**Important Dependencies:**
- pySMART (≥1.2.0) - SMART data access
- Flask (≥3.0.0) - Web framework
- flask-cors (≥4.0.0) - CORS support
- waitress (≥2.1.0) - Production WSGI server
- cryptography (≥41.0.0) - Email encryption
- CLI tool with argparse for flexible usage

## Logging Behavior (Important!)
The disk_logger.py module implements smart logging to minimize redundant entries:

### Automatic Logging Triggers:
1. **Hourly logging** - Logs once per full hour (e.g., 13:00, 14:00) during scans
2. **SMART value changes** - Logs when Reallocated Sectors (ID 5) or Pending Sectors (ID 197) change
3. **First scan** - Always logs the first time a disk is seen

### Manual Logging:
- Force scans (via web dashboard) always log
- Manual script invocations with `force=True` always log

### Implementation Details:
- State tracked in memory: `_last_logged_state` dictionary
- Each log entry includes `log_reason` field: "manual", "first_scan", "hourly", or "smart_change"
- Function signature: `log_disk_health(device, forc

## Ghost Drive Condition (GDC) Detection

### Two-Layer Detection System:

**1. GDCManager (gdc.py) - Universal Failing Disk Detection:**
- Works for **ALL disk brands** (Seagate, Western Digital, Samsung, etc.)
- Detects behavioral patterns indicating disk failure:
  - Repeated timeouts during SMART reads
  - Missing or corrupt SMART data
  - Disk disappearing between scans
  - Never delivering valid SMART data
- State machine: OK → SUSPECT → CONFIRMED → TERMINAL
- Used by web_monitor.py to skip scanning obviously dead drives

**2. detect_ghost_drive_condition() - Seagate-Specific:**
- Focused on known Seagate ST2000DM001 series issues
- Looks for specific indicators:
  - Known problematic models (ST2000DM001, ST3000DM001, ST1000DM003)
  - Extremely high reallocated sectors (>10,000)
  - Excessive command timeouts
- Returns confidence level: 'high', 'medium', 'low'

Both systems work together to provide comprehensive failing disk detection.

## Decision Engine (PASSIVE MODE - Active)

**Status**: ✅ Decision engine running in PASSIVE MODE  
**Implementation Date**: 25. desember 2025

### What is Passive Mode?

The decision engine evaluates disk health at every logging event but **DOES NOT TAKE ANY ACTIONS**. It only logs decisions for observation and testing.

### Integration Points:

**disk_logger.py**:
- `_evaluate_passive_decision()` - Evaluates health using decision_engine
- Adds `decision_engine` and `decision_engine_mode: "PASSIVE"` fields to log entries
- Prints console output: `🔍 [PASSIVE DECISION ENGINE] {device}: {status} - {reasons}`

**Log Entry Example**:
```json
{
  "timestamp": "2025-12-25T07:14:25",
  "device_name": "sda",
  "health_score": 100,
  "decision_engine": {
    "status": "OK",
    "reasons": [],
    "recommended_actions": [],
    "can_emergency_unmount": false,
    "notes": []
  },
  "decision_engine_mode": "PASSIVE"
}
```

### Decision Thresholds:

**Reallocated Sectors**:
- 5 sectors: WARNING
- 50 sectors: CRITICAL
- 500 sectors: EMERGENCY (downgraded to CRITICAL without combination signal)

**Pending Sectors**:
- 1 sector: WARNING
- 50 sectors: CRITICAL

**Temperature** (HDD/SSD):
- ≥50°C / ≥60°C: WARNING
- ≥60°C / ≥70°C: CRITICAL
- ≥65°C / ≥75°C: EMERGENCY (downgraded without combination)

**EMERGENCY Activation**:
- Requires 2+ signals OR
- Both Reallocated AND Pending sectors increasing simultaneously

### Important Guarantees:

❌ **NO ACTIONS TAKEN**:
- No email alerts based on decisions
- No automatic unmounting
- No emergency stops
- Existing alert_engine unchanged

✅ **OBSERVATION ONLY**:
- Decision engine runs on every log
- Decisions stored in log files
- Console output for real-time monitoring
- All existing functionality unchanged

### Testing:

```bash
# Test passive mode integration
sudo python3 test_passive_mode.py

# Test decision engine logic
python3 test_decision_engine.py
```

See [PASSIVE_MODE_README.md](PASSIVE_MODE_README.md) and [PASSIVE_MODE_IMPLEMENTATION.md](PASSIVE_MODE_IMPLEMENTATION.md) for complete documentation.

## Emergency Unmount (ACTIVE MODE - Implemented)

**Status**: ✅ Emergency unmount fully implemented  
**Implementation Date**: 22. januar 2026  
**Default Mode**: PASSIVE (safe - no actions)

### What is Emergency Unmount?

When a disk reaches EMERGENCY status, the system can automatically unmount it to prevent data corruption.

### Two Modes:

**PASSIVE (Default)**:
- Decision engine evaluates EMERGENCY status
- Logs decisions only
- No automatic unmounting
- Completely safe

**ACTIVE (Optional)**:
- All PASSIVE features PLUS
- Automatically unmounts disk on EMERGENCY
- Requires explicit config enable
- Full safety validation before unmount

### Safety Guarantees:

✅ **Five-Layer Validation**:
1. Decision status == EMERGENCY
2. can_emergency_unmount == True
3. Device is mounted
4. Mountpoint is NOT critical path (/, /boot, /home, /usr, /var)
5. NOT in cooldown (30 minutes)

✅ **Default to PASSIVE**:
- Config missing → PASSIVE
- Config corrupt → PASSIVE
- Any exception → PASSIVE

✅ **Cooldown Protection**:
- 30 minutes between unmount attempts per disk
- Prevents unmount spam
- Applies even if unmount fails

✅ **Critical Path Protection**:
- NEVER unmounts: /, /boot, /home, /usr, /var
- Only /mnt/* and /media/* can be unmounted

### Configuration:

Enable ACTIVE mode in `~/.mosmart/settings.json`:
```json
{
  "emergency_unmount": {
    "mode": "ACTIVE",
    "require_confirmation": true
  }
}
```

### Log Entry Example (ACTIVE mode):

```json
{
  "timestamp": "2026-01-22T14:30:05",
  "device_name": "sdb",
  "health_score": 45,
  "decision_engine": {
    "status": "EMERGENCY",
    "reasons": ["Reallocated: 1500", "Pending: 85 increasing"],
    "can_emergency_unmount": true
  },
  "decision_engine_mode": "ACTIVE",
  "emergency_unmount_attempted": true,
  "emergency_unmount_success": true
}
```

### Testing:

```bash
# Test emergency unmount system
sudo python3 test_emergency_unmount.py
```

See [EMERGENCY_UNMOUNT_IMPLEMENTATION.md](EMERGENCY_UNMOUNT_IMPLEMENTATION.md) for complete documentation.

## External Health Endpoint

**Status**: ✅ Generic health endpoint implemented  
**Implementation Date**: 15. februar 2026  
**Refactored from**: MoWIPE-specific integration to generic external health check

### What is the External Health Endpoint?

A generic, application-agnostic API that provides disk health information.

**Design Philosophy**:
- No application-specific naming
- Works with any external tool that needs disk health data
- Future-proof and extensible
- Backend function independent of WebUI/Flask
- Works with or without running web interface

### Three Ways to Access Health Data:

#### 1. Via HTTP API (requires WebUI running)
```bash
curl -s http://localhost:5000/api/external/health | jq .
```

#### 2. Via CLI (no WebUI required)
```bash
sudo python3 web_monitor.py --check-health | jq .
```

#### 3. Via Python Import (programmatic access)
```python
from web_monitor import get_external_health

health_data = get_external_health()
print(health_data['disk_count'])
```

### API Endpoint:

**GET /api/external/health** - Complete system status in one call

Returns:
- Installation status and version
- All disks with health scores
- Critical SMART attributes
- GDC states
- System information

### CLI Usage:

```bash
# Check health without starting WebUI
sudo python3 web_monitor.py --check-health

# Output as pretty JSON
sudo python3 web_monitor.py --check-health | jq .

# Check specific disk
sudo python3 web_monitor.py --check-health | jq '.disks[] | select(.name == "sda")'

# Check all disk temperatures
sudo python3 web_monitor.py --check-health | jq '.disks[] | {name, temperature}'

# Check if any disk has warnings
sudo python3 web_monitor.py --check-health | jq '.disks[] | select(.has_warnings == true)'
```

### Backend Function:

`get_external_health()` - Core function independent of Flask/WebUI
- Can be called from CLI tools
- Can be called from background services
- Can be called from other external applications
- Can be imported and used in custom scripts
- Fully decoupled from web interface

### Response Format:

```json
{
  "installed": true,
  "version": "0.9.3",
  "service": "MoSMART",
  "timestamp": "2026-02-15T11:48:32.914517",
  "uptime_seconds": 3600,
  "system": {
    "os": "Linux",
    "platform": "Linux-6.8.0-94-generic-x86_64-with-glibc2.39",
    "hostname": "magnus-dell"
  },
  "disks": [
    {
      "name": "sda",
      "model": "CT480BX500SSD1",
      "serial": "1935E19720A3",
      "capacity": "480 GB",
      "health_score": 100,
      "health_rating": "🔵 UTMERKET",
      "temperature": 31,
      "power_on_hours": 49784,
      "interface": "sat",
      "responsive": true,
      "has_warnings": false,
      "gdc_state": "OK",
      "smart_critical": {
        "reallocated_sectors": 0,
        "pending_sectors": 0,
        "uncorrectable_errors": 0,
        "power_cycle_count": 0
      }
    }
  ],
  "disk_count": 4,
  "warnings": [],
  "warning_count": 0,
  "gdc_states": {},
  "scan_error": null,
  "api_endpoints": {
    "external_health": "/api/external/health",
    "full_devices": "/api/devices"
  }
}
```

### Usage Examples:

Used by external tools such as:
- **MoWIPE** - Disk wiping tool (primary user) - Check disk health before wiping
- **System monitoring dashboards** - Real-time health status
- **Third-party health checkers** - Integration points
- **Automated disk management** - Health-based decisions
- **Backup systems** - Skip unhealthy disks
- **Data recovery tools** - Assess disk condition

### Implementation:

- `web_monitor.py::get_external_health()` - Backend function (Flask-independent)
- `web_monitor.py::api_external_health()` - Flask API endpoint
- `web_monitor.py --check-health` - CLI access

**Note**: Integration documentation for specific tools is located in their respective project repositories.

## Project Status
- [x] Create copilot-instructions.md file
- [x] Get project setup information
- [x] Scaffold Python project structure
- [x] Implement S.M.A.R.T. data collection
- [x] Install dependencies and test
- [x] Update documentation
