from __future__ import annotations

import ipaddress
import os
import platform
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS


# ==========================================================
# ALISA_OS BRIDGE FOR HOME ASSISTANT + YANDEX.STATION
# ==========================================================
# Dashboard  ->  http://localhost:5000  ->  Home Assistant  ->  Яндекс Станция
#
# Install:
#   pip install flask flask-cors requests
#
# Run:
#   python alisa_bridge.py
#
# Dashboard Bridge URL:
#   http://localhost:5000
# ==========================================================


APP_NAME = "ALISA_OS Bridge"
APP_VERSION = "3.0-clean"


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()


def env_value(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


HOST = env_value("ALISA_HOST", "127.0.0.1")
PORT = int(env_value("ALISA_PORT", "5000") or "5000")


# ==========================================================
# CHANGE THESE 3 SETTINGS
# ==========================================================

# If this works in browser, leave it:
HOME_ASSISTANT_URL = env_value("HOME_ASSISTANT_URL", "http://homeassistant.local:8123")

# If homeassistant.local does not work, use IP instead, for example:
# HOME_ASSISTANT_URL = "http://192.168.88.40:8123"

# Paste your Home Assistant Long-Lived Access Token here.
# Do not send this token to anyone.
HOME_ASSISTANT_TOKEN = env_value("HOME_ASSISTANT_TOKEN", "PASTE_YOUR_LONG_LIVED_TOKEN_HERE")

# Put your Yandex Station entity_id here.
# Example:
# YANDEX_ENTITY_ID = "media_player.alisa_1"
YANDEX_ENTITY_ID = env_value("YANDEX_ENTITY_ID", "media_player.alisa_1")
FORCE_ENGLISH = env_value("FORCE_ENGLISH", "false").lower() in {"1", "true", "yes", "on"}

ENGLISH_PREFIX = (
    "Answer only in English. "
    "Do not use Russian. "
    "If the user writes in Russian, translate the meaning and answer in English. "
)


# ==========================================================
# FLASK APP
# ==========================================================

app = Flask(__name__)
CORS(app)


@dataclass
class BridgeState:
    started_at: float = field(default_factory=time.time)
    command_count: int = 0
    last_command: str = ""
    volume: int = 30
    music_state: str = "unknown"
    last_error: str = ""


state = BridgeState()


# ==========================================================
# BASIC HELPERS
# ==========================================================

def uptime_seconds() -> int:
    return int(time.time() - state.started_at)


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def normalize_language(language: str) -> str:
    if FORCE_ENGLISH:
        return "en"

    language = (language or "en").lower().strip()
    return language if language in {"en", "ru"} else "en"


def is_ru(language: str) -> bool:
    return normalize_language(language) == "ru"


def text_for(language: str, ru: str, en: str) -> str:
    return ru if is_ru(language) else en


def language_instruction(language: str) -> str:
    language = normalize_language(language)

    if language == "ru":
        return (
            "Отвечай только на русском языке. "
            "Не используй английский язык, кроме имён, названий и технических терминов. "
            "Если пользователь пишет на английском, переведи смысл и ответь по-русски. "
        )

    return (
        "Answer only in English. "
        "Do not use Russian. "
        "If the user writes in Russian, translate the meaning and answer in English. "
    )


def english_only(text: str) -> str:
    if not FORCE_ENGLISH:
        return text

    clean = text.strip()

    if clean.lower().startswith("answer only in english"):
        return clean

    return ENGLISH_PREFIX + clean


def extract_number(text: str, default: int = 30) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())

    if not digits:
        return default

    return max(0, min(100, int(digits)))


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("192.168.88.1", 80))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


# ==========================================================
# HOME ASSISTANT HELPERS
# ==========================================================

def ha_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json",
    }


def ha_url(path: str) -> str:
    return HOME_ASSISTANT_URL.rstrip("/") + path


def ha_get(path: str) -> Any:
    response = requests.get(
        ha_url(path),
        headers=ha_headers(),
        timeout=8,
    )

    response.raise_for_status()

    if response.text.strip():
        return response.json()

    return {"ok": True}


def ha_post(path: str, payload: dict[str, Any]) -> Any:
    response = requests.post(
        ha_url(path),
        headers=ha_headers(),
        json=payload,
        timeout=12,
    )

    response.raise_for_status()

    if response.text.strip():
        return response.json()

    return {"ok": True}


def ha_call_service(domain: str, service: str, data: dict[str, Any]) -> Any:
    return ha_post(f"/api/services/{domain}/{service}", data)


def check_home_assistant() -> tuple[bool, str]:
    if not HOME_ASSISTANT_TOKEN or HOME_ASSISTANT_TOKEN == "PASTE_YOUR_LONG_LIVED_TOKEN_HERE":
        return False, "Home Assistant token is not configured."

    if not YANDEX_ENTITY_ID or not YANDEX_ENTITY_ID.startswith("media_player."):
        return False, "YANDEX_ENTITY_ID is not configured correctly."

    try:
        data = ha_get("/api/")
        message = data.get("message", "Home Assistant is online.")
        return True, str(message)
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Home Assistant. Check HOME_ASSISTANT_URL."
    except requests.exceptions.HTTPError as error:
        return False, f"Home Assistant HTTP error: {error}"
    except Exception as error:
        return False, f"Home Assistant error: {error}"


def check_yandex_entity() -> tuple[bool, str]:
    if not YANDEX_ENTITY_ID or not YANDEX_ENTITY_ID.startswith("media_player."):
        return False, "YANDEX_ENTITY_ID must look like media_player.alisa_1."

    try:
        entity = ha_get(f"/api/states/{YANDEX_ENTITY_ID}")
        friendly_name = entity.get("attributes", {}).get("friendly_name", YANDEX_ENTITY_ID)
        return True, f"Found {YANDEX_ENTITY_ID}: {friendly_name}."
    except requests.exceptions.HTTPError as error:
        if getattr(error.response, "status_code", None) == 404:
            return False, f"Entity not found: {YANDEX_ENTITY_ID}."
        return False, f"Entity check HTTP error: {error}"
    except Exception as error:
        return False, f"Entity check error: {error}"


def setup_report() -> dict[str, Any]:
    token_configured = bool(HOME_ASSISTANT_TOKEN) and HOME_ASSISTANT_TOKEN != "PASTE_YOUR_LONG_LIVED_TOKEN_HERE"
    ha_ok, ha_message = check_home_assistant()
    entity_ok, entity_message = (False, "Home Assistant is not ready yet.")

    if ha_ok:
        entity_ok, entity_message = check_yandex_entity()

    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "checks": {
            "token_configured": token_configured,
            "home_assistant_online": ha_ok,
            "yandex_entity_found": entity_ok,
        },
        "messages": {
            "home_assistant": ha_message,
            "yandex_entity": entity_message,
        },
        "manual_steps_if_failed": [
            "Install/configure HACS if Yandex Station is not available in Home Assistant.",
            "Install Yandex.Station integration through HACS or manually.",
            "Add the Yandex Station integration in Home Assistant and authorize it.",
            "Copy the media_player entity_id into .env as YANDEX_ENTITY_ID.",
            "Create a Home Assistant long-lived access token and copy it into .env.",
        ],
    }


# ==========================================================
# YANDEX STATION ACTIONS
# ==========================================================

def yandex_say(text: str, language: str = "en") -> str:
    if not text:
        return text_for(language, "Нет текста для озвучивания.", "No text to say.")

    language = normalize_language(language)

    if language == "ru":
        return yandex_command(
            "Скажи это естественно по-русски: " + text,
            language="ru",
        )

    return yandex_command(
        "Say this naturally in English: " + text,
        language="en",
    )

def yandex_command(text: str, language: str = "en") -> str:
    if not text:
        return text_for(language, "Нет команды для отправки.", "No command to send.")

    language = normalize_language(language)
    final_text = language_instruction(language) + text

    ha_call_service(
        "media_player",
        "play_media",
        {
            "entity_id": YANDEX_ENTITY_ID,
            "media_content_id": final_text,
            "media_content_type": "command",
        },
    )

    return text_for(
        language,
        f"Команда отправлена Алисе на русском: {text}",
        f"Command sent to Alice in English: {text}",
    )


def yandex_volume(percent: int, language: str = "en") -> str:
    percent = max(0, min(100, percent))
    state.volume = percent

    ha_call_service(
        "media_player",
        "volume_set",
        {
            "entity_id": YANDEX_ENTITY_ID,
            "volume_level": percent / 100,
        },
    )

    return text_for(
        language,
        f"Громкость Алисы установлена на {percent}%.",
        f"Alice volume set to {percent}%.",
    )


def yandex_pause(language: str = "en") -> str:
    ha_call_service(
        "media_player",
        "media_pause",
        {
            "entity_id": YANDEX_ENTITY_ID,
        },
    )

    state.music_state = "paused"
    return text_for(language, "Пауза отправлена.", "Pause sent.")


def yandex_play(language: str = "en") -> str:
    ha_call_service(
        "media_player",
        "media_play",
        {
            "entity_id": YANDEX_ENTITY_ID,
        },
    )

    state.music_state = "playing"
    return text_for(language, "Продолжение воспроизведения отправлено.", "Play sent.")


def yandex_stop(language: str = "en") -> str:
    ha_call_service(
        "media_player",
        "media_stop",
        {
            "entity_id": YANDEX_ENTITY_ID,
        },
    )

    state.music_state = "stopped"
    return text_for(language, "Стоп отправлен.", "Stop sent.")


def yandex_next(language: str = "en") -> str:
    ha_call_service(
        "media_player",
        "media_next_track",
        {
            "entity_id": YANDEX_ENTITY_ID,
        },
    )

    return text_for(language, "Следующий трек.", "Next track.")


def yandex_previous(language: str = "en") -> str:
    ha_call_service(
        "media_player",
        "media_previous_track",
        {
            "entity_id": YANDEX_ENTITY_ID,
        },
    )

    return text_for(language, "Предыдущий трек.", "Previous track.")


# ==========================================================
# COMMAND DISPATCHER
# ==========================================================
# This function receives commands from your dashboard.
# Do not delete this function.

def dispatch(command: str, language: str = "en") -> str:
    language = normalize_language(language)
    clean = normalize(command)

    if not clean:
        return text_for(language, "Пустая команда.", "Empty command.")

    # Bridge commands
    if clean in {"help", "помощь"}:
        return text_for(
            language,
            (
                "Команды: status, help, скажи <текст>, алиса <команда>, "
                "выполни <команда>, громкость 30, пауза, продолжить, стоп, "
                "следующий, предыдущий, play lo-fi music."
            ),
            (
                "Commands: status, help, say <text>, alice <command>, "
                "command <command>, volume 30, pause, play, stop, "
                "next, previous, play lo-fi music."
            ),
        )

    if clean in {"status", "bridge status", "статус"}:
        ok, message = check_home_assistant()
        ha_state = "online" if ok else "offline"
        return text_for(
            language,
            (
                f"Bridge работает. "
                f"Uptime: {uptime_seconds()}s. "
                f"Команд: {state.command_count}. "
                f"Home Assistant: {ha_state}. "
                f"{message}"
            ),
            (
                f"Bridge online. "
                f"Uptime: {uptime_seconds()}s. "
                f"Commands: {state.command_count}. "
                f"Home Assistant: {ha_state}. "
                f"{message}"
            ),
        )

    if clean in {"hello", "hi", "привет"}:
        return text_for(language, "ALISA_OS Bridge работает.", "ALISA_OS Bridge is working.")

    # Volume commands
    if clean.startswith("volume") or clean.startswith("громкость"):
        return yandex_volume(extract_number(clean, default=30), language)

    # Say text
    if clean.startswith("скажи "):
        text = command.strip()[6:].strip()
        return yandex_say(text, language)

    if clean.startswith("say "):
        text = command.strip()[4:].strip()
        return yandex_say(text, language)

    # Send command to Yandex Alice
    if clean.startswith("алиса "):
        text = command.strip()[6:].strip()
        return yandex_command(text, language)

    if clean.startswith("выполни "):
        text = command.strip()[8:].strip()
        return yandex_command(text, language)

    if clean.startswith("command "):
        text = command.strip()[8:].strip()
        return yandex_command(text, language)

    # Playback controls
    if clean in {"пауза", "pause"}:
        return yandex_pause(language)

    if clean in {"продолжить", "play", "resume"}:
        return yandex_play(language)

    if clean in {"стоп", "stop", "stop all playback"}:
        return yandex_stop(language)

    if clean in {"следующий", "next"}:
        return yandex_next(language)

    if clean in {"предыдущий", "previous"}:
        return yandex_previous(language)

    # Dashboard quick command
    if clean in {"play lo-fi music", "play lofi music", "lo-fi", "lofi"}:
        command_text = "включи спокойную музыку" if is_ru(language) else "play calm music"
        return yandex_command(command_text, language)

    # Default behavior:
    # Any unknown text is sent to Alice as a command.
    return yandex_command(command, language)


# ==========================================================
# LAN SCAN
# ==========================================================

def ping_host(ip: str, timeout_ms: int = 250) -> bool:
    system = platform.system().lower()

    if "windows" in system:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        seconds = max(1, round(timeout_ms / 1000))
        cmd = ["ping", "-c", "1", "-W", str(seconds), ip]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def scan_host(addr: ipaddress.IPv4Address) -> str | None:
    target = str(addr)

    if not ping_host(target):
        return None

    try:
        name = socket.gethostbyaddr(target)[0]
        return f"{target} ({name})"
    except Exception:
        return target


def scan_sort_key(item: str) -> tuple[int, ...]:
    return tuple(int(part) for part in item.split(" ")[0].split("."))


def scan_lan(limit: int = 254, max_workers: int = 64) -> list[str]:
    ip = local_ip()

    try:
        network = ipaddress.ip_network(ip + "/24", strict=False)
    except ValueError:
        return [f"Local host: {ip}"]

    hosts = list(network.hosts())[:limit]
    found: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scan_host, addr) for addr in hosts]
        for future in as_completed(futures):
            label = future.result()
            if label:
                found.append(label)

    found.sort(key=scan_sort_key)

    return found or [f"No devices found. Local IP: {ip}"]


# ==========================================================
# ROUTES USED BY YOUR DASHBOARD
# ==========================================================

@app.get("/")
def index():
    return jsonify(
        app=APP_NAME,
        version=APP_VERSION,
        message="ALISA_OS Bridge is running.",
        dashboard_bridge_url=f"http://localhost:{PORT}",
        home_assistant_url=HOME_ASSISTANT_URL,
        yandex_entity_id=YANDEX_ENTITY_ID,
    )


@app.get("/status")
def status():
    ok, message = check_home_assistant()

    return jsonify(
        online=True,
        app=APP_NAME,
        version=APP_VERSION,
        uptime=uptime_seconds(),
        local_ip=local_ip(),
        command_count=state.command_count,
        last_command=state.last_command,
        volume=state.volume,
        music_state=state.music_state,
        home_assistant_online=ok,
        home_assistant_message=message,
        home_assistant_url=HOME_ASSISTANT_URL,
        yandex_entity_id=YANDEX_ENTITY_ID,
        last_error=state.last_error,
    )


@app.get("/setup-check")
def setup_check():
    return jsonify(setup_report())


@app.post("/alisa")
def alisa():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command", "")).strip()
    language = normalize_language(str(data.get("language") or data.get("lang") or "en"))

    if not command:
        return jsonify(message="No command provided."), 400

    state.command_count += 1
    state.last_command = command
    state.last_error = ""

    try:
        message = dispatch(command, language)

        print(f"[ALISA:{language}] {command} -> {message}")

        return jsonify(
            message=message,
            command=command,
            language=language,
        )

    except requests.exceptions.ConnectionError as error:
        state.last_error = str(error)

        return jsonify(
            message=(
                "Cannot connect to Home Assistant. "
                "Проверь HOME_ASSISTANT_URL и запущен ли Home Assistant."
            ),
            error=str(error),
        ), 502

    except requests.exceptions.HTTPError as error:
        state.last_error = str(error)

        return jsonify(
            message=(
                "Home Assistant HTTP error. "
                "Проверь HOME_ASSISTANT_TOKEN и YANDEX_ENTITY_ID."
            ),
            error=str(error),
        ), 502

    except Exception as error:
        state.last_error = str(error)

        return jsonify(
            message="Bridge error: " + str(error),
            error=str(error),
        ), 500


@app.get("/scan")
def scan():
    devices = scan_lan()

    return jsonify(
        message="LAN scan complete.",
        devices=devices,
    )


# Extra helper route.
# You can open this in browser:
# http://localhost:5000/entities
@app.get("/entities")
def entities():
    try:
        all_states = ha_get("/api/states")

        media_players = [
            {
                "entity_id": item.get("entity_id"),
                "name": item.get("attributes", {}).get("friendly_name"),
                "state": item.get("state"),
            }
            for item in all_states
            if str(item.get("entity_id", "")).startswith("media_player.")
        ]

        return jsonify(
            message="Media players found.",
            media_players=media_players,
        )

    except Exception as error:
        return jsonify(
            message="Could not load Home Assistant entities.",
            error=str(error),
        ), 500


# ==========================================================
# START SERVER
# ==========================================================

if __name__ == "__main__":
    print("=" * 56)
    print(f"{APP_NAME} v{APP_VERSION}")
    print(f"Bridge URL: http://localhost:{PORT}")
    print(f"Home Assistant: {HOME_ASSISTANT_URL}")
    print(f"Yandex entity: {YANDEX_ENTITY_ID}")
    print("=" * 56)
    print("Press Ctrl+C to stop.")
    print()

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
    )
