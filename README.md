# ALISA_OS

ALISA_OS is a local dashboard and bridge for sending commands from a browser dashboard to a Yandex Station through Home Assistant.

## Quick Start

1. Download this repository as a ZIP and unzip it.
2. Double-click `START_ALISA_OS.bat`.
3. Enter your Home Assistant URL, long-lived access token, and Yandex Station `media_player` entity ID.
4. Keep the loader window open while using the dashboard.

## Requirements

- Windows
- Python 3.10+
- Home Assistant running on your network
- Yandex Station integration installed in Home Assistant
- HACS if your Yandex Station integration is installed through HACS

## Important

Do not upload or share `.env`. It contains private local settings and can contain your Home Assistant token.

Use `.env.example` as the public template.

## More Setup Help

See `README_INSTALL.md`.
