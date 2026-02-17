#!/usr/bin/env bash
set -e

APP_NAME="mosmart"
INSTALL_DIR="/opt/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"
DATA_DIR="/var/lib/$APP_NAME"
LOG_DIR="/var/log/$APP_NAME"
BIN_LINK="/usr/local/bin/mosmart-web"

echo "=========================================="
echo "  Uninstalling MoSMART Monitor"
echo "=========================================="
echo ""

# Krev root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: This script must be run as root"
  echo "   Run with: sudo ./uninstall.sh"
  exit 1
fi

# Bekreftelse
read -p "⚠️  This will remove MoSMART completely. Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "🛑 Stopping service..."
systemctl stop mosmart.service 2>/dev/null || true
systemctl disable mosmart.service 2>/dev/null || true

echo "🗑️  Removing systemd service..."
rm -f /etc/systemd/system/mosmart.service
systemctl daemon-reload

echo "🗑️  Removing application files..."
rm -rf "$INSTALL_DIR"

echo "🗑️  Removing symlink..."
rm -f "$BIN_LINK"
rm -f "$BIN_LINK-python"

# Spør om config og data skal slettes
read -p "🗑️  Remove configuration and data? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  rm -rf "$CONFIG_DIR"
  rm -rf "$DATA_DIR"
  rm -rf "$LOG_DIR"
  echo "   ✓ Configuration and data removed"
else
  echo "   ✓ Configuration and data preserved at:"
  echo "      $CONFIG_DIR"
  echo "      $DATA_DIR"
  echo "      $LOG_DIR"
fi

echo ""
echo "=========================================="
echo "  ✅ MoSMART Uninstalled"
echo "=========================================="
echo ""
