# Bookoo BLE Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/taliexo/bookoo-ble.svg)](https://github.com/taliexo/bookoo-ble/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This integration allows you to monitor your Bookoo smart coffee scale via Bluetooth Low Energy (BLE) in Home Assistant.

## Features

- 📊 Real-time weight monitoring
- 💧 Flow rate tracking for pour-over coffee
- ⏱️ Built-in timer functionality
- 🔋 Battery level monitoring
- 🔊 Configurable beep levels
- ⚙️ Auto-off timer settings
- 🔄 Automatic reconnection on connection loss

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

### bookoo_ble.tare

Tare (zero) the scale.

```yaml
service: bookoo_ble.tare
target:
  entity_id: sensor.bookoo_scale_weight
```

### bookoo_ble.start_timer

Start the built-in timer.

```yaml
service: bookoo_ble.start_timer
target:
  entity_id: sensor.bookoo_scale_timer
```

### bookoo_ble.stop_timer

Stop the built-in timer.

```yaml
service: bookoo_ble.stop_timer
target:
  entity_id: sensor.bookoo_scale_timer
```

### bookoo_ble.reset_timer

Reset the timer to 00:00.

```yaml
service: bookoo_ble.reset_timer
target:
  entity_id: sensor.bookoo_scale_timer
```

### bookoo_ble.tare_and_start_timer

Zero the scale and start the timer in one command.

```yaml
service: bookoo_ble.tare_and_start_timer
target:
  entity_id: sensor.bookoo_scale_timer # Or sensor.bookoo_scale_weight
```

### bookoo_ble.set_beep_level

Set the beep volume level.

```yaml
service: bookoo_ble.set_beep_level
target:
  entity_id: sensor.bookoo_scale_weight # Any Bookoo sensor entity
data:
  level: 3 # Volume level (0-5, 0 = silent)
```

### bookoo_ble.set_auto_off

Set the auto-off duration in minutes.

```yaml
service: bookoo_ble.set_auto_off
target:
  entity_id: sensor.bookoo_scale_weight # Any Bookoo sensor entity
data:
  minutes: 10 # Auto-off duration in minutes (1-30)
```

### bookoo_ble.set_flow_smoothing

Enable or disable flow rate smoothing.

```yaml
service: bookoo_ble.set_flow_smoothing
target:
  entity_id: sensor.bookoo_scale_weight # Any Bookoo sensor entity
data:
  enabled: true # true to enable, false to disable
```

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
  homeassistant/home-assistant
```

For systems using BlueZ, you might need to add:
```bash
  -v /var/run/dbus:/var/run/dbus:ro
```

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