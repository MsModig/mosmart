# MoSMART v0.9.4 Release Checklist

## Pre-Release Verification (✅ Complete)

### Code Quality
- [x] All syntax errors fixed
- [x] QStackedWidget import added
- [x] QFormLayout.addStretch() removed
- [x] Password field handling fixed
- [x] Email config path corrected
- [x] Logging configuration unified
- [x] Settings dialog tested and working

### Version Management
- [x] Version updated to 0.9.4 in setup.py
- [x] CHANGELOG.md created with complete v0.9.4 changes
- [x] All changes documented from v0.9.3

### File Distribution
- [x] .gitignore updated - no logs, no credentials
- [x] MANIFEST.in created - specifies included files
- [x] .gitattributes created - line ending control
- [x] INSTALL_REQUIREMENTS.md created - file documentation
- [x] No __pycache__ files in repo
- [x] No venv directories in repo
- [x] No test_*.py files in .gitignore (they should be distributed)

### Security Verification
- [x] No email credentials in any file
- [x] No user configuration (.mosmart/) included
- [x] No system configuration (settings.json) included
- [x] No log files included
- [x] No API keys or tokens in code
- [x] Password field doesn't populate existing values

### Documentation
- [x] README.md - User guide (English)
- [x] README-NO.md - User guide (Norwegian)
- [x] CHANGELOG.md - Version history
- [x] INSTALL_REQUIREMENTS.md - File requirements
- [x] PASSIVE_MODE_README.md - Decision engine docs
- [x] EMERGENCY_UNMOUNT_IMPLEMENTATION.md - Feature docs

### Dependencies
- [x] setup.py has all required packages
- [x] PyQt5 marked as optional (gui extra)
- [x] cryptography added to requirements
- [x] requirements.txt matches setup.py

### PyPI Preparation
- [x] setup.py follows PyPI standards
- [x] Long description uses README.md
- [x] Classifiers are accurate
- [x] Keywords are appropriate
- [x] Package_data configured
- [x] extras_require configured (gui, dev)
- [x] Entry points correct

## Release Steps

### Step 1: Git Commit and Tag
```bash
cd /home/magnus/mosmart

# Stage all changes
git add -A

# Commit with message
git commit -m "v0.9.4: GUI Settings refactoring, password handling fix, logging sync"

# Create annotated tag
git tag -a v0.9.4 -m "MoSMART v0.9.4 Release

- Settings dialog complete refactoring (9 categories)
- Fixed password field handling (leave blank to keep)
- Unified logging configuration with WebUI
- Added CHANGELOG.md and INSTALL_REQUIREMENTS.md
- Improved PyPI compatibility"

# Verify tag
git tag -l v0.9.4
git show v0.9.4
```

### Step 2: Push to GitHub
```bash
# Push commits
git push origin main

# Push tags
git push origin v0.9.4

# Or push all tags
git push origin --tags

# Verify on GitHub.com
# https://github.com/MsModig/mosmart/releases
```

### Step 3: Create GitHub Release
```
On GitHub.com:
1. Go to Releases section
2. Click "Draft a new release"
3. Select tag: v0.9.4
4. Title: "MoSMART v0.9.4 - GUI Settings Refactoring"
5. Description: Copy from CHANGELOG.md v0.9.4 section
6. Publish release
```

### Step 4: Build PyPI Distribution
```bash
cd /home/magnus/mosmart

# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Build distribution
python3 setup.py sdist bdist_wheel

# Verify builds
ls -lh dist/
# Should show:
# - mosmart-0.9.4-py3-none-any.whl
# - mosmart-0.9.4.tar.gz
```

### Step 5: Test Local Installation
```bash
# Create test venv
python3 -m venv /tmp/test-mosmart
source /tmp/test-mosmart/bin/activate

# Install from wheel
pip install ./dist/mosmart-0.9.4-py3-none-any.whl

# Verify installation
python3 -c "import smart_monitor; print('✓ Import successful')"
mosmart-web --help

# Test with GUI extra
pip install ./dist/mosmart-0.9.4-py3-none-any.whl[gui]

# Clean up
deactivate
rm -rf /tmp/test-mosmart
```

### Step 6: Upload to PyPI (When Ready)
```bash
# Install twine if not present
pip install twine

# Test upload to TestPyPI first (recommended)
twine upload --repository testpypi dist/*

# Then verify on: https://test.pypi.org/project/mosmart/

# Real PyPI upload
twine upload dist/*

# Verify on: https://pypi.org/project/mosmart/
```

## Post-Release

### Documentation Updates
- [ ] Add v0.9.4 to GitHub Releases page
- [ ] Update documentation links if any changed
- [ ] Update PyPI package information

### Notification
- [ ] Announce release in relevant forums/communities
- [ ] Update any installation guides
- [ ] Notify users if upgrading is recommended

### Next Steps
- [ ] Plan v0.9.5 features
- [ ] Document known issues
- [ ] Review feedback from release

## File Checklist for Distribution

### ✅ Included in Distribution
```
Core Modules:
  ✓ smart_monitor.py
  ✓ config_manager.py
  ✓ disk_logger.py
  ✓ alert_engine.py
  ✓ decision_engine.py
  ✓ emergency_actions.py
  ✓ gdc.py
  ✓ gdc_logger.py
  ✓ device_lifecycle_logger.py
  ✓ email_notifier.py
  ✓ mosmart188_manager.py
  ✓ mosmart194_manager.py

GUI & Web:
  ✓ web_monitor.py
  ✓ gui_monitor.py
  ✓ gui_advanced.py
  ✓ templates/dashboard.html
  ✓ static/main_new.js
  ✓ static/datasmart.css
  ✓ static/datasmart_gui.css

Configuration:
  ✓ setup.py
  ✓ MANIFEST.in
  ✓ requirements.txt
  ✓ translations.json
  ✓ languages/

Service:
  ✓ mosmart.service
  ✓ install.sh
  ✓ uninstall.sh
  ✓ update.sh
  ✓ start_gui.sh
  ✓ start_gui_simple.sh
  ✓ start_gui.bat

Documentation:
  ✓ README.md
  ✓ README-NO.md
  ✓ CHANGELOG.md
  ✓ INSTALL_REQUIREMENTS.md
  ✓ LICENSE
  ✓ COPYRIGHT

Assets:
  ✓ apple-touch-icon.png
  ✓ web-app-manifest-192x192.png
  ✓ web-app-manifest-512x512.png

Test Files:
  ✓ test_decision_engine.py
  ✓ test_email_system.py
  ✓ test_emergency_unmount.py
  ✓ test_gdc_model_serial.py
  ✓ test_gdc_unassessable.py
  ✓ test_gui_settings_tabs.py
  ✓ test_internationalization.py
  ✓ test_language_fallback.py
  ✓ test_passive_mode.py
```

### ❌ Excluded from Distribution
```
Runtime:
  ✗ *.log files
  ✗ .mosmart/ directory
  ✗ /var/log/mosmart/

Development:
  ✗ __pycache__/
  ✗ *.pyc, *.pyo
  ✗ .venv*, venv/
  ✗ .git/

Configuration Files:
  ✗ /etc/mosmart/settings.json
  ✗ Email credentials
  ✗ SMTP passwords

Documentation (Development only):
  ✗ *_IMPLEMENTATION.md files
  ✗ Session summaries
  ✗ Completion reports
```

## Version History

- **v0.9.4** (2026-02-17) - Settings refactoring, password fix, logging sync
- **v0.9.3** (2026-02-15) - External health endpoint, GDC detection
- **v0.9.2** - Emergency unmount system
- **v0.9.1** - Decision engine (passive mode)
- **v0.9.0** - Initial release

---

**Release Coordinator**: Magnus Modig  
**Release Date**: 2026-02-17  
**Status**: Ready for distribution
