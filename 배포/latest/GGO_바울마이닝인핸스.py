# -*- coding: utf-8 -*-


# =============================================================================
# [GGO Project] 바울 마이닝 인핸스 (Baul Mining Enhance) v1.8
# =============================================================================
# 원작자의 소중한 소스코드를 기반으로 GGO Project에서 기능적인 개선을 시도한 버전입니다.
# =============================================================================

SCRIPT_ID = "GGO_MINING"
SCRIPT_NAME = "GGO_바울마이닝인핸스"
CURRENT_VERSION = "1.8"

import os, sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from GGO_update_check import notify_update_async
    notify_update_async(SCRIPT_ID, SCRIPT_NAME, CURRENT_VERSION)
except Exception:
    pass

import System
from System.Collections.Generic import List
from System import String, Environment, Byte
from System.IO import Directory, Path, File
from System.Net import WebClient
from System.Text import Encoding
from System.Threading import Thread, ThreadStart
import time
import json
import ctypes
import traceback
import re

class _SettingsEdit(Exception):
    """채집 호출 스택을 끝낸 뒤 설정 편집으로 진입한다."""
    def __init__(self, button): self.button = button

class _ScriptStop(Exception):
    """워치독에게 종료 이유를 전달하고 스크립트를 안전하게 종료하기 위한 내부 예외"""
    def __init__(self, reason): self.reason = reason


# -----------------------------------------------------------------------------
# [1] script_settings.json 기본값
# -----------------------------------------------------------------------------
#
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 운용 모드/룬북/보관함은 대시보드 [설정]에서 캐릭터별로 저장합니다.
# 기존 script_settings.json 운용값은 최초 전환 시에만 가져옵니다.

USE_MAGERY = False       # True: 마법 리콜 사용, False: 기사도 세이크리드 저니 - ★ 체력 회복 마법 종류에도 연동됨
SKIP_ON_DANGER = True    # True: 적 감지 시 현재 룬북 스킵 (기본)
MONSTER_REPORT_MODE = 1  # 1: 종료 시 요약 보고, 0: 실시간 개별 보고
ADJACENT_DANGER_RADIUS = 20  # 보고서에 표시할 인접 위험 룬의 탐지 반경 (칸 수)
BOD_COLLECT = 0          # 1: 4시간 5분마다 홈 룬북을 이용해 BOD를 수거하고 보관합니다. 0: 끄기

WATCHDOG_MAX_RESTARTS = 5   # 크래시 자동 재시작 최대 횟수
WATCHDOG_RESTART_DELAY = 20 # 재시작 전 대기 시간 (초)

MINING_SCRIPT_SETTINGS_DEFAULTS = {
    "bod_collect": BOD_COLLECT,
    "monster_report_mode": MONSTER_REPORT_MODE,
    "adjacent_danger_radius": ADJACENT_DANGER_RADIUS,
    "skip_on_danger": SKIP_ON_DANGER,
    "use_magery": USE_MAGERY,
    "watchdog_restart_delay": WATCHDOG_RESTART_DELAY,
    "watchdog_max_restarts": WATCHDOG_MAX_RESTARTS
}

MINING_SCRIPT_SETTINGS_ORDER = [
    "bod_collect",
    "monster_report_mode",
    "adjacent_danger_radius",
    "skip_on_danger",
    "use_magery",
    "watchdog_restart_delay",
    "watchdog_max_restarts"
]

MINING_SCRIPT_SETTINGS_GUIDE = """GGO_바울마이닝인핸스 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 마이닝 운용 설정입니다.
use_magery, bod_collect, skip_on_danger는 캐릭터 설정이 없을 때의 기본값입니다.
최초 적용 이후에는 대시보드의 설정창에서 변경하며 캐릭터별로 저장됩니다.
나머지 항목은 이 파일에서 값을 바꾼 뒤 마이닝 스크립트를 다시 실행하면 적용됩니다.

수정 시 주의:
- true / false 값은 반드시 소문자로 입력하세요.
- 각 줄 끝의 쉼표는 지우지 마세요.

bod_collect
  1: 4시간 5분마다 홈 룬북으로 BOD를 수거합니다.
  0: BOD 수거를 끕니다.

monster_report_mode
  1: 종료 시 위험 감지 요약 보고
  0: 위험 감지 시 실시간 개별 보고

adjacent_danger_radius
  요약 보고서에 인접 위험 룬으로 표시할 반경(칸 수)입니다. 기본값: 20

skip_on_danger
  true: 적대 대상 감지 시 현재 룬북 구역을 스킵합니다.
  false: 위험 감지 후에도 스킵하지 않습니다.

use_magery
  true: 마법 리콜/회복 사용
  false: 기사도 세이크리드 저니/회복 사용

watchdog_restart_delay
  자동 재시작 전 대기 시간(초)입니다. 기본값: 20

watchdog_max_restarts
  크래시 자동 재시작 최대 횟수입니다. 기본값: 5
"""

_GGO_CONFIG_READY = False
try:
    from GGO_user_config import get_discord_webhook, get_character_settings_path, load_script_settings, load_character_settings, save_character_settings, ensure_script_settings_guide
    _GGO_CONFIG_READY = True
except Exception:
    pass

if _GGO_CONFIG_READY:
    try:
        ensure_script_settings_guide(SCRIPT_NAME, MINING_SCRIPT_SETTINGS_GUIDE)
        _script_settings = load_script_settings(SCRIPT_NAME, MINING_SCRIPT_SETTINGS_DEFAULTS, MINING_SCRIPT_SETTINGS_ORDER)
        BOD_COLLECT = int(_script_settings.get("bod_collect", BOD_COLLECT))
        MONSTER_REPORT_MODE = int(_script_settings.get("monster_report_mode", MONSTER_REPORT_MODE))
        ADJACENT_DANGER_RADIUS = int(_script_settings.get("adjacent_danger_radius", ADJACENT_DANGER_RADIUS))
        SKIP_ON_DANGER = bool(_script_settings.get("skip_on_danger", SKIP_ON_DANGER))
        USE_MAGERY = bool(_script_settings.get("use_magery", USE_MAGERY))
        WATCHDOG_RESTART_DELAY = int(_script_settings.get("watchdog_restart_delay", WATCHDOG_RESTART_DELAY))
        WATCHDOG_MAX_RESTARTS = int(_script_settings.get("watchdog_max_restarts", WATCHDOG_MAX_RESTARTS))
    except Exception:
        pass

# 디스코드 웹훅 주소
WEBHOOK_URL = ""
try:
    if not WEBHOOK_URL:
        WEBHOOK_URL = get_discord_webhook(True)
except Exception:
    pass


# -----------------------------------------------------------------------------
# [2] 전역 변수 및 데이터 관리 (원본 유지)
# -----------------------------------------------------------------------------

APPDATA = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "Mining")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "config_{0}.json".format(Player.Name))
SAVE_DIR = LEGACY_SAVE_DIR
CONFIG_FILE = LEGACY_CONFIG_FILE

if _GGO_CONFIG_READY:
    try:
        CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
        SAVE_DIR = Path.GetDirectoryName(CONFIG_FILE)
    except Exception:
        pass

DEFAULT_CHARACTER_SETTINGS = {
    "Home": 0,
    "Container": 0,
    "BodContainer": 0,
    "Books": []
}

MODE_FIELDS = {
    "use_magery": "USE_MAGERY", "bod_collect": "BOD_COLLECT",
    "skip_on_danger": "SKIP_ON_DANGER"
}
INITIAL_MODES = dict((key, globals()[var]) for key, var in MODE_FIELDS.items())
SETTINGS_GUMP_ID = 0x889912
settings_open = False
settings_editing = False
settings_notice = ""
reset_confirm = False
settings_dirty = False
pending_settings_button = -1

Homebook = 0
Miningbook = []
OreContainer = 0
BodContainer = 0
Recall, Chivalry = 0, 1 
Warenemy, enemyrun = 0, 0
SafeMargin = 100 

Ore = [0x19B9, 0x19B8, 0x19B7, 0x19BA, 0x1779, 0x423A]
gem = [0x0F13, 0x0F25, 0x0F0F, 0x0F10, 0x0F16, 0x0F11, 0x0F26, 0x0F16, 0x0F18, 0x0F15,
       0x3192, 0x3193, 0x3194, 0x3195, 0x3196, 0x3197, 0x3198, 0x3199, 0x0F28]
ingot, shovel, toolkit = 0x1BF2, 0x0F39, 0x1EB8
DASHBOARD_GUMP_ID = 0x889911

if 'start_time' not in globals(): start_time = time.time()
if 'total_counts' not in globals(): total_counts = {'M': 0}
if 'last_inventory' not in globals(): last_inventory = {}
if 'monitor_active' not in globals(): monitor_active = False
if 'last_dashboard_time' not in globals(): last_dashboard_time = 0
if 'is_paused' not in globals(): is_paused = False

LastBodTime = 0

recorded_rune_map = {}   # 이동 성공한 룬 좌표 기록 (인접 위험 룬 분석용)
danger_encounters = []   # 위험 조우 이력 누적 (종료 보고서용)


# -----------------------------------------------------------------------------
# [3] 시스템 유틸리티 및 무결성 로직 (럼버/마이닝 통합)
# -----------------------------------------------------------------------------

def save_config():
    data = {"Home": int(Homebook), "Container": int(OreContainer), "BodContainer": int(BodContainer), "Books": [int(x) for x in Miningbook]}
    data.update(dict((key, globals()[var]) for key, var in MODE_FIELDS.items()))
    try:
        if _GGO_CONFIG_READY:
            save_character_settings(SCRIPT_NAME, Player.Name, data)
        else:
            if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
            File.WriteAllText(CONFIG_FILE, json.dumps(data, indent=4))
        Player.HeadMessage(66, "● [System] 설정 데이터가 파일에 저장되었습니다.")
        return True
    except: return False

def load_config():
    try:
        if _GGO_CONFIG_READY:
            data = load_character_settings(
                SCRIPT_NAME,
                Player.Name,
                DEFAULT_CHARACTER_SETTINGS,
                [LEGACY_CONFIG_FILE]
            )
        else:
            if not File.Exists(CONFIG_FILE): return False
            data = json.loads(File.ReadAllText(CONFIG_FILE))
        books = data.get("Books", [])
        if isinstance(books, int): books = [books]
        values = {'Homebook': int(data.get("Home", 0)),
                  'OreContainer': int(data.get("Container", 0)),
                  'BodContainer': int(data.get("BodContainer", 0)),
                  'Miningbook': [int(x) for x in books]}
        for key, var in MODE_FIELDS.items():
            value = data.get(key, INITIAL_MODES[key])
            if value not in (True, False, 0, 1): return False
            values[var] = int(value) if key == "bod_collect" else bool(value)
        globals().update(values)
        if any(key not in data for key in MODE_FIELDS): SaveSettings()
        return True
    except: return False

def trim_working_set():
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
    except:
        pass

def reset_globals():
    globals().update({
        'start_time': time.time(),
        'total_counts': {'M': 0},
        'last_inventory': {},
        'monitor_active': False,
        'last_dashboard_time': 0,
        'pending_settings_button': -1,
        'is_paused': False,
        'danger_encounters': [],
        'recorded_rune_map': {},
    })
    Journal.Clear()
    Target.Cancel()

def SendDiscord(msg):
    if not WEBHOOK_URL: return
    def task():
        try:
            wc = WebClient()
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": "🔔 " + msg}, ensure_ascii=False)
            wc.UploadString(WEBHOOK_URL, "POST", payload)
        except: pass
    try: t = Thread(ThreadStart(task)); t.Start()
    except: pass

def HandleDeath(b_serial=0, r_idx=0):
    if Player.IsGhost:
        pos = Player.Position
        book_order = Miningbook.index(b_serial) + 1 if b_serial in Miningbook else "N/A"
        item_order = r_idx - 9 if r_idx else "N/A"
        msg = "**[마이닝 사망보고]** {0} 캐릭터 사망!\n- 위치: (X:{1}, Y:{2})\n- 대상: **{3}번째 룬북의 {4}번 항목**".format(
            Player.Name, pos.X, pos.Y, book_order, item_order)
        SendDiscord(msg)
        while Player.IsGhost: Misc.Pause(1000)
        raise _ScriptStop("death")


# -----------------------------------------------------------------------------
# [4] 지능형 위험 감지 및 보고 로직
# -----------------------------------------------------------------------------

def CheckDanger():
    fil = Mobiles.Filter()
    fil.RangeMax = 12
    fil.CheckLineOfSight = True
    nearby_mobs = Mobiles.ApplyFilter(fil)
    for m in nearby_mobs:
        if m is None: continue
        if m.Serial == Player.Serial: continue
        if m.Notoriety >= 3 and m.WarMode:
            return m
    return None

def ReportDanger(enemy, book_serial, rune_idx):
    global danger_encounters
    book_order = Miningbook.index(book_serial) + 1 if book_serial in Miningbook else "N/A"
    item_order = rune_idx - 9 if rune_idx else "N/A"
    enemy_name = enemy.Name if enemy is not None else "Unknown"
    px, py = Player.Position.X, Player.Position.Y

    if MONSTER_REPORT_MODE == 1:
        danger_encounters.append({
            'book': book_order,
            'idx': item_order,
            'enemy': enemy_name,
            'x': px, 'y': py
        })
        Player.HeadMessage(33, "[시스템] 위험 지역 감지 (요약 보고서에 추가됨)")
    else:
        msg = "**[긴급 회피 보고]** {0} 캐릭터 적대 개체 감지!\n".format(Player.Name)
        msg += "- 감지된 적: **{0}**\n".format(enemy_name)
        msg += "- 위치: **{0}번 룬북 / {1}번 포인트**\n".format(book_order, item_order)
        msg += "- 조치: 은행 귀환 및 자원 적재 완료. 현재 룬북 구역 스킵 후 다음 권 이동."
        SendDiscord(msg)

def SendSummaryReport():
    if not danger_encounters: return

    msg = "**📊 [GGO 마이닝] 작업 종료 보고 (지능형 지형 분석)**\n"
    msg += "👤 보고 캐릭터: **{0}**\n".format(Player.Name)
    msg += "**🛑 위험 감지 및 인접 룬 분석 결과**\n"
    msg += "-------------------------------------------\n"

    summary = {}
    for enc in danger_encounters:
        key = (enc['book'], enc['idx'], enc['enemy'])
        if key not in summary:
            summary[key] = {'count': 0, 'x': enc['x'], 'y': enc['y']}
        summary[key]['count'] += 1

    idx = 1
    for (b_order, r_idx, e_name), data in summary.items():
        msg += "{0}. **[{1}번 룬북] {2}번 항목**\n".format(idx, b_order, r_idx)
        msg += "   - 📍 위치: ({0}, {1})\n".format(data['x'], data['y'])
        msg += "   - 👾 감지: {0} ({1}회)\n".format(e_name, data['count'])

        adjacent = []
        for (map_b, map_r), (mx, my) in recorded_rune_map.items():
            if map_b == b_order and map_r == r_idx: continue
            dist = max(abs(data['x'] - mx), abs(data['y'] - my))
            if dist <= ADJACENT_DANGER_RADIUS:
                adjacent.append("[{0}번 룬북] {1}번 (거리: {2})".format(map_b, map_r, dist))

        if adjacent:
            msg += "   - **⚠️ 인접 위험 룬 (반경 {0}칸 내):**\n".format(ADJACENT_DANGER_RADIUS)
            for adj in adjacent:
                msg += "     * {0}\n".format(adj)
        else:
            msg += "   - **⚠️ 인접 위험 룬:** 없음\n"

        msg += "\n"
        idx += 1

    msg += "-------------------------------------------\n"
    msg += "*위 구역은 반복적으로 위협이 감지되었습니다. 룬 교체를 권장합니다.*"
    SendDiscord(msg)

def GGO_RecoverHealth():
    """도주 및 귀환 후 USE_MAGERY 설정에 연동하여 체력을 회복하는 안전지대 전용 모듈"""
    if Player.IsGhost: return
    if Player.Hits >= Player.HitsMax * 0.8 and not Player.Poisoned: return

    Player.HeadMessage(55, "🏥 도주/귀환 후 체력 회복 절차 시작")

    while Player.Hits < Player.HitsMax * 0.8 or Player.Poisoned:
        ServiceUI()
        HandleDeath()

        # 1. 해독 우선
        if Player.Poisoned:
            if USE_MAGERY:
                if Player.Mana >= 6:
                    Spells.CastMagery('Cure')
                    UIWaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                else: UIPause(2000)
            else:
                if Player.Mana >= 10:
                    Spells.CastChivalry('Cleanse by Fire')
                    UIWaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                else: UIPause(2000)
            continue

        # 2. 체력 회복
        if Player.Hits < Player.HitsMax * 0.8:
            if USE_MAGERY:
                if Player.Mana >= 11:
                    Spells.CastMagery('Greater Heal')
                    UIWaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                else:
                    Player.HeadMessage(33, "마나 회복 대기 중..."); UIPause(3000)
            else:
                if Player.Mana >= 10:
                    Spells.CastChivalry('Close Wounds')
                    UIWaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                else:
                    Player.HeadMessage(33, "마나/십일조 회복 대기 중..."); UIPause(3000)

    Player.HeadMessage(66, "✅ 체력 회복 완료! 출항 준비 이상 무.")


# -----------------------------------------------------------------------------
# [5] 모니터링 및 대시보드
# -----------------------------------------------------------------------------

def UpdateStats():
    global total_counts, last_inventory
    if not monitor_active: return
    try:
        current_inv = {item.Serial: item.Amount for item in Player.Backpack.Contains if item.ItemID in Ore} if Player.Backpack else {}
        for serial, amount in current_inv.items():
            diff = amount - last_inventory.get(serial, 0)
            if diff > 0: total_counts['M'] += diff
        last_inventory = current_inv
    except:
        pass

def _ReadButton(gump_id):
    gd = Gumps.GetGumpData(gump_id)
    if gd is None or gd.buttonid < 0: return -1
    button = gd.buttonid
    # 응답 버튼은 클라이언트에서 이미 닫힌다. 추가 Close 패킷 없이
    # RE의 로컬 응답만 소비하여 다른 검프의 current 상태도 건드리지 않는다.
    gd.buttonid = -1
    gd.hasResponse = False
    return button

def _Label(gd, x, y, text, hue=1152):
    Gumps.AddLabel(gd, x, y, hue, text)

def _Button(gd, x, y, button, text, enabled=False):
    art = 5845 if enabled else 5844
    Gumps.AddButton(gd, x, y, art, art, button, 1, 0)
    _Label(gd, x + 25, y, text, 167 if enabled else 1152)

def DrawDashboard(force=False):
    global last_dashboard_time
    now = time.time()
    if not force and now - last_dashboard_time < 60: return
    last_dashboard_time = now
    elapsed = max(0, now - start_time)
    rate = int(total_counts['M'] * 3600 / elapsed) if elapsed else 0
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 300, 175, 30546)
    _Label(gd, 20, 15, "GGO 마이닝", 52)
    _Label(gd, 205, 15, "{:02d}:{:02d}".format(int(elapsed // 3600), int(elapsed % 3600 // 60)))
    _Label(gd, 20, 50, "누적 광석")
    _Label(gd, 150, 50, "{:,} 개".format(total_counts['M']))
    _Label(gd, 20, 80, "시간당 채집")
    _Label(gd, 150, 80, "{:,} 개/h".format(rate))
    _Button(gd, 20, 125, 101, "재개" if is_paused else "일시정지")
    _Button(gd, 175, 125, 100, "설정")
    Gumps.SendGump(DASHBOARD_GUMP_ID, Player.Serial, 400, 400, gd.gumpDefinition, gd.gumpStrings)

def DrawSettings():
    if not settings_open: return
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    rows = [(202, "홈 룬북", Homebook), (203, "광석 / 잉갓 보관함", OreContainer)]
    if BOD_COLLECT: rows.append((205, "BOD 보관함", BodContainer))
    height = 310 + 30 * (len(rows) + len(Miningbook))
    Gumps.AddBackground(gd, 0, 0, 430, height, 30546)
    _Label(gd, 20, 15, "GGO 마이닝 설정 v" + CURRENT_VERSION, 52)
    _Button(gd, 330, 15, 1, "닫기")
    for y, label, bid, value, text in [
        (55, "이동 / 회복", 10, USE_MAGERY, "메져리" if USE_MAGERY else "기사도"),
        (85, "BOD 자동 수거", 13, BOD_COLLECT, "켜짐" if BOD_COLLECT else "꺼짐"),
        (115, "위험 지역 스킵", 14, SKIP_ON_DANGER, "켜짐" if SKIP_ON_DANGER else "꺼짐")]:
        _Label(gd, 20, y, label)
        _Button(gd, 230, y, bid, text, bool(value))
    _Label(gd, 20, 155, "대상 지정", 52)
    y = 185
    for bid, label, serial in rows:
        _Label(gd, 20, y, label)
        _Label(gd, 180, y, "0x{:08X}".format(serial) if serial > 0 else "미지정", 99)
        _Button(gd, 325, y, bid, "변경")
        y += 30
    _Button(gd, 20, y, 210, "채집 룬북 추가 ({0}권)".format(len(Miningbook)))
    y += 30
    for idx, serial in enumerate(Miningbook):
        _Label(gd, 20, y, "{0}. 0x{1:08X}".format(idx + 1, serial))
        _Button(gd, 230, y, 1000 + idx, "변경")
        _Button(gd, 325, y, 2000 + idx, "삭제")
        y += 30
    _Button(gd, 20, y + 10, 2, "설정 완료")
    _Button(gd, 230, y + 10, 91 if reset_confirm else 90,
            "초기화 확정" if reset_confirm else "전체 초기화")
    _Label(gd, 20, y + 45, settings_notice[:26], 33 if reset_confirm else 99)
    Gumps.SendGump(SETTINGS_GUMP_ID, Player.Serial, 710, 200, gd.gumpDefinition, gd.gumpStrings)

def GGO_GumpHandler():
    global settings_open, is_paused, g_mining_quit, reset_confirm
    bid = _ReadButton(DASHBOARD_GUMP_ID)
    if bid == 0:
        g_mining_quit = True
        raise _ScriptStop("intentional")
    if bid == 100:
        DrawDashboard(force=True)
        settings_open = True
        DrawSettings()
    elif bid == 101:
        is_paused = not is_paused
        Journal.Clear()
        DrawDashboard(force=True)
    bid = _ReadButton(SETTINGS_GUMP_ID)
    if bid < 0: return -1
    if bid in (0, 1):
        settings_open = False
        reset_confirm = False
        return 1
    return bid

def PollUI():
    """대기 중에는 창만 처리하고, 재설정은 작업 경계까지 보존한다."""
    global pending_settings_button
    if pending_settings_button > 1: return
    bid = GGO_GumpHandler()
    if bid > 1: pending_settings_button = bid

def UIPause(milliseconds):
    remaining = milliseconds
    while remaining > 0:
        PollUI()
        step = min(100, remaining)
        Misc.Pause(step)
        remaining -= step
    PollUI()

def UIWaitForGump(gump_id, milliseconds):
    remaining = milliseconds
    while remaining > 0:
        PollUI()
        step = min(100, remaining)
        if Gumps.WaitForGump(gump_id, step): return True
        remaining -= step
    PollUI()
    return False

def UIWaitForTarget(milliseconds, noshow=False):
    remaining = milliseconds
    while remaining > 0:
        PollUI()
        step = min(100, remaining)
        if Target.WaitForTarget(step, noshow): return True
        remaining -= step
    PollUI()
    return False

def ServiceUI():
    global pending_settings_button
    while True:
        if pending_settings_button > 1:
            bid = pending_settings_button
            pending_settings_button = -1
        else:
            bid = GGO_GumpHandler()
        if bid > 1: raise _SettingsEdit(bid)
        if Journal.Search("!대기"):
            globals()['is_paused'] = True
            Journal.Clear()
            DrawDashboard(force=True)
        if Journal.Search("!시작"):
            globals()['is_paused'] = False
            Journal.Clear()
            DrawDashboard(force=True)
        if not is_paused: return
        HandleDeath()
        Misc.Pause(100)

def check_item_possession(serial):
    item = Items.FindBySerial(serial)
    if not item: return False
    if item.RootContainer == Player.Serial: return True
    return bool(Player.Backpack and item.RootContainer == Player.Backpack.Serial)

def MissingSettings():
    missing = []
    for label, serial in [("홈 룬북", Homebook), ("광석 / 잉갓 보관함", OreContainer)]:
        if serial <= 0: missing.append(label)
    if BOD_COLLECT and BodContainer <= 0: missing.append("BOD 보관함")
    if not Miningbook or any(b <= 0 for b in Miningbook): missing.append("채집 룬북")
    return missing

def WaitForEquipment():
    # 재접속 직후 캐시 미스는 유실/초기화로 취급하지 않는다.
    while not all(check_item_possession(v) for v in [Homebook] + Miningbook):
        ServiceUI()
        HandleDeath()
        DrawDashboard()
        Misc.Pause(250)

def SaveSettings():
    global settings_dirty, settings_notice
    settings_dirty = not save_config()
    settings_notice = "저장 실패: 설정 완료를 눌러 재시도" if settings_dirty else "저장 완료"
    return not settings_dirty

def ResetSettings():
    global Homebook, OreContainer, BodContainer, Miningbook, reset_confirm
    Homebook = OreContainer = BodContainer = 0
    Miningbook = []
    for key, var in MODE_FIELDS.items():
        globals()[var] = MINING_SCRIPT_SETTINGS_DEFAULTS[key]
    reset_confirm = False
    SaveSettings()

def SettingsSession(first_button=-1):
    global settings_editing, settings_open, settings_notice, reset_confirm, Miningbook
    settings_editing = True
    settings_open = True
    Target.Cancel()
    job = None
    pending = first_button
    fields = {202: 'Homebook', 203: 'OreContainer', 205: 'BodContainer'}
    modes = {10: 'USE_MAGERY', 13: 'BOD_COLLECT', 14: 'SKIP_ON_DANGER'}
    requires_done = bool(MissingSettings()) or first_button not in modes
    DrawSettings()
    try:
        while True:
            HandleDeath()
            bid = pending
            pending = -1
            if bid < 0: bid = GGO_GumpHandler()
            if job is not None:
                if bid >= 0:
                    job['cancel'] = True
                    job['next'] = bid
                # PromptTarget 시작 전에 Cancel하면 RE 대기 루프가 남으므로,
                # 커서가 실제로 나타난 뒤 취소한다.
                if job['cancel'] and Target.HasTarget(): Target.Cancel()
                if not job['thread'].IsAlive:
                    if not job['cancel'] and job['value'] > 0:
                        serial = job['value']
                        action = job['button']
                        item = Items.FindBySerial(serial)
                        if not item:
                            settings_notice = "아이템을 선택하세요. 기존 지정 유지"
                        elif action in (202, 210) or 1000 <= action < 2000:
                            if not check_item_possession(serial):
                                settings_notice = "가방/장비에 있는 아이템을 선택하세요"
                            elif item.ItemID != 0x22C5:
                                settings_notice = "일반 룬북을 선택하세요"
                            else:
                                if action in fields: globals()[fields[action]] = serial
                                elif action == 210:
                                    if serial not in Miningbook: Miningbook.append(serial)
                                elif serial not in Miningbook or Miningbook[action - 1000] == serial:
                                    Miningbook[action - 1000] = serial
                                SaveSettings()
                        elif action in (203, 205) and not item.IsContainer:
                            settings_notice = "컨테이너를 선택하세요. 기존 지정 유지"
                        else:
                            globals()[fields[action]] = serial
                            SaveSettings()
                    else:
                        settings_notice = "선택 취소: 기존 지정 유지"
                    pending = job['next']
                    job = None
                    DrawSettings()
                Misc.Pause(100)
                continue
            if bid in (1, 2):
                missing = MissingSettings()
                if not missing and (not settings_dirty or SaveSettings()): return
                settings_open = True
                if missing: settings_notice = "필수 지정: " + ", ".join(missing)
            elif bid in modes:
                var = modes[bid]
                globals()[var] = int(not globals()[var]) if bid == 13 else not globals()[var]
                SaveSettings()
                # 단순 토글은 별도 완료 클릭 없이 실행으로 복귀한다.
                if not requires_done and not MissingSettings() and not settings_dirty:
                    DrawSettings()
                    return
            elif bid == 90:
                requires_done = True
                reset_confirm = True
                settings_notice = "전체 초기화하려면 초기화 확정을 누르세요"
            elif bid == 91 and reset_confirm:
                ResetSettings()
            elif 2000 <= bid < 2000 + len(Miningbook):
                requires_done = True
                del Miningbook[bid - 2000]
                SaveSettings()
            elif bid in fields or bid == 210 or 1000 <= bid < 1000 + len(Miningbook):
                requires_done = True
                Target.Cancel()
                job = {'value': -1, 'cancel': False, 'next': -1, 'button': bid}
                def pick(result=job):
                    try: result['value'] = Target.PromptTarget("대상 선택 (ESC: 취소)")
                    except: result['value'] = -1
                thread = Thread(ThreadStart(pick))
                thread.IsBackground = True
                job['thread'] = thread
                thread.Start()
                settings_notice = "대상을 선택하세요 (ESC: 기존 지정 유지)"
            if bid >= 0: DrawSettings()
            DrawDashboard()
            Misc.Pause(100)
    finally:
        # 종료/예외 시 PromptTarget 전용 스레드를 남기지 않는다.
        if job is not None:
            if Target.HasTarget(): Target.Cancel()
            if job['thread'].IsAlive:
                job['thread'].Interrupt()
                job['thread'].Join(1000)
        settings_editing = False

def SmartSetup():
    SettingsSession()

# -----------------------------------------------------------------------------
# [신규] BOD 자동 수거 모듈 (메시지 최적화)
# -----------------------------------------------------------------------------

def TravelBook(book, rune_index, bod=False):
    ServiceUI()
    start_x, start_y = Player.Position.X, Player.Position.Y
    Items.UseItem(book); UIPause(1500)
    if not UIWaitForGump(0x59, 5000): return False
    # ServUO: 50..65=Recall / 75..90=Sacred Journey (0-based rune index)
    Gumps.SendAction(0x59, (50 if USE_MAGERY else 75) + rune_index)
    if bod:
        UIPause(4000)
        return True
    wait_time = 0
    while Player.Position.X == start_x and Player.Position.Y == start_y and wait_time < 5000:
        UIPause(250)
        wait_time += 250
    return Player.Position.X != start_x or Player.Position.Y != start_y

def CollectBOD(sn):
    for x in range(10):
        ServiceUI()
        Journal.Clear()
        Target.TargetExecute(sn)
        Misc.WaitForContext(sn, 1000)
        Misc.ContextReply(sn, 1)
        UIWaitForGump(2611865322, 1500)
        Gumps.SendAction(2611865322, 1)
        
        if Journal.Search("offer may be available"):
            Journal.Clear()
            Player.HeadMessage(33, "BOD 수거 스킵 (대기 시간 미도달)")
            break
        UIPause(1000)

def ProcessBOD():
    global LastBodTime
    if BOD_COLLECT != 1 or BodContainer <= 0: return
    
    if LastBodTime == 0 or (time.time() - LastBodTime) >= 14700:
        Player.HeadMessage(66, "★ BOD 수거 사이클 시작 ★")
        SendDiscord("📦 **[BOD 수거]** {0} 캐릭터가 BOD 수거를 시작합니다.".format(Player.Name))
        
        TravelBook(Homebook, 1, bod=True)
        CollectBOD(0x0001BD87); CollectBOD(0x000000E3)
        
        TravelBook(Homebook, 2, bod=True)
        CollectBOD(0x0000023B); CollectBOD(0x0000023F); CollectBOD(0x0001BA3A)
        
        TravelBook(Homebook, 0, bod=True)
        
        loop_breaker = 0
        while loop_breaker < 30:
            ServiceUI()
            try:
                if not Player.Backpack: break
                bod_item = Items.FindByID(0x2258, -1, Player.Backpack.Serial)
                if not bod_item: break
                Items.Move(bod_item, BodContainer, -1)
                UIPause(1200)
                loop_breaker += 1
            except (_SettingsEdit, _ScriptStop):
                raise
            except:
                break
            
        LastBodTime = time.time()
        Player.HeadMessage(66, "★ BOD 수거 완료 ★")


# -----------------------------------------------------------------------------
# [7] 인벤토리 관리 및 귀환 모듈 (동적 대기 이식)
# -----------------------------------------------------------------------------

def backpackingotcheck():
    if not Player.Backpack: return
    if Items.BackpackCount(ingot, 0x0000) < 16:
        weighthome(force=True)
        Items.UseItem(OreContainer); UIPause(500)
        if Items.FindByID(ingot, -1, OreContainer):
            Player.HeadMessage(15, '삽 만들 잉갓 챙길게요')
            ingots = Items.FindByID(ingot, 0, OreContainer)
            Items.Move(ingots, Player.Backpack.Serial, 300); UIPause(1000)

def ResourceWait(milliseconds):
    # 재료 대기는 시전 중이 아니므로 재설정 요청을 즉시 작업 경계로 전달한다.
    remaining = milliseconds
    while remaining > 0:
        ServiceUI()
        step = min(100, remaining)
        UIPause(step)
        remaining -= step
    ServiceUI()

def ingotcheck():
    if not Player.Backpack: return
    while Items.BackpackCount(ingot, 0x0000) < 200:
        ServiceUI()
        Items.UseItem(OreContainer); UIPause(500)
        ingots = Items.FindByID(ingot, 0, OreContainer)
        if ingots and Items.ContainerCount(OreContainer, ingot, 0) >= 300:
            Items.Move(ingots, Player.Backpack.Serial, 250); UIPause(500)
        else:
            Player.ChatSay(15, '상자에 잉갓 좀 채워주세요. 삽을 못만들 예정...')
            ResourceWait(30000)

def oremove():
    if not Player.Backpack: return
    if Items.FindBySerial(OreContainer):
        for i in Ore:
            while Items.FindByID(i, -1, Player.Backpack.Serial):
                ServiceUI()
                ores = Items.FindByID(i, -1, Player.Backpack.Serial)
                Items.Move(ores, OreContainer, -1); UIPause(650)
        for i in gem:
            while Items.FindByID(i, -1, Player.Backpack.Serial):
                ServiceUI()
                gems = Items.FindByID(i, -1, Player.Backpack.Serial)
                Items.Move(gems, OreContainer, -1); UIPause(650)
        ingotcheck()

def weighthome(force=False): 
    Player.SetWarMode(False)
    if force or Player.Weight > (Player.MaxWeight - SafeMargin):
        Target.Cancel(); UIPause(500)
        
        ServiceUI()
        ProcessBOD() 
        
        StartX, StartY = Player.Position.X, Player.Position.Y

        if USE_MAGERY:
            Spells.CastMagery('Recall'); UIWaitForTarget(4500)
        else:
            Spells.CastChivalry('Sacred Journey'); UIWaitForTarget(4500)
        if Target.HasTarget(): Target.TargetExecute(Homebook)
        
        # [v1.4] 귀환 동적 대기
        wait_time = 0
        while Player.Position.X == StartX and Player.Position.Y == StartY and wait_time < 5000:
            UIPause(250)
            wait_time += 250
            
        Misc.Resync()
        
        if Player.Position.X == StartX and Player.Position.Y == StartY:
            box_item = Items.FindBySerial(OreContainer)
            if box_item:
                Player.HeadMessage(55, "하차 컨테이너 발견 (이미 집이거나 귀환 성공 간주)")
            else:
                Player.HeadMessage(33, "🚨 리콜 실패 감지! (제자리 하차 차단)")
                return
                
        # 안전지대에서 체력 완벽 회복
        GGO_RecoverHealth()

        oremove()
        trim_working_set()

def _craft_reply(layout, strings, names, category=False):
    """현재 제작 검프에서 이름과 같은 행의 제작 버튼을 찾는다."""
    cliloc_names = {1044046: 'Tools', 1023898: 'shovel', 1044164: 'tinker tools'}
    normalize = lambda value: re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', '', value)).strip().lower()
    wanted = set(normalize(name) for name in names)
    page, buttons, labels = 0, [], []
    for raw in re.findall(r'\{([^{}]*)\}', layout):
        fields = raw.split()
        if not fields: continue
        try:
            kind = fields[0]
            if kind == 'page':
                page = int(fields[1])
            elif kind == 'button' and int(fields[5]) == 1 and int(fields[7]) > 0:
                buttons.append((page, int(fields[1]), int(fields[2]), int(fields[7])))
            elif kind in ('text', 'croppedtext', 'htmlgump'):
                index = int(fields[4] if kind == 'text' else fields[6] if kind == 'croppedtext' else fields[5])
                labels.append((page, int(fields[1]), int(fields[2]), str(strings[index])))
            elif kind.startswith('xmfhtml'):
                number = int(fields[8] if kind == 'xmfhtmltok' else fields[5])
                labels.append((page, int(fields[1]), int(fields[2]), cliloc_names.get(number, '')))
        except (ValueError, IndexError):
            continue
    matches = []
    for label_page, x, y, text in labels:
        if normalize(text) not in wanted: continue
        if category and x >= 200: continue
        if not category and not 200 <= x <= 450: continue
        row = [reply for button_page, bx, by, reply in buttons
               if button_page in (0, label_page) and abs(by - y) <= 4 and 0 < x - bx <= 60]
        if len(row) == 1: matches.append(row[0])
    return matches[0] if len(matches) == 1 else None

def _send_named_craft(names, category=False):
    gump_id = 0x38920abd
    data = Gumps.GetGumpData(gump_id)
    if data is None: return False
    strings = [str(value) for value in data.stringList] if data.stringList is not None else []
    reply = _craft_reply(str(Gumps.GetGumpRawLayout(gump_id)), strings, names, category)
    if reply is None:
        Player.HeadMessage(33, '제작 검프에서 {0} 항목을 찾지 못했습니다.'.format(names[-1]))
        return False
    Gumps.SendAction(gump_id, reply)
    return True

def shovelcheck():
    if not Player.Backpack: return
    while Items.BackpackCount(shovel, 0x0000) < 2:
        ServiceUI()
        try:
            toolkits = Items.FindByID(toolkit, -1, Player.Backpack.Serial)
        except SystemError:
            return
        if not toolkits: return
        Items.UseItem(toolkits); UIPause(500)
        UIWaitForGump(0x38920abd, 2500); _send_named_craft(('Tools', '도구'), True)
        UIWaitForGump(0x38920abd, 2500); _send_named_craft(('shovel', '삽')); UIPause(2000); Gumps.CloseGump(0x38920abd)

def toolkitcreate():
    if not Player.Backpack: return
    while Items.BackpackCount(toolkit, 0x0000) < 3:
        ServiceUI()
        toolkits = Items.FindByID(toolkit, -1, Player.Backpack.Serial)
        if toolkits != None:
            Items.UseItem(toolkits); UIPause(500)
            UIWaitForGump(0x38920abd, 2500); _send_named_craft(('Tools', '도구'), True)
            UIWaitForGump(0x38920abd, 2500); _send_named_craft(('tinker tools', "tinker's tools", '팅커 도구'))
            UIPause(1500); Gumps.CloseGump(0x38920abd)
        else:
            ResourceWait(500)  # 도구가 공급될 때까지 대기하며 설정 입력 처리


# -----------------------------------------------------------------------------
# [8] 채집 루프 (하이브리드 이벤트 주도형 엔진 이식)
# -----------------------------------------------------------------------------

def Miningore():
    global is_paused
    if not Player.Backpack: return None
    Gumps.SendAction(0x59, 0)

    # [Point 1] 첫 번째 타겟팅 (제자리 광맥 매크로)
    chop_attempts = 0
    while chop_attempts < 50:
        chop_attempts += 1
        HandleDeath()

        ServiceUI()

        enemy = CheckDanger()
        if enemy: return enemy 
        
        shovelcheck()
        _bp = Player.Backpack
        if not _bp: break
        try:
            shovel1 = Items.FindByID(shovel, -1, _bp.Serial)
        except SystemError:
            UIPause(500)
            continue
        if not shovel1: break

        Target.Cancel()
        Journal.Clear() # 잔상 클리어
        Target.TargetResource(shovel1, 0)
        
        start_time = time.time()
        action_done = False
        ore_depleted = False
        spam_count = 0
        
        # 초정밀 저널 감시 루프
        while time.time() - start_time < 3.0:
            # [Track 1] 즉각 스킵 판정
            if Journal.Search('no metal here') or Journal.Search('blocked') or \
               Journal.Search('cannot see') or Journal.Search('not be seen') or Journal.Search('line of sight') or \
               Journal.Search('too far away') or Journal.Search('can\'t mine there') or Journal.Search('cannot mine so close') or \
               Journal.Search('시야에') or Journal.Search('보이지') or Journal.Search('멉니다') or \
               Journal.Search('캘 광석이') or Journal.Search('광석이 없습니다') or Journal.Search('캘 수'):
                ore_depleted = True
                action_done = True
                break
                
            # [Track 2] 모든 광물/보석/특수자원 완벽 대응 판정
            if Journal.Search('dig some') or Journal.Search('extract') or Journal.Search('workable stone') or \
               Journal.Search('sand') or Journal.Search('saltpeter') or Journal.Search('blackrock') or \
               Journal.Search('put some') or Journal.Search('loosen some') or Journal.Search('fail to find') or \
               Journal.Search('캤습니다') or Journal.Search('캐지 못했습니다') or Journal.Search('가방에 넣') or \
               Journal.Search('조심스럽게') or Journal.Search('추출') or Journal.Search('쓸만한 돌') or \
               Journal.Search('모래') or Journal.Search('초석') or Journal.Search('블랙락'):
                spam_count = 0
                action_done = True
                break
                
            # [Track 3] 5회 방어벽
            if Journal.Search('What do you want to use this item on') or Journal.Search('어디에 사용할까요'):
                spam_count += 1
                Target.Cancel()
                if spam_count >= 5:
                    Player.HeadMessage(33, "!! 5회 오류 감지: 강제 스킵 !!")
                    ore_depleted = True
                action_done = True
                break
                
            UIPause(10)
            
        if not action_done:
            if Target.HasTarget():
                Target.Cancel()
                spam_count += 1
                if spam_count >= 5:
                    Player.HeadMessage(33, "서버 무응답: 커서 강제 캔슬 및 스킵")
                    ore_depleted = True

        UpdateStats(); ServiceUI(); DrawDashboard()
        if Player.Weight > (Player.MaxWeight - SafeMargin): return None
        if ore_depleted: break
        
    # [Point 2] 두 번째 타겟팅 (한 칸 앞 상대 좌표 광맥)
    chop_attempts = 0
    while chop_attempts < 50:
        chop_attempts += 1
        HandleDeath() 
        
        ServiceUI()

        enemy = CheckDanger()
        if enemy: return enemy
        
        _bp = Player.Backpack
        if not _bp: break
        shovel1 = Items.FindByID(shovel, -1, _bp.Serial)
        if not shovel1: break

        Target.Cancel()
        Items.UseItem(shovel1)
        UIWaitForTarget(1500)
        Journal.Clear() # 잔상 클리어
        Target.TargetExecuteRelative(Player.Serial, 1)
        
        start_time = time.time()
        action_done = False
        ore_depleted = False
        spam_count = 0
        
        # 초정밀 저널 감시 루프
        while time.time() - start_time < 3.0:
            # [Track 1] 즉각 스킵 판정
            if Journal.Search('no metal here') or Journal.Search('blocked') or \
               Journal.Search('cannot see') or Journal.Search('not be seen') or Journal.Search('line of sight') or \
               Journal.Search('too far away') or Journal.Search('can\'t mine there') or Journal.Search('cannot mine so close') or \
               Journal.Search('시야에') or Journal.Search('보이지') or Journal.Search('멉니다') or \
               Journal.Search('캘 광석이') or Journal.Search('광석이 없습니다') or Journal.Search('캘 수'):
                ore_depleted = True
                action_done = True
                break
                
            # [Track 2] 모든 광물/보석/특수자원 완벽 대응 판정
            if Journal.Search('dig some') or Journal.Search('extract') or Journal.Search('workable stone') or \
               Journal.Search('sand') or Journal.Search('saltpeter') or Journal.Search('blackrock') or \
               Journal.Search('put some') or Journal.Search('loosen some') or Journal.Search('fail to find') or \
               Journal.Search('캤습니다') or Journal.Search('캐지 못했습니다') or Journal.Search('가방에 넣') or \
               Journal.Search('조심스럽게') or Journal.Search('추출') or Journal.Search('쓸만한 돌') or \
               Journal.Search('모래') or Journal.Search('초석') or Journal.Search('블랙락'):
                spam_count = 0
                action_done = True
                break
                
            # [Track 3] 5회 방어벽
            if Journal.Search('What do you want to use this item on') or Journal.Search('어디에 사용할까요'):
                spam_count += 1
                Target.Cancel()
                if spam_count >= 5:
                    Player.HeadMessage(33, "!! 5회 오류 감지: 강제 스킵 !!")
                    ore_depleted = True
                action_done = True
                break
                
            UIPause(10)
            
        if not action_done:
            if Target.HasTarget():
                Target.Cancel()
                spam_count += 1
                if spam_count >= 5:
                    Player.HeadMessage(33, "서버 무응답: 커서 강제 캔슬 및 스킵")
                    ore_depleted = True

        UpdateStats(); ServiceUI(); DrawDashboard()
        if Player.Weight > (Player.MaxWeight - SafeMargin): return None
        if ore_depleted: break
        
    return None

def Initialize_Routine():
    global monitor_active, start_time, last_inventory
    weighthome(force=True); backpackingotcheck()
    if not monitor_active: start_time = time.time()
    monitor_active = True
    if Player.Backpack: last_inventory = {item.Serial: item.Amount for item in Player.Backpack.Contains if item.ItemID in Ore}
    ServiceUI()
    DrawDashboard(force=True)


# =========================================================
# [9] 메인 실행부 (동적 대기 이식)
# =========================================================
def RunHarvest():
    while True:
        HandleDeath()
        ServiceUI()

        for i in Miningbook:
            for s in range(10, 26):
                HandleDeath(i, s); UpdateStats(); ServiceUI(); DrawDashboard()

                StartX, StartY = Player.Position.X, Player.Position.Y
                Journal.Clear()

                if not TravelBook(i, s - 10):
                    Player.HeadMessage(33, "룬북 이동 실패: 다음 지점으로 이동합니다")
                    continue

                if Journal.Search('blocked') or Journal.Search('location is blocked'):
                    Journal.Clear()
                    Player.HeadMessage(33, "🚨 자리 막힘 감지! 다음 포인트로 스킵")
                    continue

                # 성공적으로 이동한 룬의 좌표 기록 (인접 위험 룬 분석용)
                b_order_for_map = Miningbook.index(i) + 1 if i in Miningbook else "N/A"
                recorded_rune_map[(b_order_for_map, s - 9)] = (Player.Position.X, Player.Position.Y)

                Gumps.SendAction(0x59, 0)

                ServiceUI()
                toolkitcreate()

                danger_mob = Miningore()

                if danger_mob and SKIP_ON_DANGER:
                    Player.HeadMessage(33, "!!! 위협 감지: {0} !!!".format(danger_mob.Name))
                    ReportDanger(danger_mob, i, s)
                    weighthome(force=True)
                    break

                weighthome()
        UIPause(500)

def RunMining():
    global settings_open, settings_notice
    config_ok = load_config()
    DrawDashboard(force=True)
    if not config_ok:
        settings_notice = "설정을 읽지 못했습니다. 재지정해 주세요"
    action = -1
    announced = False
    needs_setup = not config_ok or bool(MissingSettings()) or settings_dirty
    while True:
        try:
            if needs_setup or action > 1:
                SettingsSession(action)
                needs_setup = False
                action = -1
            WaitForEquipment()
            ServiceUI()
            Initialize_Routine()
            if not announced:
                SendDiscord("🚀 {0} 채집 시작".format(Player.Name))
                announced = True
            RunHarvest()
            return
        except _SettingsEdit as request:
            action = request.button
            Target.Cancel()

g_mining_quit = False  # 우클릭 닫기 → 스크립트 종료 플래그
_restart_count = 0
while _restart_count <= WATCHDOG_MAX_RESTARTS:

    if _restart_count > 0:
        SendDiscord("✅ **[자동 복구]** {0} 마이닝 스크립트가 자동 복구되어 재시작되었습니다. ({1}/{2}회)".format(
            Player.Name, _restart_count, WATCHDOG_MAX_RESTARTS))

    try:
        Gumps.CloseGump(DASHBOARD_GUMP_ID)
        Gumps.CloseGump(SETTINGS_GUMP_ID)
        RunMining()
        break

    except _ScriptStop as e:
        label = {"death": "사망 감지", "intentional": "수동 종료"}.get(e.reason, e.reason)
        try: Player.HeadMessage(55, "스크립트 종료: {0}".format(label))
        except: pass
        try: SendSummaryReport()
        except: pass
        break

    except Exception as e:
        error_msg = str(e)
        if "Thread was being aborted" in error_msg or "스레드가 중단되었습니다" in error_msg:
            try: Player.HeadMessage(55, "스크립트가 수동으로 종료되었습니다.")
            except: pass
            break

        try:
            tb_text = traceback.format_exc()
            discord_msg = (
                "🚨 **[긴급 오류 보고]** {0} 캐릭터의 마이닝 스크립트가 비정상 종료되었습니다.\n"
                "- 에러 내용: {1}\n"
                "- 발생 위치:\n```\n{2}\n```"
            ).format(Player.Name, error_msg, tb_text[-1500:])
            SendSummaryReport()
            SendDiscord(discord_msg)
        except: pass
        try: Player.HeadMessage(33, "스크립트 치명적 오류 발생! 디스코드로 알림을 전송했습니다.")
        except: pass
        try: Misc.Pause(2000)
        except: pass

    finally:
        Gumps.CloseGump(DASHBOARD_GUMP_ID)
        Gumps.CloseGump(SETTINGS_GUMP_ID)

    if _restart_count >= WATCHDOG_MAX_RESTARTS:
        try: Player.HeadMessage(33, "[워치독] 재시작 한도({0}회) 초과. 스크립트를 종료합니다.".format(WATCHDOG_MAX_RESTARTS))
        except: pass
        try: SendDiscord("⛔ **[복구 실패]** {0} 재시작 한도({1}회) 초과. 스크립트를 종료합니다.".format(
            Player.Name, WATCHDOG_MAX_RESTARTS))
        except: pass
        break

    try: reset_globals()
    except: pass
    try: Misc.Pause(WATCHDOG_RESTART_DELAY * 1000)
    except: pass
    _restart_count += 1
