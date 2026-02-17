#!/usr/bin/env bash
set -e

APP_NAME="mosmart"
INSTALL_DIR="/opt/$APP_NAME"

echo "=========================================="
echo "  Updating MoSMART Monitor"
echo "=========================================="
echo ""

# Krev root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: This script must be run as root"
  echo "   Run with: sudo ./update.sh"
  exit 1
fi

# Sjekk at vi er i riktig mappe
if [ ! -f "web_monitor.py" ] || [ ! -f "smart_monitor.py" ]; then
  echo "❌ Error: Must be run from MoSMART source directory"
  echo "   Expected files: web_monitor.py, smart_monitor.py"
  exit 1
fi

# Sjekk at MoSMART er installert
if [ ! -d "$INSTALL_DIR" ]; then
  echo "❌ Error: MoSMART is not installed"
  echo "   Run ./install.sh first"
  exit 1
fi

echo "🛑 Stopping service..."
systemctl stop mosmart.service

echo "📋 Updating application files..."
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

echo "📦 Updating Python dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --upgrade -r "$INSTALL_DIR/requirements.txt"

echo "🚀 Starting service..."
systemctl start mosmart.service

echo ""
echo "=========================================="
echo "  ✅ Update Complete!"
echo "=========================================="
echo ""
echo "📊 Check status:"
echo "   systemctl status mosmart"
echo ""
echo "📜 View logs:"
echo "   journalctl -u mosmart -f"
echo ""
