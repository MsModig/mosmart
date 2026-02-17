# MoSMART Refactoring Plan - Server-Based Architecture

## Objective
Refactor MoSMART to use a client-server architecture where:
- **Backend**: Runs as systemd service with root privileges
- **GUI**: Runs as regular user without root, zero file I/O
- **API**: Complete REST API for all operations
- **Security**: Role-based access control (read-only, admin)

## Current Problems

1. **GUI requires root** - Violates principle of least privilege
2. **GUI writes directly to files** - `config_manager.load_config()`, state files, logs
3. **No permission model** - GUI can't enforce who should see what
4. **Scattered storage** - Config in `~/.mosmart`, state in various places
5. **Hard to audit** - No centralized access control

## New Architecture

### Directory Structure

```
/etc/mosmart/
├── settings.json          # Main configuration (root:root 0600)
├── users/
│   ├── admin-users.json   # List of users with admin rights
│   └── read-only.json     # List of read-only users
└── systemd/
    └── mosmart.service

/var/lib/mosmart/
├── state/
│   ├── mosmart188/        # Restart count tracking
│   ├── mosmart194/        # Max temperature tracking
│   ├── disk_events/       # Disk lifecycle events
│   └── gdc/              # GDC state
└── cache/
    └── api_responses/     # Cached API responses

/var/log/mosmart/
├── mosmart.log            # Main service log
├── api.log                # API access log
├── disks/                 # Per-disk logs
│   ├── sda/
│   ├── sdb/
│   └── ...
└── alerts/                # Alert history

/var/run/mosmart/
└── mosmart.pid            # PID file for service

~/.mosmart/ (Per-User)
├── cache/                 # Local GUI cache
├── preferences.json       # GUI preferences only (theme, window size)
└── recent_devices.json    # Recently viewed devices
```

### Permission Model

**Read-Only User**:
- Can view all monitoring data
- Cannot change settings
- Cannot trigger unmounts
- Cannot manage alerts

**Admin User**:
- Can view all data
- Can change settings
- Can trigger emergency unmount
- Can manage alerts and users

### API Endpoints

#### New Endpoints

```
GET /api/permissions
  → { "role": "admin" | "read-only", "username": "magnus" }

GET /api/config
  → { "general": {...}, "alert_thresholds": {...} }

POST /api/config
  → Update config (admin only)

GET /api/state/mosmart188/{disk_id}
  → Restart count data

GET /api/state/mosmart194/{disk_id}
  → Max temperature data

POST /api/state/mosmart194/{disk_id}/reset
  → Reset max temp (admin only)

GET /api/logs/{disk_id}?lines=100
  → Last N log lines for disk

POST /api/alerts/test
  → Test email alerts (admin only)
```

#### Existing Endpoints (Unchanged)

```
GET /api/devices            - Still works
GET /api/devices/{id}       - Still works
GET /api/external/health    - Still works
POST /api/scan              - Still works
POST /api/emergency-unmount - Becomes admin-only
```

## Implementation Phases

### Phase 1: Backend API Enhancements
1. Add `/api/permissions` endpoint
2. Add authentication middleware
3. Create config API endpoints
4. Create state API endpoints

### Phase 2: Configuration Management
1. Migrate settings.json to /etc/mosmart/
2. Create server-side config loading
3. Implement admin-only config endpoints
4. Backward compatibility layer

### Phase 3: GUI Refactoring
1. Remove config_manager imports from GUI
2. Create APIConfigManager class
3. Refactor SettingsDialog to use API
4. Add role checking and UI disable/enable

### Phase 4: Systemd and Installation
1. Update systemd service to run as root
2. Create /etc/mosmart and /var/lib/mosmart
3. Set correct ownership and permissions
4. Update install.sh to use standard directories

## Technical Changes

### Backend (web_monitor.py)

```python
# New authentication decorator
def require_permission(permission='read-only'):
    def decorator(f):
        def wrapper(*args, **kwargs):
            role = get_user_role(request.remote_user)
            if permission == 'admin' and role != 'admin':
                return {'error': 'Admin access required'}, 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/api/permissions')
@require_permission('read-only')
def get_permissions():
    username = request.remote_user or os.environ.get('SUDO_USER', 'unknown')
    role = 'admin' if os.getuid() == 0 else get_admin_role(username)
    return {'role': role, 'username': username}

@app.route('/api/config', methods=['GET'])
def get_config():
    return load_config('/etc/mosmart/settings.json')

@app.route('/api/config', methods=['POST'])
@require_permission('admin')
def update_config():
    data = request.json
    save_config('/etc/mosmart/settings.json', data)
    return {'success': True}
```

### GUI (gui_monitor.py)

```python
class APIConfigManager:
    """Get config from backend API instead of files"""
    
    def __init__(self, api_base='http://localhost:5000'):
        self.api_base = api_base
        self.permissions = self.fetch_permissions()
    
    def fetch_permissions(self):
        try:
            resp = requests.get(f'{self.api_base}/api/permissions', timeout=5)
            return resp.json()
        except:
            return {'role': 'read-only', 'username': 'unknown'}
    
    def load_config(self):
        resp = requests.get(f'{self.api_base}/api/config', timeout=5)
        return resp.json()
    
    def save_config(self, config):
        if self.permissions['role'] != 'admin':
            raise PermissionError("Admin access required")
        resp = requests.post(f'{self.api_base}/api/config', json=config, timeout=5)
        return resp.json()
    
    def is_admin(self):
        return self.permissions['role'] == 'admin'

class SettingsDialog:
    def __init__(self, parent, t_func):
        self.api_config = APIConfigManager()
        self.config = self.api_config.load_config()
        # If not admin, disable save button
        self.save_button.setEnabled(self.api_config.is_admin())
    
    def save_settings(self):
        try:
            self.api_config.save_config(self.config)
            show_success("Settings saved")
        except PermissionError:
            show_error("Admin access required to change settings")
```

## Security Considerations

1. **API Authentication**: Use Unix socket or localhost-only binding
2. **CORS**: Restrict to localhost
3. **File Permissions**: /etc/mosmart 0600, /var/lib/mosmart 0700
4. **Audit Logging**: Log all config changes with username and timestamp
5. **No Secrets in Config**: Use /etc/mosmart/secrets.json for passwords (0600)

## Backward Compatibility

- Keep old config at ~/.mosmart as fallback
- Migrate on first startup
- Support both old and new API paths
- Gradual transition possible

## Testing Strategy

1. Test API endpoints with/without admin role
2. Test GUI disables/enables correctly based on role
3. Test config save/load via API
4. Test systemd service startup
5. Test file permissions
6. Test migration from old config

## Files to Modify

### Backend
- `web_monitor.py` - Add API endpoints and auth
- `config_manager.py` - Add server-side config loading
- `mosmart.service` - Update to run as root

### GUI
- `gui_monitor.py` - Remove direct file access
- Remove dependency on `config_manager.py`

### Installation
- `install.sh` - Create /etc/mosmart and /var/lib/mosmart
- `setup.py` - Update to install as service

### New Files
- `backend/auth.py` - Authentication middleware
- `backend/permissions.py` - Permission checking
- `docker/Dockerfile` - Container support

## Timeline

- Phase 1: 1 hour (API endpoints)
- Phase 2: 1 hour (config migration)
- Phase 3: 2 hours (GUI refactoring)
- Phase 4: 1 hour (systemd and install)
- Testing: 1 hour
- **Total: ~6 hours**

## Success Criteria

✓ GUI runs as non-root user
✓ GUI has zero file I/O outside ~/.mosmart
✓ All configuration via /api/config
✓ All state reads via API
✓ /api/permissions returns correct role
✓ Read-only users can't change settings
✓ Admin users can change settings
✓ Systemd service runs as root
✓ /etc/mosmart owned by root:root 0600
✓ /var/lib/mosmart owned by root:root 0700
✓ Install script handles all permissions
✓ No hardcoded paths in installer
✓ Existing API unchanged
