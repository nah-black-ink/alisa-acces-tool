# ALISA_OS Quick Install

## Fast Start

1. Download and unzip the ALISA_OS folder.
2. Double-click `START_ALISA_OS.bat`.
3. Enter your Home Assistant URL, token, and Yandex Station entity ID.
4. Keep the loader window open while using ALISA_OS.

The loader automatically creates `.venv`, installs Python packages, creates `.env`, starts the bridge, opens the dashboard, and opens `/setup-check`.

## What The Loader Cannot Do For You

These steps need user login/permission inside Home Assistant or Yandex:

1. Install Python if Windows does not have it.
   - Download: https://www.python.org/downloads/
   - During install, enable `Add python.exe to PATH`.

2. Have Home Assistant running.
   - Example URL: `http://homeassistant.local:8123`
   - Your PC running ALISA_OS must be able to reach it on the same network.

3. Install HACS if the Yandex integration is not already available.
   - Official HACS setup: https://hacs.xyz/docs/use/configuration/basic/
   - In Home Assistant: `Settings > Devices & services > Add integration > HACS`
   - HACS requires GitHub device authorization.

4. Install Yandex.Station integration.
   - Project: https://github.com/AlexxIT/YandexStation
   - HACS path: `HACS > Integrations > Add > Yandex.Station > Install`
   - Then restart Home Assistant.

5. Add the Yandex Station integration.
   - In Home Assistant: `Settings > Devices & services > Add integration > Yandex Station`
   - Use QR code authorization if available.
   - After setup, find your speaker entity, for example `media_player.alisa_1`.

6. Create a Home Assistant long-lived access token.
   - Open your Home Assistant profile page.
   - Scroll to `Long-lived access tokens`.
   - Create a token and paste it into the loader when asked.
   - Keep this token private.

7. Allow Windows firewall/network access if prompted.
   - The bridge runs locally on `127.0.0.1:5000`.
   - The dashboard talks to the bridge and the bridge talks to Home Assistant.

## Auto-Opened Helper Pages

If the token is still missing, `alisa_loader.py` opens:

- Home Assistant
- Home Assistant profile page
- Home Assistant integrations page
- HACS documentation
- Yandex.Station integration page

After the bridge starts, the loader also opens:

- Dashboard
- Bridge root page
- `http://127.0.0.1:5000/setup-check`

Use `/setup-check` to see whether token, Home Assistant, and Yandex entity are ready.

## For Sharing

Double-click `MAKE_PORTABLE_ZIP.bat`.

It creates `ALISA_OS_portable.zip` without private files like `.env`, `.venv`, or `__pycache__`.

## Main Files

- `START_ALISA_OS.bat` starts everything on Windows.
- `alisa_loader.py` installs dependencies, saves config, starts the bridge, and opens setup pages.
- `alisa_bridge.py` runs the local bridge and provides `/setup-check`.
- `dashboard.html` is the dashboard UI.
- `.env` stores private local settings and should not be shared.
