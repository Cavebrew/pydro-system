#!/bin/bash
#
# Setup systemd services for Hydroponic AI System
# Run with: sudo bash utils/setup_systemd.sh
#

set -e

echo "=================================================="
echo "  Hydroponic AI System - Systemd Service Setup"
echo "=================================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (use sudo)"
  exit 1
fi

# Get the actual user who ran sudo
ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo ~$ACTUAL_USER)
SCRIPT_DIR="$USER_HOME/Python project"

echo "User: $ACTUAL_USER"
echo "Home: $USER_HOME"
echo "Project Directory: $SCRIPT_DIR"
echo

# Verify project directory exists
if [ ! -d "$SCRIPT_DIR" ]; then
  echo "Error: Project directory not found: $SCRIPT_DIR"
  exit 1
fi

# Create systemd service for main AI system
echo "Creating systemd service: hydro-ai-main.service"

cat > /etc/systemd/system/hydro-ai-main.service << EOF
[Unit]
Description=Hydroponic AI Main System (RPi5)
After=network-online.target mosquitto.service
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$USER_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 $SCRIPT_DIR/rpi5/hydro_ai_main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Created hydro-ai-main.service"

# Create systemd service template for Pi Zero cameras
echo
echo "Creating systemd service template for cameras..."
echo "Note: This needs to be deployed on each Pi Zero 2W"
echo

mkdir -p "$SCRIPT_DIR/systemd_templates"

cat > "$SCRIPT_DIR/systemd_templates/hydro-camera.service" << 'EOF'
[Unit]
Description=Hydroponic Camera Capture (Pi Zero 2W)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
Environment="PATH=/home/pi/.local/bin:/usr/local/bin:/usr/bin:/bin"
# Replace CAMERA_SCRIPT with visible_camera.py or noir_camera.py
ExecStart=/usr/bin/python3 /home/pi/CAMERA_SCRIPT
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Created camera service template at $SCRIPT_DIR/systemd_templates/hydro-camera.service"

# Reload systemd daemon
echo
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "Enabling hydro-ai-main service..."
systemctl enable hydro-ai-main.service

echo
echo "=================================================="
echo "  Setup Complete!"
echo "=================================================="
echo
echo "Service commands:"
echo "  Start:   sudo systemctl start hydro-ai-main"
echo "  Stop:    sudo systemctl stop hydro-ai-main"
echo "  Status:  sudo systemctl status hydro-ai-main"
echo "  Logs:    sudo journalctl -u hydro-ai-main -f"
echo
echo "To start the service now:"
echo "  sudo systemctl start hydro-ai-main"
echo
echo "For Pi Zero cameras:"
echo "  1. Copy pi_zero/visible_camera.py to each Pi Zero"
echo "  2. Copy systemd_templates/hydro-camera.service to /etc/systemd/system/"
echo "  3. Edit service file to set correct camera script"
echo "  4. Run: sudo systemctl enable hydro-camera && sudo systemctl start hydro-camera"
echo
