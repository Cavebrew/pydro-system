#!/bin/bash
# NFS Setup Script for Pydro System
# Sets up NFS shares between RPi5 and Pi Zero 2W cameras

set -e

echo "========================================"
echo "Pydro NFS Setup Script"
echo "========================================"
echo ""

# Configuration
RPI5_IP="10.0.0.62"
COOL_VISIBLE_IP="10.0.0.65"
COOL_NOIR_IP="10.0.0.66"
WARM_VISIBLE_IP="10.0.0.67"
WARM_NOIR_IP="10.0.0.68"

IMAGE_STORAGE="/home/pi/hydro_images"
NFS_MOUNT="/mnt/hydro_images"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo ./nfs_setup.sh)"
    exit 1
fi

# Detect if this is RPi5 or Pi Zero
echo "Detecting device..."
HOSTNAME=$(hostname)

if [[ "$HOSTNAME" == *"rpi5"* ]] || [[ "$(hostname -I | tr ' ' '\n' | grep -c "$RPI5_IP")" -gt 0 ]]; then
    echo "Detected: Raspberry Pi 5 (NFS Server)"
    MODE="server"
elif [[ "$(hostname -I | tr ' ' '\n' | grep -E "$(echo $COOL_VISIBLE_IP\|$COOL_NOIR_IP\|$WARM_VISIBLE_IP\|$WARM_NOIR_IP)")" ]]; then
    echo "Detected: Pi Zero 2W Camera (NFS Client)"
    MODE="client"
else
    echo "Could not detect device type. Please specify:"
    echo "  1) RPi5 (NFS Server)"
    echo "  2) Pi Zero 2W (NFS Client)"
    read -p "Enter choice (1 or 2): " choice
    case $choice in
        1) MODE="server" ;;
        2) MODE="client" ;;
        *) echo "Invalid choice"; exit 1 ;;
    esac
fi

echo ""
echo "Mode: $MODE"
echo ""

if [ "$MODE" == "server" ]; then
    echo "===== Setting up NFS Server (RPi5) ====="
    
    # Install NFS server
    echo "Installing NFS server packages..."
    apt update
    apt install -y nfs-kernel-server
    
    # Create image storage directory
    echo "Creating image storage directory..."
    mkdir -p "$IMAGE_STORAGE"
    mkdir -p "$IMAGE_STORAGE/cool/visible"
    mkdir -p "$IMAGE_STORAGE/cool/noir"
    mkdir -p "$IMAGE_STORAGE/warm/visible"
    mkdir -p "$IMAGE_STORAGE/warm/noir"
    mkdir -p "$IMAGE_STORAGE/archive"
    mkdir -p "$IMAGE_STORAGE/perfect"
    mkdir -p "$IMAGE_STORAGE/harvests"
    
    # Set permissions
    chown -R pi:pi "$IMAGE_STORAGE"
    chmod -R 755 "$IMAGE_STORAGE"
    
    # Configure NFS exports
    echo "Configuring NFS exports..."
    EXPORTS_LINE="$IMAGE_STORAGE 10.0.0.0/24(rw,sync,no_subtree_check,no_root_squash)"
    
    if ! grep -q "$IMAGE_STORAGE" /etc/exports; then
        echo "$EXPORTS_LINE" >> /etc/exports
        echo "Added NFS export to /etc/exports"
    else
        echo "NFS export already exists in /etc/exports"
    fi
    
    # Export file systems
    echo "Exporting file systems..."
    exportfs -ra
    
    # Enable and start NFS server
    echo "Enabling NFS server..."
    systemctl enable nfs-kernel-server
    systemctl restart nfs-kernel-server
    
    # Show exports
    echo ""
    echo "Current NFS exports:"
    exportfs -v
    
    echo ""
    echo "===== NFS Server Setup Complete! ====="
    echo "Pi Zero cameras can now mount: $IMAGE_STORAGE"
    echo ""

elif [ "$MODE" == "client" ]; then
    echo "===== Setting up NFS Client (Pi Zero 2W) ====="
    
    # Install NFS client
    echo "Installing NFS client packages..."
    apt update
    apt install -y nfs-common
    
    # Create mount point
    echo "Creating mount point..."
    mkdir -p "$NFS_MOUNT"
    
    # Add to /etc/fstab for auto-mount
    echo "Configuring auto-mount..."
    FSTAB_LINE="$RPI5_IP:$IMAGE_STORAGE $NFS_MOUNT nfs defaults,_netdev,nofail 0 0"
    
    if ! grep -q "$NFS_MOUNT" /etc/fstab; then
        echo "$FSTAB_LINE" >> /etc/fstab
        echo "Added NFS mount to /etc/fstab"
    else
        echo "NFS mount already exists in /etc/fstab"
    fi
    
    # Test mount
    echo "Testing NFS mount..."
    mount -a
    
    if mountpoint -q "$NFS_MOUNT"; then
        echo "NFS mount successful!"
        echo ""
        echo "Testing write access..."
        TEST_FILE="$NFS_MOUNT/test_$(hostname).txt"
        echo "Test from $(hostname) at $(date)" > "$TEST_FILE"
        
        if [ -f "$TEST_FILE" ]; then
            echo "Write test successful!"
            rm "$TEST_FILE"
        else
            echo "WARNING: Write test failed!"
        fi
    else
        echo "ERROR: NFS mount failed!"
        echo "Please check:"
        echo "  1. RPi5 NFS server is running"
        echo "  2. Network connectivity to $RPI5_IP"
        echo "  3. Firewall settings"
        exit 1
    fi
    
    echo ""
    echo "===== NFS Client Setup Complete! ====="
    echo "Images will be saved to: $NFS_MOUNT"
    echo ""
fi

echo "Setup complete! Please verify:"
if [ "$MODE" == "server" ]; then
    echo "  - Run 'showmount -e' to see exports"
    echo "  - Check firewall allows NFS (port 2049)"
elif [ "$MODE" == "client" ]; then
    echo "  - Run 'df -h | grep nfs' to verify mount"
    echo "  - Reboot to test auto-mount on startup"
fi
echo ""
