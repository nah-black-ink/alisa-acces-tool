from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
REQUIREMENTS = ROOT / "requirements.txt"
DASHBOARD = ROOT / "dashboard.html"
BRIDGE = ROOT / "alisa_bridge.py"
HACS_DOCS = "https://hacs.xyz/docs/use/configuration/basic/"
YANDEX_STATION_DOCS = "https://github.com/AlexxIT/YandexStation"


DEFAULT_ENV = {
    "ALISA_HOST": "127.0.0.1",
    "ALISA_PORT": "5000",
    "HOME_ASSISTANT_URL": "http://homeassistant.local:8123",
    "HOME_ASSISTANT_TOKEN": "PASTE_YOUR_LONG_LIVED_TOKEN_HERE",
    "YANDEX_ENTITY_ID": "media_player.alisa_1",
    "FORCE_ENGLISH": "false",
}


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(">", " ".join(command))
    return subprocess.run(command, cwd=ROOT, text=True, check=check)


def read_env() -> dict[str, str]:
    values = DEFAULT_ENV.copy()

    if not ENV_FILE.exists():
        return values

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value

    return values


def write_env(values: dict[str, str]) -> None:
    lines = [
        "# ALISA_OS local configuration",
        "# Keep this file private. It can contain your Home Assistant token.",
    ]
    lines.extend(f"{key}={values[key]}" for key in DEFAULT_ENV)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prompt_env() -> dict[str, str]:
    values = read_env()

    print()
    print("ALISA_OS configuration")
    print("Press Enter to keep the value shown in brackets.")
    print()

    prompts = [
        ("HOME_ASSISTANT_URL", "Home Assistant URL"),
        ("HOME_ASSISTANT_TOKEN", "Home Assistant long-lived access token"),
        ("YANDEX_ENTITY_ID", "Yandex Station entity_id"),
        ("ALISA_PORT", "Bridge port"),
    ]

    for key, label in prompts:
        current = values.get(key, DEFAULT_ENV[key])
        display = "configured" if key.endswith("TOKEN") and current != DEFAULT_ENV[key] else current
        answer = input(f"{label} [{display}]: ").strip()
        if answer:
            values[key] = answer

    write_env(values)
    return values


def open_setup_links(values: dict[str, str]) -> None:
    home_url = values.get("HOME_ASSISTANT_URL", DEFAULT_ENV["HOME_ASSISTANT_URL"]).rstrip("/")
    missing_token = values.get("HOME_ASSISTANT_TOKEN") == DEFAULT_ENV["HOME_ASSISTANT_TOKEN"]

    if not missing_token:
        return

    print()
    print("Opening setup helper pages because the Home Assistant token is not configured yet.")
    print("Use these pages to install HACS/Yandex.Station and create your access token.")
    print()

    for url in [
        home_url,
        home_url + "/profile",
        home_url + "/config/integrations",
        HACS_DOCS,
        YANDEX_STATION_DOCS,
    ]:
        webbrowser.open(url)


def ensure_venv() -> Path:
    python_path = venv_python()

    if not python_path.exists():
        print("Creating local Python environment...")
        run([sys.executable, "-m", "venv", str(VENV)])

    return python_path


def install_requirements(python_path: Path) -> None:
    print("Installing/updating required packages...")
    run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_path), "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def start_bridge(python_path: Path) -> subprocess.Popen[str]:
    print("Starting ALISA_OS Bridge...")
    return subprocess.Popen(
        [str(python_path), str(BRIDGE)],
        cwd=ROOT,
        text=True,
    )


def open_dashboard(port: str) -> None:
    dashboard_url = DASHBOARD.resolve().as_uri()
    bridge_url = f"http://127.0.0.1:{port}"
    setup_check_url = f"{bridge_url}/setup-check"

    print()
    print("Dashboard:", dashboard_url)
    print("Bridge:", bridge_url)
    print("Setup check:", setup_check_url)
    print()

    webbrowser.open(dashboard_url)
    webbrowser.open(bridge_url)
    webbrowser.open(setup_check_url)


def main() -> int:
    print("=" * 56)
    print("ALISA_OS Auto Loader")
    print("=" * 56)

    if not BRIDGE.exists() or not DASHBOARD.exists():
        print("Missing alisa_bridge.py or dashboard.html.")
        input("Press Enter to close...")
        return 1

    values = prompt_env()
    open_setup_links(values)
    python_path = ensure_venv()
    install_requirements(python_path)
    bridge_process = start_bridge(python_path)

    time.sleep(1.2)
    open_dashboard(values.get("ALISA_PORT", "5000"))

    print("ALISA_OS is running. Keep this window open.")
    print("Press Ctrl+C to stop the bridge.")
    print()

    try:
        return bridge_process.wait()
    except KeyboardInterrupt:
        print("\nStopping ALISA_OS Bridge...")
        bridge_process.terminate()
        try:
            bridge_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bridge_process.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
