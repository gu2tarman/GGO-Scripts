# -*- coding: utf-8 -*-


# =============================================================================
# [GGO Project] 바울 럼버 인핸스 (Baul Lumber Enhance) v2.2
# =============================================================================
#
# 원작자의 소중한 소스코드를 기반으로 GGO Project에서 기능적인 개선을 완료한 버전입니다.
# =============================================================================

SCRIPT_ID = "GGO_LUMBER"
SCRIPT_NAME = "GGO_바울럼버인핸스"
CURRENT_VERSION = "2.2"

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
import re
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
MERCENARY_MODE = False       # True: 용병 동행(팔로워 3칸 이상) 시 침공 기간 외에는 적을 무시하고 채집
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
    "mercenary_mode": MERCENARY_MODE,
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
    "mercenary_mode",
    "spell_channeling",
    "use_magery",
    "watchdog_restart_delay",
    "watchdog_max_restarts"
]

LUMBER_SCRIPT_SETTINGS_GUIDE = """GGO_바울럼버인핸스 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 럼버 운용 설정입니다.
값을 바꾼 뒤 럼버 스크립트를 다시 실행하면 적용됩니다.

use_wood_storage / bod_collect / spell_channeling / use_magery / skip_on_danger / mercenary_mode는
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

mercenary_mode
  true: 용병(팔로워 3칸 이상)이 있으면 침공 기간 외에는 적을 무시하고 계속 채집합니다.
        침공 기간(매달 1일·15일 0시 ~ 다음 날 오전 9시)과 용병이 없을 때는 기존처럼 회피합니다.
  false: 기존처럼 적대 대상 감지 시 회피합니다.

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
        MERCENARY_MODE = bool(_script_settings.get("mercenary_mode", MERCENARY_MODE))
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
    "skip_on_danger": "SKIP_ON_DANGER", "mercenary_mode": "MERCENARY_MODE"
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
if 'last_dashboard_sig' not in globals(): last_dashboard_sig = None
if 'storage_counts' not in globals(): storage_counts = {}

# 마고 보관함 자동수납 로그 (서버 문구라 클라이언트 언어와 무관하게 한글):
# "[보관함] 채집한 판자 (보통) 170개, 나무껍질 조각 4개를 보관함에 넣었습니다."
STORAGE_LOG_RE = re.compile(u'^\\[보관함\\] 채집한 (.+)를 보관함에 넣었습니다')
STORAGE_ITEM_RE = re.compile(u'(.+?) ([\\d,]+)개(?:, |$)')
BOARD_NAME_RE = re.compile(u'^판자 \\((.+)\\)$')
# NPC 매입가(고정, 마고 판매 대금 로그 실측): 보통~심나무는 4골드씩 오르고 피나무 25, 서리나무 30
BOARD_GRADES = [u'보통', u'떡갈나무', u'물푸레나무', u'주목나무', u'심나무', u'피나무', u'서리나무']
BOARD_PRICES = dict(zip(BOARD_GRADES, [4, 8, 12, 16, 20, 25, 30]))
DETAIL_GUMP_ID = 0x889902
detail_open = False
storage_journal = None
storage_cursor = -1.0
storage_seen = set()

# 판자 판매 (은행: 마고 보관함 → 무게 한도만큼 인출 → NPC 판매 반복)
SELL_GUMP_ID = 0x889903
SELL_BATCH_MAX = 30000     # 1회 판매 안정 수량 (마고 실측)
BOARDS_PER_STONE = 200     # 판자 200개 = 1스톤
SELL_WEIGHT_MARGIN = 5     # 인출 후에도 남겨 둘 무게 여유 (스톤)
SELL_NPC_RANGE = 8
SELL_NPC_BID, SELL_START_BID, SELL_STOP_BID = 3010, 3030, 3031
BOARD_HUES = {u'보통': 0x0000, u'떡갈나무': 0x07DA, u'물푸레나무': 0x04A7, u'주목나무': 0x04A8,
              u'심나무': 0x04A9, u'피나무': 0x04AA, u'서리나무': 0x047F}
SALE_LOG_RE = re.compile(u'^판매 대금 ([\\d,]+) 골드가 은행에 입금되었습니다')
SellGrades = [False] * len(BOARD_GRADES)
SellKeep = [0] * len(BOARD_GRADES)
SellNpc = 0
sell_open = False
sell_running = False
sell_stop = False
sell_notice = ""
sell_results = None   # 마지막 판매 {등급: {'sold', 'gold', 'missing', 'left'}}
sell_elapsed = 0
pending_sell = 0

weightpercent, numberofaxetime = 0.9, 10
cur_b_serial = 0
cur_r_idx = 0
BOD_CYCLE_INTERVAL = 14700 # 4시간 5분 사이클
BOD_TIMER_FILE = CONFIG_FILE + ".bod_timer"
# 영문 / 한글 클라이언트의 "아직 주문 없음" 문구 (cliloc 1072058, 1049039)
BOD_WAIT_TEXTS = ("offer may be available", "새로운 거래는", "다시 주문을 받을 수")

def load_bod_time():
    """재시작 전 마지막 BOD 수거 시각을 복구한다. 없거나 비정상이면 0(즉시 수거)."""
    try:
        if not File.Exists(BOD_TIMER_FILE): return 0
        saved = float(File.ReadAllText(BOD_TIMER_FILE).strip())
        return saved if 0 < saved <= time.time() + 5 else 0
    except: return 0

def remember_bod_time():
    global LastBodTime
    LastBodTime = time.time()
    try:
        if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
        File.WriteAllText(BOD_TIMER_FILE, "{:.6f}".format(LastBodTime))
    except: pass

LastBodTime = load_bod_time()
BOD_RETRY_DELAY = 600  # BOD 상인 이동 실패 시 재시도 간격 (초)
BodRetryAt = 0

# [v1.6 신규 전역 변수]
recorded_rune_map = {}
danger_encounters = []
merc_handled = {}   # 용병 모드에서 무시한 적 {serial: 이름} (종료 보고서 한 줄 요약용)
merc_present = None # 마지막으로 확인한 용병 동행 여부 (변화 시에만 알림)
MERC_FOLLOWER_SLOTS = 3


# -----------------------------------------------------------------------------
# [3] 시스템 유틸리티 및 무결성 로직
# -----------------------------------------------------------------------------

def save_json_logic():
    global myaxe, Homebook, Treecontainer, WoodStorage, Treebook, BodContainer
    save_data = {"Axe": int(myaxe), "Home": int(Homebook), "Container": int(Treecontainer), "WoodStorage": int(WoodStorage), "BodContainer": int(BodContainer), "Trees": [int(x) for x in Treebook]}
    save_data.update(dict((key, globals()[var]) for key, var in MODE_FIELDS.items()))
    save_data.update({"SellNpc": int(SellNpc), "SellGrades": [bool(v) for v in SellGrades],
                      "SellKeep": [int(v) for v in SellKeep]})
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
        values.update(LoadSellSettings(load_data))
        globals().update(values)
        if any(key not in load_data for key in MODE_FIELDS):
            SaveSettings()
        return True
    except: return False

def LoadSellSettings(load_data):
    """판매 설정은 없거나 잘못돼도 채집 설정 읽기를 실패시키지 않는다 (기본값: 전부 제외, 남길 수량 0)."""
    count = len(BOARD_GRADES)
    try: npc = max(0, int(load_data.get("SellNpc", 0)))
    except: npc = 0
    grades, keep = [False] * count, [0] * count
    try:
        for i, v in enumerate(list(load_data.get("SellGrades", []))[:count]): grades[i] = v is True
        for i, v in enumerate(list(load_data.get("SellKeep", []))[:count]): keep[i] = max(0, int(v))
    except: pass
    return {'SellNpc': npc, 'SellGrades': grades, 'SellKeep': keep}

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
        'storage_counts': {},
        'last_inventory': {},
        'monitor_active': False,
        'is_paused': False,
        'last_dashboard_time': 0,
        'last_dashboard_sig': None,
        'pending_settings_button': -1,
        'pending_sell': 0,
        'sell_running': False,
        'sell_stop': False,
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
                        WaitCastRecovery(); Spells.CastMagery('Cure')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); MarkCastEnd(); UIPause(1200)
                    else: UIPause(2000)
                else: # 기사도 Cleanse by Fire
                    if Player.Mana >= 10:
                        WaitCastRecovery(); Spells.CastChivalry('Cleanse by Fire')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); MarkCastEnd(); UIPause(1200)
                    else: UIPause(2000)
                continue

            # 2. 체력 회복
            if Player.Hits < Player.HitsMax * 0.8:
                if USE_MAGERY: # 마제리 Greater Heal
                    if Player.Mana >= 11:
                        WaitCastRecovery(); Spells.CastMagery('Greater Heal')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); MarkCastEnd(); UIPause(1200)
                    else:
                        Player.HeadMessage(33, "마나 회복 대기 중..."); UIPause(3000)
                else: # 기사도 Close Wounds
                    if Player.Mana >= 10:
                        WaitCastRecovery(); Spells.CastChivalry('Close Wounds')
                        UIWaitForTarget(2000, False)
                        if Target.HasTarget(): Target.TargetExecute(Player.Serial); MarkCastEnd(); UIPause(1200)
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
    covered = MercenaryCovers()

    for m in nearby_mobs:
        if m is None: continue
        if m.Serial == Player.Serial: continue
        if m.Notoriety >= 3 and m.WarMode:
            if covered:
                merc_handled[m.Serial] = m.Name or "Unknown"
                return None
            return m
    return None

def InvasionWindow():
    # 침공: 매달 1일·15일 0시부터 다음 날(2일·16일) 오전 9시 자동 삭제 전까지
    t = time.localtime()
    return t.tm_mday in (1, 15) or (t.tm_mday in (2, 16) and t.tm_hour < 9)

def MercenaryCovers():
    """용병 모드 + 용병 동행 + 침공 기간 아님 → 용병이 처리하므로 회피하지 않는다."""
    global merc_present
    if not MERCENARY_MODE: return False
    present = Player.Followers >= MERC_FOLLOWER_SLOTS
    if present != merc_present:
        if present:
            Player.HeadMessage(68, "[용병] 동행 확인: 침공 기간 외 적 무시")
        else:
            Player.HeadMessage(33, "[용병] 용병 미확인: 기존 회피 모드로 동작")
            SendDiscord("⚠️ **[용병 해제 감지]** {0} 팔로워 슬롯 {1}칸 — 기존 회피 모드로 전환합니다.".format(
                Player.Name, Player.Followers))
        merc_present = present
    return present and not InvasionWindow()

def MercSummaryLine():
    if not merc_handled: return ""
    names = {}
    for name in merc_handled.values():
        names[name] = names.get(name, 0) + 1
    top = sorted(names.items(), key=lambda kv: -kv[1])
    text = ", ".join("{0} {1}".format(n, c) for n, c in top[:3])
    if len(top) > 3: text += " 외"
    return "🛡️ 용병 처리 {0}회 · {1}\n".format(len(merc_handled), text)

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
    if not danger_encounters and not merc_handled: return

    msg = "**📊 [GGO 럼버] 작업 종료 보고 (지능형 지형 분석)**\n"
    msg += "👤 보고 캐릭터: **{0}**\n".format(Player.Name)
    msg += MercSummaryLine()
    if not danger_encounters:
        SendDiscord(msg)
        return
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

def _new_journal():
    from System import Activator, Array, Object, Int32
    return Activator.CreateInstance(Player.GetType().Assembly.GetType('RazorEnhanced.Journal'),
                                    Array[Object]([Int32(200)]))

def ReadStorageLog():
    """보관함 자동수납 로그를 별도 저널 인스턴스로 읽는다.
    채집 루프의 Journal.Clear()가 지우지 못하고, 같은 줄을 두 번 세지 않도록 타임스탬프 커서로 읽는다."""
    global storage_journal, storage_cursor, storage_seen
    if storage_journal is None:
        try:
            storage_journal = _new_journal()
            storage_journal.Clear()  # 실행 전 로그는 세지 않는다
        except Exception:
            storage_journal = False  # 생성 실패: 상세 통계 없이 기존 동작
        return
    if not storage_journal: return
    try:
        rows = storage_journal.GetJournalEntry(float(storage_cursor - 0.001)) or []
    except Exception:
        return
    newest = storage_cursor
    for entry in rows:
        stamp, text = float(entry.Timestamp), u'%s' % entry.Text
        key = (stamp, text)
        if key in storage_seen: continue
        storage_seen.add(key)
        if stamp > newest: newest = stamp
        # 서버 시스템 메시지만 인정 (채팅·머리 위 메시지로 같은 문구를 흉내 내도 세지 않음)
        if u'%s' % entry.Type != u'System': continue
        m = STORAGE_LOG_RE.match(text.strip())
        if not m: continue
        for name, count in STORAGE_ITEM_RE.findall(m.group(1)):
            name = name.strip()
            storage_counts[name] = storage_counts.get(name, 0) + int(count.replace(',', ''))
    storage_cursor = newest
    storage_seen = set(k for k in storage_seen if k[0] >= storage_cursor - 0.001)

def StorageBoards():
    """보관함으로 들어간 판자 수와 NPC 매입가 기준 골드."""
    boards = gold = 0
    for name, count in storage_counts.items():
        m = BOARD_NAME_RE.match(name)
        if m:
            boards += count
            gold += count * BOARD_PRICES.get(m.group(1), 0)
    return boards, gold

def UpdateStats():
    global total_counts, last_inventory
    if not monitor_active: return
    ReadStorageLog()

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
    global last_dashboard_time, last_dashboard_sig
    now = time.time()
    elapsed = max(0, now - start_time)
    # 가방 집계(일반 보관) + 보관함 자동수납 로그 집계. 보관함을 쓰면 가방 판자는 늘지 않아 중복되지 않는다.
    stored_boards, stored_gold = StorageBoards()
    boards = total_counts['L'] + stored_boards
    # 표시 값(누적·일시정지·경과 분)이 바뀔 때만, 최소 2초 간격으로 다시 그린다 (클릭·드래그 방해 최소화).
    signature = (boards, stored_gold, len(storage_counts), is_paused, int(elapsed // 60))
    if not force and (signature == last_dashboard_sig or now - last_dashboard_time < 2): return
    last_dashboard_time, last_dashboard_sig = now, signature
    rate = int(boards * 3600 / elapsed) if elapsed else 0
    gold_rate = int(stored_gold * 3600 / elapsed) if elapsed else 0
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 330, 205, 30546)
    _Label(gd, 20, 15, "GGO 럼버", 52)
    _Label(gd, 235, 15, "{:02d}:{:02d}".format(int(elapsed // 3600), int(elapsed % 3600 // 60)))
    _Label(gd, 20, 50, "누적 판자")
    total_text = "{:,} 개".format(boards)
    if storage_counts: total_text += " ({:,} 골드)".format(stored_gold)
    _Label(gd, 120, 50, total_text)
    _Label(gd, 20, 80, "시간당 채집")
    rate_text = "{:,} 개/h".format(rate)
    if storage_counts: rate_text += " ({:,} 골드/h)".format(gold_rate)
    _Label(gd, 120, 80, rate_text)
    _Button(gd, 20, 125, 101, "재개" if is_paused else "일시정지")
    if storage_counts: _Button(gd, 125, 125, 102, "상세")
    _Button(gd, 220, 125, 100, "설정")
    _Button(gd, 20, 160, 103, "판자 판매", sell_open)
    Gumps.SendGump(DASHBOARD_GUMP_ID, Player.Serial, 400, 400, gd.gumpDefinition, gd.gumpStrings)
    if detail_open: DrawDetail()

def DrawDetail():
    """보관함 자동수납 품목별 수량·골드 (보관함 사용자 전용)."""
    global detail_open
    if not storage_counts:
        detail_open = False
        return
    elapsed = max(1, time.time() - start_time)
    rows = []
    for grade in BOARD_GRADES:
        name = u'판자 (%s)' % grade
        if storage_counts.get(name): rows.append((name, storage_counts[name], BOARD_PRICES[grade]))
    known = set(r[0] for r in rows)
    # 가격표에 없는 판자 등급·특수 재료는 수량만 표시 (많은 순)
    rows += [(n, c, None) for n, c in sorted(storage_counts.items(), key=lambda kv: -kv[1]) if n not in known]
    total_gold = sum(c * p for n, c, p in rows if p)
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 330, 125 + 22 * len(rows), 30546)
    _Label(gd, 20, 15, "보관함 채집 상세", 52)
    _Button(gd, 235, 15, 1, "갱신")
    for x, text in ((20, "재료"), (170, "수량"), (245, "골드")):
        _Label(gd, x, 45, text, 946)
    y = 67
    for name, count, price in rows:
        _Label(gd, 20, y, name[:16])
        _Label(gd, 170, y, "{:,}".format(count))
        _Label(gd, 245, y, "{:,}".format(count * price) if price else "-", 53 if price else 946)
        y += 22
    _Label(gd, 20, y + 8, "총 가치", 52)
    _Label(gd, 170, y + 8, "{:,} 골드".format(total_gold), 53)
    _Label(gd, 20, y + 30, "시간당 골드", 52)
    _Label(gd, 170, y + 30, "{:,} 골드/h".format(int(total_gold * 3600 / elapsed)), 53)
    Gumps.SendGump(DETAIL_GUMP_ID, Player.Serial, 400, 580, gd.gumpDefinition, gd.gumpStrings)

def DrawSell():
    """판자 판매 창: 등급별 판매 여부·보관함에 남길 수량, 마지막 판매 결과."""
    if not sell_open: return
    results = [(g, sell_results[g]) for g in BOARD_GRADES if sell_results and g in sell_results]
    height = 300 + 26 * len(BOARD_GRADES) + (60 + 22 * len(results) if results else 0)
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 430, height, 30546)
    _Label(gd, 20, 15, "판자 판매", 52)
    _Button(gd, 330, 15, 1, "닫기")
    npc = Mobiles.FindBySerial(SellNpc) if SellNpc > 0 else None
    _Label(gd, 20, 45, "판매 NPC")
    _Label(gd, 110, 45, (npc.Name or "")[:12] if npc else ("0x{:08X}".format(SellNpc) if SellNpc > 0 else "미지정"), 99)
    _Button(gd, 325, 45, SELL_NPC_BID, "변경" if SellNpc > 0 else "지정")
    for x, text in ((20, "등급"), (130, "판매"), (215, "보관함에 남길 수량"), (330, "빠른 선택")):
        _Label(gd, x, 75, text, 946)
    y = 100
    for i, grade in enumerate(BOARD_GRADES):
        _Label(gd, 20, y, grade)
        _Button(gd, 130, y, 300 + i, "판매" if SellGrades[i] else "제외", SellGrades[i])
        Gumps.AddBackground(gd, 212, y - 2, 90, 22, 9350)
        Gumps.AddTextEntry(gd, 218, y, 80, 20, 0, 10 + i, "{0}".format(SellKeep[i]))
        _Button(gd, 330, y, 320 + i, "여기까지")
        y += 26
    _Label(gd, 20, y + 6, "남길 수량만큼 보관함에 남기고 나머지를 팝니다.", 946)
    _Label(gd, 20, y + 28, "은행의 판매 NPC 근처에서 시작하세요.", 946)
    if sell_running: _Button(gd, 20, y + 60, SELL_STOP_BID, "판매 중지", True)
    else: _Button(gd, 20, y + 60, SELL_START_BID, "판매 시작")
    _Label(gd, 20, y + 90, sell_notice[:34], 99)
    if results:
        y += 125
        for x, text in ((20, "판매 결과"), (130, "수량"), (215, "골드"), (320, "남은 재고")):
            _Label(gd, x, y, text, 946)
        total = 0
        for grade, r in results:
            y += 22
            gold = SaleGold(grade, r)
            total += gold
            _Label(gd, 20, y, grade)
            _Label(gd, 130, y, "{:,}".format(r['sold']))
            _Label(gd, 215, y, "{:,}".format(gold) + ("*" if r['missing'] else ""), 53)
            _Label(gd, 320, y, "-" if r['left'] is None else "{:,}".format(r['left']))
        _Label(gd, 20, y + 26, "총 수익", 52)
        _Label(gd, 130, y + 26, "{:,} 골드 ({:d}분)".format(total, int(sell_elapsed // 60)), 53)
    Gumps.SendGump(SELL_GUMP_ID, Player.Serial, 760, 150, gd.gumpDefinition, gd.gumpStrings)

def SaleGold(grade, r):
    """입금 로그 합계 + 로그를 못 읽은 수량은 매입가로 추정 (* 표시)."""
    return r['gold'] + r['missing'] * BOARD_PRICES[grade]

def _ReadSellResponse():
    gd = Gumps.GetGumpData(SELL_GUMP_ID)
    if gd is None or gd.buttonid < 0: return -1, {}
    texts = {}
    try:
        ids, values = list(gd.textID), list(gd.text)
        for i, tid in enumerate(ids):
            if i < len(values): texts[int(tid)] = u'%s' % values[i]
    except: pass
    button = gd.buttonid
    gd.buttonid = -1
    gd.hasResponse = False
    return button, texts

def _ApplyKeepTexts(texts):
    """입력칸 값을 남길 수량에 반영한다. (바뀜 여부, 오류 문구)"""
    changed, error = False, ""
    for i in range(len(BOARD_GRADES)):
        if 10 + i not in texts: continue
        raw = texts[10 + i].replace(',', '').strip()
        if raw == "": raw = "0"
        if not re.match(r'^\d+$', raw):
            error = "{0}: 남길 수량은 숫자로 입력하세요".format(BOARD_GRADES[i])
            continue
        if int(raw) != SellKeep[i]:
            SellKeep[i] = int(raw)
            changed = True
    return changed, error

def HandleSellButton(bid, texts):
    global sell_open, sell_notice, pending_sell, sell_stop, SellGrades
    if bid in (0, 1):
        sell_open = False   # 창만 닫는다. 진행 중인 판매는 계속된다.
        DrawDashboard(force=True)
        return
    if sell_running:
        if bid == SELL_STOP_BID:
            sell_stop = True
            sell_notice = "이번 묶음까지 팔고 중지합니다"
        else:
            sell_notice = "판매 중에는 설정을 바꿀 수 없습니다"
        DrawSell()
        return
    changed, error = _ApplyKeepTexts(texts)
    count = len(BOARD_GRADES)
    if 300 <= bid < 300 + count:
        SellGrades[bid - 300] = not SellGrades[bid - 300]
        changed = True
    elif 320 <= bid < 320 + count:
        SellGrades = [j <= bid - 320 for j in range(count)]
        changed = True
    elif bid == SELL_NPC_BID:
        pending_sell = bid
    elif bid == SELL_START_BID:
        problem = error or SellProblem()
        if problem: sell_notice = problem
        else:
            pending_sell = bid
            sell_notice = "판매를 시작합니다"
    if changed: SaveSettings()
    if error: sell_notice = error
    DrawSell()

def DrawSettings():
    if not settings_open: return
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    rows = [(201, "도끼", myaxe), (202, "홈 룬북", Homebook),
            (203, "잔여물 보관함" if USE_WOOD_STORAGE else "나무 보관함", Treecontainer)]
    if USE_WOOD_STORAGE: rows.append((204, "우드스토리지", WoodStorage))
    if BOD_COLLECT: rows.append((205, "BOD 보관함", BodContainer))
    height = 400 + 30 * (len(rows) + len(Treebook))
    Gumps.AddBackground(gd, 0, 0, 430, height, 30546)
    _Label(gd, 20, 15, "GGO 럼버 설정 v" + CURRENT_VERSION, 52)
    _Button(gd, 330, 15, 1, "닫기")
    for y, label, bid, value, text in [
        (55, "이동 / 회복", 10, USE_MAGERY, "메져리" if USE_MAGERY else "기사도"),
        (85, "자원 보관", 11, USE_WOOD_STORAGE, "우드스토리지" if USE_WOOD_STORAGE else "일반 보관함"),
        (115, "주문전달 도끼", 12, SPELL_CHANNELING, "켜짐" if SPELL_CHANNELING else "꺼짐"),
        (145, "BOD 자동 수거", 13, BOD_COLLECT, "켜짐" if BOD_COLLECT else "꺼짐"),
        (175, "위험 지역 스킵", 14, SKIP_ON_DANGER, "켜짐" if SKIP_ON_DANGER else "꺼짐"),
        (205, "용병 모드", 15, MERCENARY_MODE, "켜짐" if MERCENARY_MODE else "꺼짐")]:
        _Label(gd, 20, y, label)
        _Button(gd, 230, y, bid, text, bool(value))
    _Label(gd, 20, 245, "대상 지정", 52)
    y = 275
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
    global settings_open, is_paused, g_lumber_quit, reset_confirm, detail_open
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
    elif bid == 102:
        detail_open = True
        DrawDashboard(force=True)
    elif bid == 103:
        globals()['sell_open'] = True
        DrawDashboard(force=True)
        DrawSell()
    sbid, texts = _ReadSellResponse()
    if sbid >= 0: HandleSellButton(sbid, texts)
    # 상세 창: 우클릭은 상세 창만 닫는다 (스크립트 종료는 대시보드 우클릭)
    dbid = _ReadButton(DETAIL_GUMP_ID)
    if dbid == 0:
        detail_open = False
    elif dbid == 1:
        DrawDetail()
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
    global pending_settings_button, pending_sell
    while True:
        if pending_sell:
            # 판매·NPC 지정은 채집 호출 스택을 끝낸 뒤 RunLumber에서 처리한다.
            bid, pending_sell = pending_sell, 0
            raise _SettingsEdit(bid)
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
    globals().update(LoadSellSettings({}))
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
             13: 'BOD_COLLECT', 14: 'SKIP_ON_DANGER', 15: 'MERCENARY_MODE'}
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

# 직전 시전 직후라 시전이 거부된 경우 (cliloc 502644 / 502642, 영문·한글)
SPELL_RECOVERY_TEXTS = ("not yet recovered", "회복하지 못했습니다", "already casting", "이미 주문을 시전")

# 주문 회복 대기 (ServUO Spell.GetCastRecovery): (기준 − FCR) ÷ 4초, 메져리 6 / 기사도 7.
# FCR을 안 맞춘 캐릭터가 연속 시전에서 거부되지 않게, 남은 회복 시간만큼만 기다린다.
last_cast_end = 0.0

def CastRecoverySeconds():
    """서버 상태 정보(최대무게가 같은 정보에 들어 있음)를 받은 뒤에만 FCR을 믿는다. 아니면 None.
    시전 때마다 새로 읽어 접속 직후 오인식·장비 변경을 바로 따라간다."""
    try:
        if Player.MaxWeight <= 0: return None
        fcr = max(0, int(Player.FasterCastRecovery))
    except Exception:
        return None
    return max(0, (6 if USE_MAGERY else 7) - fcr) / 4.0

def MarkCastEnd():
    global last_cast_end
    last_cast_end = time.time()

def WaitCastRecovery():
    """직전 시전 뒤 회복 시간이 아직 남았을 때만 기다린다 (평소 이동·회복 완료 후에는 대기 없음)."""
    recovery = CastRecoverySeconds()
    if recovery is None or not last_cast_end: return
    remaining = recovery - (time.time() - last_cast_end)
    if remaining > 0: UIPause(int(remaining * 1000) + 50)

def TravelBook(book, rune_index, bod=False):
    ServiceUI()
    UnequipForTravel()
    start_x, start_y = Player.Position.X, Player.Position.Y
    moved = lambda: Player.Position.X != start_x or Player.Position.Y != start_y
    try:
        for attempt in range(3):
            # 남아 있는 룬북 창을 먼저 닫는다. 안 닫으면 새 창 도착 전에 옛 창으로 버튼이 가서 무시된다.
            Gumps.CloseGump(0x59)
            Items.UseItem(book)  # 검프가 뜨면 바로 누른다 (고정 1.5초 대기 제거)
            if not UIWaitForGump(0x59, 5000):
                Player.HeadMessage(33, "룬북 검프 무응답: 한 번 더 엽니다")
                Gumps.CloseGump(0x59)
                Items.UseItem(book)
                if not UIWaitForGump(0x59, 5000): return False
            WaitCastRecovery()
            Journal.Clear()
            # ServUO: 50..65=Recall / 75..90=Sacred Journey (0-based rune index)
            Gumps.SendAction(0x59, (50 if USE_MAGERY else 75) + rune_index)
            # BOD 이동은 상인 앞 안정화를 위해 4초를 채우고, 일반 이동은 도착 즉시 진행한다.
            limit, waited, refused, arrived = (4000 if bod else 5000), 0, False, False
            while waited < limit:
                if any(Journal.Search(text) for text in SPELL_RECOVERY_TEXTS):
                    refused = True
                    break
                if not arrived and moved():
                    arrived = True
                    MarkCastEnd()  # 회복 시간은 이동을 확인한 순간부터 센다 (실제보다 늦게 = 넉넉하게)
                    if not bod: break
                UIPause(250)
                waited += 250
            if refused and attempt < 2:
                Player.HeadMessage(33, "주문 회복 대기 후 다시 시전합니다")
                UIPause(750)
                continue
            return moved()
        return moved()
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

        if any(Journal.Search(text) for text in BOD_WAIT_TEXTS):
            Journal.Clear()
            Player.HeadMessage(33, "BOD 수거 스킵 (대기 시간 미도달)")
            break
        UIPause(1000)

def BodTravelFailed():
    # 수거 시각은 기록하지 않는다. 룬마다 재시도하며 시간을 버리지 않게 10분 뒤 다시 시도.
    global BodRetryAt
    BodRetryAt = time.time() + BOD_RETRY_DELAY
    Player.HeadMessage(33, "BOD 상인 이동 실패: 10분 뒤 다시 시도합니다")

def ProcessBOD():
    global LastBodTime
    if not BOD_COLLECT or BodContainer <= 0: return

    if time.time() < BodRetryAt: return
    if LastBodTime == 0 or (time.time() - LastBodTime) >= BOD_CYCLE_INTERVAL:
        Player.HeadMessage(66, "★ BOD 수거 사이클 시작 ★")
        SendDiscord("📦 **[BOD 수거]** {0} 캐릭터가 BOD 수거를 시작합니다.".format(Player.Name))

        if not TravelBook(Homebook, 1, bod=True): return BodTravelFailed()
        CollectBOD(0x0001BD87); CollectBOD(0x000000E3)

        if not TravelBook(Homebook, 2, bod=True): return BodTravelFailed()
        CollectBOD(0x0000023B); CollectBOD(0x0000023F); CollectBOD(0x0001BA3A)

        # 수령은 끝났으므로 집 이동이 실패해도 시각은 기록한다. BOD는 다음 회차에 보관된다.
        if TravelBook(Homebook, 0, bod=True):
            loop_breaker = 0
            while SafeFindByID(0x2258, -1, Player.Backpack.Serial) and loop_breaker < 30:
                ServiceUI()
                bod_item = SafeFindByID(0x2258, -1, Player.Backpack.Serial)
                if bod_item:
                    SafeMove(bod_item, BodContainer, -1)
                    UIPause(1200)
                loop_breaker += 1

        remember_bod_time()
        Player.HeadMessage(66, "★ BOD 수거 완료 ★")

# -----------------------------------------------------------------------------
# [신규] 판자 판매: 마고 보관함 → 무게 한도만큼 인출 → NPC 판매 반복
# 보관함 창 해석은 마이닝 보관함 정리와 같다. 품목 버튼 번호는 화면 줄마다 바뀌므로
# 매번 문구로 찾고 기대 번호와 대조하며, 어긋나면 누르지 않는다.
# -----------------------------------------------------------------------------
MARGO_STORAGE_GUMP_ID = 0x86ADFB0B
MARGO_STORAGE_SEARCH_BUTTON = 5

class _StorageError(Exception):
    pass

class _SellAbort(Exception):
    pass

def _storage_clean(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', value)).strip()

def _storage_decode(layout, raw_strings):
    """RE가 압축 검프에서 빠뜨린 빈 입력칸 문자열을 입력칸별로 복원한다.
    보관함 라벨은 HTML이고 수량 입력값은 숫자뿐이라 둘을 구분할 수 있다."""
    refs = {}
    for raw in re.findall(r'\{\s*([^{}]+?)\s*\}', layout):
        parts = raw.split()
        if not parts: continue
        kind = parts[0].lower()
        pos = {'htmlgump': 5, 'text': 4, 'textentry': 7}.get(kind)
        if pos is not None:
            refs[int(parts[pos])] = (kind, int(parts[6]) if kind == 'textentry' else None)
    if not refs: raise _StorageError(u'보관함 문자열 참조 없음')
    source = [s for s in raw_strings if s not in (u'', u'None')]
    result, cursor = [], 0
    for index in range(max(refs) + 1):
        if index not in refs: raise _StorageError(u'예상하지 못한 보관함 문자열 인덱스')
        kind, entry_id = refs[index]
        value = source[cursor] if cursor < len(source) else u''
        if kind == 'textentry':
            if not value or value.lstrip().startswith(u'<'):
                result.append(u'')
                continue
            # 검색칸(1)은 아무 글자나, 수량칸은 숫자만 온다.
            if entry_id != 1 and not re.match(r'^\d+$', value.strip()):
                raise _StorageError(u'수량 입력 문자열을 해석할 수 없습니다')
        result.append(value)
        if value: cursor += 1
    if cursor != len(source): raise _StorageError(u'보관함 문자열 수가 레이아웃과 다릅니다')
    return result

def _storage_parse(layout, raw_strings):
    strings = _storage_decode(layout, raw_strings)
    if len(strings) < 6 or u'마고 보관함' not in _storage_clean(strings[0]):
        raise _StorageError(u'마고 보관함 창을 확인할 수 없습니다')
    labels, buttons, entries = [], [], []
    for raw in re.findall(r'\{\s*([^{}]+?)\s*\}', layout):
        parts = raw.split()
        if not parts: continue
        kind = parts[0].lower()
        if kind == 'htmlgump':
            labels.append((int(parts[1]), int(parts[2]), _storage_clean(strings[int(parts[5])])))
        elif kind == 'button' and int(parts[5]) == 1:
            buttons.append((int(parts[1]), int(parts[2]), int(parts[7])))
        elif kind == 'textentry':
            entries.append((int(parts[1]), int(parts[2]), int(parts[6])))
    return dict(labels=labels, buttons=buttons, entries=entries)

def _storage_read(stage):
    # 응답을 보내면 RE가 이전 검프 캐시를 지우므로, 새 검프가 올 때까지 기다린다.
    deadline = time.time() + 8.0
    while not Gumps.HasGump(MARGO_STORAGE_GUMP_ID):
        if time.time() >= deadline: raise _StorageError(u'창 응답 대기 초과: ' + stage)
        UIPause(50)
    gd = Gumps.GetGumpData(MARGO_STORAGE_GUMP_ID)
    layout = u'%s' % (Gumps.GetGumpRawLayout(MARGO_STORAGE_GUMP_ID) or u'')
    raw = [u'%s' % v if v is not None else u'' for v in gd.stringList]
    return _storage_parse(layout, raw)

def _storage_reply(button, stage, search=u'', entry=None, amount=None):
    # 검색칸 값을 매번 함께 보낸다: 빈 값이면 이전 검색어가 분류 목록을 가리지 않는다.
    ids, values = [1], [search]
    if entry is not None:
        ids.append(entry)
        values.append(str(amount))
    Gumps.SendAdvancedAction(MARGO_STORAGE_GUMP_ID, button, [], ids, values)
    return _storage_read(stage)

def _storage_result(state):
    return [v[2] for v in state['labels'] if v[1] >= 580]

def _storage_search(name):
    """보관함을 새로 열고 품목 이름으로 검색한다."""
    if Gumps.HasGump(MARGO_STORAGE_GUMP_ID):
        Gumps.CloseGump(MARGO_STORAGE_GUMP_ID); UIPause(300)
    Player.ChatSay(0, u'[보관함')
    state = _storage_read(u'열기')
    if not any(b[2] == MARGO_STORAGE_SEARCH_BUTTON and b[1] <= 20 and 640 <= b[0] <= 670 for b in state['buttons']):
        raise _StorageError(u'검색 버튼을 확인할 수 없습니다')
    return _storage_reply(MARGO_STORAGE_SEARCH_BUTTON, u'검색', search=name)

def _storage_row(state, name):
    """검색 결과에서 품목 줄의 (인출 버튼, 입력칸, 재고). 줄이 없으면 None (재고 없음)."""
    names = [v for v in state['labels'] if 200 <= v[0] < 490 and
             re.match(u'^' + re.escape(name) + u'( |$)', v[2])]
    if not names: return None
    if len(names) != 1: raise _StorageError(name + u' 줄을 하나로 찾지 못했습니다')
    y = names[0][1]
    buttons = [b[2] for b in state['buttons'] if b[0] >= 870 and abs(b[1] - y) <= 8]
    entries = [e[2] for e in state['entries'] if e[0] >= 770 and abs(e[1] - y) <= 8]
    counts = [v[2] for v in state['labels'] if 490 <= v[0] < 600 and abs(v[1] - y) <= 8]
    if len(buttons) != 1 or len(entries) != 1 or len(counts) != 1:
        raise _StorageError(name + u' 줄을 해석할 수 없습니다')
    button, entry = buttons[0], entries[0]
    # "수량 입력해 꺼내기"는 1000+10*줄+8, 그 줄의 입력칸은 10+줄. 짝이 맞지 않으면 다른 버튼이다.
    if button < 1000 or (button - 1000) % 10 != 8 or entry != 10 + (button - 1000) // 10:
        raise _StorageError(u'인출 버튼 번호가 예상과 다릅니다: %d / %d' % (button, entry))
    return button, entry, int(counts[0].replace(',', ''))

def BackpackBoards(hue):
    total = 0
    for item in SafeGetBackpackContains():
        try:
            if item.ItemID == BoardID and item.Hue == hue: total += item.Amount
        except: pass
    return total

def SellNpcNearby():
    npc = Mobiles.FindBySerial(SellNpc) if SellNpc > 0 else None
    if npc is None: return False
    pos = Player.Position
    return max(abs(npc.Position.X - pos.X), abs(npc.Position.Y - pos.Y)) <= SELL_NPC_RANGE

def SellProblem():
    """판매를 시작할 수 없는 이유. 없으면 빈 문자열."""
    if SellNpc <= 0: return "판매 NPC를 지정하세요"
    if not SellNpcNearby(): return "판매 NPC 근처(은행)에서 시작하세요"
    if not any(SellGrades): return "판매할 등급을 선택하세요"
    if Player.MaxWeight - Player.Weight - SELL_WEIGHT_MARGIN < 1: return "무게 여유가 없습니다"
    return ""

def SellPacket(vendor, stacks):
    """판매 응답 패킷 0x9F: [id][길이 2][상인 4][개수 2] + 개수 × ([물건 4][수량 2]), 빅엔디언.
    RE 판매 에이전트가 보내는 것과 같은 패킷이라 에이전트 목록 설정 없이 판다."""
    data = [0x9F, 0, 0] + [(vendor >> s) & 0xFF for s in (24, 16, 8, 0)]
    data += [(len(stacks) >> 8) & 0xFF, len(stacks) & 0xFF]
    for serial, amount in stacks:
        data += [(serial >> s) & 0xFF for s in (24, 16, 8, 0)] + [(amount >> 8) & 0xFF, amount & 0xFF]
    data[1], data[2] = (len(data) >> 8) & 0xFF, len(data) & 0xFF
    return data

def _sell_stacks(hue):
    """가방 최상단의 이 등급 판자 묶음만 판다 (다른 등급·다른 물건은 패킷에 넣지 않음)."""
    from System import Array, Byte
    stacks = []
    for item in SafeGetBackpackContains():
        try:
            if item.ItemID == BoardID and item.Hue == hue and item.Amount > 0:
                stacks.append((int(item.Serial), min(int(item.Amount), 0xFFFF)))
        except: pass
    if not stacks: return False
    PacketLogger.SendToServer(Array[Byte](SellPacket(int(SellNpc), stacks[:99])))  # 서버 한도: 100묶음 미만
    return True

def _sale_gold(journal):
    """이 저널 인스턴스에 쌓인 서버 판매 대금 로그 합계."""
    gold = 0
    try: rows = journal.GetJournalEntry(-1.0) or []
    except: return 0
    for entry in rows:
        if u'%s' % entry.Type != u'System': continue
        m = SALE_LOG_RE.match((u'%s' % entry.Text).strip())
        if m: gold += int(m.group(1).replace(',', ''))
    return gold

def _sell_backpack(grade, journal, result):
    """가방의 이 등급 판자를 다 팔 때까지 판매 패킷을 다시 보낸다. 못 팔면 _SellAbort."""
    hue = BOARD_HUES[grade]
    idle = 0
    while BackpackBoards(hue) > 0:
        if idle >= 3:
            raise _SellAbort(u"{0} 판매 실패: NPC가 매입하지 않습니다 (판매 NPC·거리 확인)".format(grade))
        before = BackpackBoards(hue)
        if journal: journal.Clear()
        if not _sell_stacks(hue):
            idle += 1
            UIPause(500)
            continue
        waited = 0
        while waited < 6000 and BackpackBoards(hue) >= before:
            UIPause(200); waited += 200
        sold = before - BackpackBoards(hue)
        if sold <= 0:
            idle += 1
            continue
        idle = 0
        gold, waited = 0, 0
        while journal and waited < 3000:
            gold = _sale_gold(journal)
            if gold: break
            UIPause(200); waited += 200
        result['sold'] += sold
        if gold: result['gold'] += gold
        else: result['missing'] += sold
        DrawSell()

def _sell_grade(index, journal):
    grade = BOARD_GRADES[index]
    name = u'판자 (%s)' % grade
    hue = BOARD_HUES[grade]
    keep = SellKeep[index]
    result = sell_results.setdefault(grade, {'sold': 0, 'gold': 0, 'missing': 0, 'left': None})
    failures = 0
    plan = None     # 판매량은 처음 읽은 재고로 고정한다 (판매 중 공용 보관함에 들어오는 판자는 쫓지 않음)
    withdrawn = 0
    while True:
        # 가방의 같은 등급 판자(지난 묶음 늦게 도착분·개인 소지분)부터 판다.
        _sell_backpack(grade, journal, result)
        if sell_stop: return
        try:
            state = _storage_search(name)
            row = _storage_row(state, name)
            stock = row[2] if row else 0
            result['left'] = stock
            # 목표: 시작 재고 − 남길 수량. 매 묶음 재고를 다시 읽어 남길 수량 아래로는 절대 꺼내지 않는다.
            if plan is None: plan = max(0, stock - keep)
            need = min(plan - withdrawn, stock - keep)
            if need <= 0: return
            free = Player.MaxWeight - Player.Weight - SELL_WEIGHT_MARGIN
            amount = min(SELL_BATCH_MAX, need, free * BOARDS_PER_STONE)
            if amount < 1: raise _SellAbort(u'무게 여유가 없습니다')
            state = _storage_reply(row[0], u'인출', search=name, entry=row[1], amount=amount)
            expected = u'%s %d개를 꺼냈습니다.' % (name, amount)
            took = expected in [v.replace(',', '') for v in _storage_result(state)]
            if took: result['left'] = stock - amount
            Gumps.CloseGump(MARGO_STORAGE_GUMP_ID)
            waited = 0
            while waited < 3000 and BackpackBoards(hue) < amount:
                UIPause(200); waited += 200
            if not took and BackpackBoards(hue) <= 0:
                raise _StorageError(u'인출을 확인하지 못했습니다: ' + u' '.join(_storage_result(state)))
            withdrawn += amount
            failures = 0
            sell_notice_set(u'{0} {1:,}개 판매 중 (재고 {2:,} → 목표 {3:,})'.format(grade, amount, stock, keep))
        except _StorageError as error:
            failures += 1
            try: Gumps.CloseGump(MARGO_STORAGE_GUMP_ID)
            except: pass
            if failures >= 3: raise _SellAbort(u'[보관함] %s' % error)
            UIPause(1000)

def sell_notice_set(text):
    global sell_notice
    sell_notice = text
    Player.HeadMessage(68, text)
    DrawSell()

def SellReport():
    if not sell_results: return
    total = 0
    lines = []
    for grade in BOARD_GRADES:
        r = sell_results.get(grade)
        if not r: continue
        gold = SaleGold(grade, r)
        total += gold
        left = "-" if r['left'] is None else "{:,}".format(r['left'])
        lines.append(u"- {0}: {1:,}개 · {2:,}골드{3} · 남은 재고 {4}".format(
            grade, r['sold'], gold, " (추정 포함)" if r['missing'] else "", left))
    msg = u"💰 **[판자 판매]** {0} — 총 {1:,}골드 ({2}분)\n".format(Player.Name, total, int(sell_elapsed // 60))
    SendDiscord(msg + u"\n".join(lines))
    Player.HeadMessage(68, u"[판자 판매] 총 {0:,}골드".format(total))

def SellSession():
    global sell_running, sell_stop, sell_results, sell_elapsed, sell_open, is_paused
    # 판매 뒤에는 은행에 머문다. 대시보드 재개를 누르면 채집으로 돌아간다.
    is_paused = True
    sell_open = True
    problem = SellProblem()
    if problem:
        sell_notice_set(problem)
        DrawDashboard(force=True)
        return
    sell_running, sell_stop = True, False
    sell_results = {}
    started = time.time()
    try: journal = _new_journal()
    except Exception: journal = None   # 로그를 못 읽으면 매입가로 추정
    try:
        for index in range(len(BOARD_GRADES)):
            if sell_stop: break
            if SellGrades[index]: _sell_grade(index, journal)
        sell_notice_set(u"판매 중지" if sell_stop else u"판매 완료")
    except _SellAbort as error:
        sell_notice_set(u'%s' % error)
    finally:
        try: Gumps.CloseGump(MARGO_STORAGE_GUMP_ID)
        except: pass
        sell_running = False
        sell_elapsed = time.time() - started
        DrawSell()
        DrawDashboard(force=True)
    SellReport()

def SelectSellNpc():
    global SellNpc, is_paused
    is_paused = True
    Target.Cancel()
    serial = Target.PromptTarget("판매 NPC 선택 (ESC: 취소)")
    npc = Mobiles.FindBySerial(serial) if serial and serial > 0 else None
    if npc:
        SellNpc = serial
        SaveSettings()
        sell_notice_set(u'판매 NPC: %s' % (npc.Name or "0x{:08X}".format(serial)))
    else:
        sell_notice_set(u'선택 취소: 기존 지정 유지')
    DrawDashboard(force=True)

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
                WaitCastRecovery()
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
            if Player.Position.X != StartX or Player.Position.Y != StartY: MarkCastEnd()

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
    if MERCENARY_MODE:
        Player.ChatSay("all guard me"); UIPause(500)
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

                # 보관함 자동수납·용병 모드에서는 무게 귀환이 드물어 채집 중에도 BOD 시간을 확인한다.
                ProcessBOD()

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
    global settings_open, settings_notice, is_paused
    config_ok = load_json_logic()
    if config_ok and SellNpcNearby():
        # 은행의 판매 NPC 옆에서 시작하면 바로 귀환하지 않고 판매할 수 있게 멈춰 둔다.
        is_paused = True
        Player.HeadMessage(68, "판매 NPC 근처: 일시정지로 시작 (판자 판매 / 재개)")
    DrawDashboard(force=True)
    if not config_ok:
        settings_notice = "설정을 읽지 못했습니다. 재지정해 주세요"
    action = -1
    announced = False
    needs_setup = not config_ok or bool(MissingSettings()) or settings_dirty
    while True:
        try:
            if action in (SELL_NPC_BID, SELL_START_BID):
                if action == SELL_NPC_BID: SelectSellNpc()
                else: SellSession()
                action = -1
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
        Gumps.CloseGump(DETAIL_GUMP_ID)
        Gumps.CloseGump(SELL_GUMP_ID)
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
        Gumps.CloseGump(DETAIL_GUMP_ID)
        Gumps.CloseGump(SELL_GUMP_ID)

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
