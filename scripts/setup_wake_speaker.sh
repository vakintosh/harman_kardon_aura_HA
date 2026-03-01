#!/bin/bash
# =============================================================================
# HK Aura Plus — Interactive Setup Wizard for Bluetooth Wake on Linux
# =============================================================================
# This script guides you through the full setup process:
#   1. Installs required packages (bluez, pipewire, mpv, etc.)
#   2. Fixes WirePlumber for headless/SSH operation
#   3. Scans for your HK Aura Plus speaker via Bluetooth
#   4. Discovers speaker WiFi IP via mDNS
#   5. Pairs and tests the connection
#   6. Generates a config file and deploys the wake script
#
# Usage: bash setup_wake_speaker.sh
# =============================================================================

set -euo pipefail

# --- Colors & formatting ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/wake_speaker.conf"
WAKE_SCRIPT="$SCRIPT_DIR/wake_speaker_linux.sh"

# --- Helper functions ---
log()     { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
err()     { echo -e "${RED}[✗]${NC} $1"; }
info()    { echo -e "${BLUE}[i]${NC} $1"; }
step()    { echo -e "\n${BOLD}${CYAN}=== Step $1: $2 ===${NC}\n"; }
ask()     { echo -en "${BOLD}$1${NC} "; }

confirm() {
    local prompt="${1:-Continue?}"
    ask "$prompt [Y/n]: "
    read -r answer
    [[ -z "$answer" || "$answer" =~ ^[Yy] ]]
}

wait_for_enter() {
    ask "${1:-Press Enter to continue...}"
    read -r
}

# --- Banner ---
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        HK Aura Plus — Bluetooth Wake Setup Wizard          ║"
echo "║                                                            ║"
echo "║  This wizard will set up your Linux machine to wake your   ║"
echo "║  Harman Kardon Aura Plus speaker from standby using        ║"
echo "║  Bluetooth audio streaming.                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# --- Check we're on Linux ---
if [[ "$(uname)" != "Linux" ]]; then
    err "This setup script is for Linux only."
    info "For macOS, use wake_speaker.sh instead (uses blueutil + SwitchAudioSource)."
    exit 1
fi

# --- Check not running as root ---
if [[ "$EUID" -eq 0 ]]; then
    warn "Please run this script as a normal user (not root)."
    warn "The script will use 'sudo' when needed."
    exit 1
fi

# =============================================================================
# Step 1: Install required packages
# =============================================================================
step "1/7" "Installing required packages"

PACKAGES=(
    bluez              # Bluetooth stack + bluetoothctl
    pipewire           # Audio server
    pipewire-pulse     # PulseAudio compatibility layer
    libspa-0.2-bluetooth  # PipeWire Bluetooth plugin (A2DP)
    wireplumber        # PipeWire session manager
    pulseaudio-utils   # pactl command (sink detection)
    mpv                # Media player for audio streaming
    avahi-utils        # mDNS discovery (avahi-browse)
)

info "The following packages are needed:"
for pkg in "${PACKAGES[@]}"; do
    echo "    - $pkg"
done
echo ""

# Detect package manager
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    PKG_INSTALL="sudo apt-get install -y"
    PKG_UPDATE="sudo apt-get update"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_INSTALL="sudo dnf install -y"
    PKG_UPDATE=""
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    PKG_INSTALL="sudo pacman -S --noconfirm"
    PKG_UPDATE="sudo pacman -Sy"
    # Arch uses different package names
    PACKAGES=(bluez pipewire pipewire-pulse libspa-0.2-bluetooth wireplumber pulseaudio-utils mpv avahi nss-mdns)
else
    err "Could not detect package manager (apt/dnf/pacman). Please install these packages manually:"
    for pkg in "${PACKAGES[@]}"; do
        echo "    $pkg"
    done
    if ! confirm "Have you installed the packages above manually?"; then
        exit 1
    fi
    PKG_MANAGER="manual"
fi

if [[ "$PKG_MANAGER" != "manual" ]]; then
    # Check which packages are already installed
    MISSING=()
    for pkg in "${PACKAGES[@]}"; do
        if ! dpkg -l "$pkg" &>/dev/null 2>&1 && \
           ! rpm -q "$pkg" &>/dev/null 2>&1 && \
           ! pacman -Q "$pkg" &>/dev/null 2>&1; then
            MISSING+=("$pkg")
        fi
    done

    if [[ ${#MISSING[@]} -eq 0 ]]; then
        log "All required packages are already installed!"
    else
        info "Missing packages: ${MISSING[*]}"
        if confirm "Install missing packages now?"; then
            [[ -n "${PKG_UPDATE:-}" ]] && $PKG_UPDATE
            $PKG_INSTALL "${MISSING[@]}"
            log "Packages installed successfully."
        else
            warn "Skipping package installation. Some features may not work."
        fi
    fi
fi

# =============================================================================
# Step 2: Fix WirePlumber for headless/SSH operation
# =============================================================================
step "2/7" "Configuring WirePlumber for headless operation"

info "On headless systems (no monitor/SSH only), WirePlumber's seat"
info "monitoring blocks Bluetooth. We need to disable it."
echo ""

WP_CONF_DIR="$HOME/.config/wireplumber/wireplumber.conf.d"
WP_CONF_FILE="$WP_CONF_DIR/50-bluetooth-no-seat.conf"

if [[ -f "$WP_CONF_FILE" ]]; then
    log "WirePlumber headless fix already in place."
else
    if confirm "Is this machine headless (no monitor) or accessed mainly via SSH?"; then
        mkdir -p "$WP_CONF_DIR"
        cat > "$WP_CONF_FILE" << 'WPEOF'
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
WPEOF
        log "WirePlumber headless fix applied."
        info "Restarting WirePlumber..."
        systemctl --user restart wireplumber 2>/dev/null || warn "Could not restart WirePlumber (will apply on next boot)."
    else
        info "Skipping headless fix (not needed for desktop machines with a monitor)."
    fi
fi

# =============================================================================
# Step 3: Ensure Bluetooth is powered on
# =============================================================================
step "3/7" "Setting up Bluetooth adapter"

# Unblock Bluetooth
if command -v rfkill &>/dev/null; then
    if rfkill list bluetooth 2>/dev/null | grep -q "Soft blocked: yes"; then
        info "Bluetooth is soft-blocked. Unblocking..."
        sudo rfkill unblock bluetooth
        log "Bluetooth unblocked."
    fi
fi

# Power on
info "Powering on Bluetooth adapter..."
bluetoothctl power on 2>/dev/null || true
sleep 1

# Verify
BT_STATUS=$(bluetoothctl show 2>/dev/null | grep "Powered:" | awk '{print $2}')
if [[ "$BT_STATUS" == "yes" ]]; then
    log "Bluetooth adapter is powered on."
else
    err "Could not power on Bluetooth adapter."
    warn "Please check your Bluetooth hardware and try again."
    exit 1
fi

# Check for A2DP UUIDs
if bluetoothctl show 2>/dev/null | grep -q "Audio Sink"; then
    log "A2DP Audio Sink UUID registered (PipeWire Bluetooth working)."
else
    warn "A2DP Audio Sink UUID not found. This may cause issues."
    info "Try: systemctl --user restart wireplumber && systemctl --user restart pipewire"
fi

# Enable auto-power-on across reboots
MAIN_CONF="/etc/bluetooth/main.conf"
if [[ -f "$MAIN_CONF" ]]; then
    if ! grep -q "AutoEnable=true" "$MAIN_CONF" 2>/dev/null; then
        if confirm "Enable Bluetooth auto-power-on at boot?"; then
            sudo sed -i '/^\[Policy\]/a AutoEnable=true' "$MAIN_CONF" 2>/dev/null || \
            echo -e "\n[Policy]\nAutoEnable=true" | sudo tee -a "$MAIN_CONF" >/dev/null
            log "Auto-power-on enabled."
        fi
    fi
fi

# =============================================================================
# Step 4: Scan for HK Aura Plus speakers
# =============================================================================
step "4/7" "Scanning for HK Aura Plus speakers"

info "Scanning for Bluetooth devices... (this takes about 15 seconds)"
info "Make sure your speaker is powered on!"
echo ""

# Start scan and collect results
SCAN_RESULTS=$(mktemp)
trap "rm -f $SCAN_RESULTS" EXIT

# Scan for devices - use a timeout approach
(
    bluetoothctl --timeout 15 scan on 2>/dev/null &
    sleep 15
    bluetoothctl scan off 2>/dev/null
) &>/dev/null &
SCAN_PID=$!

# Show a simple progress indicator
echo -n "    Scanning"
for i in $(seq 1 15); do
    echo -n "."
    sleep 1
done
echo " done!"
wait $SCAN_PID 2>/dev/null || true

# Get all discovered + paired devices
ALL_DEVICES=$(bluetoothctl devices 2>/dev/null)

# Filter for HK speakers (common names)
HK_DEVICES=$(echo "$ALL_DEVICES" | grep -iE "(harman|HK|Aura)" || true)

# Also check already paired devices
PAIRED_DEVICES=$(bluetoothctl devices Paired 2>/dev/null || bluetoothctl paired-devices 2>/dev/null || true)
HK_PAIRED=$(echo "$PAIRED_DEVICES" | grep -iE "(harman|HK|Aura)" || true)

# Merge and deduplicate
HK_ALL=$(echo -e "${HK_DEVICES}\n${HK_PAIRED}" | grep -v "^$" | sort -u || true)

BT_MAC=""
BT_NAME=""

if [[ -n "$HK_ALL" ]]; then
    log "Found HK speaker(s):"
    echo ""

    # Parse into arrays
    declare -a FOUND_MACS=()
    declare -a FOUND_NAMES=()
    i=1
    while IFS= read -r line; do
        mac=$(echo "$line" | awk '{print $2}')
        name=$(echo "$line" | cut -d' ' -f3-)
        FOUND_MACS+=("$mac")
        FOUND_NAMES+=("$name")
        echo "    [$i] $name ($mac)"
        i=$((i + 1))
    done <<< "$HK_ALL"

    echo ""
    if [[ ${#FOUND_MACS[@]} -eq 1 ]]; then
        BT_MAC="${FOUND_MACS[0]}"
        BT_NAME="${FOUND_NAMES[0]}"
        log "Auto-selected: $BT_NAME ($BT_MAC)"
    else
        ask "Select speaker number [1-${#FOUND_MACS[@]}]: "
        read -r choice
        idx=$((choice - 1))
        BT_MAC="${FOUND_MACS[$idx]}"
        BT_NAME="${FOUND_NAMES[$idx]}"
        log "Selected: $BT_NAME ($BT_MAC)"
    fi
else
    warn "No HK speakers found automatically."
    echo ""
    info "Showing ALL discovered Bluetooth devices:"
    echo ""

    declare -a ALL_MACS=()
    declare -a ALL_NAMES=()
    i=1
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        mac=$(echo "$line" | awk '{print $2}')
        name=$(echo "$line" | cut -d' ' -f3-)
        ALL_MACS+=("$mac")
        ALL_NAMES+=("$name")
        echo "    [$i] $name ($mac)"
        i=$((i + 1))
    done <<< "$ALL_DEVICES"

    echo "    [M] Enter MAC address manually"
    echo ""
    ask "Select your speaker [1-${#ALL_MACS[@]}/M]: "
    read -r choice

    if [[ "$choice" =~ ^[Mm] ]]; then
        ask "Enter your speaker's Bluetooth MAC address (e.g., AA:BB:CC:DD:EE:FF): "
        read -r BT_MAC
        ask "Enter a friendly name for the speaker (e.g., HK Aura BT): "
        read -r BT_NAME
    else
        idx=$((choice - 1))
        BT_MAC="${ALL_MACS[$idx]}"
        BT_NAME="${ALL_NAMES[$idx]}"
    fi

    log "Using: $BT_NAME ($BT_MAC)"
fi

# =============================================================================
# Step 5: Discover speaker WiFi IP via mDNS
# =============================================================================
step "5/7" "Discovering speaker WiFi IP address"

SPEAKER_IP=""
SPEAKER_PORT="10025"

info "Attempting mDNS discovery (looking for HK speaker on the network)..."
echo ""

# Try avahi-browse first
if command -v avahi-browse &>/dev/null; then
    info "Using avahi-browse to scan for AirPlay devices (HK speakers advertise via AirPlay)..."

    MDNS_RESULTS=$(timeout 10 avahi-browse -rpt _airplay._tcp 2>/dev/null | grep -iE "(HK|Harman|Aura)" || true)

    if [[ -n "$MDNS_RESULTS" ]]; then
        # Extract IP from avahi-browse output
        DISCOVERED_IP=$(echo "$MDNS_RESULTS" | grep -oP '\d+\.\d+\.\d+\.\d+' | head -1)
        if [[ -n "$DISCOVERED_IP" ]]; then
            SPEAKER_IP="$DISCOVERED_IP"
            log "Found speaker via mDNS at: $SPEAKER_IP"
        fi
    fi
fi

# Try avahi-resolve with known mDNS name pattern
if [[ -z "$SPEAKER_IP" ]] && command -v avahi-resolve &>/dev/null; then
    info "Trying known mDNS hostname patterns..."
    # HK Aura uses pattern: HK-Aura-WF-XXXXXX.local
    for hostname in $(avahi-browse -rpt _airplay._tcp 2>/dev/null | grep -oP 'HK-[A-Za-z0-9-]+\.local' | sort -u); do
        resolved=$(avahi-resolve -n "$hostname" 2>/dev/null | awk '{print $2}')
        if [[ -n "$resolved" ]]; then
            SPEAKER_IP="$resolved"
            log "Resolved $hostname → $SPEAKER_IP"
            break
        fi
    done
fi

# Try checking ARP table for known HK MAC prefixes
if [[ -z "$SPEAKER_IP" ]]; then
    info "Checking network for known HK WiFi MAC prefixes..."
    # Known HK WiFi MAC prefixes: E8:C7:4F
    ARP_IP=$(ip neigh 2>/dev/null | grep -i "e8:c7:4f" | awk '{print $1}' | head -1 || true)
    if [[ -n "$ARP_IP" ]]; then
        SPEAKER_IP="$ARP_IP"
        log "Found speaker via ARP table: $SPEAKER_IP (MAC prefix E8:C7:4F)"
    fi
fi

# If still not found, ask user
if [[ -z "$SPEAKER_IP" ]]; then
    warn "Could not auto-discover speaker's WiFi IP address."
    echo ""
    info "To find your speaker's IP address:"
    info "  1. Check your router's device list for 'HK Aura' or MAC starting with E8:C7:4F"
    info "  2. Or use the HK Remote app → Settings → About"
    info "  3. Or try: ping HK-Aura-WF-XXXXXX.local (replace X's with your speaker's ID)"
    echo ""
    ask "Enter your speaker's WiFi IP address: "
    read -r SPEAKER_IP
    log "Using IP: $SPEAKER_IP"
fi

# Verify connectivity
info "Testing connectivity to $SPEAKER_IP..."
if ping -c 2 -W 3 "$SPEAKER_IP" &>/dev/null; then
    log "Speaker is reachable at $SPEAKER_IP"
else
    warn "Cannot ping $SPEAKER_IP — speaker may be in deep standby or IP is wrong."
    if ! confirm "Continue anyway?"; then
        exit 1
    fi
fi

# =============================================================================
# Step 6: Pair and test connection
# =============================================================================
step "6/7" "Pairing and testing speaker connection"

# Check if already paired
IS_PAIRED=$(bluetoothctl info "$BT_MAC" 2>/dev/null | grep "Paired: yes" || true)

if [[ -n "$IS_PAIRED" ]]; then
    log "Speaker is already paired."
else
    info "We need to pair with your speaker."
    echo ""
    warn "ACTION REQUIRED: Put your speaker in Bluetooth pairing mode!"
    info "  → Usually: Press and hold the Bluetooth button on the speaker"
    info "  → The LED should blink to indicate pairing mode"
    echo ""
    wait_for_enter "Press Enter when the speaker is in pairing mode..."

    info "Pairing with $BT_NAME ($BT_MAC)..."
    if bluetoothctl pair "$BT_MAC" 2>/dev/null; then
        log "Pairing successful!"
    else
        err "Pairing failed."
        info "Trying with a fresh scan..."
        bluetoothctl --timeout 10 scan on &>/dev/null &
        sleep 10
        if bluetoothctl pair "$BT_MAC" 2>/dev/null; then
            log "Pairing successful on retry!"
        else
            err "Could not pair. Please pair manually using 'bluetoothctl' and re-run this script."
            exit 1
        fi
    fi
fi

# Trust the device (auto-connect in future)
bluetoothctl trust "$BT_MAC" &>/dev/null
log "Speaker is trusted (will auto-accept connections)."

# Test connection
if confirm "Test the Bluetooth connection now? (will play a short sound on the speaker)"; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"

    info "Connecting to $BT_NAME..."
    CONNECT_OUTPUT=$(bluetoothctl connect "$BT_MAC" 2>&1)

    if echo "$CONNECT_OUTPUT" | grep -q "Connection successful"; then
        log "Bluetooth connection successful!"

        # Wait for audio sink
        info "Waiting for audio sink..."
        SINK_FOUND=false
        for i in $(seq 1 10); do
            if pactl list sinks short 2>/dev/null | grep -q "bluez_output"; then
                SINK_FOUND=true
                break
            fi
            sleep 1
        done

        if $SINK_FOUND; then
            log "Audio sink registered."
            info "Playing test audio (3 seconds)..."
            mpv --no-video --quiet --length=3 --ao=pulse \
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3" 2>/dev/null || \
                warn "Audio playback failed, but connection worked."
            log "Test complete!"
        else
            warn "Audio sink did not appear. Audio streaming may not work."
        fi

        bluetoothctl disconnect "$BT_MAC" &>/dev/null
        log "Disconnected."
    else
        warn "Connection test failed. The wake script may still work (speakers can be finicky)."
        echo "$CONNECT_OUTPUT"
    fi
fi

# =============================================================================
# Step 7: Generate config and deploy wake script
# =============================================================================
step "7/7" "Saving configuration"

# Ask for optional settings
echo ""
ask "Audio duration in seconds for wake-up [default: 5]: "
read -r AUDIO_DURATION
AUDIO_DURATION="${AUDIO_DURATION:-5}"

ask "Max wait time for speaker TCP port (seconds) [default: 60]: "
read -r MAX_WAIT
MAX_WAIT="${MAX_WAIT:-60}"

ask "Audio URL for wake-up [Enter for default test tone]: "
read -r CUSTOM_URL
INTRO_SONG_URL="${CUSTOM_URL:-https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3}"

# Write config file
cat > "$CONFIG_FILE" << CONFEOF
# =============================================================================
# HK Aura Plus — Wake Speaker Configuration
# Generated by setup wizard on $(date)
# =============================================================================

# Bluetooth settings (auto-detected)
BT_MAC="$BT_MAC"
BT_NAME="$BT_NAME"

# WiFi/Network settings (auto-detected)
SPEAKER_IP="$SPEAKER_IP"
SPEAKER_PORT=$SPEAKER_PORT

# Wake behavior
MAX_WAIT=$MAX_WAIT
AUDIO_DURATION=$AUDIO_DURATION
INTRO_SONG_URL="$INTRO_SONG_URL"
CONFEOF

log "Configuration saved to: $CONFIG_FILE"

# Enable PipeWire user services at boot
if confirm "Enable PipeWire/WirePlumber services at boot? (recommended for headless)"; then
    systemctl --user enable pipewire pipewire-pulse wireplumber 2>/dev/null || true
    log "PipeWire services enabled at boot."

    if confirm "Enable user lingering? (needed if no one logs in at boot — typical for Raspberry Pi)"; then
        sudo loginctl enable-linger "$USER" 2>/dev/null || true
        log "User lingering enabled."
    fi
fi

# Make wake script executable
chmod +x "$WAKE_SCRIPT" 2>/dev/null || true

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     Setup Complete! ✓                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${BOLD}Speaker:${NC}      $BT_NAME"
echo -e "  ${BOLD}BT MAC:${NC}       $BT_MAC"
echo -e "  ${BOLD}WiFi IP:${NC}      $SPEAKER_IP"
echo -e "  ${BOLD}Control Port:${NC}  $SPEAKER_PORT"
echo -e "  ${BOLD}Config File:${NC}  $CONFIG_FILE"
echo ""
echo -e "  ${BOLD}To wake your speaker:${NC}"
echo -e "    ${GREEN}./wake_speaker_linux.sh${NC}"
echo ""
echo -e "  ${BOLD}To re-run setup:${NC}"
echo -e "    ${GREEN}./setup_wake_speaker.sh${NC}"
echo ""
info "The wake script will automatically read your saved configuration."
echo ""
