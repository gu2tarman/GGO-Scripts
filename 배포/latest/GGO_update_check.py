# -*- coding: utf-8 -*-
# =============================================================================
# GGO Update Check - 새 버전 알림 전용 모듈
# =============================================================================
# 역할: 새 버전이 있을 때 채팅창에 안내 메시지만 출력한다.
# 파일 다운로드/교체는 하지 않는다 (그 역할은 GGO_업데이트매니저가 담당).
#
# 사용법:
#   try:
#       from GGO_update_check import notify_update_async
#       notify_update_async(SCRIPT_ID, SCRIPT_NAME, CURRENT_VERSION)
#   except:
#       pass
# =============================================================================

from System.Net import WebClient
from System.Text import Encoding
from System.Threading import Thread, ThreadStart
import json
import time

SCRIPT_ID = "GGO_UPDATE_CHECK"
SCRIPT_NAME = "GGO_update_check"
CURRENT_VERSION = "1.0"

MANIFEST_URL = (
    "https://raw.githubusercontent.com/gu2tarman/GGO-Scripts"
    "/main/%EB%B0%B0%ED%8F%AC/GGO_update_manifest.json"
)
NOTICE_HUE = 33


def _cache_busted_url(url):
    sep = "&" if "?" in url else "?"
    return url + sep + "t=" + str(int(time.time()))


def _version_tuple(v):
    parts = []
    for part in str(v).split("."):
        try:
            parts.append(int(part))
        except Exception:
            parts.append(0)
    return tuple(parts)


def _check_and_notify(script_id, script_name, current_version):
    try:
        wc = WebClient()
        wc.Encoding = Encoding.UTF8
        raw = wc.DownloadString(_cache_busted_url(MANIFEST_URL))
        data = json.loads(raw)
        for entry in data.get("scripts", []):
            if entry.get("id") == script_id:
                remote = entry.get("version", "0.0")
                if _version_tuple(remote) > _version_tuple(current_version):
                    Misc.SendMessage(
                        "[{0}] 새 버전이 있습니다. 현재 v{1} / 최신 v{2}".format(
                            script_name, current_version, remote),
                        NOTICE_HUE)
                    Misc.SendMessage(
                        "업데이트하려면 GGO_업데이트매니저를 실행하세요.", NOTICE_HUE)
                    try:
                        Player.HeadMessage(
                            NOTICE_HUE,
                            "새 버전 v{0} 있음 - 업데이터 실행".format(remote))
                    except Exception:
                        pass
                break
    except Exception:
        pass


def notify_update_async(script_id, script_name, current_version):
    """백그라운드에서 새 버전 여부를 확인하고 있으면 채팅창에 안내한다."""
    _id = script_id
    _name = script_name
    _ver = current_version

    def _run():
        _check_and_notify(_id, _name, _ver)

    t = Thread(ThreadStart(_run))
    t.IsBackground = True
    t.Start()
