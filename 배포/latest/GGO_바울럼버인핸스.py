# -*- coding: utf-8 -*-


# =============================================================================
# [GGO Project] 바울 럼버 인핸스 (Baul Lumber Enhance) v1.9
# =============================================================================
#
# 원작자의 소중한 소스코드를 기반으로 GGO Project에서 기능적인 개선을 완료한 버전입니다.
# =============================================================================

SCRIPT_ID = "GGO_LUMBER"
SCRIPT_NAME = "GGO_바울럼버인핸스"
CURRENT_VERSION = "1.9"

import os
import sys

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
import traceback
import ctypes

class _ScriptStop(Exception):
    """워치독에게 종료 이유를 전달하고 스크립트를 안전하게 종료하기 위한 내부 예외"""
    def __init__(self, reason): self.reason = reason

class _SettingsEdit(Exception):
    """채집 호출 스택을 끝낸 뒤 설정 편집으로 진입한다."""
    def __init__(self, button): self.button = button


# -----------------------------------------------------------------------------
# [1] script_settings.json 기본값
# -----------------------------------------------------------------------------
#
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 일상 운용 옵션/대상은 대시보드의 [설정]에서 캐릭터별로 저장합니다.
# script_settings.json의 운용 옵션은 기존 캐릭터 설정 최초 전환 시에만 사용합니다.

WATCHDOG_MAX_RESTARTS = 5    # 크래시 자동 재시작 최대 횟수
WATCHDOG_RESTART_DELAY = 20  # 재시작 전 대기 시간 (초)

USE_MAGERY = False           # True: 마법 리콜 사용, False: 기사도 세이크리드 저니 (기본) - ★ 체력 회복 마법 종류에도 연동됨
SPELL_CHANNELING = True      # True: 주문전달 도끼 사용 (기본), False: 도끼 탈착 후 캐스팅 (힐링 시에도 연동)
SKIP_ON_DANGER = True        # True: 적 감지 시 현재 룬북 스킵 (기본)
MONSTER_REPORT_MODE = 1  # 1: 종료 시 요약 보고, 0: 실시간 개별 보고
ADJACENT_DANGER_RADIUS = 20 # [v1.6.4 신규] 보고서에 표시할 인접 위험 룬의 탐지 반경 (칸 수)

# [v1.2 신규 설정] 우드 스토리지 사용 여부
USE_WOOD_STORAGE = False     # True: 우드 스토리지 쾌속 수납 사용, False: 기존 드래그 상자 사용

# [v1.3 신규 설정] BOD 자동 수거
BOD_COLLECT = 0          # 1: 4시간 5분마다 홈 룬북을 이용해 BOD 수거하고 보관합니다. 0: 끄기

LUMBER_SCRIPT_SETTINGS_DEFAULTS = {
    "use_wood_storage": USE_WOOD_STORAGE,
    "bod_collect": BOD_COLLECT,
    "monster_report_mode": MONSTER_REPORT_MODE,
    "adjacent_danger_radius": ADJACENT_DANGER_RADIUS,
    "skip_on_danger": SKIP_ON_DANGER,
    "spell_channeling": SPELL_CHANNELING,
    "use_magery": USE_MAGERY,
    "watchdog_restart_delay": WATCHDOG_RESTART_DELAY,
    "watchdog_max_restarts": WATCHDOG_MAX_RESTARTS
}

LUMBER_SCRIPT_SETTINGS_ORDER = [
    "use_wood_storage",
    "bod_collect",
    "monster_report_mode",
    "adjacent_danger_radius",
    "skip_on_danger",
    "spell_channeling",
    "use_magery",
    "watchdog_restart_delay",
    "watchdog_max_restarts"
]

LUMBER_SCRIPT_SETTINGS_GUIDE = """GGO_바울럼버인핸스 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 럼버 운용 설정입니다.
값을 바꾼 뒤 럼버 스크립트를 다시 실행하면 적용됩니다.

use_wood_storage / bod_collect / spell_channeling / use_magery / skip_on_danger는
최초 전환 시 기본값입니다. 이후에는 대시보드 [설정]의 캐릭터별 값을 사용합니다.
워치독 및 보고 옵션은 계속 이 파일에서 조절합니다.

수정 시 주의:
- true / false 값은 반드시 소문자로 입력하세요.
- 각 줄 끝의 쉼표는 지우지 마세요.

use_wood_storage
  true: 우드 스토리지에 쾌속 수납합니다.
  false: 일반 나무 보관함으로 드래그 수납합니다.

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

spell_channeling
  true: 주문전달 도끼를 사용한다고 보고 도끼를 벗지 않습니다.
  false: 회복/캐스팅 전 도끼를 탈착합니다.

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
        ensure_script_settings_guide(SCRIPT_NAME, LUMBER_SCRIPT_SETTINGS_GUIDE)
        _script_settings = load_script_settings(SCRIPT_NAME, LUMBER_SCRIPT_SETTINGS_DEFAULTS, LUMBER_SCRIPT_SETTINGS_ORDER)
        WATCHDOG_MAX_RESTARTS = int(_script_settings.get("watchdog_max_restarts", WATCHDOG_MAX_RESTARTS))
        WATCHDOG_RESTART_DELAY = int(_script_settings.get("watchdog_restart_delay", WATCHDOG_RESTART_DELAY))
        USE_MAGERY = bool(_script_settings.get("use_magery", USE_MAGERY))
        SPELL_CHANNELING = bool(_script_settings.get("spell_channeling", SPELL_CHANNELING))
        SKIP_ON_DANGER = bool(_script_settings.get("skip_on_danger", SKIP_ON_DANGER))
        MONSTER_REPORT_MODE = int(_script_settings.get("monster_report_mode", MONSTER_REPORT_MODE))
        ADJACENT_DANGER_RADIUS = int(_script_settings.get("adjacent_danger_radius", ADJACENT_DANGER_RADIUS))
        USE_WOOD_STORAGE = bool(_script_settings.get("use_wood_storage", USE_WOOD_STORAGE))
        BOD_COLLECT = int(_script_settings.get("bod_collect", BOD_COLLECT))
    except Exception:
        pass

# 디스코드 웹훅 주소 (디스코드 알림이 필요하다면 웹훅 주소를 입력하세요)
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
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "Lumberjack")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "Lumber_{0}.json".format(Player.Name))
OLD_LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "Lumber")
OLD_LEGACY_CONFIG_FILE = Path.Combine(OLD_LEGACY_SAVE_DIR, "Lumber_{0}.json".format(Player.Name))
SAVE_DIR = LEGACY_SAVE_DIR
CONFIG_FILE = LEGACY_CONFIG_FILE

if _GGO_CONFIG_READY:
    try:
        CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
        SAVE_DIR = Path.GetDirectoryName(CONFIG_FILE)
    except Exception:
        pass

DEFAULT_CHARACTER_SETTINGS = {
    "Axe": 0,
    "Home": 0,
    "Container": 0,
    "WoodStorage": 0,
    "BodContainer": 0,
    "Trees": []
}

# 최초 1회는 기존 script_settings 값을 사용하고, 이후에는 캐릭터별로 저장한다.
MODE_FIELDS = {
    "use_magery": "USE_MAGERY", "spell_channeling": "SPELL_CHANNELING",
    "use_wood_storage": "USE_WOOD_STORAGE", "bod_collect": "BOD_COLLECT",
    "skip_on_danger": "SKIP_ON_DANGER"
}
INITIAL_MODES = dict((key, globals()[var]) for key, var in MODE_FIELDS.items())
SETTINGS_GUMP_ID = 0x889901
settings_open = False
settings_editing = False
settings_notice = ""
reset_confirm = False
settings_dirty = False
pending_settings_button = -1

myaxe = 0
Homebook = 0
Treecontainer = 0
WoodStorage = 0
BodContainer = 0
Treebook = []

DASHBOARD_GUMP_ID = 0x889900
OreIDs = [0x19B9, 0x19B8, 0x19B7, 0x19BA, 0x1779, 0x423A]
BoardID = 0x1BD7
TargetIDs = set(OreIDs + [BoardID])
log = 0x1BDD
Tree = [0x1BD7, 0x318F, 0x2F5F, 0x5738, 0x3190, 0x3199, 0x3191]
TreeStaticID = [3221, 3222, 3225, 3227, 3228, 3229, 3210, 3238, 3240, 3242, 3243, 3267, 3268, 3272, 3273, 3274, 3275, 3276, 3277, 3280, 3283, 3286, 3288, 3290, 3293, 3296, 3299, 3302, 3320, 3323, 3326, 3329, 3365, 3367, 3381, 3383, 3384, 3394, 3395, 3417, 3440, 3461, 3476, 3478, 3480, 3482, 3484, 3486, 3488, 3490, 3492, 3496]

if 'start_time' not in globals(): start_time = time.time()
if 'total_counts' not in globals(): total_counts = {'M': 0, 'L': 0}
if 'last_inventory' not in globals(): last_inventory = {}
if 'monitor_active' not in globals(): monitor_active = False
if 'is_paused' not in globals(): is_paused = False
if 'last_dashboard_time' not in globals(): last_dashboard_time = 0

weightpercent, numberofaxetime = 0.9, 10
cur_b_serial = 0
cur_r_idx = 0
LastBodTime = 0
BOD_CYCLE_INTERVAL = 14700 # 4시간 5분 사이클

# [v1.6 신규 전역 변수]
recorded_rune_map = {}
danger_encounters = []


# -----------------------------------------------------------------------------
# [3] 시스템 유틸리티 및 무결성 로직
# -----------------------------------------------------------------------------

def save_json_logic():
    global myaxe, Homebook, Treecontainer, WoodStorage, Treebook, BodContainer
    save_data = {"Axe": int(myaxe), "Home": int(Homebook), "Container": int(Treecontainer), "WoodStorage": int(WoodStorage), "BodContainer": int(BodContainer), "Trees": [int(x) for x in Treebook]}
    save_data.update(dict((key, globals()[var]) for key, var in MODE_FIELDS.items()))
    try:
        if _GGO_CONFIG_READY:
            save_character_settings(SCRIPT_NAME, Player.Name, save_data)
        else:
            if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
            serialized = json.dumps(save_data, indent=4)
            File.WriteAllText(CONFIG_FILE, serialized)
        Player.HeadMessage(66, "● [System] 설정 데이터가 파일에 저장되었습니다.")
        return True
    except: return False

def load_json_logic():
    try:
        if _GGO_CONFIG_READY:
            load_data = load_character_settings(
                SCRIPT_NAME,
                Player.Name,
                DEFAULT_CHARACTER_SETTINGS,
                [LEGACY_CONFIG_FILE, OLD_LEGACY_CONFIG_FILE]
            )
        else:
            if not File.Exists(CONFIG_FILE): return False
            content = File.ReadAllText(CONFIG_FILE)
            load_data = json.loads(content)
        values = dict((var, int(load_data.get(key, 0))) for key, var in
                      [("Axe", "myaxe"), ("Home", "Homebook"), ("Container", "Treecontainer"),
                       ("WoodStorage", "WoodStorage"), ("BodContainer", "BodContainer")])
        values['Treebook'] = [int(x) for x in load_data.get("Trees", [])]
        for key, var in MODE_FIELDS.items():
            value = load_data.get(key, INITIAL_MODES[key])
            if value not in (True, False, 0, 1): return False
            values[var] = int(value) if key == "bod_collect" else bool(value)
        globals().update(values)
        if any(key not in load_data for key in MODE_FIELDS):
            SaveSettings()
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
        'total_counts': {'M': 0, 'L': 0},
        'last_inventory': {},
        'monitor_active': False,
        'is_paused': False,
        'last_dashboard_time': 0,
        'pending_settings_button': -1,
    })
    Journal.Clear()
    Target.Cancel()

def SendDiscord(msg):
    if not WEBHOOK_URL: return
    def task():
        try:
            wc = WebClient()
            wc.Proxy = None # [v1.6.3 신규] 네트워크 스캔 10초 딜레이 완벽 차단
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": "🔔 " + msg}, ensure_ascii=False)
            wc.UploadString(WEBHOOK_URL, "POST", payload)
        except: pass
    try:
        t = Thread(ThreadStart(task))
        t.IsBackground = True
        t.Start()
    except: pass

def HandleDeath(current_book=0, rune_idx=0):
    if Player.IsGhost:
        pos = Player.Position
        book = current_book if current_book else globals().get('cur_b_serial', 0)
        idx = rune_idx if rune_idx else globals().get('cur_r_idx', 0)
        book_order = Treebook.index(book) + 1 if book in Treebook else "N/A"
        item_order = idx - 9 if idx else "N/A"
        msg = "**[사망 보고]** {0} 캐릭터 사망!\n- 위치: (X:{1}, Y:{2})\n- 대상: **{3}번째 룬북의 {4}번 항목**".format(
            Player.Name, pos.X, pos.Y, book_order, item_order)
        SendDiscord(msg)
        raise _ScriptStop("death")


# -----------------------------------------------------------------------------
# [4] 지능형 가공, 위험 감지 및 회복 로직 (Safe Wrapper 추가)
# -----------------------------------------------------------------------------

def SafeFindByID(item_id, item_color, container_serial):
    try: return Items.FindByID(item_id, item_color, container_serial)
    except: return None

def SafeFindBySerial(serial):
    try: return Items.FindBySerial(serial)
    except: return None

def SafeGetBackpackContains():
    try: return [item for item in Player.Backpack.Contains if item is not None] if Player.Backpack else []
    except: return []

def SafeMove(item, container_serial, amount):
    try: Items.Move(item, container_serial, amount)
    except: pass

def ProcessLogsSafely():
    """서버 렉으로 인한 타겟 갇힘을 방지하는 물리적 상태 추적형 가공 모듈"""
    if not Player.Backpack: return
    strike_count = 0

    while True:
        if Player.Backpack is None: break

        logs = SafeFindByID(0x1BDD, -1, Player.Backpack.Serial)
        if not logs: break # 가공 완료

        ServiceUI()
        before_amount = logs.Amount
        before_serial = logs.Serial

        Items.UseItem(myaxe)
        UIWaitForTarget(1500, False)
        if Target.HasTarget():
            Target.TargetExecute(logs)
            UIPause(800)
        else:
            Target.Cancel()

        # 물리적 상태(Amount) 변화 교차 검증
        current_logs = SafeFindBySerial(before_serial)
        current_amount = current_logs.Amount if current_logs else 0

        if current_amount == before_amount:
            # 렉으로 인해 깎이지 않고 헛방침
            strike_count += 1
        else:
            # 정상적으로 깎임 (카운트 초기화)
            strike_count = 0

        # 3번 연속 헛방 시 렉으로 간주하고 일시 탈출 (메인 루프에서 재진입 유도)
        if strike_count >= 3:
            Player.HeadMessage(33, "🚨 가공 렉 감지! 갇힘 방지를 위해 일시 탈출")
            Target.Cancel()
            break

def GGO_RecoverHealth():
    """도주 및 귀환 후 설정(USE_MAGERY)에 연동하여 체력을 회복하는 안전지대 전용 모듈"""
    if Player.IsGhost: return
    if Player.Hits >= Player.HitsMax * 0.8 and not Player.Poisoned: return

    Player.HeadMessage(55, "🏥 도주/귀환 후 체력 회복 절차 시작")

    # 캐스팅 전 도끼 해제 (SPELL_CHANNELING 연동)
    restore_axe = not SPELL_CHANNELING
    if restore_axe:
        Player.UnEquipItemByLayer("LeftHand"); UIPause(600)
        Player.UnEquipItemByLayer("RightHand"); UIPause(600)

    try:
        while Player.Hits < Player.HitsMax * 0.8 or Player.Poisoned:
            ServiceUI()
            HandleDeath()

            # 1. 해독 우선
            if Player.Poisoned:
                if USE_MAGERY: # 마제리 Cure
                    if Player.Mana >= 6:
                        Spells.CastMagery('Cure')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                    else: UIPause(2000)
                else: # 기사도 Cleanse by Fire
                    if Player.Mana >= 10:
                        Spells.CastChivalry('Cleanse by Fire')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                    else: UIPause(2000)
                continue

            # 2. 체력 회복
            if Player.Hits < Player.HitsMax * 0.8:
                if USE_MAGERY: # 마제리 Greater Heal
                    if Player.Mana >= 11:
                        Spells.CastMagery('Greater Heal')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                    else:
                        Player.HeadMessage(33, "마나 회복 대기 중..."); UIPause(3000)
                else: # 기사도 Close Wounds
                    if Player.Mana >= 10:
                        Spells.CastChivalry('Close Wounds')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); UIPause(1200)
                    else:
                        Player.HeadMessage(33, "마나/십일조 회복 대기 중..."); UIPause(3000)

    finally:
        # 도끼 재장착
        if restore_axe:
            Misc.Pause(600)
            Player.EquipItem(myaxe)
            Misc.Pause(600)

    Player.HeadMessage(66, "✅ 체력 회복 완료! 출항 준비 이상 무.")

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
    book_order = Treebook.index(book_serial) + 1 if book_serial in Treebook else "N/A"
    item_order = rune_idx - 9 if rune_idx else "N/A"
    enemy_name = enemy.Name if enemy is not None else "Unknown"
    px, py = Player.Position.X, Player.Position.Y

    if MONSTER_REPORT_MODE == 1:
        # 요약 모드: 리스트에 누적 저장
        danger_encounters.append({
            'book': book_order,
            'idx': item_order,
            'enemy': enemy_name,
            'x': px, 'y': py
        })
        Player.HeadMessage(33, "[시스템] 위험 지역 감지 (요약 보고서에 추가됨)")
    else:
        # 실시간 모드
        msg = "**[긴급 회피 보고]** {0} 캐릭터 적대 개체 감지!\n".format(Player.Name)
        msg += "- 감지된 적: **{0}**\n".format(enemy_name)
        msg += "- 위치: **{0}번 룬북 / {1}번 포인트**\n".format(book_order, item_order)
        msg += "- 조치: 은행 귀환 및 자원 적재 완료. 현재 룬북 구역 스킵 후 다음 권 이동."
        SendDiscord(msg)

def SendSummaryReport():
    if not danger_encounters: return

    msg = "**📊 [GGO 럼버] 작업 종료 보고 (지능형 지형 분석)**\n"
    msg += "👤 보고 캐릭터: **{0}**\n".format(Player.Name)
    msg += "**🛑 위험 감지 및 인접 룬 분석 결과**\n"
    msg += "-------------------------------------------\n"

    # 조우 기록 요약 (같은 장소/같은 몹 카운트 병합)
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

        # 인접 룬 찾기
        adjacent = []
        for (map_b, map_r), (mx, my) in recorded_rune_map.items():
            if map_b == b_order and map_r == r_idx: continue # 자기 자신 제외
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

# -----------------------------------------------------------------------------
# [5] 모니터링 및 대시보드
# -----------------------------------------------------------------------------

def UpdateStats():
    global total_counts, last_inventory
    if not monitor_active: return

    current_inv = {}
    if Player.Backpack:
        for item in SafeGetBackpackContains():
            try:
                if item and item.ItemID in TargetIDs:
                    current_inv[item.Serial] = item.Amount
            except:
                pass

    for serial, amount in current_inv.items():
        diff = amount - last_inventory.get(serial, 0)
        if diff > 0:
            item = SafeFindBySerial(serial)
            if item:
                if item.ItemID in OreIDs: total_counts['M'] += diff
                elif item.ItemID == BoardID: total_counts['L'] += diff
    last_inventory = current_inv

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
    rate = int(total_counts['L'] * 3600 / elapsed) if elapsed else 0
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 300, 175, 30546)
    _Label(gd, 20, 15, "GGO 럼버", 52)
    _Label(gd, 205, 15, "{:02d}:{:02d}".format(int(elapsed // 3600), int(elapsed % 3600 // 60)))
    _Label(gd, 20, 50, "누적 판자")
    _Label(gd, 150, 50, "{:,} 개".format(total_counts['L']))
    _Label(gd, 20, 80, "시간당 채집")
    _Label(gd, 150, 80, "{:,} 개/h".format(rate))
    _Button(gd, 20, 125, 101, "재개" if is_paused else "일시정지")
    _Button(gd, 175, 125, 100, "설정")
    Gumps.SendGump(DASHBOARD_GUMP_ID, Player.Serial, 400, 400, gd.gumpDefinition, gd.gumpStrings)

def DrawSettings():
    if not settings_open: return
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    rows = [(201, "도끼", myaxe), (202, "홈 룬북", Homebook),
            (203, "잔여물 보관함" if USE_WOOD_STORAGE else "나무 보관함", Treecontainer)]
    if USE_WOOD_STORAGE: rows.append((204, "우드스토리지", WoodStorage))
    if BOD_COLLECT: rows.append((205, "BOD 보관함", BodContainer))
    height = 370 + 30 * (len(rows) + len(Treebook))
    Gumps.AddBackground(gd, 0, 0, 430, height, 30546)
    _Label(gd, 20, 15, "GGO 럼버 설정 v" + CURRENT_VERSION, 52)
    _Button(gd, 330, 15, 1, "닫기")
    for y, label, bid, value, text in [
        (55, "이동 / 회복", 10, USE_MAGERY, "메져리" if USE_MAGERY else "기사도"),
        (85, "자원 보관", 11, USE_WOOD_STORAGE, "우드스토리지" if USE_WOOD_STORAGE else "일반 보관함"),
        (115, "주문전달 도끼", 12, SPELL_CHANNELING, "켜짐" if SPELL_CHANNELING else "꺼짐"),
        (145, "BOD 자동 수거", 13, BOD_COLLECT, "켜짐" if BOD_COLLECT else "꺼짐"),
        (175, "위험 지역 스킵", 14, SKIP_ON_DANGER, "켜짐" if SKIP_ON_DANGER else "꺼짐")]:
        _Label(gd, 20, y, label)
        _Button(gd, 230, y, bid, text, bool(value))
    _Label(gd, 20, 215, "대상 지정", 52)
    y = 245
    for bid, label, serial in rows:
        _Label(gd, 20, y, label)
        _Label(gd, 180, y, "0x{:08X}".format(serial) if serial > 0 else "미지정", 99)
        _Button(gd, 325, y, bid, "변경")
        y += 30
    _Button(gd, 20, y, 210, "채집 룬북 추가 ({0}권)".format(len(Treebook)))
    y += 30
    for idx, serial in enumerate(Treebook):
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
    global settings_open, is_paused, g_lumber_quit, reset_confirm
    bid = _ReadButton(DASHBOARD_GUMP_ID)
    if bid == 0:
        g_lumber_quit = True
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
    item = SafeFindBySerial(serial)
    if not item: return False
    if item.RootContainer == Player.Serial: return True
    return bool(Player.Backpack and item.RootContainer == Player.Backpack.Serial)

def MissingSettings():
    missing = []
    for label, serial in [("도끼", myaxe), ("홈 룬북", Homebook), ("보관함", Treecontainer)]:
        if serial <= 0: missing.append(label)
    if USE_WOOD_STORAGE and WoodStorage <= 0: missing.append("우드스토리지")
    if BOD_COLLECT and BodContainer <= 0: missing.append("BOD 보관함")
    if not Treebook or any(b <= 0 for b in Treebook): missing.append("채집 룬북")
    return missing

def WaitForEquipment():
    # 재접속 직후 캐시 미스는 유실/초기화로 취급하지 않는다.
    while not all(check_item_possession(v) for v in [myaxe, Homebook] + Treebook):
        ServiceUI()
        HandleDeath()
        DrawDashboard()
        Misc.Pause(250)

def SaveSettings():
    global settings_dirty, settings_notice
    settings_dirty = not save_json_logic()
    settings_notice = "저장 실패: 설정 완료를 눌러 재시도" if settings_dirty else "저장 완료"
    return not settings_dirty

def ResetSettings():
    global myaxe, Homebook, Treecontainer, WoodStorage, BodContainer, Treebook, reset_confirm
    myaxe = Homebook = Treecontainer = WoodStorage = BodContainer = 0
    Treebook = []
    for key, var in MODE_FIELDS.items():
        globals()[var] = LUMBER_SCRIPT_SETTINGS_DEFAULTS[key]
    reset_confirm = False
    SaveSettings()  # 삭제하지 않는다: AppData의 옛 설정 재유입 방지

def SettingsSession(first_button=-1):
    global settings_editing, settings_open, settings_notice, reset_confirm, Treebook
    settings_editing = True
    settings_open = True
    Target.Cancel()
    job = None
    pending = first_button
    fields = {201: 'myaxe', 202: 'Homebook', 203: 'Treecontainer',
              204: 'WoodStorage', 205: 'BodContainer'}
    modes = {10: 'USE_MAGERY', 11: 'USE_WOOD_STORAGE', 12: 'SPELL_CHANNELING',
             13: 'BOD_COLLECT', 14: 'SKIP_ON_DANGER'}
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
                        item = SafeFindBySerial(serial)
                        if not item:
                            settings_notice = "아이템을 선택하세요. 기존 지정 유지"
                        elif action in (201, 202, 210) or 1000 <= action < 2000:
                            if not check_item_possession(serial):
                                settings_notice = "가방/장비에 있는 아이템을 선택하세요"
                            elif action != 201 and item.ItemID != 0x22C5:
                                settings_notice = "일반 룬북을 선택하세요"
                            else:
                                if action in fields: globals()[fields[action]] = serial
                                elif action == 210:
                                    if serial not in Treebook: Treebook.append(serial)
                                elif serial not in Treebook or Treebook[action - 1000] == serial:
                                    Treebook[action - 1000] = serial
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
            elif 2000 <= bid < 2000 + len(Treebook):
                requires_done = True
                del Treebook[bid - 2000]
                SaveSettings()
            elif bid in fields or bid == 210 or 1000 <= bid < 1000 + len(Treebook):
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

def UnequipForTravel():
    if not SPELL_CHANNELING:
        Player.UnEquipItemByLayer("LeftHand"); Misc.Pause(600)
        Player.UnEquipItemByLayer("RightHand"); Misc.Pause(600)

def EquipAfterTravel():
    if not SPELL_CHANNELING:
        Misc.Pause(1200)
        Player.EquipItem(myaxe)

def TravelBook(book, rune_index, bod=False):
    ServiceUI()
    UnequipForTravel()
    start_x, start_y = Player.Position.X, Player.Position.Y
    try:
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
    finally:
        EquipAfterTravel()

# -----------------------------------------------------------------------------
# [신규] BOD 자동 수거 모듈
# -----------------------------------------------------------------------------
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
    if not BOD_COLLECT or BodContainer <= 0: return

    if LastBodTime == 0 or (time.time() - LastBodTime) >= BOD_CYCLE_INTERVAL:
        Player.HeadMessage(66, "★ BOD 수거 사이클 시작 ★")
        SendDiscord("📦 **[BOD 수거]** {0} 캐릭터가 BOD 수거를 시작합니다.".format(Player.Name))

        TravelBook(Homebook, 1, bod=True)
        CollectBOD(0x0001BD87); CollectBOD(0x000000E3)

        TravelBook(Homebook, 2, bod=True)
        CollectBOD(0x0000023B); CollectBOD(0x0000023F); CollectBOD(0x0001BA3A)

        TravelBook(Homebook, 0, bod=True)

        loop_breaker = 0
        while SafeFindByID(0x2258, -1, Player.Backpack.Serial) and loop_breaker < 30:
            ServiceUI()
            bod_item = SafeFindByID(0x2258, -1, Player.Backpack.Serial)
            if bod_item:
                SafeMove(bod_item, BodContainer, -1)
                UIPause(1200)
            loop_breaker += 1

        LastBodTime = time.time()
        Player.HeadMessage(66, "★ BOD 수거 완료 ★")

# -----------------------------------------------------------------------------
# [7] 귀환 및 채집 로직
# -----------------------------------------------------------------------------

def weighthome(force=False):
    Player.SetWarMode(False)
    if force or Player.Weight > Player.MaxWeight * weightpercent:
        Target.Cancel(); UIPause(500)

        while True:
            ServiceUI()
            ProcessBOD()

            StartX, StartY = Player.Position.X, Player.Position.Y

            ServiceUI()
            UnequipForTravel()
            try:
                if USE_MAGERY: Spells.CastMagery('Recall')
                else: Spells.CastChivalry('Sacred Journey')
                UIWaitForTarget(4500)
                if Target.HasTarget(): Target.TargetExecute(Homebook)
            finally:
                EquipAfterTravel()

            # 리콜 동적 대기 (최대 5초)
            wait_time = 0
            while Player.Position.X == StartX and Player.Position.Y == StartY and wait_time < 5000:
                UIPause(250)
                wait_time += 250

            box_item = Items.FindBySerial(Treecontainer)
            if box_item is not None and box_item.Position is not None and abs(Player.Position.X - box_item.Position.X) <= 3 and abs(Player.Position.Y - box_item.Position.Y) <= 3:
                Player.HeadMessage(55, "하차 컨테이너 발견 (귀환 성공)")
                break
            else:
                if Journal.Search('blocked') or Journal.Search('location is blocked'):
                    Journal.Clear()
                    Player.HeadMessage(33, "🚨 집 자리 막힘 감지! 3초 대기 후 재시도...")
                    UIPause(3000)
                    continue

                Player.HeadMessage(33, "🚨 리콜 실패 또는 보관함 인식 불가! 재시도...")
                UIPause(2000)
                continue

        Player.ChatSay(55, 'bank'); UIPause(700)

        # 렉 갇힘 방지 모듈
        if not (USE_WOOD_STORAGE and WoodStorage > 0):
            ProcessLogsSafely()

        if USE_WOOD_STORAGE and WoodStorage > 0:
            ServiceUI()
            Items.UseItem(WoodStorage)
            UIWaitForGump(0x06ABCE12, 2000)
            Gumps.SendAction(0x06ABCE12, 25)
            UIPause(1000)
            Gumps.CloseGump(0x06ABCE12)

        for Treeid in [0x1BD7, 0x318F, 0x2F5F, 0x5738, 0x3190, 0x3199, 0x3191]:
            for item in SafeGetBackpackContains():
                ServiceUI()
                if item.ItemID == Treeid:
                    SafeMove(item, Treecontainer, -1)
                    UIPause(1000)

        # 안전지대에서 체력 완벽 회복
        GGO_RecoverHealth()

def cuttrees():
    Journal.Clear()
    global is_paused
    for x in range(-2, 3):
        for y in range(-2, 3):
            px, py, pz = Player.Position.X, Player.Position.Y, Player.Map
            tileinfo = Statics.GetStaticsTileInfo(px + x, py + y, pz)
            for tile in tileinfo:
                if tile.StaticID in TreeStaticID:
                    Journal.Clear()
                    tree_depleted = False

                    while not tree_depleted:
                        ServiceUI()
                        HandleDeath()

                        enemy = CheckDanger()
                        if enemy: return enemy

                        if Player.Weight > Player.MaxWeight * 0.8:
                            ProcessLogsSafely()

                        Target.Cancel()
                        Items.UseItem(myaxe)
                        UIWaitForTarget(1500)

                        Journal.Clear()
                        Target.TargetExecute(px + x, py + y, tile.StaticZ, tile.StaticID)

                        start_time = time.time()
                        action_done = False

                        # 0.01초 이벤트 감시 루프
                        while time.time() - start_time < 3.0:
                            if Journal.Search('enough wood') or Journal.Search('blocked') or \
                               Journal.Search('use an axe on that') or \
                               Journal.Search('cannot see') or Journal.Search('not be seen') or Journal.Search('line of sight') or \
                               Journal.Search('too far away') or \
                               Journal.Search('도끼를 사용할 수 없습니다') or \
                               Journal.Search('시야에') or Journal.Search('보이지') or \
                               Journal.Search('너무 멉니다') or \
                               Journal.Search('나무가 없습니다') or Journal.Search('더 이상 나무를'):
                                tree_depleted = True
                                action_done = True
                                break

                            if Journal.Search('chop some') or Journal.Search('나무를 캤습니다') or \
                               Journal.Search('hack at the') or Journal.Search('나무를 캐지 못했습니다'):
                                action_done = True
                                break

                            UIPause(10)

                        # [1-Strike Out] 타임아웃 방어
                        if not action_done:
                            if Target.HasTarget():
                                Target.Cancel()
                            Player.HeadMessage(33, "서버 무응답: 1회 타임아웃 강제 스킵")
                            tree_depleted = True

                        UpdateStats()
                        ServiceUI()
                        DrawDashboard()

                        if Player.Weight > Player.MaxWeight * weightpercent: break
    return None

def Initialize_Routine():
    global monitor_active, start_time, last_inventory
    weighthome(force=True)
    if not monitor_active: start_time = time.time()
    monitor_active = True

    last_inventory = {}
    if Player.Backpack:
        for item in SafeGetBackpackContains():
            try:
                if item and item.ItemID in TargetIDs:
                    last_inventory[item.Serial] = item.Amount
            except:
                pass

    # 초기 귀환/정리 중 누른 버튼을 먼저 소비해야 새 검프에 덮이지 않는다.
    ServiceUI()
    DrawDashboard(force=True)


# -----------------------------------------------------------------------------
# [8] 메인 실행 루프
# -----------------------------------------------------------------------------

def RunHarvest():
    global is_paused
    while True:
        HandleDeath()
        ServiceUI()

        for b_serial in Treebook:
            globals()['cur_b_serial'] = b_serial
            if not Items.FindBySerial(b_serial): continue

            for r_idx in range(10, 26):
                globals()['cur_r_idx'] = r_idx
                HandleDeath(b_serial, r_idx)
                ServiceUI()
                UpdateStats(); DrawDashboard()

                StartX, StartY = Player.Position.X, Player.Position.Y

                Journal.Clear()

                if not TravelBook(b_serial, r_idx - 10):
                    Player.HeadMessage(33, "룬북 이동 실패: 다음 지점으로 이동합니다")
                    continue

                if Journal.Search('blocked') or Journal.Search('location is blocked'):
                    Journal.Clear()
                    Player.HeadMessage(33, "🚨 자리 막힘 감지! 다음 포인트로 스킵")
                    continue

                # [v1.6 신규] 성공적으로 이동한 룬의 좌표 기록 (거리 계산용)
                b_order_for_map = Treebook.index(b_serial) + 1 if b_serial in Treebook else "N/A"
                r_idx_for_map = r_idx - 9
                recorded_rune_map[(b_order_for_map, r_idx_for_map)] = (Player.Position.X, Player.Position.Y)

                danger_mob = cuttrees()
                trim_working_set()

                if danger_mob and SKIP_ON_DANGER:
                    Player.HeadMessage(33, "!!! 위협 감지: {0} !!!".format(danger_mob.Name))
                    ReportDanger(danger_mob, b_serial, r_idx)
                    weighthome(force=True)
                    break

                weighthome()

        UIPause(500)

def RunLumber():
    global settings_open, settings_notice
    config_ok = load_json_logic()
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

g_lumber_quit = False  # 우클릭 닫기 → 스크립트 종료 플래그
_restart_count = 0
while _restart_count <= WATCHDOG_MAX_RESTARTS:

    if _restart_count > 0:
        SendDiscord("✅ **[자동 복구]** {0} 럼버 스크립트가 자동 복구되어 재시작되었습니다. ({1}/{2}회)".format(
            Player.Name, _restart_count, WATCHDOG_MAX_RESTARTS))

    try:
        Gumps.CloseGump(DASHBOARD_GUMP_ID)
        Gumps.CloseGump(SETTINGS_GUMP_ID)
        RunLumber()
        break

    except _ScriptStop as e:
        label = {"death": "사망 감지", "intentional": "수동 종료"}.get(e.reason, e.reason)
        Player.HeadMessage(55, "스크립트 종료: {0}".format(label))
        break

    except Exception as e:
        error_msg = str(e)
        if "Thread was being aborted" in error_msg or "스레드가 중단되었습니다" in error_msg:
            try: Player.HeadMessage(55, "스크립트가 수동으로 종료되었습니다.")
            except: pass
            try: SendSummaryReport()
            except: pass
            break

        try:
            error_detail = traceback.format_exc()
            SendSummaryReport()
            clean_detail = error_detail[-1500:] if len(error_detail) > 1500 else error_detail
            SendDiscord("🚨 **[긴급 오류 추적 보고]** {0} 캐릭터 매크로 중단\n- 에러 상세 내역:\n```python\n{1}\n```".format(Player.Name, clean_detail))
        except: pass
        try: Player.HeadMessage(33, "스크립트 치명적 오류 발생! 디스코드로 상세 로그를 전송했습니다.")
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
