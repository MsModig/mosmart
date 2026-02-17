# MoSMART Installation Requirements

## Essential Files for MoSMART to Function

MoSMART requires the following files to be installed and functional:

### Core Python Modules (Required)
```
smart_monitor.py              - Main SMART monitoring engine
config_manager.py             - Configuration management
disk_logger.py                - Disk health logging
alert_engine.py               - Alert processing system
decision_engine.py            - Health decision logic
emergency_actions.py          - Emergency unmount execution
gdc.py                        - Ghost Drive Condition detection
gdc_logger.py                 - GDC event logging
device_lifecycle_logger.py    - Device connection tracking
email_notifier.py             - Email notification system
mosmart188_manager.py         - SMART attribute manager (188)
mosmart194_manager.py         - SMART attribute manager (194)
```

### Web Interface (Required for WebUI)
```
web_monitor.py                - Flask web application
templates/dashboard.html      - Web dashboard HTML
static/main_new.js            - Web dashboard JavaScript
static/datasmart.css          - Web dashboard CSS
static/datasmart_gui.css      - GUI-specific styles
```

### Desktop GUI (Required for GUI)
```
gui_monitor.py                - PyQt5 desktop application
gui_advanced.py               - Advanced GUI features
apple-touch-icon.png          - App icon
web-app-manifest-192x192.png  - App manifest icon
web-app-manifest-512x512.png  - App manifest icon
```

### Configuration & Data Files
```
translations.json             - Multi-language translations
languages/english.lang        - English language file
languages/norwegian.lang      - Norwegian language file
```

### Service & Installation Scripts (Required for Linux Integration)
```
setup.py                      - Python package setup
requirements.txt              - Python dependencies
mosmart.service               - systemd service file
install.sh                    - Installation script
uninstall.sh                  - Uninstallation script
update.sh                     - Update script
start_gui.sh                  - GUI launcher script
start_gui_simple.sh           - Simple GUI launcher
```

### Documentation
```
README.md                     - English documentation
README-NO.md                  - Norwegian documentation
documentation-en.md           - Extended English docs
dokumentasjon-no.md           - Extended Norwegian docs
CHANGELOG.md                  - Version history
PASSIVE_MODE_README.md        - Decision engine documentation
EMERGENCY_UNMOUNT_IMPLEMENTATION.md - Emergency feature docs
```

### Optional But Recommended
```
LICENSE                       - GPL v3 license
COPYRIGHT                     - Copyright notice
```

## Excluded Files (Should NOT be included in distribution)

### Runtime/Log Files
- `*.log` - Log files
- `.mosmart/` - User configuration directory
- `*.jsonl` - Log line files

### Development/Testing Files
- `__pycache__/` - Python cache
- `.venv/` - Virtual environments
- `*.pyc`, `*.pyo`, `*.pyd` - Compiled Python
- `.git/` - Git repository
- `.idea/`, `.vscode/` - IDE files
- `dist/`, `build/`, `*.egg-info/` - Build artifacts

### Implementation Documentation (Not for Release)
- `*_IMPLEMENTATION.md` - Implementation notes
- `ALERT_ENGINE_README.md`
- `EMAIL_SECURITY.md`
- `LANGUAGE_FALLBACK.md`
- `LANGUAGES.md`
- `LOGGING_ENHANCEMENT_SUMMARY.md`

### User Configuration (Must NOT be included)
- `~/.mosmart/` - User settings
- `/etc/mosmart/settings.json` - System settings
- Email passwords in any form
- SMTP credentials
- API keys or tokens

## Installation Methods

### Method 1: From Source (Development)
```bash
git clone https://github.com/MsModig/mosmart.git
cd mosmart
pip install -e .
```

Required: All files except excluded items

### Method 2: From PyPI (User Installation)
```bash
pip install mosmart
```

Includes: All essential modules and configuration files only
Excludes: Development files, test files, documentation

### Method 3: Linux System Package
```bash
sudo apt install mosmart  # (when available)
```

Or manual installation:
```bash
sudo ./install.sh
```

Includes: All files with proper permissions
Excludes: Development and test files

## Minimum Viable Installation

To have a working MoSMART installation, you need:

**For CLI/Backend**:
- All core Python modules (smart_monitor.py, config_manager.py, etc.)
- setup.py and requirements.txt
- translations.json

**For WebUI**:
- web_monitor.py
- templates/dashboard.html
- static/ directory (all CSS/JS files)

**For Desktop GUI**:
- gui_monitor.py
- Icons (apple-touch-icon.png, etc.)

**For System Integration**:
- mosmart.service
- install.sh

## Disk Space Requirements

- Core installation: ~2.5 MB
- With documentation: ~3.5 MB
- With venv: ~100 MB
- Log files (per disk): 1-10 MB (configurable)

## Configuration Files Created at Runtime

These are created by MoSMART when first run:
- `/etc/mosmart/settings.json` - System configuration
- `/var/log/mosmart/` - Log directory
- `~/.mosmart/` - User preferences

## System Requirements

**Operating System**: Linux (Debian, Ubuntu, RHEL, Arch, etc.)
**Python**: 3.7 or later
**Root Access**: Required for SMART data reading
**Dependencies**: See requirements.txt

## Verification Checklist

Before distribution, verify:
- [ ] setup.py version matches CHANGELOG.md
- [ ] No *.log files present
- [ ] No email credentials in any file
- [ ] All *.pyc and __pycache__ removed
- [ ] .git/ directory excluded
- [ ] /venv directory excluded
- [ ] No settings.json from test installations
- [ ] CHANGELOG.md up to date
- [ ] All imports in Python files are valid
- [ ] All template/static files present
- [ ] README.md matches current version
