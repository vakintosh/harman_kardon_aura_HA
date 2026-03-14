# HK Aura Plus Speaker Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration for controlling the Harman Kardon Aura Plus speaker over your local network. Provides Home Assistant entities for volume, bass, EQ mode, mute, and power control.

## Features

- **Volume Control** — Adjust speaker volume (0–100)
- **Bass Control** — Fine-tune bass level (0–100)
- **EQ Mode** — Toggle between Basic and Stereo Widening
- **Mute/Unmute** — Toggle switch
- **Power Off** — Turn off speaker via button
- **Volume Sync** — Optionally sync with a media_player entity
- Seamless integration with Home Assistant UI and automations

> **⚠️ Note**: The power-off button fully shuts down the speaker. To turn it back on, you must use the physical power button, the official HK Remote app, or a [Bluetooth wake script](#bluetooth-wake-from-standby).

## Requirements

- Home Assistant 2024.1.0 or newer
- Harman Kardon Aura Plus speaker connected to your local network

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → click the **⋮** menu (top right) → **Custom repositories**.
3. Add `https://github.com/vakintosh/harman_kardon_aura_HA` with category **Integration**.
4. Search for **HK Aura Plus Speaker** and install.
5. Restart Home Assistant.

### Manual

1. **Clone or download** this repository.
2. **Copy** the `custom_components/hkaura_plus/` directory to your Home Assistant `custom_components/` folder.
3. **Restart** Home Assistant.

## Configuration

This integration is configured via the UI:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **HK Aura Plus**.
3. Enter your speaker's IP address and port.

See [configuration.yaml.example](docs/configuration.yaml.example) for optional template sensors.

### Configuration Options

| Option | Required | Description |
|--------|----------|-------------|
| Host | Yes | IP address or hostname of your HK Aura Plus speaker |
| Port | Yes | Port number for communication (default: 10025) |
| Media Player Entity | No | Entity ID of a media player to sync volume with |

### Volume Sync

If you configure `media_player_entity` (e.g., `media_player.hk_aura_airplay` from Music Assistant), volume changes on the media player will automatically be sent to the physical speaker. This keeps the speaker volume in sync regardless of how you control it.

## Usage

After configuration and restart, the following entities appear in Home Assistant:

| Entity | Description |
|--------|-------------|
| `number.hk_aura_volume` | Volume control (0–100) |
| `number.hk_aura_bass` | Bass level (0–100) |
| `switch.hk_aura_eq_mode` | EQ mode toggle |
| `switch.hk_aura_mute` | Mute toggle |
| `button.hk_aura_power_off` | Power off button |

## Dashboard

![HK Aura Plus Speaker](img/HA_HK_Aura_App.png)

<details>
<summary>Lovelace YAML</summary>

```yaml
type: grid
cards:
  - type: heading
    heading_style: title
    heading: HK Aura App
  - type: entities
    entities:
      - entity: number.hk_aura_volume
      - entity: number.hk_aura_bass
      - entity: switch.hk_aura_eq_mode
      - entity: switch.hk_aura_mute
      - entity: button.hk_aura_power_off
```

</details>

## Bluetooth Wake from Standby

The speaker's WiFi control port (TCP 10025) only opens after it receives a Bluetooth A2DP audio stream. Scripts are provided to automate this:

| Script | Platform | Description |
|--------|----------|-------------|
| [`scripts/wake_speaker_mac.sh`](scripts/wake_speaker_mac.sh) | macOS | Uses blueutil + mpv |
| [`scripts/wake_speaker_linux.sh`](scripts/wake_speaker_linux.sh) | Linux / Raspberry Pi | Uses bluetoothctl + PipeWire + mpv |
| [`scripts/setup_wake_speaker.sh`](scripts/setup_wake_speaker.sh) | Linux | Interactive setup wizard |


## Project Structure

```
├── custom_components/
│   └── hkaura_plus/      # Home Assistant custom component
├── scripts/              # Wake scripts & test utilities
└── img/                  # Screenshots
```

## How It Works

The speaker exposes a TCP control port (default 10025) that accepts XML commands. The integration sends XML payloads over raw TCP — no HTTP framing is used. The speaker processes the command and optionally returns a status XML response.

## Troubleshooting

- Ensure your speaker is on the same network as Home Assistant.
- Check the IP address in your configuration.
- Review Home Assistant logs for integration errors.

## Disclaimer

This integration is not affiliated with or endorsed by Harman Kardon.

## License

MIT — see [LICENSE](LICENSE) for details.