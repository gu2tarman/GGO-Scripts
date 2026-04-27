# -*- coding: utf-8 -*-
from System import Environment
from System.IO import Directory, File, Path
from System.Text import Encoding

import json
import os
from collections import OrderedDict


SCRIPT_ID = "GGO_USER_CONFIG"
SCRIPT_NAME = "GGO_user_config"
CURRENT_VERSION = "1.0"

SETTINGS_DIR_NAME = "GGO_Settings"
WEBHOOK_FILE = "GGO_webhook.json"
OLD_WEBHOOK_FILE = "GGO_user_settings.json"
DEFAULT_WEBHOOK_SETTINGS = {
    "discord_webhook_url": ""
}

_settings_root = None
_empty_notice_shown = False
_fallback_notice_shown = False


def _base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _copy_dict(value):
    try:
        return json.loads(json.dumps(value))
    except Exception:
        return dict(value)


def _ensure_dir(path):
    if path and not Directory.Exists(path):
        Directory.CreateDirectory(path)
    return Directory.Exists(path)


def _read_json(path, default_value=None):
    try:
        if not File.Exists(path):
            return _copy_dict(default_value) if isinstance(default_value, dict) else default_value
        raw = File.ReadAllText(path, Encoding.UTF8)
        if not raw:
            return _copy_dict(default_value) if isinstance(default_value, dict) else default_value
        return json.loads(raw)
    except Exception:
        return _copy_dict(default_value) if isinstance(default_value, dict) else default_value


def _write_json(path, value):
    folder = os.path.dirname(path)
    if folder:
        _ensure_dir(folder)
    File.WriteAllText(path, json.dumps(value, indent=4), Encoding.UTF8)


def _ordered_settings(settings, ordered_keys=None):
    if not ordered_keys:
        return settings

    ordered = OrderedDict()
    for key in ordered_keys:
        if key in settings:
            ordered[key] = settings[key]

    for key, value in settings.items():
        if key not in ordered:
            ordered[key] = value

    return ordered


def _merge_defaults(settings, defaults):
    changed = False
    if settings is None or not isinstance(settings, dict):
        settings = {}
        changed = True

    for key, value in defaults.items():
        if key not in settings:
            settings[key] = _copy_dict(value) if isinstance(value, dict) else value
            changed = True

    return settings, changed


def _desktop_dir():
    try:
        path = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)
        if path:
            return path
    except Exception:
        pass
    try:
        return os.path.join(os.path.expanduser("~"), "Desktop")
    except Exception:
        return ""


def _appdata_project_dir():
    try:
        appdata = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
        if appdata:
            return Path.Combine(appdata, "GGO_Project")
    except Exception:
        pass
    return ""


def get_settings_root(show_notice=False):
    global _settings_root, _fallback_notice_shown
    if _settings_root:
        return _settings_root

    candidates = [
        os.path.join(_base_dir(), SETTINGS_DIR_NAME),
        os.path.join(_desktop_dir(), SETTINGS_DIR_NAME),
        _appdata_project_dir()
    ]

    for index, candidate in enumerate(candidates):
        if not candidate:
            continue
        try:
            if _ensure_dir(candidate):
                _settings_root = candidate
                if show_notice and index > 0 and not _fallback_notice_shown:
                    _fallback_notice_shown = True
                    try:
                        Misc.SendMessage("[GGO] 설정 폴더: {0}".format(_settings_root), 53)
                    except Exception:
                        pass
                return _settings_root
        except Exception:
            pass

    _settings_root = _base_dir()
    return _settings_root


def get_webhook_path():
    return os.path.join(get_settings_root(), WEBHOOK_FILE)


def load_user_settings():
    path = get_webhook_path()
    settings = None

    if not File.Exists(path):
        old_path = os.path.join(_base_dir(), OLD_WEBHOOK_FILE)
        if File.Exists(old_path):
            settings = _read_json(old_path, DEFAULT_WEBHOOK_SETTINGS)

    if settings is None:
        settings = _read_json(path, DEFAULT_WEBHOOK_SETTINGS)

    settings, changed = _merge_defaults(settings, DEFAULT_WEBHOOK_SETTINGS)
    if changed or not File.Exists(path):
        _write_json(path, settings)
    return settings


def get_discord_webhook(show_notice=False):
    global _empty_notice_shown
    settings = load_user_settings()
    webhook = str(settings.get("discord_webhook_url", "") or "").strip()

    if show_notice and not webhook and not _empty_notice_shown:
        _empty_notice_shown = True
        try:
            Misc.SendMessage("[GGO] Discord webhook이 비어 있습니다.", 53)
            Misc.SendMessage("[GGO] GGO_Settings\\GGO_webhook.json 파일에 주소를 넣으세요.", 53)
        except Exception:
            pass

    return webhook


def get_script_settings_dir(script_name):
    return os.path.join(get_settings_root(), script_name)


def get_script_settings_path(script_name):
    return os.path.join(get_script_settings_dir(script_name), "script_settings.json")


def load_script_settings(script_name, defaults, ordered_keys=None):
    path = get_script_settings_path(script_name)
    settings = _read_json(path, defaults)
    settings, changed = _merge_defaults(settings, defaults)
    settings = _ordered_settings(settings, ordered_keys)
    if changed or ordered_keys or not File.Exists(path):
        _write_json(path, settings)
    return settings


def save_script_settings(script_name, settings):
    _write_json(get_script_settings_path(script_name), settings)


def ensure_script_settings_guide(script_name, text):
    path = os.path.join(get_script_settings_dir(script_name), "script_settings_설명.txt")
    should_write = True
    if File.Exists(path):
        try:
            should_write = File.ReadAllText(path, Encoding.UTF8) != text
        except Exception:
            should_write = True

    if should_write:
        folder = os.path.dirname(path)
        if folder:
            _ensure_dir(folder)
        File.WriteAllText(path, text, Encoding.UTF8)


def get_character_settings_path(script_name, character_name):
    safe_name = str(character_name or "Unknown")
    return os.path.join(get_script_settings_dir(script_name), "{0}.json".format(safe_name))


def load_character_settings(script_name, character_name, defaults, legacy_paths=None):
    path = get_character_settings_path(script_name, character_name)
    settings = None

    if not File.Exists(path) and legacy_paths:
        for legacy_path in legacy_paths:
            if legacy_path and File.Exists(legacy_path):
                settings = _read_json(legacy_path, defaults)
                break

    if settings is None:
        settings = _read_json(path, defaults)

    settings, changed = _merge_defaults(settings, defaults)
    if changed or not File.Exists(path):
        _write_json(path, settings)
    return settings


def save_character_settings(script_name, character_name, settings):
    _write_json(get_character_settings_path(script_name, character_name), settings)
