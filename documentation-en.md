# MoSMART - Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [Installation](#installation)
   - [Linux](#installation-linux)
   - [Windows (via WSL2)](#installation-windows-wsl2)
3. [Using the Tool](#using-the-tool)
4. [Scoring System](#scoring-system)
5. [Ghost Drive Condition (GDC)](#ghost-drive-condition-gdc)
6. [Alert System](#alert-system)
7. [Frequently Asked Questions](#frequently-asked-questions)

---

## Introduction

MoSMART is a comprehensive monitoring tool for hard drives and SSDs that reads and interprets S.M.A.R.T. data (Self-Monitoring, Analysis and Reporting Technology). The program provides you with:

- **Real-time monitoring** of disk status and health
- **Health score** (0-100) based on critical parameters
- **Automatic alerts** via email when problems occur
- **GDC detection** (Ghost Drive Condition) for freezing drives
- **History** with graphs and trend analysis
- **Modern web interface** accessible from any browser

### Testing and Validation

MoSMART has been validated through comprehensive testing with **24 different storage devices**:

- **Diverse disk types:** SSDs, SATA HDDs and IDE (legacy) drives
- **Real-world conditions:** Drives have been used by different users with varying workloads
- **Different wear levels:** From nearly new drives to near end-of-life
- **Real-world alignment:** The test set reflects how drives are actually used in practice - not just lab tests

This testing ensures that the program works reliably on drives in all conditions and user scenarios.

---

## Installation

### Installation: Linux

#### Prerequisites
- Ubuntu/Debian-based Linux (20.04 or newer)
- Python 3.7 or newer
- Root/sudo access

#### Step 1: Install system dependencies
```bash
sudo apt update
sudo apt install smartmontools python3-pip python3-venv git
```

#### Step 2: Clone or download the project
```bash
cd ~
git clone <repository-url> mosmart
# Or extract the zip file if downloaded manually
```

#### Step 3: Set up Python virtual environment
```bash
cd mosmart
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Step 4: Start the server
```bash
sudo ./venv/bin/python3 web_monitor.py
```

#### Step 5: Open in browser
Go to: `http://localhost:5000`

#### Run in background (optional)
To run the server in the background:
```bash
nohup sudo -b ./venv/bin/python3 web_monitor.py > /tmp/mosmart.log 2>&1
```

Stop the server:
```bash
sudo pkill -f "web_monitor.py"
```

#### Auto-start on system boot (recommended)
To make MoSMART start automatically when the system boots:

1. Install the systemd service:
```bash
cd ~/mosmart
sudo cp mosmart.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mosmart.service
```

2. Start the service:
```bash
sudo systemctl start mosmart.service
```

3. Check status:
```bash
sudo systemctl status mosmart.service
```

Useful commands:
- `sudo systemctl stop mosmart` - Stop service
- `sudo systemctl restart mosmart` - Restart service
- `sudo journalctl -u mosmart -f` - View live logs
- `sudo systemctl disable mosmart` - Disable auto-start

---

### Installation: Windows (WSL2)

⚠️ **NOTE:** WSL2 support is based on theoretical implementation and is **NOT tested** in practice. The instructions below provide guidance, but functionality with SMART reading via WSL2 may vary.

WSL2 (Windows Subsystem for Linux) allows you to run Linux programs directly in Windows.

#### Step 1: Install WSL2
Open PowerShell as Administrator and run:
```powershell
wsl --install
```

This installs Ubuntu automatically. Restart your computer when prompted.

#### Step 2: Set up Ubuntu
The first time you start Ubuntu, you need to:
1. Choose a username
2. Choose a password
3. Update the system:
```bash
sudo apt update && sudo apt upgrade
```

#### Step 3: Install dependencies in WSL
```bash
sudo apt install smartmontools python3-pip python3-venv git
```

#### Step 4: Copy the project to WSL
From Windows, you can copy files to WSL:
```bash
# In WSL terminal:
cd ~
cp -r /mnt/c/Users/YourUsername/Downloads/mosmart ~/mosmart
```

Or clone directly:
```bash
cd ~
git clone <repository-url> mosmart
```

#### Step 5: Set up Python environment
```bash
cd ~/mosmart
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Step 6: Start the server
```bash
sudo ./venv/bin/python3 web_monitor.py
```

#### Step 7: Open in Windows browser
Even though the server runs in WSL, it's accessible in Windows:
```
http://localhost:5000
```

#### Tips for Windows users
- **Access WSL files from Windows:** Open `\\wsl$\Ubuntu\home\username\mosmart` in File Explorer
- **Start WSL:** Search for "Ubuntu" in the Start menu
- **Auto-start on boot:** Create a task in Windows Task Scheduler that runs `wsl -d Ubuntu -u root /home/username/mosmart/start.sh`

---

## Using the Tool

### Main Screen

When you open `http://localhost:5000` you'll see:

- **Device cards** for each disk with:
  - Model and serial number
  - Health score (0-100)
  - Temperature
  - Power-on hours
  - Capacity
  - Status icon (✅ OK, ⚠️ Warning, 🔴 Critical, 👻 GDC)

### Filter View
- **All devices** - shows everything
- **Monitored** - only disks set to be monitored
- **Not monitored** - disks you've disabled monitoring for
- **With alerts** - disks with active problems

### Score Weighting

**For HDD (Hard Disk Drives):**
- Reallocated sectors: 35% - Defective sectors (solved problem)
- **Pending sectors: 25%** - Sectors failing NOW (active danger)
- Power cycles: 10% - Number of power on/off cycles (mechanical wear)
- Uncorrectable sectors: 10% - Permanently damaged sectors
- Command timeouts: 10% - Responsiveness issues
- Age: 5% - Expected lifespan (3-5 years typical)
- Temperature: 5% - Operating temperature (<35°C ideal)

**For SSD (Solid State Drives):**
- Reallocated sectors: 35-40% - Defective blocks (solved problem)
- **Pending sectors: 25%** - Blocks failing NOW (active danger)
- Wear level: 0-15% - Based on total bytes written (when available)
- Temperature: 10% - Operating temperature (<50°C ideal)
- Uncorrectable sectors: 5-10% - Permanently damaged blocks
- Command timeouts: 5-10% - Responsiveness issues
- Age: 2-5% - Expected lifespan (5-10 years typical)

### Score Interpretation:
- `95-100`: 🔵 EXCELLENT - Perfect condition
- `80-94`: 🟢 Good - Normal operation
- `60-79`: 🟡 Acceptable - Monitor regularly
- `40-59`: 🟠 Warning - Secure data with backup
- `20-39`: 🔴 Poor - High risk
- `0-19`: 🔴 CRITICAL - Replace ASAP
- `<0`: 💀 DEAD/ZOMBIE - Immediate replacement

### Force Scan
Click **"Force Scan"** at the top right to:
- Force a full scan of all disks (including GDC drives)
- Update data immediately
- Trigger the alert system

### Per-Disk Actions

For each disk you have buttons:

#### 📊 Details
Shows detailed information:
- All S.M.A.R.T. attributes
- Current values, thresholds, raw data
- Attribute type (Pre-fail/Old age)

#### 📈 History
Shows historical graphs for:
- Health score over time
- Temperature over time
- Critical attributes (reallocated sectors, pending sectors)
- Can select time period: 24h, Week, Month

#### 📝 View Log
Shows detailed log for the disk:
- When disk was scanned
- Changes in health score
- GDC events
- Alerts that were sent

#### ⏸️/▶️ Toggle Monitoring
Toggles monitoring on/off for this disk:
- **ON** (⏸️): Disk is scanned and alerts are sent
- **OFF** (▶️): Disk is scanned, but no alerts

### Settings ⚙️

Click the gear icon at the top right to configure:

#### General Settings
- **Refresh Interval:** How often data is updated automatically (seconds)
- **Language:** Interface language (Norwegian/English)

#### Health Alerts
- **Score Drop Threshold:** How much health score can drop before alert is sent
- **Critical Score:** Below this score a critical alert is sent

#### Temperature Alerts
- **SSD Warning:** Temperature threshold for warning (SSD)
- **SSD Critical:** Temperature threshold for critical alert (SSD)
- **HDD Warning:** Temperature threshold for warning (HDD)
- **HDD Critical:** Temperature threshold for critical alert (HDD)
- **Consecutive Readings:** How many consecutive readings above threshold before alert

#### Milestone Alerts
- **Reallocated Sectors:** Threshold values for reallocated sectors (e.g. 1, 10, 50)
- **Pending Sectors:** Threshold values for pending sectors

#### Alert Channels (Email)
- **SMTP Server:** Your email server (e.g. smtp.gmail.com)
- **SMTP Port:** Port (587 for TLS, 465 for SSL)
- **Username:** Your email address
- **Password:** App password (not regular password!)
- **From Email:** Sender address
- **To Emails:** Recipient(s), comma-separated
- **Use TLS / Use STARTTLS:** Encryption settings

**Test Email:** Send a test email to verify everything works.

---

## Scoring System

Health score (0-100) is calculated differently for HDD and SSD based on critical S.M.A.R.T. parameters.

### For HDD (Hard Disk Drives)

**Component Weighting:**
- **Reallocated Sectors (35%):** Number of defective sectors replaced
- **Pending Sectors (25%):** Sectors waiting to be reallocated (active danger)
- **Power Cycles (10%):** Number of power on/off cycles (mechanical wear)
- **Uncorrectable Errors (10%):** Errors that cannot be corrected
- **Command Timeout (10%):** Commands that timed out
- **Age (5%):** Disk age based on power-on hours
- **Temperature (5%):** Disk temperature

**Scoring Logic:**
```
Reallocated Sectors:
  0 sectors = 100 points
  1-10 sectors = 90 points
  11-100 sectors = 70 points
  101-500 sectors = 40 points
  501-1000 sectors = 20 points
  1001-5000 sectors = 5 points
  5001-10000 sectors = -10 points
  10001-20000 sectors = -50 points
  >20000 sectors = -100 points (Zombie disk)

Pending Sectors:
  0 = 100 points
  1 = 85 points
  2-5 = 60 points
  6-20 = 30 points
  21-100 = 10 points
  101-300 = -30 points
  301-500 = -70 points
  >500 = -100 points (Critical zombie)

Power Cycles:
  <1000 = 100 points (normal usage)
  1000-5000 = 90 points (frequent reboots)
  5000-10000 = 80 points (heavy use)
  10000-20000 = 70 points
  20000-50000 = 50 points (very heavy cycling)
  >50000 = 30 points (extreme usage)

Temperature (HDD):
  <35°C = 100 points
  35-39°C = 90 points
  40-44°C = 70 points
  45-49°C = 40 points
  ≥50°C = 10 points

Uncorrectable Errors:
  0 = 100 points
  1 = 60 points (warning)
  2-5 = 20 points (serious)
  6-10 = -30 points (critical)
  11-20 = -70 points (terminal)
  >20 = -100 points (zombie - permanent data loss)

Command Timeout:
  0 = 100 points
  1-5 = 70 points
  6-50 = 40 points
  51-200 = 20 points
  >200 = 0 points

Age (power-on hours):
  <17,520 hours (2 years) = 100 points
  17,520-26,280 hours (3 years) = 90 points
  26,280-43,800 hours (5 years) = 70 points
  43,800-61,320 hours (7 years) = 50 points
  61,320-87,600 hours (10 years) = 30 points
  >87,600 hours = 10 points
```

**Example:** An HDD with 0 reallocated sectors (100p), 0 pending (100p), 1540 power cycles (90p), 25°C (100p), no errors (100p), no timeouts (100p), and 2.8 years old (90p):
```
Score = (100×0.35) + (100×0.25) + (90×0.10) + (100×0.10) + (100×0.10) + (90×0.05) + (100×0.05)
      = 35 + 25 + 9 + 10 + 10 + 4.5 + 5 = 98.5 points
```

### For SSD (Solid State Drives)

**Weighting without wear data:**
- **Reallocated Sectors (40%):** Defective blocks
- **Pending Sectors (25%):** Pending blocks (active danger)
- **Temperature (10%):** SSD temperature
- **Uncorrectable Errors (10%):** Errors
- **Command Timeout (10%):** Timeouts
- **Age (5%):** Age

**Weighting with wear data (when bytes written is available):**
- **Reallocated Sectors (35%):** Reduced weight
- **Pending Sectors (25%):** Critical weight (active danger)
- **Wear Level (15%):** New component based on written data
- **Temperature (10%):** Adjusted weight
- **Uncorrectable Errors (8%):** Adjusted weight
- **Command Timeout (5%):** Adjusted weight
- **Age (2%):** Adjusted weight

**Wear Level Calculation:**
```
Bytes Written (LBAs × 512 or Pages × 4096)
Rated Endurance (depends on model and size)

Example: CT480BX500SSD1 (480GB SSD)
  Rated: ~96 TB (based on typical TBW for budget SSD)
  Written: 7 TB
  Wear: 7/96 = 7.3%
  Score: 100 - (7.3 × 1.5) = ~89 points

Over 100% wear = 0 points
```

**Temperature for SSD:**
- Optimal: <50°C
- High: 50-70°C (linear decrease)
- Critical: >70°C

### Lifetime Remaining (SMART ID 202)

Modern SSDs report remaining lifetime via SMART ID 202 (Percent_Lifetime_Remaining):

**Display:**
- **>10%:** Shown inline with other data
- **≤10%:** Shown as separate warning (yellow or red)
- **≤5%:** Critical warning with replacement recommendation

**Penalty Scoring:**
```
Lifetime Remaining → Health Score Penalty
  ≤5%:  -35 points (CRITICAL)
  6%:   -20 points
  7%:   -17 points
  8%:   -14 points
  9%:   -11 points
  10%:  -10 points
  11-20%: Linear decrease (-0.5 per %)
  ≥21%: 0 penalty (no concern)
```

**Tooltips:**
- **≤10%:** "Remaining lifetime is critically low – replace soon"
- **≤20%:** "Remaining lifetime is low – plan replacement soon"
- **>20%:** "SMART ID 202 shows remaining lifetime in percent"

---

## Technical Improvements

### Thread-safe Scanning (2026)

MoSMART uses thread-safe locking for all scanning operations:

**Features:**
- **Atomic updates:** Placeholder data never overwritten by stale data
- **Race condition protection:** Threading.Lock() on all scan_results accesses
- **Watchdog monitoring:** Automatic detection of stuck devices (30-second timeout)
- **Lifecycle logging:** Logs stuck devices to `~/.mosmart/device_events/lifecycle.jsonl`

**Implementation:**
```python
# Thread-safe placeholder initialization
set_scan_result_placeholder(device_name)

# Thread-safe atomic update with collision protection
update_scan_result(device_name, device_data)

# Thread-safe bulk read for API
devices = get_all_scan_results()
```

**Watchdog:**
- Runs every 60 seconds in background_scanner
- Logs devices stuck in "⏳ Scanning..." >30 seconds
- Prevents permanent UI hang on problematic USB drives

### Windows Support via WSL2

MoSMART works fully on Windows 10/11 via WSL2 (Windows Subsystem for Linux):

**Benefits:**
- Full Linux functionality inside Windows
- Dashboard available at `http://localhost:5000` in Windows browser
- Access to WSL files via `\\wsl$\Ubuntu\home\username\mosmart` in File Explorer
- Auto-start possible via Windows Task Scheduler

**Limitations:**
- Only Linux disks within WSL visible (not native Windows disks)
- Requires WSL2 (not WSL1)
- See [Installation: Windows (WSL2)](#installation-windows-wsl2) for setup guide

---

## Ghost Drive Condition (GDC)

GDC is a condition where a disk "freezes" or becomes unstable, often due to hardware problems.

### Detection

The system monitors several indicators:

1. **Timeouts:** Disk doesn't respond within timeout period
2. **Invalid JSON:** pySMART returns corrupt data
3. **Disappeared:** Disk disappears from system
4. **Corrupt data:** S.M.A.R.T. data is inconsistent

### GDC States

Disks progress through different states:

```
OK → SUSPECT → PROBABLE → CONFIRMED → TERMINAL
```

**OK:** Disk functioning normally
- All requests go through
- No abnormal timeouts

**SUSPECT:** First signs of problems
- 3-5 consecutive timeouts
- Resets to OK after one successful read

**PROBABLE:** Likely GDC
- 6-9 consecutive timeouts
- Requires 2 successful reads to return to OK

**CONFIRMED:** Confirmed GDC
- 10+ consecutive timeouts
- Disk is **not** scanned automatically (saves resources)
- Requires 3 successful reads to recover

**TERMINAL:** Permanently dead disk
- 50+ consecutive timeouts without any successful reads
- Disk is ignored completely

### GDC Freeze Mode

When you click **Force Scan**, all GDC disks are set to "freeze mode" for 5 minutes:
- State temporarily set to OK
- Disk is scanned again
- Gives you a chance to see if disk has recovered

### History

The system logs all GDC events:
- When disk entered which state
- Total number of timeouts/errors
- Pattern of failures (last 10 events)

You can see this in **View Log** for the disk.

---

## Alert System

### Alert Types

#### 1. Health Score Alerts
- **Score Drop:** Sent when health score drops by X points since last scan
- **Critical Score:** Sent when health score goes below critical threshold

#### 2. Temperature Alerts
- **Warning:** Disk reaches warning temperature
- **Critical:** Disk reaches critical temperature
- **Normalized:** Disk returns to normal temperature

**Consecutive Readings:** Requires temperature to be above threshold for X consecutive scans before alert is sent (avoids false alarms).

#### 3. Milestone Alerts
- **Reallocated Sectors:** Sent when count crosses a threshold value (e.g. 1, 10, 50)
- **Pending Sectors:** Sent when count crosses a threshold value

#### 4. GDC Alerts
- **State Change:** Sent when disk changes GDC state
- **Confirmed GDC:** Critical alert when disk is confirmed as GDC

### Email Alerts

**Setup:**
1. Go to Settings → Alert Channels
2. Fill in SMTP details
3. **Important:** Use app password, not regular password!

**Gmail Example:**
- SMTP Server: `smtp.gmail.com`
- Port: `587`
- Use TLS: `✓`
- Username: `your@gmail.com`
- Password: [App password from Google](https://myaccount.google.com/apppasswords)

**Email Format:**
```
Subject: [MoSMART] Critical Alert: sda Health Score

Device: CT480BX500SSD1 (sda)
Alert Type: CRITICAL_SCORE
Severity: HIGH

Health score critically low: 35 (threshold: 40)

Timestamp: 2025-12-02 10:30:15
```

### Alert History

All sent alerts are logged and can be seen in **View Log** for each disk.

---

## Frequently Asked Questions

### Why does the program need sudo/root?
S.M.A.R.T. data requires direct access to disk hardware, which is only allowed for root users.

### Can I run this on a headless server?
Yes! The web interface can be accessed from any computer on the network. Just make sure port 5000 is open.

### How often should I scan the disks?
Default is 60 seconds. This is a good balance between updated data and disk wear.

### What do the different S.M.A.R.T. attributes mean?
- **005 Reallocated Sectors:** Defective sectors that have been replaced
- **196 Reallocation Events:** Number of times reallocation has occurred
- **197 Current Pending Sector:** Sectors waiting to be tested/reallocated
- **198 Uncorrectable Sector:** Sectors that cannot be read/written
- **199 UltraDMA CRC Errors:** Data errors during transfer
- **194 Temperature:** Disk temperature in Celsius

### How do I interpret the health score?
- **90-100:** Excellent - disk is in top condition
- **70-89:** Good - disk functioning normally
- **50-69:** Acceptable - keep an eye on disk
- **30-49:** Poor - backup data soon!
- **0-29:** Critical - replace disk immediately

### What is "Bytes Written" on SSD?
This shows total data written to the SSD over its lifetime. Together with rated endurance (TBW) this gives a measure of "wear".

Example: 7 TB written out of 96 TB rated = 7.3% wear = excellent!

### Can I monitor disks in a RAID?
Yes, but you see individual disks, not the RAID array as a whole. Each disk is monitored separately.

### How do I stop alerts from a disk?
Click **"Toggle Monitoring"** (⏸️/▶️) on the disk card. The disk will still be scanned, but won't send alerts.

### What happens if a disk gets GDC?
1. Disk is marked as CONFIRMED
2. Disk is no longer automatically scanned (saves resources)
3. You can force scan with "Force Scan"
4. If disk recovers, it gradually returns to OK status

### Where is data stored?
- **Configuration:** `~/.mosmart/settings.json`
- **Logs:** `~/.mosmart/logs/<model>_<serial>/YYYY-MM-DD.jsonl`
- **GDC events:** `~/.mosmart/gdc_events/<device>.json`

### Can I run this on multiple computers?
Yes! Just install on each machine. Each installation monitors its own disks.

### Does the system support NVMe drives?
Yes, if smartmontools and pySMART support them on your system. Most modern NVMe drives are supported.

### What does "Force Scan" do?
- Forces full scan of all disks (including GDC)
- Sets GDC disks to "freeze mode" for 5 minutes
- Triggers alert system immediately
- Updates all data

---

## Support and Troubleshooting

### Server won't start
```bash
# Check if port 5000 is occupied
sudo lsof -i :5000

# Check logs
tail -f /tmp/mosmart.log

# Check that all dependencies are installed
./venv/bin/pip list
```

### No data is shown
- Check that you're running with sudo
- Check that smartmontools is installed: `smartctl --version`
- Check that disks are visible: `sudo smartctl --scan`

### Email doesn't work
- Test SMTP settings with "Test Email" button
- Check that you're using app password, not regular password
- Check that port 587/465 isn't blocked by firewall

### GDC false positive
If a disk is incorrectly marked as GDC:
1. Click "Force Scan"
2. If disk responds, GDC status will gradually normalize
3. Check cables and power supply

---

**Version:** 0.9 beta  
**Last Updated:** February 2, 2026  
**Created by:** Magnus S. Modig with help from GitHub Copilot
