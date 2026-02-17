# MoSMART - S.M.A.R.T. Monitor

A Python-based tool for reading and interpreting S.M.A.R.T. (Self-Monitoring, Analysis and Reporting Technology) data from hard drives on Linux systems.

> 🇳🇴 [Norsk dokumentasjon](dokumentasjon-no.md) | 🇬🇧 [Full English Documentation](documentation-en.md)

## 🚀 Quick Installation

```bash
pip install mosmart
sudo mosmart-web
```

Open **http://localhost:5000** in your browser.

## Features

- 📊 Scan and display all available storage devices
- 🔍 Read detailed S.M.A.R.T. attributes
- ⚠️ Detect potential health issues
- 🌡️ Monitor disk temperature
- 📈 Display critical parameters like reallocated sectors, power-on hours, and more
- 🧠 **Health Score System** - Intelligent scoring (0-100) based on critical parameters
- 🌐 **Web Dashboard** - Modern web interface for real-time monitoring
- ⚙️ Configurable auto-refresh and individual disk monitoring
- 🛡️ **Emergency Unmount** - Automatic removal of critically failing drives (optional)
- ⌛ **Lifetime Remaining** - SMART ID 202 support for SSD wear measurement
- 🔒 **Thread-safe Scanning** - Race condition protection with watchdog monitoring
- 💻 Linux support and ⚠️ **Windows (via WSL2 - theoretical, not tested)**

## Testing and Validation

MoSMART has been validated through comprehensive testing with **24 different storage devices**:

- **Diverse disk types:** SSDs, SATA HDDs and IDE (legacy) drives
- **Real-world conditions:** Drives have been used by different users with varying workloads
- **Different wear levels:** From nearly new drives to near end-of-life
- **Real-world alignment:** The test set reflects how drives are actually used in practice - not just lab tests

This testing ensures that the program works reliably on drives in all conditions and user scenarios.

## Requirements

### System Requirements
- Linux operating system
- Python 3.7 or newer
- `smartmontools` installed on the system
- Root/sudo access to read S.M.A.R.T. data

### Installing System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install smartmontools python3-pip python3-venv

# Fedora/RHEL
sudo dnf install smartmontools python3-pip

# Arch Linux
sudo pacman -S smartmontools python-pip
```

## Installation

### Install via PyPI (Recommended)

```bash
pip install mosmart
```

**Run the web dashboard:**
```bash
sudo mosmart-web
```

### Manual Installation (Development)

1. **Install system dependencies**
   ```bash
   sudo apt update
   sudo apt install smartmontools python3-full python3-pip pipx
   ```

2. **Virtual Environment Setup (Isolated and Clean)**
   
   A virtual environment has been created at `/home/magnus/mosmart-venv`. This keeps MoSMART isolated from system Python.
   
   ```bash
   # Use the pre-configured virtual environment:
   /home/magnus/mosmart-venv/bin/python3 web_monitor.py
   
   # Or with sudo:
   sudo /home/magnus/mosmart-venv/bin/python3 web_monitor.py
   ```
   
   **To create a fresh virtual environment:**
   ```bash
   cd /path/to/mosmart
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   When using virtual environment, activate it before use:
   ```bash
   source venv/bin/activate
   ```

## Usage

> **Important:** If you're using the pre-configured venv: `/home/magnus/mosmart-venv/bin/python3` (no activation needed)
> 
> If using a manually created venv, activate it first: `source venv/bin/activate`

### Web Dashboard (Recommended!)

**Start the web server (using pre-configured venv):**
```bash
sudo /home/magnus/mosmart-venv/bin/python3 web_monitor.py
```

**Check disk health (CLI, no WebUI needed):**
```bash
sudo /home/magnus/mosmart-venv/bin/python3 web_monitor.py --check-health
```

**With custom port:**
```bash
sudo /home/magnus/mosmart-venv/bin/python3 web_monitor.py --port 8080
```

**With custom refresh interval:**
```bash
sudo ./venv/bin/python3 web_monitor.py --refresh 30
```

Then open your browser and go to: **http://localhost:5000**

### systemd Service (Recommended for servers)

If you install via PyPI, use the console script in `ExecStart` so it works regardless of install path:

```ini
[Service]
Type=simple
User=root
ExecStart=/usr/bin/env mosmart-web
Restart=always
RestartSec=10
StandardOutput=append:/var/log/mosmart.log
StandardError=append:/var/log/mosmart.log
```

**Web Dashboard features:**
- 🎨 Modern, color-coded display of all disks
- 🔄 Auto-refresh (configurable, default 60 sec)
- ⏯️ Enable/disable monitoring per disk
- 📊 Real-time updates of health scores
- 🎯 Detailed view of all health components
- 📱 Responsive design for mobile and desktop

### Command Line (CLI)

**List all storage devices:**
```bash
sudo ./venv/bin/python3 smart_monitor.py --list
```

**Display information about a specific disk:**
```bash
sudo ./venv/bin/python3 smart_monitor.py -d /dev/sda
```

**Display detailed S.M.A.R.T. attributes:**
```bash
sudo ./venv/bin/python3 smart_monitor.py -d /dev/sda --attributes
```

**Health summary only:**
```bash
sudo ./venv/bin/python3 smart_monitor.py -d /dev/sda --health
```

**Scan all disks:**
```bash
sudo ./venv/bin/python3 smart_monitor.py
```

### Command Line Options (CLI)

**smart_monitor.py:**
```
-l, --list          List all available storage devices
-d, --device PATH   Specify which device to monitor (e.g. /dev/sda)
-a, --attributes    Display detailed S.M.A.R.T. attributes
--health            Display health summary only
```

**web_monitor.py:**
```
-p, --port PORT     Port for webserver (default: 5000)
-r, --refresh SEC   Auto-refresh interval in seconds (default: 60)
--host HOST         Host to bind to (default: 127.0.0.1)
```

## Health Score System

The program uses an advanced scoring system based on industry standards from Backblaze, Google and disk manufacturers:

**Weighting:**
- **Reallocated sectors: 50%** - Most critical parameter
- **Pending sectors: 15%** - Sectors waiting for reallocation
- **Uncorrectable sectors: 10%** - Permanently damaged sectors
- **Command timeouts: 10%** - Responsiveness issues
- **Age: 10%** - Expected lifespan (HDD: 3-5 years, SSD: 5-10 years)
- **Temperature: 5%** - Operating temperature (HDD: <35°C ideal, SSD: <40°C)

**Score interpretation:**
- `95-100`: 🔵 EXCELLENT - Perfect condition
- `80-94`: 🟢 Good - Normal operation
- `60-79`: 🟡 Acceptable - Monitor regularly
- `40-59`: 🟠 Warning - Secure data with backup
- `20-39`: 🔴 Poor - High risk
- `0-19`: 🔴 CRITICAL - Replace ASAP
- `<0`: 💀 DEAD/ZOMBIE - Immediate replacement

## Important S.M.A.R.T. Attributes

The program specifically monitors these critical attributes:

- **ID 5**: Reallocated Sectors Count - Number of defective sectors that have been moved
- **ID 187**: Reported Uncorrectable Errors - Errors that could not be corrected
- **ID 196**: Reallocation Event Count - Number of attempts to move sectors
- **ID 197**: Current Pending Sectors - Sectors waiting to be moved (CRITICAL)
- **ID 198**: Offline Uncorrectable - Sectors that cannot be read
- **ID 199**: UltraDMA CRC Errors - Communication errors
- **ID 194**: Temperature - Current disk temperature
- **ID 9**: Power On Hours - Total operating time

## Ghost Drive Condition (GDC)

MoSMART includes special detection for "ghost drives" - drives that freeze or become unresponsive during SMART reads. This is especially common in certain Seagate models (ST2000DM001).

**GDC Status Levels:**
- `OK` - Drive responds normally
- `SUSPECT` - Some timeout issues detected
- `CONFIRMED` - Repeated failures, drive likely failing
- `TERMINAL` - Drive completely unresponsive

**GDC drives are:**
- Automatically excluded from normal scans (to prevent freezing)
- Only scanned during manual "Force Scan"
- Clearly marked with 👻 icon in the web interface

## Alert System

MoSMART can send email alerts when disk problems are detected:

**Alert Triggers:**
- Health score drops below thresholds
- Pending sectors detected
- Temperature exceeds limits
- GDC status changes

**Configuration:**
Edit `~/.mosmart/settings.json`:

```json
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password",
    "recipient_email": "alert-recipient@example.com"
  }
}
```

## Emergency Unmount

When a disk reaches EMERGENCY status, MoSMART can automatically unmount it to prevent data corruption.

**Two Modes:**
- **PASSIVE (Default)**: Logs decisions only, takes no action
- **ACTIVE (Optional)**: Automatically unmounts on EMERGENCY

**Safety Features:**
- Five-layer validation before unmount
- Never unmounts critical paths (/, /boot, /home, /usr, /var)
- 30-minute cooldown between attempts
- Comprehensive logging

**Enable ACTIVE mode:**
```json
{
  "emergency_unmount": {
    "mode": "ACTIVE",
    "require_confirmation": true
  }
}
```

See [EMERGENCY_UNMOUNT_IMPLEMENTATION.md](EMERGENCY_UNMOUNT_IMPLEMENTATION.md) for details.

## Multi-Language Support

MoSMART supports multiple languages:

- 🇬🇧 English
- 🇳🇴 Norwegian (Norsk)

Language files are located in `languages/` directory. The web interface automatically uses the language from your browser settings, with fallback to English.

## Example Output

```
============================================================
Device: /dev/sda
============================================================
Model:        Samsung SSD 870 EVO 500GB
Serial:       S5XXXXXXXX
Capacity:     500.107 GB
Interface:    ATA
Assessment:   PASS
Temperature:  35°C
Power On:     1234 hours

Health Summary:
Status: PASS
✓ No issues detected
```

## Project Structure

- `smart_monitor.py` - Main S.M.A.R.T. monitoring and health score calculation
- `web_monitor.py` - Flask web application with dashboard
- `disk_logger.py` - Smart logging with periodic and change-based triggers
- `decision_engine.py` - Pure decision logic for disk health evaluation
- `emergency_actions.py` - Emergency unmount execution with safety checks
- `gdc.py` - GDCManager class for detecting failing drives
- `alert_engine.py` & `email_notifier.py` - Alert system with email notifications
- `config_manager.py` - Configuration management
- `device_lifecycle_logger.py` - Track disk connection/disconnection events
- `requirements.txt` - Python dependencies
- `setup.py` - Package installation configuration

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Magnus Modig**
- Email: kontakt@modigs-datahjelp.no
- GitHub: [@MsModig](https://github.com/MsModig)

## Acknowledgments

- Based on the [pySMART](https://github.com/truenas/py-SMART) library
- Health score algorithms inspired by [Backblaze Hard Drive Stats](https://www.backblaze.com/b2/hard-drive-test-data.html)
- Special thanks to all beta testers who provided drives for testing

## Support

- 📖 [Full Documentation](documentation-en.md)
- 🐛 [Report Issues](https://github.com/MsModig/mosmart/issues)
- 💬 [Discussions](https://github.com/MsModig/mosmart/discussions)

---

**⚠️ Important Disclaimer:**

This tool is provided as-is for monitoring purposes. While it can help detect drive failures early, it is **NOT a substitute for regular backups**. Always maintain backups of important data, regardless of drive health status.
