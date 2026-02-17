# Desktop GUI Installation Guide

## Problem: externally-managed-environment

On modern Debian/Ubuntu systems (Python 3.11+), you cannot install packages system-wide with pip.

## Solution 1: Use Startup Script (Recommended)

The `start_gui.sh` script automatically creates and manages a virtual environment:

```bash
./start_gui.sh
```

This will:
1. Create a virtual environment in `.venv-gui/`
2. Install PyQt5 and dependencies
3. Start the GUI

## Solution 2: Manual Virtual Environment

### Create Virtual Environment

```bash
cd ~/mosmart
python3 -m venv .venv-gui
source .venv-gui/bin/activate
```

### Install Dependencies

```bash
pip install PyQt5 PyQtChart requests
```

### Run GUI

```bash
python3 gui_monitor.py
```

### Deactivate When Done

```bash
deactivate
```

## Solution 3: System Packages (Ubuntu/Debian)

Install PyQt5 from system repositories:

```bash
sudo apt update
sudo apt install python3-pyqt5 python3-pyqt5.qtchart python3-requests
```

Then run directly:

```bash
python3 gui_monitor.py
```

## Solution 4: Override (Not Recommended)

**WARNING:** This can break your system Python!

```bash
pip install --break-system-packages PyQt5 PyQtChart requests
```

Only use this if you understand the risks.

## Quick Start

### First Time

```bash
# Make script executable
chmod +x start_gui.sh

# Run (creates venv automatically)
./start_gui.sh
```

### Subsequent Runs

```bash
./start_gui.sh
```

## Troubleshooting

### "Permission denied"

```bash
chmod +x start_gui.sh
```

### "Module not found" even with venv

Check that venv is activated:

```bash
which python3
# Should show: /home/magnus/mosmart/.venv-gui/bin/python3
```

### PyQt5 installation fails

Try using system packages instead:

```bash
sudo apt install python3-pyqt5 python3-pyqt5.qtchart
```

### Backend not running

```bash
# Terminal 1 - Start backend
python3 web_monitor.py --port 5000

# Terminal 2 - Start GUI
./start_gui.sh
```

## File Structure

After installation:

```
mosmart/
├── .venv-gui/              # Virtual environment (auto-created)
│   ├── bin/
│   │   ├── python3
│   │   └── pip
│   └── lib/
├── gui_monitor.py          # Main GUI
├── gui_advanced.py         # Advanced features
├── start_gui.sh            # Startup script
└── web_monitor.py          # Backend server
```

## Virtual Environment Benefits

✅ **Isolated** - Won't affect system Python  
✅ **Safe** - No system breakage risk  
✅ **Portable** - Easy to delete/recreate  
✅ **Automatic** - Startup script handles everything  

## Cleaning Up

To remove the virtual environment:

```bash
rm -rf ~/mosmart/.venv-gui
```

Next run of `start_gui.sh` will recreate it.

## Integration with WebUI

The GUI and WebUI can run simultaneously:

```bash
# Terminal 1 - WebUI
python3 web_monitor.py --port 5000

# Terminal 2 - Desktop GUI
./start_gui.sh
```

Both connect to the same backend and share data.
