# -*- coding: utf-8 -*-
# =============================================================================
# [바울 바드봇 인핸스 1.2] - Stable Integrated (Rebuild)
# 바보울온님의 원작 코드를 100% 무결하게 유지하면서 다음 기능만 이식했습니다.
# =============================================================================

SCRIPT_ID = "GGO_BARD"
SCRIPT_NAME = "GGO_바울바드봇인핸스"
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
# GGO_Settings/GGO_바울바드봇인핸스/script_settings.json에서 수정하세요.
# =============================================================================
musicbuff        = 1  # 1: 프롭버프(딜), 0: 피스버프(생존)
protection       = 1  # 1: 마법 차단 방지(Protection) 버프 자동 유지
usepathfinding   = 0  # 1: 지능형 길찾기 사용
doomtile         = 1  # 1: 둠 던전 타일 자동 인식
veterinary       = 0  # 1: 펫 부활(붕대) 사용
pathfinddistance = 8
distanceleader   = 2
instrument       = [0x0EB3, 0x0E9C, 0x0EB2, 0x0E9D, 0x2805, 0xe9d, 0x315C]
pet_food         = [
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
dress_name            = "luck"
use_undertaker_staff  = True  # True: 부활 시 장의사 지팡이(0x13F8) 사용
SELL_AGENT_LIST_NAME  = "ps"          # Vendor Sell 에이전트 목록 이름
NPC_SELL              = 0x0000DE29    # 파워스크롤 판매 NPC 시리얼
TRASH_ORGANIZER_NAME  = "trash"       # Organizer 에이전트 목록 이름

BARD_SCRIPT_SETTINGS_DEFAULTS = {
    "musicbuff": musicbuff,
    "protection": protection,
    "usepathfinding": usepathfinding,
    "doomtile": doomtile,
    "veterinary": veterinary,
    "pathfinddistance": pathfinddistance,
    "distanceleader": distanceleader,
    "instrument": instrument,
    "pet_food": pet_food,
    "dress_name": dress_name,
    "use_undertaker_staff": use_undertaker_staff,
    "sell_agent_list_name": SELL_AGENT_LIST_NAME,
    "npc_sell": NPC_SELL,
    "trash_organizer_name": TRASH_ORGANIZER_NAME
}

BARD_SCRIPT_SETTINGS_ORDER = [
    "musicbuff",
    "protection",
    "usepathfinding",
    "doomtile",
    "veterinary",
    "pathfinddistance",
    "distanceleader",
    "instrument",
    "pet_food",
    "dress_name",
    "use_undertaker_staff",
    "sell_agent_list_name",
    "npc_sell",
    "trash_organizer_name"
]

BARD_SCRIPT_SETTINGS_GUIDE = """GGO_바울바드봇인핸스 script_settings.json 설명

이 파일은 바드봇의 공용 설정 파일입니다.
숫자는 숫자로, true/false는 반드시 소문자로 입력하세요.
쉼표는 지우지 마세요.

musicbuff:
  1 = 프롭/딜 버프, 0 = 피스/생존 버프입니다.

protection:
  1 = Protection 버프 자동 유지, 0 = 사용 안 함입니다.

usepathfinding:
  1 = 리더 추적 시 PathFinding 사용, 0 = 일반 이동입니다.

doomtile:
  1 = 둠 던전 타일 자동 인식 사용, 0 = 사용 안 함입니다.

veterinary:
  1 = 펫 부활 붕대 사용, 0 = 사용 안 함입니다.

pathfinddistance:
  PathFinding을 시도할 리더와의 거리입니다.

distanceleader:
  리더와 유지할 거리입니다.

instrument:
  사용할 악기 아이템 ID 목록입니다.

pet_food:
  펫 먹이로 사용할 아이템 ID 목록입니다.

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
    ensure_script_settings_guide(SCRIPT_NAME, BARD_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, BARD_SCRIPT_SETTINGS_DEFAULTS, BARD_SCRIPT_SETTINGS_ORDER)
    musicbuff = _setting_int(_script_settings.get("musicbuff", musicbuff), musicbuff)
    protection = _setting_int(_script_settings.get("protection", protection), protection)
    usepathfinding = _setting_int(_script_settings.get("usepathfinding", usepathfinding), usepathfinding)
    doomtile = _setting_int(_script_settings.get("doomtile", doomtile), doomtile)
    veterinary = _setting_int(_script_settings.get("veterinary", veterinary), veterinary)
    pathfinddistance = _setting_int(_script_settings.get("pathfinddistance", pathfinddistance), pathfinddistance)
    distanceleader = _setting_int(_script_settings.get("distanceleader", distanceleader), distanceleader)
    instrument = list(_script_settings.get("instrument", instrument))
    pet_food = list(_script_settings.get("pet_food", pet_food))
    dress_name = str(_script_settings.get("dress_name", dress_name))
    use_undertaker_staff = bool(_script_settings.get("use_undertaker_staff", use_undertaker_staff))
    SELL_AGENT_LIST_NAME = str(_script_settings.get("sell_agent_list_name", SELL_AGENT_LIST_NAME))
    NPC_SELL = _setting_int(_script_settings.get("npc_sell", NPC_SELL), NPC_SELL)
    TRASH_ORGANIZER_NAME = str(_script_settings.get("trash_organizer_name", TRASH_ORGANIZER_NAME))
except Exception:
    load_character_settings = None
    save_character_settings = None
    get_character_settings_path = None

# =============================================================================
# [내부 코드 — 수정 불필요]
# =============================================================================
APPDATA = os.environ['APPDATA']
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "BardBot")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "{}.json".format(Player.Name))
if get_character_settings_path:
    CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
    SAVE_DIR = os.path.dirname(CONFIG_FILE)
else:
    SAVE_DIR = LEGACY_SAVE_DIR
    CONFIG_FILE = LEGACY_CONFIG_FILE
MENU_GUMP_ID = 0x47471237

# 구동 모니터링 변수 (0.3 원본 변수 및 새 변수 통합)
current_lock         = None   
target_start_time    = 0 
pending_action       = None
gate_cooldown        = 0
self_gate_active     = False
locked_gate_serial   = None
watch_start_time     = 0
current_map          = 0
is_running           = True
loot_mode            = True

# 강화된 게이트 감시용 변수
gate_watch_active    = False
gate_watch_start     = 0.0
ignored_gate_serials = set()

# 생존 및 정비 상태
last_weight          = 0
revival_state        = make_revival_state()
locked_target_serial = 0
last_bard_time       = 0.0
BARD_COOLDOWN       = 6.0
current_bard_mode    = "Discordance"
discorded_mobs       = []

# 상하차 모드
sanghacha_mode       = False
sanghacha_protected  = set()
last_trim_time       = 0.0
bot_paused           = False  # 리더 일시정지 명령 상태
following_mode       = False  # 팔로잉 모드 (공격 억제, 리더 추적만)

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
# [v0.2 스타일 검프 UI]
# =============================================================================
def draw_menu():
    global is_running, current_bard_mode, loot_mode
    display_text, food_hue = "감지된 먹이 없음", 33
    found_items = Items.FindAllByID(pet_food, -1, Player.Backpack.Serial, True)
    if found_items:
        type_count = len(set(i.ItemID for i in found_items))
        total_amount = sum(i.Amount for i in found_items)
        f_item = found_items[0]
        food_name = f_item.Name if f_item.Name else "Food"
        display_text = "{} ({}종/{}개)".format(food_name, type_count, total_amount)
        food_hue = 68

    gump_w, gump_h = 280, 182
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddBackground(gd, 0, 0, gump_w, gump_h, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, gump_w, gump_h)
    Gumps.AddLabel(gd, 10, 10, 53, "GGO Bard Bot v1.2")
    Gumps.AddImageTiled(gd, 5, 28, gump_w - 10, 2, 9107)

    y = 38
    # ── [1행] 시작 / 재설정 ──
    start_btn_id = 40030 if not is_running else 40297
    start_btn_txt = "시작" if not is_running else "정지"
    Gumps.AddButton(gd, 8,  y, start_btn_id, start_btn_id + 1, 1, 1, 0)
    Gumps.AddLabel(gd,  42, y + 2, (68 if is_running else 33), start_btn_txt)
    Gumps.AddButton(gd, 148, y, 40021, 40022, 2, 1, 0)
    Gumps.AddLabel(gd,  182, y + 2, 53, "재설정")
    y += 32

    # ── [2행] 디코(프로보) / 먹이 재설정 ──
    Gumps.AddButton(gd, 8,  y, 40299, 40300, 5, 1, 0)
    Gumps.AddLabel(gd,  42, y + 2, (68 if current_bard_mode == "Discordance" else 53), ("디코 모드" if current_bard_mode == "Discordance" else "프로보 모드"))
    Gumps.AddButton(gd, 148, y, 40021, 40022, 3, 1, 0)
    Gumps.AddLabel(gd,  182, y + 2, 1152, "먹이 재설정")
    y += 32

    # ── [3행] 먹이 텍스트 ──
    Gumps.AddLabel(gd,  15,  y, food_hue, "현재먹이: " + display_text)
    y += 24

    # ── [4행] 송금 On/Off / 종료 ──
    Gumps.AddButton(gd, 8,   y, 40299, 40300, 4, 1, 0)
    Gumps.AddLabel(gd,  42,  y + 2, (68 if loot_mode else 33), ("송금: On" if loot_mode else "송금: Off"))
    Gumps.AddButton(gd, 148, y, 40297, 40298, 9, 1, 0)
    Gumps.AddLabel(gd,  182, y + 2, 33, "종료")
    Gumps.AddImageTiled(gd, 5, 152, gump_w - 10, 2, 9107)
    Gumps.AddHtml(gd, 5, 156, gump_w - 10, 20, "<center><basefont color=#99AACC>Sponsored by Carrot</basefont></center>", False, False)
    Gumps.SendGump(MENU_GUMP_ID, Player.Serial, 50, 200, gd.gumpDefinition, gd.gumpStrings)

def handle_menu():
    global loot_mode, config, leader, runebook, extra_party, extra_pets, mypet, is_running, current_bard_mode
    md = Gumps.GetGumpData(MENU_GUMP_ID)
    if not md or md.buttonid <= 0: return
    btn = md.buttonid; Gumps.CloseGump(MENU_GUMP_ID)
    if btn == 1: is_running = not is_running; Player.ChatSay(68, "★봇 작동 {}★".format("시작" if is_running else "정지"))
    elif btn == 2: Player.ChatSay(158, "★설정 초기화★"); config = run_setup(); leader, runebook, extra_party, extra_pets, mypet = config['leader'], config['runebook'], config.get('party', []), config.get('pets', []), (config.get('pets', [])[0] if config.get('pets', []) else None)
    elif btn == 3:
        Player.ChatSay(158, "★먹이 아이템 선택★")
        new_food_id = Target.PromptTarget("먹이 선택")
        food_item = Items.FindBySerial(new_food_id)
        if food_item: pet_food.insert(0, food_item.ItemID); Player.ChatSay(68, "★먹이 등록 완료★")
        else: Player.ChatSay(33, "★등록 취소★")
    elif btn == 4: loot_mode = not loot_mode; Player.ChatSay(66, "★송금모드: {}★".format("On" if loot_mode else "Off"))
    elif btn == 5: current_bard_mode = ("Discordance" if current_bard_mode == "Provocation" else "Provocation"); Player.ChatSay(66, "★모드변경: {}★".format(current_bard_mode))
    elif btn == 9: Player.ChatSay(33, "★프로그램 종료★"); raise SystemExit
    draw_menu()

# 원본 0.3 유틸리티
def save_config(data):
    if save_character_settings:
        save_character_settings(SCRIPT_NAME, Player.Name, data)
    else:
        if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
        File.WriteAllText(CONFIG_FILE, json.dumps(data, indent=4))
    Player.ChatSay(68, "★설정 저장 완료★")

def load_config():
    if load_character_settings:
        try:
            data = load_character_settings(SCRIPT_NAME, Player.Name, {}, [LEGACY_CONFIG_FILE])
            return data if data else None
        except:
            pass
    if File.Exists(CONFIG_FILE):
        try: return json.loads(File.ReadAllText(CONFIG_FILE))
        except: return None
    return None

def run_setup():
    Player.ChatSay(158, "★설정: 리더를 선택하세요★"); l_id = Target.PromptTarget("Select Leader")
    mob = Mobiles.FindBySerial(l_id)
    if mob: Player.ChatSay(68, "★리더: {} 지정★".format(mob.Name))
    Misc.Pause(500); Player.ChatSay(158, "★설정: 룬북을 선택하세요★"); rb_id = Target.PromptTarget("Select Runebook")
    if Items.FindBySerial(rb_id): Player.ChatSay(68, "★룬북 인식 완료★")
    Misc.Pause(500); p_list = []
    Player.ChatSay(158, "★설정: 파티원 선택 (종료: 우클릭)★")
    while True:
        p_target = Target.PromptTarget("Select Party Member")
        if p_target == -1 or p_target == None: break
        mob = Mobiles.FindBySerial(p_target)
        if mob: p_list.append(p_target); Player.ChatSay(68, "★파티원: {} 추가★".format(mob.Name))
        Misc.Pause(300)
    pet_list = []
    Player.ChatSay(158, "★설정: 펫 선택 (종료: 우클릭)★")
    while True:
        pet_target = Target.PromptTarget("Select Pet")
        if pet_target == -1 or pet_target == None: break
        mob = Mobiles.FindBySerial(pet_target)
        if mob: pet_list.append(pet_target); Player.ChatSay(68, "★펫: {} 추가★".format(mob.Name))
        Misc.Pause(300)
    data = {"leader": l_id, "runebook": rb_id, "party": p_list, "pets": pet_list}
    save_config(data); return data

# 0.3 원본 연동 로직 (100% 원문 보존)
def findtile():
  if doomtile == 1:
   if Player.InRangeMobile(leader, 2):  
    if Items.FindByID(0x1822, 0x0482, -1, 3):
     item = Items.FindByID(0x1822, 0x0482, -1, 3) 
     if item != None:
      if Player.Position.X > item.Position.X  and Player.Position.Y > item.Position.Y: Player.Run('Up')
      elif Player.Position.X > item.Position.X  and Player.Position.Y < item.Position.Y: Player.Run('Left')  
      elif Player.Position.X > item.Position.X  and Player.Position.Y == item.Position.Y: Player.Run('West')
      elif Player.Position.X < item.Position.X  and Player.Position.Y > item.Position.Y: Player.Run('Right')   
      elif Player.Position.X < item.Position.X  and Player.Position.Y < item.Position.Y: Player.Run('Down')
      elif Player.Position.X < item.Position.X  and Player.Position.Y == item.Position.Y: Player.Run('East')
      elif Player.Position.X == item.Position.X  and Player.Position.Y > item.Position.Y: Player.Run('North')   
      elif Player.Position.X == item.Position.X  and Player.Position.Y < item.Position.Y: Player.Run('South')  

def instrumentdoubleclick():
  if Journal.Search('What instrument shall you play?'):
    Journal.Clear(); Misc.Pause(400); Target.Cancel()
    for i in instrument:
        if Items.FindByID(i, -1, Player.Backpack.Serial):
          Player.ChatSay(68, '★악기 교체 확인★')  
          myinstrument = Items.FindByID(i, -1, Player.Backpack.Serial)
          if myinstrument != None:  
             Items.UseItem(myinstrument)
          Misc.Pause(100); break

# [강화된 게이트 로직 - v0.2 이식] (유일한 로직 교체 포인트)
def Moongatet():
    global gate_cooldown, locked_gate_serial, current_map, gate_watch_active, gate_watch_start, ignored_gate_serials
    if Player.Map != current_map:
        current_map, gate_cooldown = Player.Map, time.time() + 5
        locked_gate_serial, gate_watch_active = None, False
        Player.ChatSay(68, "★게이트 이동★"); trim_working_set(); return
    if time.time() < gate_cooldown: return
    if not gate_watch_active and not locked_gate_serial:
        for s in [leader] + extra_party:
            m = Mobiles.FindBySerial(s); n = m.Name if m else ""
            if n and (Journal.SearchByName("Vas Rel", n) or Journal.SearchByName("Gate Travel", n)):
                Journal.Clear(); ignored_gate_serials = set(g.Serial for g in Items.FindAllByID([0x0F6C, 0x0DDA], -1, -1, 5))
                gate_watch_active, gate_watch_start = True, time.time(); Player.ChatSay(158, "★게이트 포착★"); break
    if gate_watch_active and not locked_gate_serial:
        if time.time() - gate_watch_start > 12: gate_watch_active = False; Player.ChatSay(33, "★게이트 타임아웃★")
        else:
            new_g = [g for g in Items.FindAllByID([0x0F6C, 0x0DDA], -1, -1, 5) if g.Serial not in ignored_gate_serials]
            if new_g: locked_gate_serial, gate_watch_active = new_g[0].Serial, False
    if locked_gate_serial:
        t = Items.FindBySerial(locked_gate_serial)
        if t:
            if Player.DistanceTo(t) > 0: PathFinding.RunPath(PathFinding.GetPath(t.Position.X, t.Position.Y, -1), 500)
            else:
                Items.UseItem(t)
                if Gumps.WaitForGump(0xdd8b146a, 1500): Gumps.SendAction(0xdd8b146a, 1)
                Misc.IgnoreObject(t)
        else: locked_gate_serial = None

# [전투 로직] (0.3 원본 연계 대기 및 안전 시스템 100% 복원)
def auto_idle_combat():
    global locked_target_serial, last_bard_time, current_bard_mode, leader, current_lock, discorded_mobs
    if Player.Hits < Player.HitsMax * 0.8: return
    fil = Mobiles.Filter(); fil.RangeMax, fil.CheckLineOfSight = 12, True
    nearby_mobs = Mobiles.ApplyFilter(fil)
    v_mobs = []
    for m in nearby_mobs:
        if m is None: continue
        if m.Serial == Player.Serial: continue
        if m.Serial == leader: continue
        if m.Notoriety >= 3 and m.WarMode: v_mobs.append(m)
        
    target_mob, bard_target = None, None
    if v_mobs:
        locked_mob = None
        if locked_target_serial != 0:
            for m in v_mobs:
                if m.Serial == locked_target_serial: locked_mob = m; break
        if locked_mob: target_mob = locked_mob
        else:
            v_mobs.sort(key=lambda m: Player.DistanceTo(m))
            target_mob = v_mobs[0]; locked_target_serial = target_mob.Serial
        un_disco = [m for m in v_mobs if m.Serial not in discorded_mobs]
        if un_disco: un_disco.sort(key=lambda m: Player.DistanceTo(m)); bard_target = un_disco[0]
    else:
        locked_target_serial = 0
        if not Player.Mount and current_lock is None: mount_pet()
        
    if target_mob:
        if not Player.WarMode: Player.SetWarMode(True); Misc.Pause(100)
        Mobiles.UseMobile(Player.Serial); Misc.Pause(250)
        
        bard_in_danger = False
        for m in v_mobs:
            if Player.DistanceTo(m) <= 4: bard_in_danger = True; break
                
        if not bard_in_danger: Player.Attack(target_mob)
        else:
            tank_is_near = False
            lead_mob = Mobiles.FindBySerial(leader)
            if lead_mob and not lead_mob.IsGhost:
                if lead_mob.DistanceTo(target_mob) <= 2 or Player.DistanceTo(lead_mob) <= 2: tank_is_near = True
            if not tank_is_near:
                for p_id in extra_pets:
                    p_mob = Mobiles.FindBySerial(p_id)
                    if p_mob and not p_mob.IsGhost:
                        if p_mob.DistanceTo(target_mob) <= 2 or Player.DistanceTo(p_mob) <= 2: tank_is_near = True; break
            if tank_is_near: Player.Attack(target_mob)
            
        now = time.time()
        if now - last_bard_time >= BARD_COOLDOWN:
            if current_bard_mode == "Provocation" and bard_target and target_mob.Serial != bard_target.Serial:
                Player.UseSkill("Provocation"); Target.WaitForTarget(2000, False); Target.TargetExecute(target_mob.Serial); Target.WaitForTarget(2000, False); Target.TargetExecute(bard_target.Serial)
                Player.ChatSay(68, "★프로보: {} vs {}★".format(target_mob.Name, bard_target.Name))
                Misc.Pause(150)
                if Journal.Search("must wait") or Journal.Search("아직 스킬"): last_bard_time = time.time() - (BARD_COOLDOWN - 1.0); Journal.Clear()
                else: last_bard_time = time.time()
            elif current_bard_mode == "Discordance" and bard_target:
                Player.UseSkill("Discordance"); Target.WaitForTarget(2000, False); Target.TargetExecute(bard_target.Serial); Misc.Pause(150)
                if Journal.Search("jarring") or Journal.Search("기운을"):
                    discorded_mobs.append(bard_target.Serial); Player.ChatSay(68, "★디코 성공★"); last_bard_time = time.time(); Journal.Clear()
                elif Journal.Search("already") or Journal.Search("불협화음") or Journal.Search("면역"):
                    discorded_mobs.append(bard_target.Serial); last_bard_time = 0.0; Journal.Clear()
                elif Journal.Search("must wait") or Journal.Search("아직 스킬"):
                    last_bard_time = time.time() - (BARD_COOLDOWN - 1.0); Journal.Clear()
                else: last_bard_time = time.time()

def following():
    leadman = Mobiles.FindBySerial(leader)
    if not leadman: Player.ChatSay(33, '★리더 소실★'); Misc.Pause(1000); return
    elif Player.InRangeMobile(leadman, 30):   
      if not Player.InRangeMobile(leadman, distanceleader): 
        if usepathfinding == 1:
          if not Player.InRangeMobile(leader, pathfinddistance):          
            leaderserial = Mobiles.FindBySerial(leader)
            if leaderserial != None: 
             PathFinding.RunPath(PathFinding.GetPath(leaderserial.Position.X, leaderserial.Position.Y,-1), 1500)
        dx = leadman.Position.X - Player.Position.X; dy = leadman.Position.Y - Player.Position.Y
        direction = calculateDirection(dx, dy)
        if direction: Player.Run(direction)

def evade_threat():
    fil = Mobiles.Filter(); fil.RangeMax, fil.CheckLineOfSight = 2, True
    nearby_mobs = Mobiles.ApplyFilter(fil)
    th = [m for m in nearby_mobs if m and m.Serial != Player.Serial and m.Serial != leader and m.Notoriety >= 3 and m.WarMode]
    if th:
        th.sort(key=lambda m: Player.DistanceTo(m)); threat = th[0]; Target.Cancel()
        dx, dy = Player.Position.X - threat.Position.X, Player.Position.Y - threat.Position.Y
        if dx == 0 and dy == 0: dx = 1
        direction = calculateDirection(dx, dy)
        if direction: Player.Run(direction); return True
    return False

def pheal_target():
    for p_id in extra_pets:
        pet = Mobiles.FindBySerial(p_id)
        if pet and Player.InRangeMobile(pet, 12):
            if pet.Poisoned: Spells.CastMagery('Arch Cure', pet, 1500); smart_pause(300)
            elif pet.Hits < pet.HitsMax * 0.77 and pet.Hits > 0: Spells.CastMagery('Greater Heal', pet, 1500); smart_pause(300)
            elif veterinary == 1 and pet.Hits == 0 and Player.InRangeMobile(pet, 2):
                Items.UseItemByID(0x0E21,-1); Target.WaitForTarget(2500); Target.TargetExecute(pet); Misc.Pause(3500)
        
def fheal_target():
    targets = [Player.Serial, leader] + extra_party
    for tid in targets:
        target = Mobiles.FindBySerial(tid)
        if target and getattr(target, 'Hits', None) is not None and getattr(target, 'HitsMax', None) is not None:
            if target.Hits < target.HitsMax * 0.77:
                if Player.InRangeMobile(target, 12):
                    if target.Poisoned: Spells.CastMagery('Arch Cure', target, 1500); smart_pause(300)
                    elif target.Hits < target.HitsMax * 0.77 and not target.Hits == 0: Spells.CastMagery('Greater Heal', target, 1500); smart_pause(300)
                    elif target.IsGhost and Player.InRangeMobile(target, 1): Spells.CastMagery('Resurrection', target, 1500); smart_pause(500)
                    
def bardbuff():
   if musicbuff == 1:
        if not (Player.BuffsExist('Inspire') and Player.BuffsExist('Invigorate')):
          if not Player.BuffsExist('Inspire'): Spells.CastMastery('Inspire'); Misc.Pause(500)        
          if not Player.BuffsExist('Invigorate'): Spells.CastMastery('Invigorate'); Misc.Pause(500)
   else: 
        if not (Player.BuffsExist('Resilience') and Player.BuffsExist('Perseverance')):
          if not Player.BuffsExist('Resilience'): Spells.CastMastery('Resilience'); Misc.Pause(500)  
          if not Player.BuffsExist('Perseverance'): Spells.CastMastery('Perseverance'); Misc.Pause(500)  
            
def protectionbuff():
     if protection == 1:
        if not Player.BuffsExist('Protection') and Player.Mana > 10: Spells.CastMagery('Protection',1000)  

def smart_pause(duration_ms):
    global pending_action, current_bard_mode, gate_watch_active, gate_watch_start, ignored_gate_serials
    global sanghacha_mode, sanghacha_protected, following_mode
    for _ in range(max(1, duration_ms // 250)):
        if _lcmd("!상하차"):
            Journal.Clear()
            if sanghacha_mode:
                sanghacha_mode = False
                Player.ChatSay(33, "★상하차 취소★")
            else:
                sanghacha_mode = True
                Player.ChatSay(158, "★상하차 대기: 컨테이너 지정 대기★")
        elif _lcmd("!팔로우"):
            Journal.Clear()
            following_mode = True
            Player.ChatSay("all follow me")
            Player.ChatSay(68, "★팔로잉 모드★")
        elif _lcmd("!밥줘"): Journal.Clear(); pending_action = 'feed'; Player.ChatSay(158, "★비둘기야 밥먹자 (예약)★")
        elif _lcmd("!프로보"): Journal.Clear(); current_bard_mode = "Provocation"; Player.ChatSay(66, "★모드: 프로보 예약★")
        elif _lcmd("!디코"): Journal.Clear(); current_bard_mode = "Discordance"; Player.ChatSay(66, "★모드: 디코 예약★")
        elif Journal.Search("0x"):
            lead = Mobiles.FindBySerial(leader); ln = lead.Name if lead else ""
            if ln and Journal.SearchByName("0x", ln):
                m = re.search(r"0x[0-9a-fA-F]+", Journal.GetLineText("0x", True).lower())
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
                        pending_action = int(m.group(), 16)
                        Player.ChatSay(68, "★점사 예약★")
        for s in [leader] + extra_party:
            m = Mobiles.FindBySerial(s); n = m.Name if m else ""
            if n and Journal.SearchByName("Vas Rel", n):
                Journal.Clear(); ignored_gate_serials = set(g.Serial for g in Items.FindAllByID([0x0F6C, 0x0DDA], -1, -1, 5))
                gate_watch_active, gate_watch_start = True, time.time(); Player.ChatSay(158, "★게이트 포착★"); break
        Misc.Pause(250)

def run_action(idx, mode):
    global gate_watch_active, gate_watch_start, ignored_gate_serials
    rb = Items.FindBySerial(runebook)
    if not rb: return
    Items.UseItem(rb)
    if Gumps.WaitForGump(0x59, 2000):
        Gumps.SendAction(0x59, (50 if mode == 'recall' else 100) + (idx - 1))
        if mode == 'recall': Player.ChatSay(158, "★순례 {}번위치★".format(idx))
        elif mode == 'gate':
            ignored_gate_serials = set(g.Serial for g in Items.FindAllByID([0x0F6C, 0x0DDA], -1, -1, 5))
            gate_watch_active, gate_watch_start = True, time.time(); Player.ChatSay(158, "★게이트 이동★")

def check_pet_hp():
    global pet_follow_mode, pet_follow_attempts, pet_follow_last_try
    if not mypet: return
    # 탑승 중이면 mypet HP 판정 불가 → 스킵
    if Player.Mount: return
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

def mount_pet():
    if not mypet: return
    p = Mobiles.FindBySerial(mypet)
    if not Player.Mount and p and Player.InRangeMobile(p, 2): Mobiles.UseMobile(p)

def dismount_pet():
    if Player.Mount: Mobiles.UseMobile(Player.Serial)

def feed_pet():
    if not mypet: return
    if Player.Mount: dismount_pet(); Misc.Pause(1500)
    pet = Mobiles.FindBySerial(mypet)
    if pet:
        for f in pet_food:
            food = Items.FindByID(f, -1, Player.Backpack.Serial)
            if food: Items.Move(food, mypet, 1); Player.ChatSay(68, "★비둘기야 밥먹자★"); Misc.Pause(500); break
    mount_pet()

def command_handler():
    global current_lock, target_start_time, pending_action, config, leader, runebook, extra_party, extra_pets, mypet, current_bard_mode
    global sanghacha_mode, sanghacha_protected
    global ps_sort_mode, pink_sort_mode, skull_sort_mode, gate_mode
    global bot_paused, following_mode
    if pending_action:
        if pending_action == 'feed': feed_pet()
        elif isinstance(pending_action, tuple) and pending_action[0] == 'sanghacha':
            do_sanghacha(pending_action[1], sanghacha_protected, pet_food)
            sanghacha_mode = False
        elif isinstance(pending_action, int):
            mob = Mobiles.FindBySerial(pending_action)
            if mob:
                current_lock, target_start_time = pending_action, time.time(); Player.ChatSay(68, "★일제사격 : {}★".format(mob.Name))
                dismount_pet(); Misc.Pause(250); Target.Cancel(); Player.ChatSay("all kill")
                if Target.WaitForTarget(500): Target.TargetExecute(mob)
        pending_action = None; return
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
        current_lock = None
        locked_target_serial = 0
        Player.SetWarMode(False)
        Player.ChatSay("all follow me")
        Player.ChatSay(68, "★팔로잉 모드★")
        return
    if _lcmd("!정상화"):
        Journal.Clear()
        following_mode = False
        Player.ChatSay("all guard me")
        Player.ChatSay(68, "★일반 모드 복귀★")
        return

    if _lcmd("!상하차"):
        Journal.Clear()
        if sanghacha_mode:
            sanghacha_mode = False
            Player.ChatSay(33, "★상하차 취소★")
        else:
            sanghacha_mode = True
            Player.ChatSay(158, "★상하차 대기: 컨테이너 지정 대기★")
        return
    if _lcmd("!프로보"): Journal.Clear(); current_bard_mode = "Provocation"; Player.ChatSay(66, "★모드: 프로보★"); return
    if _lcmd("!디코"): Journal.Clear(); current_bard_mode = "Discordance"; Player.ChatSay(66, "★모드: 디코★"); return
    if _lcmd("!송금"): Journal.Clear(); handle_loot(); return
    if _lcmd("!밥줘"): Journal.Clear(); feed_pet(); return
    if _lcmd("!sell"): Journal.Clear(); sell_powerscrolls(NPC_SELL, SELL_AGENT_LIST_NAME); return
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
    if _lcmd("!설정"): 
        Journal.Clear(); config = run_setup(); leader, runebook = config['leader'], config['runebook']
        extra_party, extra_pets, mypet = config.get('party', []), config.get('pets', []), (config.get('pets', [])[0] if config.get('pets', []) else None); return
    if Journal.Search("0x"):
        lead = Mobiles.FindBySerial(leader); ln = lead.Name if lead else ""
        if ln and Journal.SearchByName("0x", ln):
            m = re.search(r"0x[0-9a-fA-F]+", Journal.GetLineText("0x", True).lower())
            if m:
                val = int(m.group(), 16)
                Journal.Clear()
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
                mob = Mobiles.FindBySerial(val)
                if mob:
                    current_lock, target_start_time = val, time.time(); Player.ChatSay(68, "★일제사격 : {}★".format(mob.Name))
                    dismount_pet(); Misc.Pause(250); Target.Cancel(); Player.ChatSay("all kill")
                    if Target.WaitForTarget(500): Target.TargetExecute(mob); return
    if Journal.Search("pf") and current_lock: Journal.Clear(); Spells.CastMagery("Poison Field"); Target.WaitForTarget(2000) and Target.TargetExecute(current_lock); return
    if Journal.Search("r") or Journal.Search("g"):
        line = Journal.GetLineText("").lower(); m = re.search(r"([rg])(\d+)", line)
        if m: Journal.Clear(); run_action(int(m.group(2)), 'recall' if m.group(1) == 'r' else 'gate')

def combat_logic():
    global current_lock, target_start_time
    if not current_lock: return
    mob = Mobiles.FindBySerial(current_lock)
    if not mob or mob.Hits <= 0:
        if mob and mob.Hits <= 0 and time.time() - target_start_time < 1.5:
            if (int(time.time() * 10) % 5 == 0): Mobiles.WaitForProps(mob, 200); Target.SetLast(mob)
            return
        Player.ChatSay("all guard me"); current_lock = None

# =============================================================================
# [메인 루프] - 0.3 원본 순서 매칭
# =============================================================================
_c = load_config()
if _c:
    ids = [_c['leader']] + _c.get('party', [])
    if not any(Mobiles.FindBySerial(i) for i in ids): Player.ChatSay(33, "★설정 초기화 대기★"); config = run_setup()
    else: config = _c
else: config = run_setup()
leader, runebook = config['leader'], config['runebook']
extra_party, extra_pets, mypet = config.get('party', []), config.get('pets', []), (config.get('pets', [])[0] if config.get('pets', []) else None)

def _lcmd(keyword):
    mob = Mobiles.FindBySerial(leader)
    name = mob.Name if mob else ""
    return bool(name and Journal.SearchByName(keyword, name))

dismount_pet(); Misc.Pause(1000); Player.ChatSay("all guard me"); Misc.Pause(1000)
mount_pet(); Journal.Clear(); draw_menu()

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
Player.ChatSay(66, "★바드봇 v1.2 기동 / 보호: {}개★".format(len(sanghacha_protected)))

while True:

    # ── 리더 일시정지 대기 ──
    while bot_paused:
        command_handler()
        Misc.Pause(500)

    handle_menu()
    # ── 사망 / 부활 / 시체 추적 ──
    if handle_revival(revival_state, dress_name, use_undertaker=use_undertaker_staff):
        ld = Mobiles.FindBySerial(leader)
        if ld and Player.DistanceTo(ld) > distanceleader:
            Player.SetWarMode(True)
            following()
        Misc.Pause(500)
        continue

    command_handler()
    check_pet_hp()
    if is_running:
        combat_logic()
        evading = evade_threat()
        if not evading:
            following(); lead = Mobiles.FindBySerial(leader)
            if lead and Player.InRangeMobile(lead, 12):
                findtile(); fheal_target(); pheal_target(); protectionbuff(); bardbuff(); autoparty(); Moongatet()
                if not following_mode:
                    auto_idle_combat()
                instrumentdoubleclick()

    if time.time() - last_trim_time >= 30:
        trim_working_set()
        last_trim_time = time.time()

    Misc.Pause(100)
