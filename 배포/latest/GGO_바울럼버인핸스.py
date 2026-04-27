# -*- coding: utf-8 -*-


# =============================================================================
# [GGO Project] 바울 럼버 인핸스 (Baul Lumber Enhance) v1.8
# =============================================================================
#
# 원작자의 소중한 소스코드를 기반으로 GGO Project에서 기능적인 개선을 완료한 버전입니다.
# =============================================================================

SCRIPT_ID = "GGO_LUMBER"
SCRIPT_NAME = "GGO_바울럼버인핸스"
CURRENT_VERSION = "1.8"

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


# -----------------------------------------------------------------------------
# [1] script_settings.json 기본값
# -----------------------------------------------------------------------------
#
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 사용자 설정은 스크립트 파일이 아니라
# GGO_Settings/GGO_바울럼버인핸스/script_settings.json에서 수정하세요.

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
        globals()['myaxe'] = int(load_data.get("Axe", 0))
        globals()['Homebook'] = int(load_data.get("Home", 0))
        globals()['Treecontainer'] = int(load_data.get("Container", 0))
        globals()['WoodStorage'] = int(load_data.get("WoodStorage", 0))
        globals()['BodContainer'] = int(load_data.get("BodContainer", 0))
        globals()['Treebook'] = [int(x) for x in load_data.get("Trees", [])]
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
        
        before_amount = logs.Amount
        before_serial = logs.Serial

        Items.UseItem(myaxe)
        Target.WaitForTarget(1500, False)
        if Target.HasTarget():
            Target.TargetExecute(logs)
            Misc.Pause(800)
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
    if not SPELL_CHANNELING:
        Player.UnEquipItemByLayer("LeftHand"); Misc.Pause(600)
        Player.UnEquipItemByLayer("RightHand"); Misc.Pause(600)

    while Player.Hits < Player.HitsMax * 0.8 or Player.Poisoned:
        HandleDeath()
        
        # 1. 해독 우선
        if Player.Poisoned:
            if USE_MAGERY: # 마제리 Cure
                if Player.Mana >= 6:
                    Spells.CastMagery('Cure')
                    Target.WaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(1200)
                else: Misc.Pause(2000)
            else: # 기사도 Cleanse by Fire
                if Player.Mana >= 10:
                    Spells.CastChivalry('Cleanse by Fire')
                    Target.WaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(1200)
                else: Misc.Pause(2000)
            continue
            
        # 2. 체력 회복
        if Player.Hits < Player.HitsMax * 0.8:
            if USE_MAGERY: # 마제리 Greater Heal
                if Player.Mana >= 11:
                    Spells.CastMagery('Greater Heal')
                    Target.WaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(1200)
                else:
                    Player.HeadMessage(33, "마나 회복 대기 중..."); Misc.Pause(3000)
            else: # 기사도 Close Wounds
                if Player.Mana >= 10:
                    Spells.CastChivalry('Close Wounds')
                    Target.WaitForTarget(2000, False)
                    if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(1200)
                else:
                    Player.HeadMessage(33, "마나/십일조 회복 대기 중..."); Misc.Pause(3000)
                    
    # 도끼 재장착
    if not SPELL_CHANNELING:
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

def GGO_GumpHandler():
    gd = Gumps.GetGumpData(DASHBOARD_GUMP_ID)
    if gd and gd.buttonid == 100:
        Gumps.SendAction(DASHBOARD_GUMP_ID, 0); Gumps.CloseGump(DASHBOARD_GUMP_ID)
        weighthome(force=True)
        if File.Exists(CONFIG_FILE): File.Delete(CONFIG_FILE)
        globals()['myaxe'] = globals()['Homebook'] = globals()['Treecontainer'] = globals()['WoodStorage'] = globals()['BodContainer'] = 0; globals()['Treebook'] = []
        SmartSetup()
        Initialize_Routine()
        return True
    return False

def DrawDashboard(force=False):
    global last_dashboard_time
    GGO_GumpHandler()
    if not monitor_active: return
    now = time.time()
    
    if not force and (now - last_dashboard_time < 60):
        return
    last_dashboard_time = now
    
    elapsed = now - start_time
    l_ph = int(total_counts['L'] / (elapsed / 3600.0)) if elapsed > 0 else 0
    
    title_text = "⏸️ 일시 정지 (!시작)" if is_paused else "GGO BAUL ENHANCE"
    color_code = 33 if is_paused else 1152
    
    layout = ("{ resizepic 0 0 30546 260 140 }{ checkertrans 10 10 240 120 }"
              "{ text 25 15 " + str(color_code) + " 0 }{ text 180 15 1152 1 }"
              "{ text 25 35 1152 2 }{ text 25 55 1271 3 }{ text 130 55 1271 4 }"
              "{ button 25 100 4005 4006 1 0 100 }{ text 60 102 1152 5 }"
              "{ text 190 102 1152 6 }")
              
    texts = List[String]()
    texts.Add(title_text)
    texts.Add("{:02d}:{:02d}".format(int(elapsed // 3600), int((elapsed % 3600) // 60)))
    texts.Add("-" * 35)
    texts.Add("Lumber (Board):")
    texts.Add("{:,} ({:,.0f}/h)".format(total_counts['L'], l_ph))
    texts.Add("RESET ALL (Setup)")
    texts.Add("v" + CURRENT_VERSION)
    Gumps.SendGump(DASHBOARD_GUMP_ID, Player.Serial, 400, 400, layout, texts)


# -----------------------------------------------------------------------------
# [6] 스마트 셋업 및 아이템 검증
# -----------------------------------------------------------------------------

def check_item_possession(serial):
    item = SafeFindBySerial(serial)
    if not item: return False
    if item.RootContainer == Player.Serial: return True
    if Player.Backpack and item.RootContainer == Player.Backpack.Serial: return True
    return False

def SmartSetup():
    global myaxe, Homebook, Treecontainer, WoodStorage, Treebook, BodContainer
    changed = False
    
    setup_list = [{'var': 'myaxe', 'label': '[도끼]', 'curr': myaxe}, {'var': 'Homebook', 'label': '[홈 & BOD수거용 룬북]', 'curr': Homebook}]
        
    for c in setup_list:
        if not check_item_possession(c['curr']):
            Player.HeadMessage(33, "!!! 유실 감지: {0}을(를) 다시 선택하세요 !!!".format(c['label']))
            t = Target.PromptTarget("{0} 선택 (ESC: 종료)".format(c['label']))
            if t > 0:
                globals()[c['var']] = t
                changed = True
                Player.HeadMessage(66, "{0} 지정 완료".format(c['label']))
            else:
                Player.HeadMessage(33, "설정이 취소되어 스크립트를 중지합니다.")
                raise _ScriptStop("intentional")
    
    if USE_WOOD_STORAGE:
        if WoodStorage == 0 or not SafeFindBySerial(WoodStorage):
            Player.HeadMessage(33, "!!! 필수 설정: [우드 스토리지]를 선택하세요 !!!")
            t = Target.PromptTarget("우드 스토리지 선택 (ESC: 취소)")
            if t > 0:
                WoodStorage = t
                changed = True
                Player.HeadMessage(66, "[우드 스토리지] 지정 완료")

    if Treecontainer == 0 or not SafeFindBySerial(Treecontainer):
        box_name = "[잔여물(앰버) 보관함]" if USE_WOOD_STORAGE else "[일반 나무 보관함]"
        Player.HeadMessage(33, "!!! 필수 설정: {0}을(를) 선택하세요 !!!".format(box_name))
        t = Target.PromptTarget("{0} 선택 (ESC: 취소)".format(box_name))
        if t > 0:
            Treecontainer = t
            changed = True
            Player.HeadMessage(66, "{0} 지정 완료".format(box_name))
            
    if BOD_COLLECT == 1:
        if BodContainer == 0 or not SafeFindBySerial(BodContainer):
            Player.HeadMessage(33, "!!! 필수 설정: [BOD 보관 컨테이너]를 선택하세요 !!!")
            t = Target.PromptTarget("[BOD 보관 컨테이너] 지정 (ESC: 취소)")
            if t > 0:
                BodContainer = t
                changed = True
                Player.HeadMessage(66, "[BOD 보관 컨테이너] 지정 완료")
    
    if not Treebook:
        Player.HeadMessage(33, "!!! 필수 설정: [채집 룬북]을 추가하세요 !!!")
        while True:
            t = Target.PromptTarget("채집 룬북 추가 (ESC: 완료 및 취소)")
            if t <= 0: break
            if t not in Treebook: 
                Treebook.append(t)
                changed = True
                Player.HeadMessage(66, "[채집 룬북] {0}권째 추가 완료".format(len(Treebook)))
    else:
        new_books = []
        for b in Treebook:
            if not check_item_possession(b):
                Player.HeadMessage(33, "!!! 유실 감지: 룬북을 다시 지정하세요 !!!")
                t = Target.PromptTarget("유실 룬북 재지정 (ESC: 삭제)")
                if t > 0:
                    new_books.append(t)
                    changed = True
                    Player.HeadMessage(66, "[채집 룬북] 재지정 완료")
            else: new_books.append(b)
        Treebook = new_books
        
    if changed: save_json_logic()

# -----------------------------------------------------------------------------
# [신규] BOD 자동 수거 모듈
# -----------------------------------------------------------------------------
def CollectBOD(sn):
    for x in range(10): 
        Journal.Clear()
        Target.TargetExecute(sn)
        Misc.WaitForContext(sn, 1000)
        Misc.ContextReply(sn, 1)
        Gumps.WaitForGump(2611865322, 1500)
        Gumps.SendAction(2611865322, 1)
        
        if Journal.Search("offer may be available"):
            Journal.Clear()
            Player.HeadMessage(33, "BOD 수거 스킵 (대기 시간 미도달)")
            break
        Misc.Pause(1000) 

def ProcessBOD():
    global LastBodTime
    if not BOD_COLLECT or BodContainer <= 0: return
    
    if LastBodTime == 0 or (time.time() - LastBodTime) >= BOD_CYCLE_INTERVAL:
        Player.HeadMessage(66, "★ BOD 수거 사이클 시작 ★")
        SendDiscord("📦 **[BOD 수거]** {0} 캐릭터가 BOD 수거를 시작합니다.".format(Player.Name))
        
        Items.UseItem(Homebook); Misc.Pause(1500)
        Gumps.WaitForGump(89, 2000); Gumps.SendAction(89, 11); Misc.Pause(4000)
        CollectBOD(0x0001BD87); CollectBOD(0x000000E3)
        
        Items.UseItem(Homebook); Misc.Pause(1500)
        Gumps.WaitForGump(89, 2000); Gumps.SendAction(89, 12); Misc.Pause(4000)
        CollectBOD(0x0000023B); CollectBOD(0x0000023F); CollectBOD(0x0001BA3A)
        
        Items.UseItem(Homebook); Misc.Pause(1500)
        Gumps.WaitForGump(89, 2000); Gumps.SendAction(89, 10); Misc.Pause(4000)
        
        loop_breaker = 0
        while SafeFindByID(0x2258, -1, Player.Backpack.Serial) and loop_breaker < 30:
            bod_item = SafeFindByID(0x2258, -1, Player.Backpack.Serial)
            if bod_item:
                SafeMove(bod_item, BodContainer, -1)
                Misc.Pause(1200)
            loop_breaker += 1
            
        LastBodTime = time.time()
        Player.HeadMessage(66, "★ BOD 수거 완료 ★")

# -----------------------------------------------------------------------------
# [7] 귀환 및 채집 로직
# -----------------------------------------------------------------------------

def weighthome(force=False):
    Player.SetWarMode(False)
    if force or Player.Weight > Player.MaxWeight * weightpercent:
        Target.Cancel(); Misc.Pause(500)
        
        while True:
            ProcessBOD()
            
            StartX, StartY = Player.Position.X, Player.Position.Y
            
            if USE_MAGERY:
                if not SPELL_CHANNELING:
                    Player.UnEquipItemByLayer("LeftHand") 
                    Misc.Pause(600)
                Spells.CastMagery('Recall')
                Target.WaitForTarget(4500); Target.TargetExecute(Homebook) 
                if not SPELL_CHANNELING:
                    Misc.Pause(1200); Player.EquipItem(myaxe) 
            else:
                Spells.CastChivalry('Sacred Journey')
                Target.WaitForTarget(4500); Target.TargetExecute(Homebook) 
                
            # 리콜 동적 대기 (최대 5초)
            wait_time = 0
            while Player.Position.X == StartX and Player.Position.Y == StartY and wait_time < 5000:
                Misc.Pause(250)
                wait_time += 250
            
            box_item = Items.FindBySerial(Treecontainer)
            if box_item is not None and box_item.Position is not None and abs(Player.Position.X - box_item.Position.X) <= 3 and abs(Player.Position.Y - box_item.Position.Y) <= 3:
                Player.HeadMessage(55, "하차 컨테이너 발견 (귀환 성공)")
                break 
            else:
                if Journal.Search('blocked') or Journal.Search('location is blocked'):
                    Journal.Clear()
                    Player.HeadMessage(33, "🚨 집 자리 막힘 감지! 3초 대기 후 재시도...")
                    Misc.Pause(3000)
                    continue
                    
                Player.HeadMessage(33, "🚨 리콜 실패 또는 보관함 인식 불가! 재시도...")
                Misc.Pause(2000)
                continue
                
        Player.ChatSay(55, 'bank'); Misc.Pause(700)
        
        # 렉 갇힘 방지 모듈
        if not (USE_WOOD_STORAGE and WoodStorage > 0):
            ProcessLogsSafely()
            
        if USE_WOOD_STORAGE and WoodStorage > 0:
            Items.UseItem(WoodStorage)
            Gumps.WaitForGump(0x06ABCE12, 2000)
            Gumps.SendAction(0x06ABCE12, 25) 
            Misc.Pause(1000)
            Gumps.CloseGump(0x06ABCE12) 
        
        for Treeid in [0x1BD7, 0x318F, 0x2F5F, 0x5738, 0x3190, 0x3199, 0x3191]:
            for item in SafeGetBackpackContains():
                if item.ItemID == Treeid:
                    SafeMove(item, Treecontainer, -1)
                    Misc.Pause(1000)
                    
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
                        HandleDeath()
                        
                        if Journal.Search("!대기"):
                            is_paused = True
                            DrawDashboard(force=True)
                            Player.HeadMessage(33, "스크립트 일시 정지 (재개: !시작)")

                        while is_paused:
                            if Journal.Search("!시작"):
                                is_paused = False
                                DrawDashboard(force=True)
                                Player.HeadMessage(66, "스크립트 작업 재개!")
                                break
                            Misc.Pause(500)
                            HandleDeath()
                        
                        enemy = CheckDanger()
                        if enemy: return enemy 
                        
                        if Player.Weight > Player.MaxWeight * 0.8:
                            ProcessLogsSafely()
                        
                        Target.Cancel()
                        Items.UseItem(myaxe)
                        Target.WaitForTarget(1500)
                        
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
                            
                            Misc.Pause(10) 
                            
                        # [1-Strike Out] 타임아웃 방어 
                        if not action_done:
                            if Target.HasTarget():
                                Target.Cancel()
                            Player.HeadMessage(33, "서버 무응답: 1회 타임아웃 강제 스킵")
                            tree_depleted = True
                        
                        UpdateStats(); DrawDashboard()
                        
                        if Player.Weight > Player.MaxWeight * weightpercent: break
    return None

def Initialize_Routine():
    global monitor_active, start_time, last_inventory
    weighthome(force=True); monitor_active = True; start_time = time.time()
    
    last_inventory = {}
    if Player.Backpack:
        for item in SafeGetBackpackContains():
            try:
                if item and item.ItemID in TargetIDs:
                    last_inventory[item.Serial] = item.Amount
            except:
                pass
                
    DrawDashboard(force=True)


# -----------------------------------------------------------------------------
# [8] 메인 실행 루프
# -----------------------------------------------------------------------------

_restart_count = 0
while _restart_count <= WATCHDOG_MAX_RESTARTS:

    if _restart_count > 0:
        SendDiscord("✅ **[자동 복구]** {0} 럼버 스크립트가 자동 복구되어 재시작되었습니다. ({1}/{2}회)".format(
            Player.Name, _restart_count, WATCHDOG_MAX_RESTARTS))

    try:
        Gumps.SendAction(DASHBOARD_GUMP_ID, 0); Gumps.CloseGump(DASHBOARD_GUMP_ID)

        while True:
            config_ok = load_json_logic()
            missing = []
            if config_ok:
                if not check_item_possession(myaxe): missing.append("도끼")
                if not check_item_possession(Homebook): missing.append("홈 룬북")
                if USE_WOOD_STORAGE and WoodStorage <= 0: missing.append("우드 스토리지")
                if BOD_COLLECT == 1 and BodContainer <= 0: missing.append("BOD 보관 컨테이너")
                if not Treebook: missing.append("룬북 리스트")
                else:
                    for b in Treebook:
                        if not check_item_possession(b): missing.append("채집 룬북")
                if Treecontainer <= 0: missing.append("보관함")

            if not config_ok or missing:
                SmartSetup(); Misc.Pause(1000)
            else:
                Player.HeadMessage(66, "★ 모든 아이템 무결성 검사 통과 ★")
                break

        Initialize_Routine()
        SendDiscord("🚀 {0} 채집 시작".format(Player.Name))

        while True:
            HandleDeath()
            if GGO_GumpHandler(): continue

            if Journal.Search("!대기"):
                is_paused = True
                DrawDashboard(force=True)
                Player.HeadMessage(33, "스크립트 일시 정지 (재개: !시작)")

            while is_paused:
                if Journal.Search("!시작"):
                    is_paused = False
                    DrawDashboard(force=True)
                    Player.HeadMessage(66, "스크립트 작업 재개!")
                    break
                Misc.Pause(500)
                HandleDeath()

            for b_serial in Treebook:
                globals()['cur_b_serial'] = b_serial
                if not Items.FindBySerial(b_serial): continue

                for r_idx in range(10, 26):
                    globals()['cur_r_idx'] = r_idx
                    HandleDeath(b_serial, r_idx)
                    UpdateStats(); DrawDashboard()

                    StartX, StartY = Player.Position.X, Player.Position.Y

                    Journal.Clear()

                    Items.UseItem(b_serial); Misc.Pause(1500)
                    Gumps.WaitForGump(0x59, 5000); Gumps.SendAction(0x59, r_idx)

                    wait_time = 0
                    while Player.Position.X == StartX and Player.Position.Y == StartY and wait_time < 5000:
                        Misc.Pause(250)
                        wait_time += 250

                    if Player.Position.X == StartX and Player.Position.Y == StartY:
                        Player.HeadMessage(33, "🚨 룬북 이동 실패! (타임아웃) 다음 포인트로 스킵")
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

            Misc.Pause(500)

        break  # 정상 종료

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
