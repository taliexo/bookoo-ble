# Bookoo BLE Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/taliexo/bookoo-ble.svg)](https://github.com/taliexo/bookoo-ble/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/taliexo/bookoo-ble/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/taliexo/bookoo-ble.svg)](https://github.com/taliexo/bookoo-ble/issues)

This integration allows you to monitor and control your Bookoo smart coffee scale via Bluetooth Low Energy (BLE) in Home Assistant. It provides real-time weight monitoring, flow rate calculation, and timer functionality with full control over scale settings.

## Features

- 📊 **Real-time weight monitoring** - Accurate weight measurements with configurable units
- 💧 **Flow rate tracking** - Perfect for pour-over coffee with smoothing options
- ⏱️ **Built-in timer** - Start/stop/reset functionality with auto-start options
- 🔋 **Battery monitoring** - Track remaining battery percentage
- 🔊 **Configurable beep levels** - Adjust volume or mute completely (0-5)
- ⚙️ **Auto-off timer** - Configure shutdown delay from 1-30 minutes
- 🔄 **Automatic reconnection** - Handles connection drops gracefully
- 🏠 **Home Assistant UI** - Native UI controls and configuration
- 🔌 **Service API** - Full control via Home Assistant services
- 🚀 **Fast response** - Optimized BLE communication for minimal latency

## Supported Devices

- Bookoo Scale (BOOKOO_SC series)
- Bookoo Themis

## Requirements

- Home Assistant 2024.1.0 or newer
- Bluetooth adapter accessible to Home Assistant
- Bookoo scale within Bluetooth range

## Installation

### HACS Installation (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add `https://github.com/taliexo/bookoo-ble` as a custom repository with category "Integration"
5. Click "Install" on the Bookoo BLE card
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/taliexo/bookoo-ble/releases)
2. Extract the `bookoo_ble` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### Automatic Discovery

If your Bookoo scale is powered on and in range, it should be automatically discovered:

1. Go to **Settings** → **Devices & Services**
2. Look for a notification about a discovered Bookoo device
3. Click **Configure** and follow the setup wizard

### Manual Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Bookoo BLE"
4. Choose between automatic scanning or manual MAC address entry
5. Configure your device settings:
   - **Name**: Custom name for your scale
   - **Beep Level**: Volume of beeps (0-5, 0 = silent)
   - **Auto-off Timer**: Minutes before automatic shutdown (1-30)
   - **Flow Smoothing**: Enable/disable flow rate smoothing

## Sensors

The integration provides the following sensors:

| Sensor | Description | Unit |
|--------|-------------|------|
| Weight | Current weight on the scale | grams (g) |
| Flow Rate | Rate of weight change | grams/second (g/s) |
| Timer | Elapsed time since timer start | MM:SS |
| Battery Level | Remaining battery percentage | % |

## Services

The integration provides several services that can be called from Home Assistant automations, scripts, or the Developer Tools → Services panel.

### Service Overview

| Service | Description | Parameters |
|---------|-------------|------------|
| `bookoo_ble.tare` | Tare (zero) the scale | `entity_id` or `device_id` |
| `bookoo_ble.start_timer` | Start the built-in timer | `entity_id` or `device_id` |
| `bookoo_ble.stop_timer` | Stop the built-in timer | `entity_id` or `device_id` |
| `bookoo_ble.reset_timer` | Reset timer to 00:00 | `entity_id` or `device_id` |
| `bookoo_ble.tare_and_start_timer` | Tare and start timer in one command | `entity_id` or `device_id` |
| `bookoo_ble.set_beep_level` | Set beep volume (0-5) | `entity_id`/`device_id`, `level` |
| `bookoo_ble.set_auto_off` | Set auto-off timer (1-30 min) | `entity_id`/`device_id`, `minutes` |
| `bookoo_ble.set_flow_smoothing` | Toggle flow rate smoothing | `entity_id`/`device_id`, `enabled` |

### Service Details

#### Tare the Scale
Zero the scale's current weight reading.

```yaml
service: bookoo_ble.tare
target:
  entity_id: sensor.bookoo_scale_weight
  # OR
  device_id: abcdef1234567890
```

#### Start/Stop/Reset Timer
Control the built-in timer functionality.

```yaml
service: bookoo_ble.start_timer
target:
  entity_id: sensor.bookoo_scale_timer
  # OR
  device_id: abcdef1234567890
```

#### Set Beep Level
Adjust the beep volume (0-5, where 0 is silent).

```yaml
service: bookoo_ble.set_beep_level
target:
  entity_id: sensor.bookoo_scale_weight
data:
  level: 3  # 0-5 (0 = silent)
```

#### Set Auto-Off Timer
Configure the auto-shutdown delay (1-30 minutes).

```yaml
service: bookoo_ble.set_auto_off
target:
  entity_id: sensor.bookoo_scale_weight
data:
  minutes: 10  # 1-30 minutes
```

### Entity Services

Each sensor entity also provides direct service calls. For example, to tare the scale:

```yaml
service: button.bookoo_scale_tare
data: {}
target:
  entity_id: button.bookoo_scale_tare
```

### Automation Examples

#### Auto-Start Timer When Pouring Begins
```yaml
alias: "Auto-start scale timer on pour"
description: "Start timer when weight exceeds 5g"
trigger:
  - platform: numeric_state
    entity_id: sensor.bookoo_scale_weight
    above: 5
    for:
      seconds: 1
condition:
  - condition: state
    entity_id: sensor.bookoo_scale_timer
    state: "00:00"
action:
  - service: bookoo_ble.tare_and_start_timer
    target:
      entity_id: sensor.bookoo_scale_weight
```

#### Notify When Brewing is Complete
```yaml
alias: "Notify when brewing is complete"
description: "Send notification when weight stabilizes after pouring"
trigger:
  - platform: state
    entity_id: sensor.bookoo_scale_flow_rate
    to: "0"
    for:
      seconds: 5
condition:
  - condition: numeric_state
    entity_id: sensor.bookoo_scale_weight
    above: 0
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Brew Complete!"
      message: "Your coffee is ready. Total brew time: {{ states('sensor.bookoo_scale_timer') }}"

## BLE Protocol Details

This integration communicates with the Bookoo scale using Bluetooth Low Energy (BLE) with the following characteristics:

- **Service UUID**: `00000FFE-0000-1000-8000-00805F9B34FB` (0x0FFE)
- **Command Characteristic**: `0000FF12-0000-1000-8000-00805F9B34FB` (0xFF12)
  - Used for sending commands to the scale
  - Also receives timer status notifications (data[0]=0x03, data[1]=0x0D)
- **Data Characteristic**: `0000FF11-0000-1000-8000-00805F9B34FB` (0xFF11)
  - Receives weight, flow rate, battery level, and other sensor data

### Checksum Calculation
All commands use a simple XOR checksum:
```python
def calculate_checksum(data: bytes) -> int:
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum
```

## Known Issues

1. **Timer Status Notifications**
   - The scale sends timer status updates on the Command Characteristic (0xFF12)
   - These notifications have the format: `[0x03, 0x0D, status, 0x00, ..., checksum]`
   - Status: 0x01 = timer started, 0x00 = timer stopped

2. **Connection Stability**
   - Some Bluetooth adapters may have issues maintaining a stable connection
   - If experiencing disconnections, try moving the scale closer to your Home Assistant instance

3. **Multiple Scales**
   - The integration supports multiple scales, but each must be configured with a unique name
   - Ensure scales are powered on one at a time during initial setup

## Troubleshooting

### Scale not discovered

1. Ensure the scale is powered on and showing the Bluetooth icon
2. Check that your Home Assistant instance has Bluetooth access:
   - For Docker installations, ensure the container has access to the Bluetooth device
   - For supervised installations, the Bluetooth integration should be enabled

### Connection drops frequently

1. Move the scale closer to your Bluetooth adapter
2. Check for interference from other Bluetooth devices
3. Ensure the scale battery is sufficiently charged

### Docker Bluetooth Setup

If running Home Assistant in Docker, you need to give the container access to Bluetooth:

```bash
docker run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  -v /PATH_TO_YOUR_CONFIG:/config \
  --device /dev/ttyUSB0 \
  --net=host \
  -v /var/run/dbus:/var/run/dbus:ro \
  --device /dev/ttyACM0 \
  --device /dev/ttyAMA0 \
  --device /dev/ttyS0 \
  --device /dev/ttyUSB0 \
  --device /dev/ttyUSB1 \
  --device /dev/hidraw0 \
  --device /dev/hidraw1 \
  -e TZ=America/New_York \
  homeassistant/home-assistant:latest
```

### Debugging

To enable debug logging, add the following to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.bookoo_ble: debug
    bleak: warning
    homeassistant.components.bluetooth: warning
```

### Common Issues

1. **Scale Not Connecting**
   - Ensure the scale is in pairing mode (usually by pressing the power button)
   - Check that no other devices are connected to the scale
   - Restart Home Assistant after configuration changes

2. **Intermittent Disconnections**
   - Try moving the scale closer to your Bluetooth adapter
   - Check for sources of interference (microwaves, wireless devices, etc.)
   - Consider using a Bluetooth USB adapter with external antenna

3. **Missing Entities**
   - Ensure all required platforms are loaded (sensor, button, number, switch)
   - Check the Home Assistant logs for any errors during startup
   - Try removing and re-adding the integration if entities don't appear

## Automation Examples

### Auto-tare when placing cup

```yaml
automation:
  - alias: "Auto-tare Bookoo Scale"
    trigger:
      - platform: state
        entity_id: sensor.bookoo_scale_weight
        from: "0.0"
    condition:
      - condition: numeric_state
        entity_id: sensor.bookoo_scale_weight
        above: 50  # Trigger when weight > 50g
    action:
      - delay: "00:00:02"  # Wait for weight to stabilize
      - service: bookoo_ble.tare
        target:
          entity_id: sensor.bookoo_scale_weight
```

### Coffee brewing timer

```yaml
automation:
  - alias: "Start coffee timer on first pour"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bookoo_scale_flow_rate
        above: 2  # Trigger when flow > 2g/s
    condition:
      - condition: state
        entity_id: sensor.bookoo_scale_timer
        state: "00:00"
    action:
      - service: bookoo_ble.start_timer
        target:
          entity_id: sensor.bookoo_scale_timer
```

## Support

- [GitHub Issues](https://github.com/taliexo/bookoo-ble/issues)
- [Home Assistant Community](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Bookoo Coffee for protocol documentation
- Home Assistant Bluetooth integration developers
- [AcaiaArduinoBLE](https://github.com/tatemazer/AcaiaArduinoBLE) for protocol insights