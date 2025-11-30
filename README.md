# Service Result Entities

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

A Home Assistant custom integration that exposes entities whose attributes are populated from the **response data of Home Assistant services/actions**.

## ✨ What It Does

This integration creates **sensor entities** that:

1. Call any Home Assistant service at configurable intervals
2. Capture the **service response data**
3. Expose the complete response in the sensor's `data` attribute

This is a "**service response → attribute bridge**" that allows Dashboards and cards (which only work with entity states and attributes) to display data from service responses.

## 🎯 Use Cases

- Display **Tibber price data** from `tibber.get_price_info` in a dashboard
- Show **weather forecast data** in custom cards
- Access **calendar events** in Lovelace
- Any service that returns response data with `return_response: true`

## ⚠️ Important Notes

- This integration is for **advanced users** who understand YAML and service calls
- Large responses and short polling intervals can impact:
  - Home Assistant performance
  - Database/Recorder size
  - Frontend rendering speed
- The `data` attribute contains the **raw service response** - format varies by service

## 🚀 Quick Start

### Step 1: Install the Integration

**Prerequisites:** This integration requires [HACS](https://hacs.xyz/) (Home Assistant Community Store).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jpawlowski&repository=hass.service_result&category=integration)

Then:

1. Click "Download" to install the integration
2. **Restart Home Assistant** (required after installation)

### Step 2: Add a Service Result Entity

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=service_result)

Configure:

1. **Name**: A friendly name for this sensor (e.g., "Tibber Prices")
2. **Service Domain**: The service domain (e.g., `tibber`)
3. **Service Name**: The service name (e.g., `get_price_info`)
4. **Service Data (YAML)**: Optional YAML data for the service call

> **Tip**: Copy the YAML directly from Developer Tools → Services

### Step 3: Access the Data

The sensor exposes:

- **State**: `ok` or `error`
- **Attributes**:
  - `data`: The complete service response
  - `service`: The service that was called
  - `last_update`: When the data was last refreshed
  - `success`: Whether the last call succeeded
  - `error_message`: Error details (if any)

Example template to access the data:

```yaml
{{ state_attr('sensor.tibber_prices', 'data') }}
```

## 📋 Configuration Options

### Initial Setup

| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Friendly name for the sensor |
| Service Domain | Yes | Domain of the service to call |
| Service Name | Yes | Name of the service to call |
| Service Data (YAML) | No | Optional YAML data for the service |

### Options (After Setup)

| Option | Default | Description |
|--------|---------|-------------|
| Polling Interval | 300s | How often to call the service (10-86400 seconds) |

## 📝 Example: Tibber Price Info

**Service Domain**: `tibber`  
**Service Name**: `get_price_info`  
**Polling Interval**: 3600 (1 hour)

The sensor's `data` attribute will contain the price information returned by Tibber.

## 🔧 Troubleshooting

### Service Not Found

Verify the service exists in Developer Tools → Services.

### YAML Parse Error

Check your YAML syntax. The service data must be valid YAML with key: value pairs.

### Empty Data Attribute

- Verify the service supports `return_response`
- Check if the service requires specific input data
- Review Home Assistant logs for errors

### Enable Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.service_result: debug
```

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jpawlowski/hass.service_result?quickstart=1)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by [@jpawlowski][user_profile]**

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/jpawlowski/hass.service_result.svg?style=for-the-badge
[commits]: https://github.com/jpawlowski/hass.service_result/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/jpawlowski/hass.service_result.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40jpawlowski-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/jpawlowski/hass.service_result.svg?style=for-the-badge
[releases]: https://github.com/jpawlowski/hass.service_result/releases
[user_profile]: https://github.com/jpawlowski
