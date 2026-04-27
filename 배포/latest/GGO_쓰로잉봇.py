# -*- coding: utf-8 -*-
# =============================================================================
# [GGO_쓰로잉봇 v1.2] - 가고일 팔라딘 쓰로잉 전사 전용
# 바울 바드봇 인핸스 v0.3 기반으로 전사 특화 기능 재설계
# =============================================================================

SCRIPT_ID = "GGO_THROWING"
SCRIPT_NAME = "GGO_쓰로잉봇"
CURRENT_VERSION = "1.2"

import os, sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from GGO_update_check import notify_update_async
    notify_update_async(SCRIPT_ID, SCRIPT_NAME, CURRENT_VERSION)
except Exception:
    pass

from System.IO import Directory, Path, File
from System.Collections.Generic import List
from System import Byte, Int32
import json
import re
import time
import os
import math
import ctypes
import sys
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)
from GGO_봇공통_모듈 import (
    trim_working_set, collect_all_items, get_movable_items,
    do_sanghacha, calculateDirection, do_skull_sort, do_item_sort,
    find_bag_of_sending, get_bos_charges, recharge_bos,
    handle_loot, sell_powerscrolls, do_gate, autoparty, init_backpack_containers,
    do_help_escape, make_revival_state, handle_revival
)

# =============================================================================
# script_settings.json 기본값
# -----------------------------------------------------------------------------
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 실제 사용자 설정은 스크립트 파일을 직접 수정하지 말고
# GGO_Settings/GGO_쓰로잉봇/script_settings.json에서 수정하세요.
# =============================================================================
usepathfinding        = 0     # 1: 지능형 길찾기 사용, 0: 단순 직선 추적
doomtile              = 1     # 1: 둠 던전 타일 자동 인식
pathfinddistance      = 8     # 리더와 이 거리(타일) 이상 벌어지면 지능형 추적 발동
distanceleader        = 2     # 비전투 시 리더와 유지할 기본 거리 (타일)
distanceleader_combat = 8     # 전투 시 리더와 허용 최대 거리 (타일)
combat_range          = 14    # 쓰로잉 사정거리 (타일)
evade_range           = 4     # 이 거리 이하로 적이 접근하면 카이팅 이동
max_mode_range        = 12    # !max 모드 유지 거리 (타일)
champ_mode_range      = 20    # !champ 모드 행동 반경 (타일)
champ_anchor_radius   = 10    # 챔프 앵커 순찰 반경 (타일)
stam_threshold        = 210   # 이 수치 이하로 스태미너 감소 시 Divine Fury 사용
dress_name            = "th"  # 부활 시 입을 드레스 에이전트 이름
use_undertaker_staff  = True  # True: 부활 시 장의사 지팡이(0x13F8) 사용
SELL_AGENT_LIST_NAME  = "ps"          # Vendor Sell 에이전트 목록 이름
NPC_SELL              = 0x0000DE29    # 파워스크롤 판매 NPC 시리얼
TRASH_ORGANIZER_NAME  = "trash"       # Organizer 에이전트 목록 이름

# 광범위한 펫 먹이 ID 리스트 (고기, 과일, 채소 등)
pet_food = [
    0x09C0, 0x09C1,  # Sausage
    0x0976, 0x0977, 0x0978, 0x0979, # Bacon
    0x1607, 0x1608,  # Chicken Leg (Raw/Cooked)
    0x1609, 0x160A,  # Leg of Lamb (Raw/Cooked)
    0x09F1, 0x09F2,  # Ribs (Raw/Cooked)
    0x09B7, 0x09B8,  # Raw/Cooked Bird
    0x097A, 0x097B,  # Raw/Cooked Fish Steak
    0x09C9,          # Ham
    0x09BB,          # Roast Pig
    0x09D0,          # Apple
    0x09D1,          # Grapes
    0x171F, 0x1720,  # Banana
    0x172C,          # Peach
    0x0994,          # Pear
    0x1728,          # Lemon
    0x172A,          # Lime
    0x0C5C,          # Watermelon
    0x0C77, 0x0C78,  # Carrot
    0x0C82, 0x0C81,  # Corn
    0x0C70, 0x0C71,  # Lettuce
    0x0C7B, 0x0C7C,  # Cabbage
    0x0C6D, 0x0C6E,  # Onion
    0x0C6A, 0x0C6B,  # Pumpkin
]

THROWING_SCRIPT_SETTINGS_DEFAULTS = {
    "usepathfinding": usepathfinding,
    "doomtile": doomtile,
    "pathfinddistance": pathfinddistance,
    "distanceleader": distanceleader,
    "distanceleader_combat": distanceleader_combat,
    "combat_range": combat_range,
    "evade_range": evade_range,
    "max_mode_range": max_mode_range,
    "champ_mode_range": champ_mode_range,
    "champ_anchor_radius": champ_anchor_radius,
    "stam_threshold": stam_threshold,
    "dress_name": dress_name,
    "use_undertaker_staff": use_undertaker_staff,
    "sell_agent_list_name": SELL_AGENT_LIST_NAME,
    "npc_sell": NPC_SELL,
    "trash_organizer_name": TRASH_ORGANIZER_NAME,
    "pet_food": pet_food
}

THROWING_SCRIPT_SETTINGS_ORDER = [
    "usepathfinding",
    "doomtile",
    "pathfinddistance",
    "distanceleader",
    "distanceleader_combat",
    "combat_range",
    "evade_range",
    "max_mode_range",
    "champ_mode_range",
    "champ_anchor_radius",
    "stam_threshold",
    "dress_name",
    "use_undertaker_staff",
    "sell_agent_list_name",
    "npc_sell",
    "trash_organizer_name",
    "pet_food"
]

THROWING_SCRIPT_SETTINGS_GUIDE = """GGO_쓰로잉봇 script_settings.json 설명

이 파일은 쓰로잉봇의 공용 설정 파일입니다.
숫자는 숫자로, true/false는 반드시 소문자로 입력하세요.
쉼표는 지우지 마세요.

usepathfinding:
  1 = 리더 추적 시 PathFinding 사용, 0 = 일반 이동입니다.

doomtile:
  1 = 둠 던전 타일 자동 인식 사용, 0 = 사용 안 함입니다.

pathfinddistance:
  PathFinding을 시도할 리더와의 거리입니다.

distanceleader:
  비전투 시 리더와 유지할 거리입니다.

distanceleader_combat:
  전투 중 리더와 허용할 최대 거리입니다.

combat_range:
  쓰로잉 공격 사정거리입니다.

evade_range:
  적이 이 거리 이하로 접근하면 카이팅 이동을 시도합니다.

max_mode_range:
  !max 모드 유지 거리입니다.

champ_mode_range:
  !champ 모드 행동 반경입니다.

champ_anchor_radius:
  챔프 앵커 순찰 반경입니다.

stam_threshold:
  스태미너가 이 수치 이하가 되면 Divine Fury를 사용합니다.

dress_name:
  부활 복구에 사용할 RE Dress 리스트 이름입니다.

use_undertaker_staff:
  부활 시 장의사 지팡이 사용 여부입니다.

sell_agent_list_name:
  판매에 사용할 RE Sell Agent 리스트 이름입니다.

npc_sell:
  파워스크롤 판매 NPC 시리얼입니다.
  예: 56873
  16진수로 넣을 경우 큰따옴표로 감싸세요. 예: "0x0000DE29"

trash_organizer_name:
  트래쉬에 사용할 RE Organizer 리스트 이름입니다.

pet_food:
  펫 먹이로 사용할 아이템 ID 목록입니다.
"""

try:
    _STRING_TYPES = (basestring,)
except Exception:
    _STRING_TYPES = (str,)

def _setting_int(value, default_value):
    try:
        if isinstance(value, _STRING_TYPES):
            text = value.strip()
            if text.lower().startswith("0x"):
                return int(text, 16)
            return int(text)
        return int(value)
    except Exception:
        return default_value

try:
    from GGO_user_config import (
        load_script_settings, ensure_script_settings_guide,
        get_character_settings_path, load_character_settings, save_character_settings
    )
    ensure_script_settings_guide(SCRIPT_NAME, THROWING_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, THROWING_SCRIPT_SETTINGS_DEFAULTS, THROWING_SCRIPT_SETTINGS_ORDER)
    usepathfinding = _setting_int(_script_settings.get("usepathfinding", usepathfinding), usepathfinding)
    doomtile = _setting_int(_script_settings.get("doomtile", doomtile), doomtile)
    pathfinddistance = _setting_int(_script_settings.get("pathfinddistance", pathfinddistance), pathfinddistance)
    distanceleader = _setting_int(_script_settings.get("distanceleader", distanceleader), distanceleader)
    distanceleader_combat = _setting_int(_script_settings.get("distanceleader_combat", distanceleader_combat), distanceleader_combat)
    combat_range = _setting_int(_script_settings.get("combat_range", combat_range), combat_range)
    evade_range = _setting_int(_script_settings.get("evade_range", evade_range), evade_range)
    max_mode_range = _setting_int(_script_settings.get("max_mode_range", max_mode_range), max_mode_range)
    champ_mode_range = _setting_int(_script_settings.get("champ_mode_range", champ_mode_range), champ_mode_range)
    champ_anchor_radius = _setting_int(_script_settings.get("champ_anchor_radius", champ_anchor_radius), champ_anchor_radius)
    stam_threshold = _setting_int(_script_settings.get("stam_threshold", stam_threshold), stam_threshold)
    dress_name = str(_script_settings.get("dress_name", dress_name))
    use_undertaker_staff = bool(_script_settings.get("use_undertaker_staff", use_undertaker_staff))
    SELL_AGENT_LIST_NAME = str(_script_settings.get("sell_agent_list_name", SELL_AGENT_LIST_NAME))
    NPC_SELL = _setting_int(_script_settings.get("npc_sell", NPC_SELL), NPC_SELL)
    TRASH_ORGANIZER_NAME = str(_script_settings.get("trash_organizer_name", TRASH_ORGANIZER_NAME))
    pet_food = list(_script_settings.get("pet_food", pet_food))
except Exception:
    load_character_settings = None
    save_character_settings = None
    get_character_settings_path = None


# =============================================================================
# [명령어 / 검프 가이드]
# -----------------------------------------------------------------------------
# 시작 시 검프 메뉴가 자동으로 열립니다.
# 검프 버튼: [시작] [재설정] [먹이지정] [송금모드 ON/OFF]
## !s1~16       : 룬북 Sacred Journey 이동
# =============================================================================

# =============================================================================
# [검프 ID]
# =============================================================================
MENU_GUMP_ID = 0x57A21001

# =============================================================================
# [전역 상태 관리]
# =============================================================================
APPDATA     = os.environ['APPDATA']
LEGACY_SAVE_DIR    = Path.Combine(APPDATA, "GGO_Project", "WarriorBot")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "{}.json".format(Player.Name))
if get_character_settings_path:
    CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
    SAVE_DIR = os.path.dirname(CONFIG_FILE)
else:
    SAVE_DIR = LEGACY_SAVE_DIR
    CONFIG_FILE = LEGACY_CONFIG_FILE

current_lock         = None   # 현재 점사 타겟 시리얼
target_start_time    = 0
pending_action       = None   # smart_pause 중 예약된 명령
gate_cooldown        = 0
locked_gate_serial   = None
current_map          = 0

gate_watch_active  = False  # 리더 게이트 발화 감지 후 탐색 창
gate_watch_start   = 0.0
ignored_gate_serials = set() # 주문 시점에 이미 있던 게이트 목록

last_leader_x      = 0      # 리더 소실 추적용 마지막 위치
last_leader_y      = 0
last_leader_dir    = None
leader_lost_time   = 0.0
leader_chase_done  = False

revival_state        = make_revival_state()

locked_target_serial = 0      # 자동 전투 중 고정된 타겟
in_combat            = False  # 전투 상태 여부

leader_separated_time = 0.0   # 리더 이탈 시작 시각 (전투 중)
escape_start_time     = 0.0   # 강제복귀 모드 진입 시각
last_trim_time        = 0.0   # 마지막 trim 호출 시각
bot_paused            = False  # 리더 일시정지 명령 상태
following_mode        = False  # 팔로잉 모드 (공격 억제, 리더 추적만)

stam_max_baseline      = 0    # 최대 스태미너 기준값 (저주 감지용)
armor_ignore_always    = True
loot_mode              = False # 송금모드
is_running             = True  # 봇 작동 스위치
bot_mode               = "normal"  # 전투 모드: "normal" / "aggro" / "max" / "champ"
patrol_angle           = 0.0       # 순찰 현재 각도 (radian)
PATROL_WAYPOINTS       = 8         # 원형 순찰 웨이포인트 수
champ_anchor_x         = 0         # 챔프 앵커 X 좌표 (0이면 미설정)
champ_anchor_y         = 0         # 챔프 앵커 Y 좌표

# 상하차 모드
sanghacha_mode         = False  # 상하차 대기 상태
sanghacha_protected    = set()  # 보호 아이템 시리얼 세트

# 아이템 정리 모드
ps_sort_mode   = False  # !파스정리 대기 상태
pink_sort_mode = False  # !분홍정리 대기 상태
skull_sort_mode = False  # !해골정리 대기 상태
gate_mode       = False  # !게이트 대기 상태

# 펫 체력 감시 상태
pet_follow_mode      = False   # True: follow me 발령 중 (HP 회복 대기)
pet_follow_attempts  = 0       # follow me 시도 횟수 (최대 3회)
pet_follow_last_try  = 0.0     # 마지막 follow me 발령 시각

# =============================================================================
# [검프 메뉴]
# =============================================================================
def draw_menu():
    """
    버튼 ID 정의:
      1 = 시작/정지
      2 = 재설정
      5 = 아머 On/Off
      3 = 먹이지정
      4 = 송금모드 ON/OFF
      9 = 종료
    """
    global is_running, armor_ignore_always, loot_mode

    # 백팩에서 먹이 검색
    display_text = "감지된 먹이 없음"
    food_hue = 33
    found_items = Items.FindAllByID(pet_food, -1, Player.Backpack.Serial, True)
    if found_items:
        type_count = len(set(i.ItemID for i in found_items))
        total_amount = sum(i.Amount for i in found_items)
        f_item = found_items[0]
        food_name = f_item.Name
        if not food_name:
            Mobiles.WaitForProps(f_item.Serial, 200)
            food_name = f_item.Name if f_item.Name else "Food"
        display_text = "{} ({}종/{}개)".format(food_name, type_count, total_amount)
        food_hue = 68

    gump_w, gump_h = 280, 165
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddBackground(gd, 0, 0, gump_w, gump_h, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, gump_w, gump_h)

    # 타이틀
    Gumps.AddLabel(gd, 10, 10, 53, "GGO Throwing Bot v1.2")
    Gumps.AddImageTiled(gd, 5, 28, gump_w - 10, 2, 9107)

    y = 38
    # ── [1행] 시작(정지) / 재설정 ──
    start_btn_id = 40030 if not is_running else 40297
    start_btn_txt = "시작" if not is_running else "정지"
    start_btn_hue = 68 if is_running else 33
    Gumps.AddButton(gd, 8,  y, start_btn_id, start_btn_id + 1, 1, 1, 0)
    Gumps.AddLabel(gd,  42, y + 2, start_btn_hue, start_btn_txt)

    Gumps.AddButton(gd, 148, y, 40021, 40022, 2, 1, 0)
    Gumps.AddLabel(gd,  182, y + 2, 53, "재설정")
    y += 32

    # ── [2행] 아머 On/Off / 먹이지정 ──
    armor_hue = 68 if armor_ignore_always else 33
    armor_txt = "아머: On" if armor_ignore_always else "아머: Off"
    Gumps.AddButton(gd, 8,  y, 40299, 40300, 5, 1, 0)
    Gumps.AddLabel(gd,  42, y + 2, armor_hue, armor_txt)

    Gumps.AddButton(gd, 148, y, 40021, 40022, 3, 1, 0)
    Gumps.AddLabel(gd,  182, y + 2, 1152, "먹이지정")
    y += 32

    # ── [3행] 자동 감지된 먹이 수량 (배경 제거) ──
    Gumps.AddLabel(gd,  15,  y, food_hue, display_text)
    y += 24

    # ── [4행] 송금모드 On/Off / 종료 ──
    loot_hue = 68 if loot_mode else 33
    loot_txt = "송금: On" if loot_mode else "송금: Off"
    Gumps.AddButton(gd, 8,   y, 40299, 40300, 4, 1, 0)
    Gumps.AddLabel(gd,  42,  y + 2, loot_hue, loot_txt)

    Gumps.AddButton(gd, 148, y, 40297, 40298, 9, 1, 0)
    Gumps.AddLabel(gd,  182, y + 2, 33, "종료")

    Gumps.SendGump(MENU_GUMP_ID, Player.Serial, 50, 200, gd.gumpDefinition, gd.gumpStrings)

def handle_menu():
    """메인 루프에서 매 사이클 호출 — 검프 버튼 입력 처리"""
    global loot_mode, config, leader, runebook, extra_party, extra_pets, mypet, is_running, armor_ignore_always
    md = Gumps.GetGumpData(MENU_GUMP_ID)
    if not md or md.buttonid <= 0:
        return
    btn = md.buttonid
    Gumps.CloseGump(MENU_GUMP_ID)

    if btn == 1:    # 시작 / 정지
        is_running = not is_running
        status_txt = "봇 작동 시작" if is_running else "봇 일시 정지"
        Player.ChatSay(68, "★{}★".format(status_txt))
    elif btn == 2:  # 재설정
        Player.ChatSay(158, "★설정 초기화★")
        config      = run_setup()
        leader      = config['leader']
        runebook    = config['runebook']
        extra_party = config.get('party', [])
        extra_pets  = config.get('pets', [])
        mypet       = extra_pets[0] if extra_pets else None
    elif btn == 3:  # 먹이지정
        Player.ChatSay(158, "★먹이 아이템 선택★")
        new_food_id = Target.PromptTarget("먹이 선택")
        food_item   = Items.FindBySerial(new_food_id)
        if food_item:
            pet_food.insert(0, food_item.ItemID)
            Player.ChatSay(68, "★먹이 등록 완료★")
        else:
            Player.ChatSay(33, "★등록 취소★")
    elif btn == 4:  # 송금모드 ON/OFF
        loot_mode = not loot_mode
        config['loot_mode'] = loot_mode
        save_config(config)
        Player.ChatSay(66, "★송금모드: {}★".format("On" if loot_mode else "Off"))
    elif btn == 5:  # 아머모드 ON/OFF
        armor_ignore_always = not armor_ignore_always
        Player.ChatSay(66, "★아머모드: {}★".format("On" if armor_ignore_always else "Off"))
    elif btn == 9:  # 종료
        Player.ChatSay(33, "★프로그램 종료★")
        raise SystemExit

    draw_menu()

# =============================================================================
# [설정 저장 / 로드]
# =============================================================================
def save_config(data):
    if save_character_settings:
        save_character_settings(SCRIPT_NAME, Player.Name, data)
    else:
        if not Directory.Exists(SAVE_DIR):
            Directory.CreateDirectory(SAVE_DIR)
        File.WriteAllText(CONFIG_FILE, json.dumps(data, indent=4))
    Player.ChatSay(68, "[보고] 설정 저장 완료")

def load_config():
    if load_character_settings:
        try:
            data = load_character_settings(SCRIPT_NAME, Player.Name, {}, [LEGACY_CONFIG_FILE])
            return data if data else None
        except:
            pass
    if File.Exists(CONFIG_FILE):
        try:
            return json.loads(File.ReadAllText(CONFIG_FILE))
        except:
            return None
    return None

def run_setup():
    Player.ChatSay(158, "● [설정] 리더를 선택하세요.")
    l_id = Target.PromptTarget("Select Leader")
    mob  = Mobiles.FindBySerial(l_id)
    if mob:
        Player.ChatSay(68, "[설정] 리더: {} 지정".format(mob.Name))
    Misc.Pause(500)

    Player.ChatSay(158, "● [설정] 룬북을 선택하세요.")
    rb_id = Target.PromptTarget("Select Runebook")
    item  = Items.FindBySerial(rb_id)
    if item:
        Player.ChatSay(68, "[설정] 룬북: {} 인식".format(item.Name))
    Misc.Pause(500)

    p_list = []
    Player.ChatSay(158, "● [설정] 파티원 선택 (종료: 우클릭/취소)")
    while True:
        p_target = Target.PromptTarget("Select Party Member")
        if p_target == -1 or p_target is None:
            break
        mob = Mobiles.FindBySerial(p_target)
        if mob:
            p_list.append(p_target)
            Player.ChatSay(68, "[설정] 파티원: {} 추가 (총 {}명)".format(mob.Name, len(p_list)))
        Misc.Pause(300)

    pet_list = []
    Player.ChatSay(158, "● [설정] 펫 선택 (종료: 우클릭/취소)")
    while True:
        pet_target = Target.PromptTarget("Select Pet")
        if pet_target == -1 or pet_target is None:
            break
        mob = Mobiles.FindBySerial(pet_target)
        if mob:
            pet_list.append(pet_target)
            Player.ChatSay(68, "[설정] 펫: {} 추가 (총 {}명)".format(mob.Name, len(pet_list)))
        Misc.Pause(300)

    data = {"leader": l_id, "runebook": rb_id, "party": p_list, "pets": pet_list}
    save_config(data)
    return data

# 시작 시 설정 로드
config = load_config()
if config:
    check_ids = [config['leader']] + config.get('party', [])
    if not any(Mobiles.FindBySerial(cid) for cid in check_ids):
        Player.ChatSay(33, "[경고] 파티원이 주변에 없습니다. 재설정 시작.")
        config = run_setup()
else:
    config = run_setup()

leader      = config['leader']
runebook    = config['runebook']
extra_party = config.get('party', [])
extra_pets  = config.get('pets', [])
mypet       = extra_pets[0] if extra_pets else None
loot_mode   = config.get('loot_mode', False)

def _lcmd(keyword):
    mob = Mobiles.FindBySerial(leader)
    name = mob.Name if mob else ""
    return bool(name and Journal.SearchByName(keyword, name))

# =============================================================================
# [유틸리티]
# =============================================================================

def smart_pause(duration_ms):
    """딜레이 중에도 핵심 명령어를 감지하여 예약 처리"""
    global pending_action, armor_ignore_always, gate_watch_active, gate_watch_start
    global sanghacha_mode, sanghacha_protected, bot_mode, patrol_angle, champ_anchor_x, champ_anchor_y
    global following_mode, in_combat, locked_target_serial, current_lock
    steps = max(1, duration_ms // 250)
    for _ in range(steps):
        if _lcmd("!max"):
            Journal.Clear()
            bot_mode = "max"
            Player.ChatSay(68, "★MAX 모드: 원거리 {}타일★".format(max_mode_range))
        elif _lcmd("!선공"):
            Journal.Clear()
            bot_mode = "aggro"
            Player.ChatSay(68, "★선공 모드★")
        elif _lcmd("!챔프 {}".format(Player.Name)):
            Journal.Clear()
            champ_anchor_x = Player.Position.X
            champ_anchor_y = Player.Position.Y
            bot_mode = "champ"
            Player.HeadMessage(68, "★챔프 앵커 ({},{}) 반경{}★".format(champ_anchor_x, champ_anchor_y, champ_anchor_radius))
        elif _lcmd("!정상화"):
            Journal.Clear()
            bot_mode = "normal"
            champ_anchor_x = 0
            champ_anchor_y = 0
            Player.ChatSay(33, "★일반 모드 복귀★")
        elif _lcmd("!상하차"):
            Journal.Clear()
            if sanghacha_mode:
                sanghacha_mode = False
                Player.HeadMessage(33, "[상하차 취소]")
            else:
                sanghacha_mode = True
                Player.HeadMessage(68, "[상하차 대기: 컨테이너 지정 대기]")
        elif _lcmd("!밥줘"):
            Journal.Clear()
            pending_action = 'feed'
            Player.ChatSay(158, "★먹이 예약★")
        elif _lcmd("!에너미오프"):
            Journal.Clear()
            if Player.BuffsExist('Enemy Of One'):
                pending_action = 'enemy_off'
                Player.ChatSay(158, "★에너미 해제 예약★")
        elif _lcmd("!에너미"):
            Journal.Clear()
            if not Player.BuffsExist('Enemy Of One'):
                pending_action = 'enemy'
                Player.ChatSay(158, "★에너미 예약★")
        elif _lcmd("!팔로우"):
            Journal.Clear()
            following_mode = True
            in_combat = False
            locked_target_serial = 0
            current_lock = None
            Player.SetWarMode(False)
            Player.ChatSay("all follow me")
            Player.ChatSay(68, "★팔로잉 모드★")
        elif _lcmd("!아머"):
            Journal.Clear()
            armor_ignore_always = not armor_ignore_always
            Player.ChatSay(66, "★아머:{}★".format("On" if armor_ignore_always else "Off"))
        elif Journal.Search("0x"):
            lead_mob    = Mobiles.FindBySerial(leader)
            leader_name = lead_mob.Name if lead_mob else ""
            # SearchByName으로 발화자와 시리얼 동시 확인
            if leader_name and Journal.SearchByName("0x", leader_name):
                line = Journal.GetLineText("0x", True) # 이름 포함해서 가져오기
                m = re.search(r"0x[0-9a-fA-F]+", line.lower())
                if m:
                    val = int(m.group(), 16)
                    Journal.Clear()
                    if sanghacha_mode:
                        container = Items.FindBySerial(val)
                        if container:
                            pending_action = ('sanghacha', val)
                            Player.ChatSay(68, "★상하차 컨테이너 포착 (예약)★")
                        else:
                            Player.ChatSay(33, "★컨테이너 인식 실패★")
                            sanghacha_mode = False
                            sanghacha_protected = set()
                    else:
                        pending_action = val
                        Player.ChatSay(68, "★점사 예약★")
        Misc.Pause(250)

# =============================================================================
# [둠 타일 이동]
# =============================================================================
def findtile():
    if doomtile == 1:
        if Player.InRangeMobile(leader, 2):
            item = Items.FindByID(0x1822, 0x0482, -1, 3)
            if item is not None:
                if   Player.Position.X > item.Position.X and Player.Position.Y > item.Position.Y: Player.Run('Up')
                elif Player.Position.X > item.Position.X and Player.Position.Y < item.Position.Y: Player.Run('Left')
                elif Player.Position.X > item.Position.X and Player.Position.Y == item.Position.Y: Player.Run('West')
                elif Player.Position.X < item.Position.X and Player.Position.Y > item.Position.Y: Player.Run('Right')
                elif Player.Position.X < item.Position.X and Player.Position.Y < item.Position.Y: Player.Run('Down')
                elif Player.Position.X < item.Position.X and Player.Position.Y == item.Position.Y: Player.Run('East')
                elif Player.Position.X == item.Position.X and Player.Position.Y > item.Position.Y: Player.Run('North')
                elif Player.Position.X == item.Position.X and Player.Position.Y < item.Position.Y: Player.Run('South')

# =============================================================================
# [게이트 탑승 - 리더가 열어준 게이트 자동 탑승]
# =============================================================================
def Moongatet():
    global gate_cooldown, locked_gate_serial, current_map, gate_watch_active, gate_watch_start, ignored_gate_serials

    # 1. 맵 이동 감지 (역행 방지: 5초 잠금)
    if Player.Map != current_map:
        current_map        = Player.Map
        gate_cooldown      = time.time() + 5
        locked_gate_serial = None
        gate_watch_active  = False
        Player.ChatSay(68, "★게이트 이동★")
        trim_working_set()
        return

    if time.time() < gate_cooldown:
        return

    # 2. 리더 및 파티원 게이트 주문 자동 감지 (발화자 확인 강화)
    if not gate_watch_active and not locked_gate_serial:
        # 감시 대상: 리더 + 파티원(extra_party)
        watch_serials = [leader] + extra_party
        
        for s in watch_serials:
            m = Mobiles.FindBySerial(s)
            name = m.Name if m else ""
            if not name: continue
            
            # SearchByName으로 발화자와 키워드 동시 체크
            if Journal.SearchByName("Vas Rel", name) or Journal.SearchByName("Gate Travel", name):
                Journal.Clear() # 인식 즉시 초기화
                
                # [중요] 주문 발화 시점에 이미 열려있는 게이트들을 스냅샷하여 무시 목록에 추가
                existing_gates = Items.FindAllByID([0x0F6C, 0x0DDA], -1, -1, 5)
                ignored_gate_serials = set(g.Serial for g in existing_gates)
                
                gate_watch_active = True
                gate_watch_start  = time.time()
                Player.ChatSay(158, "★게이트 포착★")
                break

    # 3. 탐색 창 활성 중 게이트 스캔 (주문 이후 생성된 게이트 선별)
    if gate_watch_active and not locked_gate_serial:
        if time.time() - gate_watch_start > 12: 
            gate_watch_active = False
            Player.ChatSay(33, "★게이트 타임아웃★")
        else:
            # 주변 5타일 게이트 스캔
            gates = Items.FindAllByID([0x0F6C, 0x0DDA], -1, -1, 5)
            # 스냅샷 시점에 없었던 신규 게이트만 선별
            new_gates = [g for g in gates if g.Serial not in ignored_gate_serials]
            
            if new_gates:
                locked_gate_serial = new_gates[0].Serial
                gate_watch_active  = False
                Player.ChatSay(158, "[시스템] 신규 게이트 포착: 시리얼 박제 완료")

    # 4. 박제된 시리얼 탑승 (맵 이동 전까지 유지)
    if locked_gate_serial:
        target = Items.FindBySerial(locked_gate_serial)
        if target:
            if Player.DistanceTo(target) > 0:
                PathFinding.RunPath(PathFinding.GetPath(target.Position.X, target.Position.Y, -1), 500)
            else:
                Items.UseItem(target)
                if Gumps.WaitForGump(0xdd8b146a, 1500):
                    Gumps.SendAction(0xdd8b146a, 1)
                Misc.IgnoreObject(target) # 중복 클릭 방지
                # locked_gate_serial = None 를 여기서 하지 않음 (바드봇 방식: 맵 이동 시까지 고정)
        else:
            # 게이트가 사라졌음에도 맵 이동이 안 되었다면 해제
            locked_gate_serial = None

# =============================================================================
# [Sacred Journey 이동]
# 룬북 열기 → 검프 0x59 → 버튼 10번부터 순서대로 1~16번 룬
# =============================================================================
def run_sacred(idx):
    rb = Items.FindBySerial(runebook)
    if not rb:
        Player.ChatSay(33, "[오류] 룬북을 찾을 수 없습니다.")
        return
    Items.UseItem(rb)
    if Gumps.WaitForGump(0x59, 2000):
        action_id = 10 + (idx - 1)
        Gumps.SendAction(0x59, action_id)
        Misc.Pause(500)
        Gumps.CloseGump(0x59)
        Player.ChatSay(158, "★순례 {}번위치★".format(idx))
    else:
        Player.ChatSay(33, "[오류] 룬북 검프가 열리지 않았습니다. 검프 ID 확인 필요.")

# =============================================================================
# [팔로잉]
# =============================================================================
def following():
    global last_leader_x, last_leader_y, last_leader_dir, leader_lost_time, leader_chase_done, patrol_angle, champ_anchor_x, champ_anchor_y

    # 챔프 앵커 모드: 리더 팔로우 대신 앵커 기반 이동
    if bot_mode == "champ" and champ_anchor_x != 0:
        fil = Mobiles.Filter()
        fil.RangeMax = champ_anchor_radius + combat_range
        fil.CheckLineOfSight = True
        nearby = Mobiles.ApplyFilter(fil)
        anchor_enemies = [
            m for m in nearby
            if m and m.Notoriety >= 3
            and m.Serial != Player.Serial
            and m.Serial != leader
            and m.Serial not in extra_party
            and m.Serial not in extra_pets
            and abs(m.Position.X - champ_anchor_x) <= champ_anchor_radius
            and abs(m.Position.Y - champ_anchor_y) <= champ_anchor_radius
        ]
        if anchor_enemies:
            nearest = min(anchor_enemies, key=lambda m: Player.DistanceTo(m))
            if Player.DistanceTo(nearest) > combat_range - 2:
                dx = nearest.Position.X - Player.Position.X
                dy = nearest.Position.Y - Player.Position.Y
                direction = calculateDirection(dx, dy)
                if direction:
                    Player.Run(direction)
        else:
            # 적 없음 → 앵커로 복귀
            dist_to_anchor = max(abs(Player.Position.X - champ_anchor_x), abs(Player.Position.Y - champ_anchor_y))
            if dist_to_anchor > distanceleader:
                dx = champ_anchor_x - Player.Position.X
                dy = champ_anchor_y - Player.Position.Y
                direction = calculateDirection(dx, dy)
                if direction:
                    Player.Run(direction)
        return

    DIR_DELTA = {
        'North': (0, -6), 'South': (0,  6),
        'East':  (6,  0), 'West':  (-6, 0),
        'Down':  (4,  4), 'Up':    (-4, -4),
        'Right': (4, -4), 'Left':  (-4,  4),
    }

    leadman = Mobiles.FindBySerial(leader)

    if leadman:
        if not leadman.IsGhost:
            # 리더 위치 및 이동 방향 갱신
            if last_leader_x != 0:
                dx_t = leadman.Position.X - last_leader_x
                dy_t = leadman.Position.Y - last_leader_y
                if dx_t != 0 or dy_t != 0:
                    d = calculateDirection(dx_t, dy_t)
                    if d:
                        last_leader_dir = d
            last_leader_x     = leadman.Position.X
            last_leader_y     = leadman.Position.Y
            leader_lost_time  = 0.0
            leader_chase_done = False

        if bot_mode == "champ":
            dist_limit = champ_mode_range
        elif in_combat:
            dist_limit = distanceleader_combat
        else:
            dist_limit = distanceleader
        if Player.InRangeMobile(leadman, 30):
            if not Player.InRangeMobile(leadman, dist_limit):
                if usepathfinding == 1:
                    if not Player.InRangeMobile(leader, pathfinddistance):
                        leaderserial = Mobiles.FindBySerial(leader)
                        if leaderserial is not None:
                            Player.ChatSay(158, '[알림] PathFinding 이동')
                            leaderroute = PathFinding.GetPath(
                                leaderserial.Position.X, leaderserial.Position.Y, -1)
                            PathFinding.RunPath(leaderroute, 1500)
                dx = leadman.Position.X - Player.Position.X
                dy = leadman.Position.Y - Player.Position.Y
                direction = calculateDirection(dx, dy)
                if direction:
                    Player.Run(direction)
    else:
        # 리더 소실 — 2초 후 마지막 방향으로 6타일 1회 이동
        if leader_lost_time == 0.0:
            leader_lost_time = time.time()

        if not leader_chase_done and last_leader_x != 0 and last_leader_dir:
            if time.time() - leader_lost_time >= 2.0:
                ddx, ddy = DIR_DELTA.get(last_leader_dir, (0, 0))
                target_x = last_leader_x + ddx
                target_y = last_leader_y + ddy
                leader_chase_done = True
        elif not leader_chase_done and last_leader_x == 0:
            Misc.Pause(1000)

# =============================================================================
# [카이팅 이동 - 무빙샷 유지]
# 전투 상태를 유지하면서 접근 적 반대 방향으로만 이동
# =============================================================================
last_kite_msg_time = 0.0  # 카이팅 메시지 스팸 방지

def kite_move():
    global last_kite_msg_time
    effective_evade = max_mode_range if bot_mode == "max" else evade_range
    fil = Mobiles.Filter()
    fil.RangeMax = effective_evade
    fil.CheckLineOfSight = True
    nearby_mobs = Mobiles.ApplyFilter(fil)

    threats = [m for m in nearby_mobs
               if m is not None
               and m.Serial != Player.Serial
               and m.Serial != leader
               and m.Serial not in extra_party
               and m.Serial not in extra_pets
               and m.Notoriety >= 3
               and m.WarMode]

    if not threats:
        return False

    threats.sort(key=lambda m: Player.DistanceTo(m))

    # 모든 위협의 무게중심 기준으로 반대 방향 계산 → 양방향 적에 의한 진동 방지
    avg_x = sum(m.Position.X for m in threats) / len(threats)
    avg_y = sum(m.Position.Y for m in threats) / len(threats)
    dx = Player.Position.X - avg_x
    dy = Player.Position.Y - avg_y
    if abs(dx) < 0.1 and abs(dy) < 0.1:
        dx = 1
    direction = calculateDirection(int(round(dx)), int(round(dy)))
    if direction:
        Player.Run(direction)

    return True

# =============================================================================
# [펫 소환 / 먹이]
# =============================================================================
def check_pet_hp():
    global pet_follow_mode, pet_follow_attempts, pet_follow_last_try
    if not mypet: return
    pet = Mobiles.FindBySerial(mypet)
    if not pet or pet.IsGhost or pet.HitsMax <= 0: return
    hp_pct = float(pet.Hits) / float(pet.HitsMax)
    if pet_follow_mode:
        # 60% 이상 회복 → guard me 복귀
        if hp_pct >= 0.70:
            pet_follow_mode     = False
            pet_follow_attempts = 0
            Player.ChatSay("all guard me")
            Player.HeadMessage(68, "★펫 체력 회복 → guard me★")
            return
        # 2타일 이내 접근 → 명령 성공, 회복 대기
        if Player.InRangeMobile(pet, 2): return
        # 미접근 + 3회 미만 → 재시도 (4초 쿨)
        if pet_follow_attempts < 3 and time.time() - pet_follow_last_try >= 4.0:
            Player.ChatSay("all follow me")
            pet_follow_attempts += 1
            pet_follow_last_try  = time.time()
            Player.HeadMessage(33, "★펫 HP {}% follow me ({}/3)★".format(int(hp_pct * 100), pet_follow_attempts))
    else:
        # 40% 미만 감지 → follow me 첫 발령
        if hp_pct < 0.55:
            pet_follow_mode     = True
            pet_follow_attempts = 1
            pet_follow_last_try = time.time()
            Player.ChatSay("all follow me")
            Player.HeadMessage(33, "★펫 HP {}% → follow me (1/3)★".format(int(hp_pct * 100)))

def summon_pet():
    crystal_ball = Items.FindByID(0x0E2E, -1, Player.Backpack.Serial)
    if crystal_ball:
        Items.UseItem(crystal_ball)
        Player.ChatSay(68, "★비둘기 소환★")
        Misc.Pause(1000)
    else:
        Player.HeadMessage(33, "크리스탈 볼 없음!")

def feed_pet():
    pet = Mobiles.FindBySerial(mypet)
    if not pet:
        return
    
    # 내 백팩 내부 전체를 재귀적으로 검색하여 첫 번째 먹이 발견
    found_items = Items.FindAllByID(pet_food, -1, Player.Backpack.Serial, True)
    if found_items:
        food_item = found_items[0]
        # 이름 확보 시도
        food_name = food_item.Name
        if not food_name:
            Mobiles.WaitForProps(food_item.Serial, 200)
            food_name = food_item.Name if food_item.Name else "Food(ID:{:#06x})".format(food_item.ItemID)
            
        Items.Move(food_item, mypet, 1)
        Player.ChatSay(68, "★비둘기야 밥먹자★")
        Misc.Pause(500)
    else:
        Player.HeadMessage(33, "펫 먹이 없음!")

# =============================================================================
# [저주 해제 - 셀프 전용]
# 타인 저주 감지는 API 한계로 불가 → 추후 채팅 도움요청 감지 방식으로 추가 예정
# =============================================================================
def remove_curse_check():
    CURSE_BUFFS = ['Curse', 'Evil Omen', 'Strangle', 'Mana Vampire', 'Blood Oath']
    for buff_name in CURSE_BUFFS:
        if Player.BuffsExist(buff_name):
            Spells.CastChivalry("Remove Curse")
            if Target.WaitForTarget(2000):
                Target.TargetExecute(Player.Serial)
            smart_pause(800)
            return

# =============================================================================
# [버프 관리 - 전투 중에만 유지]
# 우선순위:
#   1. 최대 스태미너 감소 감지 → Remove Curse
#   2. Consecrate Weapon
#   3. Divine Fury (스태미너 임계값 이하 + 버프 없을 때)
#   4. Armor Ignore 상시 모드 (Player.WeaponPrimarySA 또는 SecondarySA)
#      → 무기의 Armor Ignore 슬롯에 따라 아래 주석 참고
# =============================================================================
def combat_buffs():
    global stam_max_baseline

    # --- 1순위: 최대 스태미너 감소 감지 → 저주 추가 감지 보조 ---
    if stam_max_baseline == 0:
        stam_max_baseline = Player.StamMax
    elif Player.StamMax < stam_max_baseline - 5:
        Spells.CastChivalry("Remove Curse")
        if Target.WaitForTarget(2000):
            Target.TargetExecute(Player.Serial)
        smart_pause(800)
        stam_max_baseline = Player.StamMax
        return
    else:
        if Player.StamMax > stam_max_baseline:
            stam_max_baseline = Player.StamMax

    # --- 2순위: Consecrate Weapon ---
    if not Player.BuffsExist('Consecrate Weapon'):
        Spells.CastChivalry("Consecrate Weapon")
        smart_pause(600)

    # --- 3순위: Divine Fury (스태미너 임계값 이하 + 버프 없을 때) ---
    if not Player.BuffsExist('Divine Fury'):
        if Player.Stam < stam_threshold:
            Spells.CastChivalry("Divine Fury")
            smart_pause(600)

    # --- 4순위: Armor Ignore 상시 유지 모드 ---
    if armor_ignore_always:
        if (current_lock or locked_target_serial) and not Player.HasPrimarySpecial:
            Player.WeaponPrimarySA()

# =============================================================================
# [자동 전투 로직]
# =============================================================================
def auto_combat():
    global locked_target_serial, in_combat, current_lock

    fil = Mobiles.Filter()
    fil.RangeMax = champ_mode_range if bot_mode == "champ" else combat_range
    fil.CheckLineOfSight = True
    nearby_mobs = Mobiles.ApplyFilter(fil)

    valid_mobs = []
    for m in nearby_mobs:
        if m is None: continue
        if m.Serial == Player.Serial: continue
        if m.Serial == leader: continue
        if m.Serial in extra_party: continue
        if m.Serial in extra_pets: continue
        if bot_mode in ("champ", "aggro"):
            if m.Notoriety >= 3:
                valid_mobs.append(m)
        else:
            if m.Notoriety >= 3 and m.WarMode:
                valid_mobs.append(m)

    # 챔프 앵커 모드: 앵커 반경 밖의 적은 무시
    if bot_mode == "champ" and champ_anchor_x != 0:
        valid_mobs = [
            m for m in valid_mobs
            if abs(m.Position.X - champ_anchor_x) <= champ_anchor_radius + 2
            and abs(m.Position.Y - champ_anchor_y) <= champ_anchor_radius + 2
        ]

    if not valid_mobs:
        if in_combat:
            in_combat = False
            locked_target_serial = 0
            Player.SetWarMode(False)
            # all guard me는 점사(current_lock) 종료 시에만 combat_logic에서 발동
            # 자동 전투 종료 시에는 펫 명령 불필요 (guard me 상태 유지 중)
        return

    if not in_combat:
        in_combat = True

    if not Player.WarMode:
        Player.SetWarMode(True)
        Misc.Pause(100)

    # 점사 중이면 자동 타겟 선정 건너뜀
    if current_lock:
        return

    # 자동 타겟: 기존 고정 타겟 유지 우선, 없으면 가장 가까운 적
    target_mob = None
    if locked_target_serial != 0:
        for m in valid_mobs:
            if m.Serial == locked_target_serial:
                target_mob = m
                break

    if target_mob is None:
        lead_mob = Mobiles.FindBySerial(leader)
        if lead_mob:
            valid_mobs.sort(key=lambda m: lead_mob.DistanceTo(m))
        else:
            valid_mobs.sort(key=lambda m: Player.DistanceTo(m))
        target_mob = valid_mobs[0]
        locked_target_serial = target_mob.Serial

    Player.Attack(target_mob)

# =============================================================================
# [점사 로직 - 리더 명령에 의한 타겟 고정]
# =============================================================================
def combat_logic():
    global current_lock, target_start_time

    if not current_lock:
        return

    mob = Mobiles.FindBySerial(current_lock)

    if not mob:
        Player.ChatSay("all guard me")
        current_lock = None
        return

    if mob.Hits <= 0:
        if time.time() - target_start_time < 1.5:
            if (int(time.time() * 10) % 5 == 0):
                Mobiles.WaitForProps(mob, 200)
                Target.SetLast(mob)
            return
        Player.ChatSay("all guard me")
        current_lock = None
        return

    # 극딜: 점사 중 Armor Ignore 상시 모드 무관하게 항상 사용
    if not Player.HasPrimarySpecial:
        Player.WeaponPrimarySA()

# =============================================================================
# [치유 - 현재 미구현 (전사는 메저리 없음)]
# =============================================================================
def heal_check():
    pass

# =============================================================================
# [뱀파이어폼 / 비행 — 가고일 전용]
# =============================================================================
def cast_vampiric_embrace():
    """뱀파이어폼 없으면 시전. 피즐 시 최대 10회 재시도."""
    if Player.BuffsExist('Vampiric Embrace'):
        return
    Player.ChatSay(68, "★뱀파이어폼 시전 중★")
    for _ in range(10):
        if Player.BuffsExist('Vampiric Embrace'):
            Player.ChatSay(68, "★뱀파이어폼 ON★")
            return
        Spells.CastNecro("Vampiric Embrace")
        if Target.WaitForTarget(2000, False):
            Target.TargetExecute(Player.Serial)
        Misc.Pause(1500)
    Player.ChatSay(33, "★뱀파이어폼 시전 실패★")

def activate_fly():
    """비행 중이 아니면 Fly 활성화."""
    mob = Mobiles.FindBySerial(Player.Serial)
    if mob and mob.Flying:
        return
    Player.Fly(True)
    Misc.Pause(500)
    mob = Mobiles.FindBySerial(Player.Serial)
    if mob and mob.Flying:
        Player.ChatSay(68, "★비행 ON★")
    else:
        Player.ChatSay(33, "★비행 활성화 실패★")

# =============================================================================
# [명령어 처리]
# =============================================================================
def command_handler():
    global current_lock, target_start_time, pending_action, config, leader, runebook, extra_party, extra_pets, mypet
    global armor_ignore_always, gate_watch_active, gate_watch_start, bot_mode, patrol_angle
    global sanghacha_mode, sanghacha_protected, champ_anchor_x, champ_anchor_y
    global ps_sort_mode, pink_sort_mode, skull_sort_mode, gate_mode
    global bot_paused, following_mode, in_combat, locked_target_serial

    # 예약된 행동 처리
    if pending_action is not None:
        if pending_action == 'feed':
            feed_pet()
        elif pending_action == 'enemy':
            if not Player.BuffsExist('Enemy Of One'):
                Player.ChatSay(158, "★보스전 돌입★")
                Spells.CastChivalry("Enemy of One")
                smart_pause(600)
        elif pending_action == 'enemy_off':
            if Player.BuffsExist('Enemy Of One'):
                Spells.CastChivalry("Enemy of One")
                smart_pause(600)
        elif isinstance(pending_action, tuple) and pending_action[0] == 'sanghacha':
            _, container_serial = pending_action
            do_sanghacha(container_serial, sanghacha_protected, pet_food)
            sanghacha_mode = False
        elif isinstance(pending_action, int):
            mob = Mobiles.FindBySerial(pending_action)
            if mob:
                current_lock      = pending_action
                target_start_time = time.time()
                Player.ChatSay(68, "★일제사격 : {}★".format(mob.Name))
                Target.Cancel()
                Player.ChatSay("all kill")
                if Target.WaitForTarget(500):
                    Target.TargetExecute(mob)
        pending_action = None
        return

    # 일시정지 / 재개
    if _lcmd("!정지"):
        Journal.Clear()
        bot_paused = True
        Player.ChatSay(33, "★일시정지★")
        return
    if _lcmd("!재개"):
        Journal.Clear()
        bot_paused = False
        Player.ChatSay(68, "★재개★")
        return
    if _lcmd("!팔로우"):
        Journal.Clear()
        following_mode = True
        in_combat = False
        current_lock = None
        locked_target_serial = 0
        Player.SetWarMode(False)
        Player.ChatSay("all follow me")
        Player.ChatSay(68, "★팔로잉 모드★")
        return

    # 전투 모드 전환
    if _lcmd("!max"):
        Journal.Clear()
        bot_mode = "max"
        following_mode = False
        Player.ChatSay(68, "★MAX 모드: 원거리 유지 {}타일★".format(max_mode_range))
        return
    if _lcmd("!선공"):
        Journal.Clear()
        bot_mode = "aggro"
        following_mode = False
        Player.ChatSay(68, "★선공 모드★")
        return
    if _lcmd("!챔프 {}".format(Player.Name)):
        Journal.Clear()
        champ_anchor_x = Player.Position.X
        champ_anchor_y = Player.Position.Y
        bot_mode = "champ"
        following_mode = False
        Player.HeadMessage(68, "★챔프 앵커 ({},{}) 반경{}★".format(champ_anchor_x, champ_anchor_y, champ_anchor_radius))
        return
    if _lcmd("!정상화"):
        Journal.Clear()
        bot_mode = "normal"
        following_mode = False
        champ_anchor_x = 0
        champ_anchor_y = 0
        Player.ChatSay("all guard me")
        Player.ChatSay(33, "★일반 모드 복귀★")
        return

    # 상하차 명령
    if _lcmd("!상하차"):
        Journal.Clear()
        if sanghacha_mode:
            sanghacha_mode = False
            Player.HeadMessage(33, "[상하차 취소]")
        else:
            sanghacha_mode = True
            Player.HeadMessage(68, "[상하차 대기: 컨테이너 지정 대기]")
        return

    # 재설정
    if _lcmd("!설정"):
        Journal.Clear()
        config      = run_setup()
        leader      = config['leader']
        runebook    = config['runebook']
        extra_party = config.get('party', [])
        extra_pets  = config.get('pets', [])
        mypet       = extra_pets[0] if extra_pets else None
        return

    # 펫 소환
    if _lcmd("!소환"):
        Journal.Clear()
        summon_pet()
        return

    # 펫 먹이
    if _lcmd("!밥줘"):
        Journal.Clear()
        feed_pet()
        return

    # Enemy of One 해제 (먼저 체크)
    if _lcmd("!에너미오프"):
        Journal.Clear()
        if Player.BuffsExist('Enemy Of One'):
            Spells.CastChivalry("Enemy of One")
            smart_pause(600)
        return

    # Enemy of One 발동 (버프 없을 때만)
    if _lcmd("!에너미"):
        Journal.Clear()
        if not Player.BuffsExist('Enemy Of One'):
            Player.ChatSay(158, "★보스전 돌입★")
            Spells.CastChivalry("Enemy of One")
            smart_pause(600)
        else:
            Player.HeadMessage(68, "[에너미 이미 활성]")
        return

    # Armor Ignore 상시 모드 토글
    if _lcmd("!아머"):
        Journal.Clear()
        armor_ignore_always = not armor_ignore_always
        Player.ChatSay(66, "★아머:{}★".format("On" if armor_ignore_always else "Off"))
        return

    # 골드 수집 — 송금모드 ON인 캐릭터만 반응
    if _lcmd("!송금"):
        Journal.Clear()
        if loot_mode:
            handle_loot("★앵벌이 시작★", "★골드 수집 완료★")
        return

    if _lcmd("!sell"):
        Journal.Clear()
        sell_powerscrolls(NPC_SELL, SELL_AGENT_LIST_NAME)
        return

    if _lcmd("!trash"):
        Journal.Clear()
        Player.ChatSay(158, "★트래쉬 오거나이저 실행★")
        Organizer.RunOnce(TRASH_ORGANIZER_NAME, -1, -1, 800)
        Player.ChatSay(68, "★트래쉬 완료★")
        return

    if _lcmd("!파스정리"):
        Journal.Clear()
        if ps_sort_mode:
            ps_sort_mode = False
            Player.ChatSay(33, "★파스정리 취소★")
        else:
            ps_sort_mode = True
            Player.ChatSay(158, "★파스정리 대기: 리더가 컨테이너 시리얼 전달 요망★")
        return

    if _lcmd("!분홍정리"):
        Journal.Clear()
        if pink_sort_mode:
            pink_sort_mode = False
            Player.ChatSay(33, "★분홍정리 취소★")
        else:
            pink_sort_mode = True
            Player.ChatSay(158, "★분홍정리 대기: 리더가 컨테이너 시리얼 전달 요망★")
        return

    if _lcmd("!해골정리"):
        Journal.Clear()
        if skull_sort_mode:
            skull_sort_mode = False
            Player.ChatSay(33, "★해골정리 취소★")
        else:
            skull_sort_mode = True
            Player.ChatSay(158, "★해골정리 대기: 리더가 아이템 시리얼 전달 요망★")
        return
    if _lcmd("!게이트"):
        Journal.Clear()
        gate_mode = True
        Player.ChatSay(158, "★게이트 대기: 리더가 게이트 시리얼 전달 요망★")
        return
    if _lcmd("!헬프"):
        Journal.Clear()
        do_help_escape()
        return

    if _lcmd("!뱀폼"):
        Journal.Clear()
        cast_vampiric_embrace()
        return

    if _lcmd("!날아"):
        Journal.Clear()
        activate_fly()
        return

    # 점사 타겟 (0x 시리얼) — 리더가 발화한 경우에만 반응
    if Journal.Search("0x"):
        lead_mob    = Mobiles.FindBySerial(leader)
        leader_name = lead_mob.Name if lead_mob else ""
        
        # SearchByName으로 발화자와 시리얼 동시 확인
        if leader_name and Journal.SearchByName("0x", leader_name):
            line = Journal.GetLineText("0x", True) # 이름 포함해서 획득
            m = re.search(r"0x[0-9a-fA-F]+", line.lower())
            if m:
                val = int(m.group(), 16)
                Journal.Clear()
                # 컨테이너 모드: 시리얼을 컨테이너로 인식
                if sanghacha_mode:
                    container = Items.FindBySerial(val)
                    if container:
                        Player.ChatSay(68, "★상하차 컨테이너 인식★")
                        do_sanghacha(val, sanghacha_protected, pet_food)
                    else:
                        Player.ChatSay(33, "★컨테이너 인식 실패★")
                    sanghacha_mode = False
                    sanghacha_protected = set()
                    return
                elif ps_sort_mode:
                    container = Items.FindBySerial(val)
                    if container:
                        Player.ChatSay(68, "★파스정리 컨테이너 인식★")
                        do_item_sort(0x14F0, 0x0496, val)
                    else:
                        Player.ChatSay(33, "★컨테이너 인식 실패★")
                    ps_sort_mode = False
                    return
                elif pink_sort_mode:
                    container = Items.FindBySerial(val)
                    if container:
                        Player.ChatSay(68, "★분홍정리 컨테이너 인식★")
                        do_item_sort(0x14EF, 0x0490, val)
                    else:
                        Player.ChatSay(33, "★컨테이너 인식 실패★")
                    pink_sort_mode = False
                    return
                elif skull_sort_mode:
                    Player.ChatSay(68, "★해골정리 아이템 인식★")
                    do_skull_sort(val)
                    skull_sort_mode = False
                    return
                elif gate_mode:
                    Player.ChatSay(68, "★게이트 이동★")
                    do_gate(val)
                    gate_mode = False
                    return
                # 일반 점사 타겟
                mob = Mobiles.FindBySerial(val)
                if mob:
                    current_lock      = val
                    target_start_time = time.time()
                    # 0x ID 미출력 — 봇 간 복창 루프 방지
                    Player.ChatSay(68, "★일제사격 : {}★".format(mob.Name))
                    Target.Cancel()
                    Player.ChatSay("all kill")
                    if Target.WaitForTarget(500):
                        Target.TargetExecute(mob)
                    Player.Attack(mob) # 전사 직접 공격 추가
                    return

    # Sacred Journey (!s번호)
    sj_match = None
    if _lcmd("!s") or _lcmd("!S"):
        line = Journal.GetLineText("").lower()
        sj_match = re.search(r"!s(\d+)", line)
    if sj_match:
        Journal.Clear()
        run_sacred(int(sj_match.group(1)))
        return

# =============================================================================
# [초기화]
# =============================================================================
Player.ChatSay("all guard me")
Misc.Pause(500)
Journal.Clear()
stam_max_baseline = Player.StamMax

Player.ChatSay(66, "▶ [GGO_쓰로잉봇 v1.2 가동]")
Player.ChatSay(66, "▶ 최대 스태미너 기준: {}".format(stam_max_baseline))

# 하위 가방 내용물 동기화 (보호 리스트 등록 전)
init_backpack_containers()

# Vendor Sell 에이전트 자동 활성화
try:
    SellAgent.ChangeList(SELL_AGENT_LIST_NAME)
    SellAgent.Enable()
    Player.ChatSay(68, "★Vendor Sell [{}] 활성화★".format(SELL_AGENT_LIST_NAME))
except:
    pass

# 상하차 보호 리스트 초기화 (스크립트 시작 시점 백팩 스냅샷)
sanghacha_protected = collect_all_items(Player.Backpack.Serial)
Player.ChatSay(66, "▶ 상하차 보호 등록: {}개".format(len(sanghacha_protected)))

# 초기 버프 활성화 (뱀파이어폼 → 비행 순)
cast_vampiric_embrace()
activate_fly()

draw_menu()

# =============================================================================
# [메인 루프]
# =============================================================================
while True:

    # ── 리더 일시정지 대기 ──
    while bot_paused:
        command_handler()
        Misc.Pause(500)

    # ── 검프 메뉴 처리 ──
    handle_menu()

    # ── 사망 / 부활 / 시체 추적 ──
    if Player.IsGhost and not revival_state['was_ghost']:
        in_combat            = False
        current_lock         = None
        locked_target_serial = 0
    if handle_revival(revival_state, dress_name, use_undertaker=use_undertaker_staff):
        lead = Mobiles.FindBySerial(leader)
        if lead and Player.DistanceTo(lead) > distanceleader:
            Player.SetWarMode(True)
            following()
        Misc.Pause(500)
        continue
    if revival_state['just_revived']:
        Player.ChatSay("all guard me")
        stam_max_baseline = Player.StamMax

    # ── 일반 루프 ──
    command_handler()
    check_pet_hp()

    if is_running:
        combat_logic()
        if not following_mode:
            auto_combat()

        if (in_combat and not following_mode) or current_lock:
            combat_buffs()
            remove_curse_check()

        # ── 강제 복귀: 전투 중 5초 이상 리더 이탈 시 PathFinding (3초 후 자동 해제) ──
        lead = Mobiles.FindBySerial(leader)
        force_return = False
        if lead and not lead.IsGhost and in_combat:
            if not Player.InRangeMobile(lead, distanceleader_combat):
                if leader_separated_time == 0.0:
                    leader_separated_time = time.time()
                elif time.time() - leader_separated_time >= 5.0:
                    if escape_start_time == 0.0:
                        escape_start_time = time.time()
                    if time.time() - escape_start_time >= 3.0:
                        # 3초 경과 → 강제복귀 종료, 타이머 초기화
                        leader_separated_time = 0.0
                        escape_start_time = 0.0
                    else:
                        Player.HeadMessage(33, "★강제 복귀★")
                        route = PathFinding.GetPath(lead.Position.X, lead.Position.Y, -1)
                        PathFinding.RunPath(route, 1500)
                        leader_separated_time = 0.0
                        escape_start_time = 0.0
            else:
                leader_separated_time = 0.0
                escape_start_time = 0.0
        else:
            leader_separated_time = 0.0
            escape_start_time = 0.0

        if not force_return:
            if following_mode:
                following()
                if lead and Player.InRangeMobile(lead, 12):
                    autoparty()
            else:
                kiting = kite_move()
                if not kiting:
                    following()
                    if lead and Player.InRangeMobile(lead, 12):
                        findtile()
                        heal_check()
                        autoparty()
        Moongatet()

    if time.time() - last_trim_time >= 30:
        trim_working_set()
        last_trim_time = time.time()

    Misc.Pause(100)
