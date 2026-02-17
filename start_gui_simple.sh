#!/bin/bash

# MoSMART Desktop GUI Launcher (Simple Version)
# Bruker virtual environment for å unngå system-wide pip-problemer

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-gui"

echo "🚀 MoSMART Desktop GUI Starter"
echo "=============================="
echo ""

# Step 1: Create or activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Oppretter virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✅ Virtual environment opprettet"
else
    echo "✅ Virtual environment finnes allerede"
fi

echo ""
echo "📥 Installerer PyQt5 (dette kan ta 1-2 minutter første gang)..."

# Upgrade pip first
"$VENV_DIR/bin/python3" -m pip install --upgrade pip --quiet

# Install PyQt5 with progress
"$VENV_DIR/bin/python3" -m pip install PyQt5 PyQtChart requests

echo ""
echo "✅ Alle pakker installert!"

# Step 2: Check if backend is running
echo ""
echo "🔍 Sjekker om backend kjører..."
if curl -s http://localhost:5000/api/devices > /dev/null 2>&1; then
    echo "✅ Backend kjører på port 5000"
else
    echo "⚠️  ADVARSEL: Backend ser ikke ut til å kjøre"
    echo "   Start backend først: sudo python3 web_monitor.py"
    echo ""
    read -p "Fortsett likevel? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Avbrutt."
        exit 1
    fi
fi

# Step 3: Launch GUI
echo ""
echo "🖥️  Starter Desktop GUI..."
cd "$SCRIPT_DIR"
"$VENV_DIR/bin/python3" gui_monitor.py

echo ""
echo "GUI lukket."
