#!/usr/bin/env bash
set -e

APP_NAME="mosmart"
INSTALL_DIR="/opt/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"
DATA_DIR="/var/lib/$APP_NAME"
LOG_DIR="/var/log/$APP_NAME"
BIN_LINK="/usr/local/bin/mosmart-web"

echo "=========================================="
echo "  Installing MoSMART Monitor"
echo "=========================================="
echo ""

# Krev root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: This script must be run as root"
  echo "   Run with: sudo ./install.sh"
  exit 1
fi

# Sjekk at vi er i riktig mappe
if [ ! -f "web_monitor.py" ] || [ ! -f "smart_monitor.py" ]; then
  echo "❌ Error: Must be run from MoSMART source directory"
  echo "   Expected files: web_monitor.py, smart_monitor.py"
  exit 1
fi

echo "📦 Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"

echo "📋 Copying application files..."
# Core Python modules
cp *.py "$INSTALL_DIR/" 2>/dev/null || true

# Web interface files
if [ -d "templates" ]; then
  cp -r templates "$INSTALL_DIR/"
fi
if [ -d "static" ]; then
  cp -r static "$INSTALL_DIR/"
fi

# Language files
if [ -d "languages" ]; then
  cp -r languages "$INSTALL_DIR/"
fi
if [ -f "translations.json" ]; then
  cp translations.json "$INSTALL_DIR/"
fi

# Configuration and requirements
if [ -f "requirements.txt" ]; then
  cp requirements.txt "$INSTALL_DIR/"
fi

# License and documentation
cp LICENSE "$INSTALL_DIR/" 2>/dev/null || true
cp COPYRIGHT "$INSTALL_DIR/" 2>/dev/null || true
cp README.md "$INSTALL_DIR/" 2>/dev/null || true

echo "🐍 Creating virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"

echo "📦 Installing Python dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "⚙️  Creating default configuration..."
# Standard config hvis ikke finnes
if [ ! -f "$CONFIG_DIR/settings.json" ]; then
  cat > "$CONFIG_DIR/settings.json" <<EOF
{
  "general": {
    "language": "en",
    "temperature_unit": "C",
    "polling_interval": 60
  },
  "disk_selection": {
    "monitored_devices": {}
  },
  "emergency_unmount": {
    "mode": "PASSIVE",
    "require_confirmation": true
  }
}
EOF
  echo "   ✓ Created default settings.json"
fi

echo "🔗 Creating symlink..."
ln -sf "$INSTALL_DIR/venv/bin/python3" "$BIN_LINK-python"
cat > "$BIN_LINK" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/web_monitor.py" "\$@"
EOF
chmod +x "$BIN_LINK"

echo "🔧 Creating systemd service..."
# Use the mosmart.service file if it exists, otherwise create one
if [ -f "mosmart.service" ]; then
  # Copy the service file and update paths
  sed "s|/opt/mosmart|$INSTALL_DIR|g; s|/opt/mosmart-venv|$INSTALL_DIR/venv|g" mosmart.service > /etc/systemd/system/mosmart.service
  echo "   ✓ Installed mosmart.service"
else
  # Fallback: create service file
  cat > /etc/systemd/system/mosmart.service <<EOF
[Unit]
Description=MoSMART Disk Monitor - Backend Service
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$INSTALL_DIR

ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/web_monitor.py

StandardOutput=append:$LOG_DIR/backend.log
StandardError=append:$LOG_DIR/backend.log

Restart=always
RestartSec=10

PrivateDevices=no
ProtectSystem=no
ProtectHome=no

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable mosmart.service

echo ""
echo "=========================================="
echo "  ✅ Installation Complete!"
echo "=========================================="
echo ""
echo "📂 Installation locations:"
echo "   Application:   $INSTALL_DIR"
echo "   Configuration: $CONFIG_DIR"
echo "   Data:          $DATA_DIR"
echo "   Logs:          $LOG_DIR"
echo ""
echo "🚀 Start MoSMART:"
echo "   systemctl start mosmart"
echo ""
echo "📊 Check status:"
echo "   systemctl status mosmart"
echo ""
echo "🌐 Access web dashboard:"
echo "   http://localhost:5000"
echo ""
echo "💡 Run manually (testing):"
echo "   sudo mosmart-web"
echo "   sudo mosmart-web --check-health"
echo ""
