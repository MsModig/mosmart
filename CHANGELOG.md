# Changelog

All notable changes to this project will be documented in this file.

## [0.9.4] - 2026-02-17

### Added
- **GUI Settings Dialog Enhancements**:
  - Fixed QStackedWidget import for 3x3 grid navigation
  - Fixed QFormLayout.addStretch() incompatibility
  - Settings window now 850x700 with geometry persistence (remembers size)
  - Category buttons reduced to 40px height for compact layout

- **Emergency Unmount Testing**:
  - "Test Emergency Unmount" button in Security tab
  - Shows what would be unmounted without actually unmounting
  - Displays protected disks and reasons for protection

- **Documentation Button**:
  - "View Documentation" button in About tab
  - Language-specific URLs (Norwegian/English)
  - Opens documentation in default browser

- **New Settings Categories** (9 total in 3x3 grid):
  - **⬛ GDC Tab**: Timeout threshold (1-60s), max retries (1-20), persist state checkbox
  - **🟧 Logging Tab**: Log retention (100-10240 KB, default 1024), rolling logs checkbox, verbosity level (debug/info/warning/error)
  - **🟪 Notifications Tab**: Full email SMTP configuration with test button

- **WebUI Control** (partial implementation):
  - Added `enable_webui` setting to general config
  - WebUI respects disable setting at startup and during runtime
  - Middleware blocks requests with HTTP 503 when disabled

### Fixed
- **Password Field Handling**:
  - Password field now stays empty when opening Settings (not populating with asterisks)
  - Password only updates if user explicitly enters a new value
  - Matches WebUI behavior - "leave blank to keep existing"
  - Prevents accidental password overwrite with empty string

- **Email Settings Path**:
  - Fixed config path from `email` (root) to `alert_channels.email` (nested)
  - Email config fields now sync with WebUI: `from_email`, `to_emails`
  - Settings properly saved/loaded from correct backend location

- **Logging Configuration**:
  - Updated from separate log level/retention_days to unified structure
  - Now uses: `retention_size_kb` (100-10240), `rolling_logs` (checkbox), `verbosity` (dropdown)
  - Matches WebUI logging configuration exactly

- **Emergency Unmount Status**:
  - Fixed status badge in main window
  - Now reads from API instead of non-existent config variable
  - Updates correctly when settings change

### Changed
- **Settings Dialog Startup**:
  - Increased minimum size from 700x600 to 850x700
  - Added QSettings persistence to remember window position/size
  - Reduced tab button height from 100px to 40px

- **Config Structure Updates**:
  - Logging: `level` → `verbosity`, added `retention_size_kb`, added `rolling_logs`
  - General: Added `enable_webui` setting (default: true)

- **WebUI Behavior**:
  - Added before_request middleware to check enable_webui
  - Returns HTTP 503 if WebUI disabled
  - Startup now shows status: "Dashboard: http://..." or "⚠️ WebUI is DISABLED"
  - If disabled at startup, service stays alive but doesn't serve HTTP (background mode only)

### Security
- Password fields no longer populate existing passwords in GUI
- Prevents password display in placeholder asterisks
- Email credentials only updated if explicitly changed by user

### Known Issues
- Enable WebUI toggle needs further testing for runtime switching
- Planned for refinement in 0.9.5

### Dependencies
- No new external dependencies added
- Existing dependencies: pySMART, Flask, flask-cors, waitress, cryptography

### Files Modified
- `gui_monitor.py` - Settings dialog complete refactor (9 categories, password handling, logging sync)
- `config_manager.py` - Added `enable_webui` to DEFAULT_CONFIG
- `web_monitor.py` - Added before_request middleware, startup logic for enable_webui
- `setup.py` - Version bumped to 0.9.4

### Installation Notes
- Run `pip install -e .` after pulling changes
- Settings dialog requires PyQt5 (already in gui_monitor.py dependencies)
- No system-level configuration changes required

### Breaking Changes
- None for end users
- Config migration: Old `logging.level` settings will use `verbosity` default (info)
- Config migration: Old `logging.retention_days` settings will use `retention_size_kb` default (1024)

### Migration Guide
For users upgrading from 0.9.3:
1. Settings will use defaults for logging if not present
2. Email settings path updated transparently
3. Re-save settings in GUI to update to new structure
4. WebUI enabled by default (no action needed unless you want to disable)

## [0.9.3] - 2026-02-15

### Features
- External health endpoint for API integration
- Ghost Drive Condition (GDC) detection for all disk brands
- Emergency Unmount system (PASSIVE mode by default)
- Decision engine for disk health evaluation
- Multi-language support (Norwegian/English)
- Email alerting system
- Web dashboard with real-time monitoring
- Desktop GUI with PyQt5

---

For detailed information about previous versions, see the README.md and PASSIVE_MODE_README.md files.
