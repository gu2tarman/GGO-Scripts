# -*- coding: utf-8 -*-
# =============================================================================
# GGO - Leader Control Panel v1.2 (멀티페이지 단일 검프)
# =============================================================================
# Page 1: 메인 메뉴
# Page 2: 펫&이동  (펫소환 / 밥주기 / 게이트지정)
# Page 3: 정리용  (파스판매 / 상하차 / 파스정리 / 분홍정리 / 해골정리 / 마스터리)
# Page 4: 직업특화  (디코모드 / 프롭모드 / 포이즌필드 / 골드전송 / 뱀파폼 / 비행)
# =============================================================================

SCRIPT_ID = "GGO_LEADER_CONTROL"
SCRIPT_NAME = "GGO_리더컨트롤"
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

import ctypes
import time
import sys
import os
import json
import winsound
from System.Collections.Generic import List
from System import Int32
from System.Net import WebClient
from System.Text import Encoding
from System.Threading import Thread, ThreadStart

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)
from GGO_봇공통_모듈 import (
    trim_working_set, collect_all_items, get_movable_items, sell_powerscrolls,
    do_help_escape, make_revival_state, handle_revival
)

# =============================================================================
# script_settings.json 기본값
# -----------------------------------------------------------------------------
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 실제 사용자 설정은 스크립트 파일을 직접 수정하지 말고
# GGO_Settings/GGO_리더컨트롤/script_settings.json에서 수정하세요.
# =============================================================================
GUMP_ID      = 0x47474C43
NPC_SELL     = 0x0000DE29
SELL_AGENT_LIST_NAME = "ps"

DISCORD_WEBHOOK_URL = ""
DRESS_LIST_NAME      = "sdi"
USE_UNDERTAKER_STAFF = True  # True: 부활 시 장의사 지팡이(0x13F8) 사용

BOSS_NAMES = [
    "Rikktor", "Barracoon", "Neira", "Semidar",
    "Mephitis", "Lord Oaks", "Queen Silvani"
]
BOSS_ALERT_RANGE       = 25    # 보스 탐지 범위 (타일)
BOSS_ALERT_COOLDOWN    = 60.0  # 같은 보스 재알림 쿨다운 (초)
BOSS_SOUND_ENABLED     = False # 윈도우 알림음 (True=켜기)
WF_MANA_MIN            = 50    # 와파 시전 최소 마나

LEADER_SCRIPT_SETTINGS_DEFAULTS = {
    "npc_sell": NPC_SELL,
    "sell_agent_list_name": SELL_AGENT_LIST_NAME,
    "dress_list_name": DRESS_LIST_NAME,
    "use_undertaker_staff": USE_UNDERTAKER_STAFF,
    "boss_names": BOSS_NAMES,
    "boss_alert_range": BOSS_ALERT_RANGE,
    "boss_alert_cooldown": BOSS_ALERT_COOLDOWN,
    "boss_sound_enabled": BOSS_SOUND_ENABLED,
    "wf_mana_min": WF_MANA_MIN
}

LEADER_SCRIPT_SETTINGS_ORDER = [
    "npc_sell",
    "sell_agent_list_name",
    "dress_list_name",
    "use_undertaker_staff",
    "boss_names",
    "boss_alert_range",
    "boss_alert_cooldown",
    "boss_sound_enabled",
    "wf_mana_min"
]

LEADER_SCRIPT_SETTINGS_GUIDE = """GGO_리더컨트롤 script_settings.json 설명

이 파일은 리더컨트롤의 공용 설정 파일입니다.
숫자는 숫자로, true/false는 반드시 소문자로 입력하세요.
쉼표는 지우지 마세요.

npc_sell:
  파워스크롤 판매 NPC 시리얼입니다.
  예: 56873
  16진수로 넣을 경우 큰따옴표로 감싸세요. 예: "0x0000DE29"

sell_agent_list_name:
  판매에 사용할 RE Sell Agent 리스트 이름입니다.

dress_list_name:
  부활 복구에 사용할 RE Dress 리스트 이름입니다.

use_undertaker_staff:
  부활 시 장의사 지팡이 사용 여부입니다.

boss_names:
  보스 알림으로 감지할 이름 목록입니다.

boss_alert_range:
  보스 탐지 거리입니다.

boss_alert_cooldown:
  같은 보스를 다시 알릴 때까지 기다리는 시간(초)입니다.

boss_sound_enabled:
  보스 감지 시 윈도우 알림음을 사용할지 여부입니다.

wf_mana_min:
  와일드파이어 자동 시전 최소 마나입니다.
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
    from GGO_user_config import get_discord_webhook, load_script_settings, ensure_script_settings_guide
    ensure_script_settings_guide(SCRIPT_NAME, LEADER_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, LEADER_SCRIPT_SETTINGS_DEFAULTS, LEADER_SCRIPT_SETTINGS_ORDER)
    NPC_SELL = _setting_int(_script_settings.get("npc_sell", NPC_SELL), NPC_SELL)
    SELL_AGENT_LIST_NAME = str(_script_settings.get("sell_agent_list_name", SELL_AGENT_LIST_NAME))
    DRESS_LIST_NAME = str(_script_settings.get("dress_list_name", DRESS_LIST_NAME))
    USE_UNDERTAKER_STAFF = bool(_script_settings.get("use_undertaker_staff", USE_UNDERTAKER_STAFF))
    BOSS_NAMES = list(_script_settings.get("boss_names", BOSS_NAMES))
    BOSS_ALERT_RANGE = _setting_int(_script_settings.get("boss_alert_range", BOSS_ALERT_RANGE), BOSS_ALERT_RANGE)
    BOSS_ALERT_COOLDOWN = float(_script_settings.get("boss_alert_cooldown", BOSS_ALERT_COOLDOWN))
    BOSS_SOUND_ENABLED = bool(_script_settings.get("boss_sound_enabled", BOSS_SOUND_ENABLED))
    WF_MANA_MIN = _setting_int(_script_settings.get("wf_mana_min", WF_MANA_MIN), WF_MANA_MIN)
    if not DISCORD_WEBHOOK_URL:
        DISCORD_WEBHOOK_URL = get_discord_webhook(True)
except Exception:
    try:
        from GGO_user_config import get_discord_webhook
        if not DISCORD_WEBHOOK_URL:
            DISCORD_WEBHOOK_URL = get_discord_webhook(True)
    except Exception:
        pass

# =============================================================================

BOSS_NAMES_LOWER = [n.lower() for n in BOSS_NAMES]

# ── 버튼 아트 ──
BTN_GREEN_N = 40030; BTN_GREEN_P = 40031
BTN_GOLD_N  = 40299; BTN_GOLD_P  = 40300
BTN_RED_N   = 40297; BTN_RED_P   = 40298
BTN_BLUE_N  = 40021; BTN_BLUE_P  = 40031
HEADER_BAR  = 9107

# ── 색상 ──
HUE_TITLE = 53
HUE_GREEN = 167
HUE_GOLD  = 52
HUE_RED   = 33
HUE_BLUE  = 53
HUE_CYAN  = 1153

# ── 액션 버튼 ID (type=1) ──
# 메인 페이지
BTN_ARMOR        = 3
BTN_AGGRO        = 4
BTN_CHAMP        = 5
BTN_NORMAL       = 6
BTN_MAX          = 7
BTN_ENEMY        = 8
BTN_ENEMY_OFF    = 9
BTN_TARGET       = 11
BTN_PAUSE        = 12
BTN_BOSS_ALERT   = 13
BTN_BOSS_LOOT    = 14
BTN_AUTO_WF      = 15
BTN_FOLLOWING    = 16
# 펫 페이지
BTN_PET_SUMMON  = 21
BTN_PET_FEED    = 22
BTN_PET_GATE    = 23
BTN_HELP_ESCAPE = 24
# 정리 페이지
BTN_SORT_SELL      = 31
BTN_SORT_SANGHACHA = 32
BTN_SORT_PAS       = 33
BTN_SORT_PINK      = 34
BTN_SORT_SKULL     = 35
BTN_SORT_TRASH     = 36
BTN_LEADER_PAS       = 51
BTN_LEADER_PINK      = 52
BTN_LEADER_SANGHACHA = 53
BTN_LEADER_SELL      = 54
# 직업특화 페이지
BTN_BARD_DECO  = 41
BTN_BARD_PROVO = 42
BTN_BARD_PF    = 43
BTN_BARD_GOLD  = 44
BTN_VAMP_FORM  = 45
BTN_FLY        = 46

# ── 상태 ──
leader_paused      = False
enemy_active       = False
boss_alert_enabled = True
boss_loot_enabled  = True
auto_wf_enabled    = False
follow_active      = False
wf_pos             = None   # Point3D (지점) 또는 int (모바일 시리얼)
wf_casting         = False  # Thread 중복 방지 플래그

last_trim_time   = 0.0
last_boss_check  = 0.0
last_loot_check  = 0.0
last_wf_time     = 0.0

protected_backpack  = set()
boss_alert_cooldown = {}   # {boss_name_lower: last_alert_time}
known_corpses       = set()  # 이미 열린 시체 serials

revival_state        = make_revival_state()


# =============================================================================
# 유틸
# =============================================================================
def send_discord_webhook(message):
    if not DISCORD_WEBHOOK_URL:
        return
    def task():
        try:
            wc = WebClient()
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": message}, ensure_ascii=False)
            wc.UploadString(DISCORD_WEBHOOK_URL, "POST", payload)
        except:
            pass
    t = Thread(ThreadStart(task))
    t.IsBackground = True
    t.Start()


def approach_container(target_serial):
    for _ in range(5):
        ti = Items.FindBySerial(target_serial)
        if not ti:
            break
        if max(abs(Player.Position.X - ti.Position.X), abs(Player.Position.Y - ti.Position.Y)) <= 2:
            break
        Player.PathFindTo(ti.Position.X, ti.Position.Y, ti.Position.Z)
        Misc.Pause(1000)


def do_item_sort(item_id, item_color, target_serial):
    found = Items.FindAllByID([item_id], item_color, Player.Backpack.Serial, True)
    if not found:
        Player.HeadMessage(HUE_RED, "정리할 아이템 없음")
        return
    approach_container(target_serial)
    Player.HeadMessage(HUE_GOLD, "정리 시작: {}개".format(len(found)))
    moved = 0; failed = 0
    for item in found:
        success = False
        for _ in range(3):
            Items.Move(item, target_serial, 0)
            Misc.Pause(600)
            if item.Serial not in collect_all_items(Player.Backpack.Serial):
                success = True
                break
            Misc.Pause(400)
        if success:
            moved += 1
        else:
            failed += 1
    if failed > 0:
        Player.HeadMessage(HUE_RED, "정리 완료: {}개 / {}개 실패".format(moved, failed))
    else:
        Player.HeadMessage(HUE_GREEN, "정리 완료: {}개".format(moved))


def do_leader_sanghacha(target_serial):
    all_items = get_movable_items(Player.Backpack.Serial, protected_backpack)
    if not all_items:
        Player.HeadMessage(HUE_RED, "이동할 아이템 없음")
        return
    approach_container(target_serial)
    Player.HeadMessage(HUE_GOLD, "상하차 시작: {}개".format(len(all_items)))
    moved = 0; failed = 0
    for item_serial in all_items:
        item = Items.FindBySerial(item_serial)
        if not item:
            continue
        success = False
        for _ in range(3):
            Items.Move(item, target_serial, 0)
            Misc.Pause(600)
            if item_serial not in collect_all_items(Player.Backpack.Serial):
                success = True
                break
            Misc.Pause(400)
        if success:
            moved += 1
        else:
            failed += 1
    if failed > 0:
        Player.HeadMessage(HUE_RED, "상하차 완료: {}개 / {}개 실패".format(moved, failed))
    else:
        Player.HeadMessage(HUE_GREEN, "상하차 완료: {}개".format(moved))


# =============================================================================
# 보스 알림
# =============================================================================
def check_boss_alert():
    now = time.time()
    mob_filter = Mobiles.Filter()
    mob_filter.Enabled = True
    mob_filter.RangeMax = BOSS_ALERT_RANGE
    mobs = Mobiles.ApplyFilter(mob_filter)
    for mob in mobs:
        if not mob.Name:
            continue
        name_lower = mob.Name.lower()
        for i, boss_lower in enumerate(BOSS_NAMES_LOWER):
            if boss_lower in name_lower:
                display_name = BOSS_NAMES[i]
                Mobiles.Message(mob, HUE_CYAN, "★ {} ★".format(display_name))
                Mobiles.SingleClick(mob.Serial)
                last_alert = boss_alert_cooldown.get(boss_lower, 0)
                if now - last_alert >= BOSS_ALERT_COOLDOWN:
                    boss_alert_cooldown[boss_lower] = now
                    msg = "🔥 **[GGO 보스 스폰]** {} | 좌표: {}, {}".format(
                        display_name, mob.Position.X, mob.Position.Y)
                    Player.HeadMessage(HUE_RED, "★ 보스 스폰: {} ★".format(display_name))
                    if BOSS_SOUND_ENABLED:
                        try:
                            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                        except Exception:
                            pass
                    send_discord_webhook(msg)
                    pass
                break


# =============================================================================
# 보스 시체 열기
# =============================================================================
def check_boss_loot():
    item_filter = Items.Filter()
    item_filter.Enabled = True
    item_filter.RangeMax = 20
    all_items = Items.ApplyFilter(item_filter)

    for item in all_items:
        if item.Serial in known_corpses:
            continue
        if not item.Name:
            continue
        name_lower = item.Name.lower()
        if name_lower.startswith("the remains of "):
            remains_part = name_lower[len("the remains of "):]
        elif name_lower.startswith("remains of "):
            remains_part = name_lower[len("remains of "):]
        else:
            continue
        if not any(boss_lower in remains_part for boss_lower in BOSS_NAMES_LOWER):
            continue

        dx = abs(Player.Position.X - item.Position.X)
        dy = abs(Player.Position.Y - item.Position.Y)
        dist = max(dx, dy)
        if dist <= 2:
            Items.Message(item, HUE_GOLD, "★ 보스 시체 열기 ★")
            Items.UseItem(item)
            known_corpses.add(item.Serial)
            Misc.Pause(500)
        else:
            Items.Message(item, HUE_RED, "▼ 보스 시체 ({}타일) ▼".format(dist))


# =============================================================================
# 자동 와일드파이어
# =============================================================================
def _wf_thread():
    global wf_casting
    try:
        Spells.CastSpellweaving("Wildfire")
        if Target.WaitForTarget(3000, False):
            if isinstance(wf_pos, int):
                Target.TargetExecute(wf_pos)
            else:
                Target.TargetExecute(wf_pos.X, wf_pos.Y, wf_pos.Z, 0)
    except:
        pass
    finally:
        wf_casting = False

def do_auto_wildfire():
    global wf_casting
    if wf_pos is None or wf_casting:
        return
    if Player.Mana < WF_MANA_MIN:
        return
    wf_casting = True
    t = Thread(ThreadStart(_wf_thread))
    t.IsBackground = True
    t.Start()


# =============================================================================
# 검프
# =============================================================================
def draw_gump():
    gw, gh = 265, 260
    gd = Gumps.CreateGump(movable=True)

    # ── Page 0: 모든 페이지에 표시 ──
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, gw, gh, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, gw, gh)
    Gumps.AddLabel(gd, 10, 8, HUE_TITLE, "GGO Leader Control")
    Gumps.AddImageTiled(gd, 5, 26, gw - 10, 2, HEADER_BAR)
    Gumps.AddHtml(gd, 5, 246, gw - 10, 20,
        "<center><basefont color=#99AACC>Sponsored by Carrot</basefont></center>", False, False)

    # ── Page 1: 메인 메뉴 ──
    Gumps.AddPage(gd, 1)
    y = 33
    # 펫&이동▶ / 정리용▶
    Gumps.AddButton(gd, 8,   y, BTN_BLUE_N, BTN_BLUE_P, 0, 0, 2)
    Gumps.AddLabel(gd,  42,  y+2, HUE_BLUE, "펫&이동 ▶")
    Gumps.AddButton(gd, 135, y, BTN_BLUE_N, BTN_BLUE_P, 0, 0, 3)
    Gumps.AddLabel(gd,  169, y+2, HUE_BLUE, "정리용 ▶")
    y += 28
    # 아머 / 선공
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_ARMOR, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "아머")
    Gumps.AddButton(gd, 135, y, BTN_GOLD_N, BTN_GOLD_P, BTN_AGGRO, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GOLD, "선공")
    y += 28
    # 챔프모드▶ / 일반모드
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_CHAMP,  1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "챔프모드 ▶")
    Gumps.AddButton(gd, 135, y, BTN_GOLD_N, BTN_GOLD_P, BTN_NORMAL, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GOLD, "일반모드")
    y += 28
    # 맥스모드 / 에너미 toggle
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_MAX, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "맥스모드")
    if enemy_active:
        en_n, en_p, en_hue, en_lbl = BTN_RED_N,   BTN_RED_P,   HUE_RED,   "에너미 OFF"
    else:
        en_n, en_p, en_hue, en_lbl = BTN_GREEN_N, BTN_GREEN_P, HUE_GREEN, "에너미 ON"
    Gumps.AddButton(gd, 135, y, en_n, en_p, BTN_ENEMY, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, en_hue, en_lbl)
    y += 28
    # 팔로잉모드 / 보스설정▶
    if follow_active:
        fw_n, fw_p, fw_hue, fw_lbl = BTN_RED_N,   BTN_RED_P,   HUE_RED,   "팔로잉 ON"
    else:
        fw_n, fw_p, fw_hue, fw_lbl = BTN_GREEN_N, BTN_GREEN_P, HUE_GREEN, "팔로잉 OFF"
    Gumps.AddButton(gd, 8,   y, fw_n, fw_p, BTN_FOLLOWING, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, fw_hue, fw_lbl)
    Gumps.AddButton(gd, 135, y, BTN_BLUE_N, BTN_BLUE_P, 0, 0, 5)
    Gumps.AddLabel(gd,  169, y+2, HUE_BLUE, "보스설정 ▶")
    y += 28
    # 타겟지정 / 바드용▶
    Gumps.AddButton(gd, 8,   y, BTN_GREEN_N, BTN_GREEN_P, BTN_TARGET, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GREEN, "타겟지정")
    Gumps.AddButton(gd, 135, y, BTN_BLUE_N,  BTN_BLUE_P,  0, 0, 4)
    Gumps.AddLabel(gd,  169, y+2, HUE_BLUE,  "직업특화 ▶")
    y += 28
    # 와파 toggle / 일시정지 toggle
    if auto_wf_enabled:
        wf_n, wf_p, wf_hue, wf_lbl = BTN_GREEN_N, BTN_GREEN_P, HUE_GREEN, "와파 ON"
    else:
        wf_n, wf_p, wf_hue, wf_lbl = BTN_BLUE_N,  BTN_BLUE_P,  HUE_BLUE,  "와파 OFF"
    if leader_paused:
        p_n, p_p, p_hue, p_lbl = BTN_GREEN_N, BTN_GREEN_P, HUE_GREEN, "재개"
    else:
        p_n, p_p, p_hue, p_lbl = BTN_RED_N,   BTN_RED_P,   HUE_RED,   "일시정지"
    Gumps.AddButton(gd, 8,   y, wf_n, wf_p, BTN_AUTO_WF, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, wf_hue, wf_lbl)
    Gumps.AddButton(gd, 135, y, p_n,  p_p,  BTN_PAUSE,   1, 0)
    Gumps.AddLabel(gd,  169, y+2, p_hue, p_lbl)

    # ── Page 2: 펫&이동 ──
    Gumps.AddPage(gd, 2)
    Gumps.AddLabel(gd, 10, 33, HUE_GOLD, "[ 펫&이동 ]")
    y = 60
    Gumps.AddButton(gd, 8,   y, BTN_GREEN_N, BTN_GREEN_P, BTN_PET_SUMMON, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GREEN, "펫소환")
    Gumps.AddButton(gd, 135, y, BTN_GREEN_N, BTN_GREEN_P, BTN_PET_FEED,   1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GREEN, "밥주기")
    y += 30
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_PET_GATE,    1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "게이트지정")
    Gumps.AddButton(gd, 135, y, BTN_RED_N,  BTN_RED_P,  BTN_HELP_ESCAPE, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_RED,  "헬프탈출")
    y += 35
    Gumps.AddButton(gd, 8,   y, BTN_RED_N, BTN_RED_P, 0, 0, 1)
    Gumps.AddLabel(gd,  42,  y+2, HUE_RED, "◀ 돌아가기")

    # ── Page 3: 정리용 ──
    Gumps.AddPage(gd, 3)
    Gumps.AddLabel(gd, 10, 33, HUE_GOLD, "[ 정리용 ]")
    y = 60
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_SORT_SELL,      1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "파스판매")
    Gumps.AddButton(gd, 135, y, BTN_GOLD_N, BTN_GOLD_P, BTN_SORT_SANGHACHA, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GOLD, "상하차")
    y += 26
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_SORT_PAS,  1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "파스정리")
    Gumps.AddButton(gd, 135, y, BTN_GOLD_N, BTN_GOLD_P, BTN_SORT_PINK, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GOLD, "분홍정리")
    y += 26
    Gumps.AddButton(gd, 8,   y, BTN_GOLD_N, BTN_GOLD_P, BTN_SORT_SKULL, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_GOLD, "해골정리")
    Gumps.AddButton(gd, 135, y, BTN_GOLD_N, BTN_GOLD_P, BTN_SORT_TRASH, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GOLD, "마스터리")
    y += 26
    Gumps.AddButton(gd, 8,   y, BTN_BLUE_N, BTN_BLUE_P, BTN_LEADER_PAS,  1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_BLUE, "리더파스")
    Gumps.AddButton(gd, 135, y, BTN_BLUE_N, BTN_BLUE_P, BTN_LEADER_PINK, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_BLUE, "리더분홍")
    y += 26
    Gumps.AddButton(gd, 8,   y, BTN_BLUE_N, BTN_BLUE_P, BTN_LEADER_SANGHACHA, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_BLUE, "리더상하차")
    Gumps.AddButton(gd, 135, y, BTN_BLUE_N, BTN_BLUE_P, BTN_LEADER_SELL, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_BLUE, "리더판매")
    y += 26
    Gumps.AddButton(gd, 8,   y, BTN_RED_N, BTN_RED_P, 0, 0, 1)
    Gumps.AddLabel(gd,  42,  y+2, HUE_RED, "◀ 돌아가기")

    # ── Page 4: 직업특화 ──
    Gumps.AddPage(gd, 4)
    Gumps.AddLabel(gd, 10, 33, HUE_BLUE, "[ 직업특화 ]")
    y = 60
    # 바드 명령
    Gumps.AddButton(gd, 8,   y, BTN_BLUE_N, BTN_BLUE_P, BTN_BARD_DECO,  1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_BLUE, "디코모드")
    Gumps.AddButton(gd, 135, y, BTN_BLUE_N, BTN_BLUE_P, BTN_BARD_PROVO, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_BLUE, "프롭모드")
    y += 28
    Gumps.AddButton(gd, 8,   y, BTN_BLUE_N, BTN_BLUE_P, BTN_BARD_PF,   1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_BLUE, "포이즌필드")
    Gumps.AddButton(gd, 135, y, BTN_GOLD_N, BTN_GOLD_P, BTN_BARD_GOLD, 1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_GOLD, "골드전송")
    y += 28
    Gumps.AddImageTiled(gd, 5, y, gw - 10, 1, HEADER_BAR)
    y += 8
    # 가고일 전용 (뱀파폼 / 비행)
    Gumps.AddButton(gd, 8,   y, BTN_RED_N, BTN_RED_P, BTN_VAMP_FORM, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, HUE_RED, "뱀파폼")
    Gumps.AddButton(gd, 135, y, BTN_RED_N, BTN_RED_P, BTN_FLY,       1, 0)
    Gumps.AddLabel(gd,  169, y+2, HUE_RED, "비행")
    y += 32
    Gumps.AddButton(gd, 8,   y, BTN_RED_N, BTN_RED_P, 0, 0, 1)
    Gumps.AddLabel(gd,  42,  y+2, HUE_RED, "◀ 돌아가기")

    # ── Page 5: 보스설정 ──
    Gumps.AddPage(gd, 5)
    Gumps.AddLabel(gd, 10, 33, HUE_RED, "[ 보스설정 ]")
    y = 60
    if boss_alert_enabled:
        ba_n, ba_p, ba_hue, ba_lbl = BTN_GREEN_N, BTN_GREEN_P, HUE_GREEN, "보스알림 ON"
    else:
        ba_n, ba_p, ba_hue, ba_lbl = BTN_RED_N,   BTN_RED_P,   HUE_RED,   "보스알림 OFF"
    if boss_loot_enabled:
        bl_n, bl_p, bl_hue, bl_lbl = BTN_GREEN_N, BTN_GREEN_P, HUE_GREEN, "보스루팅 ON"
    else:
        bl_n, bl_p, bl_hue, bl_lbl = BTN_RED_N,   BTN_RED_P,   HUE_RED,   "보스루팅 OFF"
    Gumps.AddButton(gd, 8,   y, ba_n, ba_p, BTN_BOSS_ALERT, 1, 0)
    Gumps.AddLabel(gd,  42,  y+2, ba_hue, ba_lbl)
    Gumps.AddButton(gd, 135, y, bl_n, bl_p, BTN_BOSS_LOOT,  1, 0)
    Gumps.AddLabel(gd,  169, y+2, bl_hue, bl_lbl)
    y += 30
    Gumps.AddButton(gd, 8,   y, BTN_RED_N, BTN_RED_P, 0, 0, 1)
    Gumps.AddLabel(gd,  42,  y+2, HUE_RED, "◀ 돌아가기")

    Gumps.SendGump(GUMP_ID, Player.Serial, 100, 400, gd.gumpDefinition, gd.gumpStrings)


# =============================================================================
# 메인 루프
# =============================================================================
protected_backpack = collect_all_items(Player.Backpack.Serial)
Player.HeadMessage(HUE_GREEN, "백팩 보호 완료: {}개".format(len(protected_backpack)))
send_discord_webhook("✅ **[GGO 리더 컨트롤]** {} 구동 시작 | 보스알림 ON | 보스루팅 ON".format(Player.Name))
draw_gump()

while True:
    Misc.Pause(50)
    now = time.time()

    if now - last_trim_time >= 30.0:
        trim_working_set()
        last_trim_time = now

    if boss_alert_enabled and now - last_boss_check >= 3.0:
        check_boss_alert()
        last_boss_check = now

    if boss_loot_enabled and now - last_loot_check >= 1.0:
        check_boss_loot()
        last_loot_check = now

    if auto_wf_enabled and wf_pos is not None and now - last_wf_time >= 1.5:
        do_auto_wildfire()
        last_wf_time = now

    # ── 사망 / 부활 / 시체 추적 ──
    handle_revival(revival_state, DRESS_LIST_NAME, enable_loot=False,
                   use_undertaker=USE_UNDERTAKER_STAFF)

    md = Gumps.GetGumpData(GUMP_ID)
    if not md or md.buttonid <= 0:
        continue

    btn = md.buttonid
    Gumps.SendAction(GUMP_ID, 0)
    Gumps.CloseGump(GUMP_ID)

    # ── 메인 페이지 ──
    if btn == BTN_ARMOR:    Player.ChatSay("!아머")
    elif btn == BTN_AGGRO:  Player.ChatSay("!선공")
    elif btn == BTN_NORMAL: Player.ChatSay("!정상화")
    elif btn == BTN_MAX:    Player.ChatSay("!max")

    elif btn == BTN_ENEMY:
        enemy_active = not enemy_active
        if enemy_active:
            Player.ChatSay("!에너미")
        else:
            Player.ChatSay("!에너미오프")

    elif btn == BTN_CHAMP:
        Player.HeadMessage(HUE_TITLE, "챔프 구역 지정: 봇을 클릭하세요")
        serial = Target.PromptTarget("챔프 구역 지정할 봇 선택")
        if serial and serial != -1:
            mob = Mobiles.FindBySerial(serial)
            if mob and not mob.IsGhost:
                Player.ChatSay("!챔프 {}".format(mob.Name))
            else:
                Player.HeadMessage(HUE_RED, "유효한 봇 캐릭터를 선택하세요")

    elif btn == BTN_TARGET:
        serial = Target.PromptTarget("바드에게 공격 명령을 내릴 적을 선택하세요")
        if serial and serial != -1:
            hex_serial = "{0:#010x}".format(serial)
            Player.ChatSay(hex_serial)
            Player.HeadMessage(68, "Target Sent: " + hex_serial)

    elif btn == BTN_PAUSE:
        leader_paused = not leader_paused
        if leader_paused:
            Player.ChatSay("!정지")
            Player.HeadMessage(HUE_RED, "★일시정지★")
        else:
            Player.ChatSay("!재개")
            Player.HeadMessage(HUE_GREEN, "★재개★")

    elif btn == BTN_FOLLOWING:
        follow_active = not follow_active
        if follow_active:
            Player.ChatSay("!팔로우")
            Player.HeadMessage(HUE_GREEN, "★팔로잉 모드★")
        else:
            Player.ChatSay("!정상화")
            Player.HeadMessage(HUE_RED, "★일반 모드 복귀★")

    elif btn == BTN_BOSS_ALERT:
        boss_alert_enabled = not boss_alert_enabled
        if boss_alert_enabled:
            Player.HeadMessage(HUE_GREEN, "보스 알림 ON")
        else:
            Player.HeadMessage(HUE_RED, "보스 알림 OFF")

    elif btn == BTN_BOSS_LOOT:
        boss_loot_enabled = not boss_loot_enabled
        if boss_loot_enabled:
            known_corpses.clear()
            Player.HeadMessage(HUE_GREEN, "보스 루팅 ON")
        else:
            Player.HeadMessage(HUE_RED, "보스 루팅 OFF")

    elif btn == BTN_AUTO_WF:
        if not auto_wf_enabled:
            pos = Target.PromptGroundTarget("와일드파이어 지점 선택 (지점 클릭)")
            if pos and pos.X != 0:
                wf_pos = pos
                auto_wf_enabled = True
                Player.HeadMessage(HUE_GREEN, "와파 ON ({},{})".format(pos.X, pos.Y))
            else:
                Player.HeadMessage(HUE_RED, "지점 선택 취소됨")
        else:
            auto_wf_enabled = False
            wf_pos = None
            Player.HeadMessage(HUE_RED, "와파 자동시전 OFF")

    # ── 펫 페이지 ──
    elif btn == BTN_PET_SUMMON: Player.ChatSay("!소환")
    elif btn == BTN_PET_FEED:   Player.ChatSay("!밥줘")
    elif btn == BTN_PET_GATE:   Player.ChatSay("!게이트")
    elif btn == BTN_HELP_ESCAPE:
        do_help_escape()
        Player.ChatSay("!헬프")

    # ── 정리 페이지 ──
    elif btn == BTN_SORT_SELL:      Player.ChatSay("!sell")
    elif btn == BTN_SORT_SANGHACHA: Player.ChatSay("!상하차")
    elif btn == BTN_SORT_PAS:       Player.ChatSay("!파스정리")
    elif btn == BTN_SORT_PINK:      Player.ChatSay("!분홍정리")
    elif btn == BTN_SORT_SKULL:     Player.ChatSay("!해골정리")
    elif btn == BTN_SORT_TRASH:     Player.ChatSay("!trash")

    elif btn == BTN_LEADER_PAS:
        serial = Target.PromptTarget("파스 넣을 컨테이너 선택")
        if serial and serial != -1:
            do_item_sort(0x14F0, 0x0496, serial)

    elif btn == BTN_LEADER_PINK:
        serial = Target.PromptTarget("분홍 넣을 컨테이너 선택")
        if serial and serial != -1:
            do_item_sort(0x14EF, 0x0490, serial)

    elif btn == BTN_LEADER_SANGHACHA:
        serial = Target.PromptTarget("상하차 대상 컨테이너 선택")
        if serial and serial != -1:
            do_leader_sanghacha(serial)

    elif btn == BTN_LEADER_SELL:
        sell_powerscrolls(NPC_SELL, SELL_AGENT_LIST_NAME, use_sell_agent=True)

    # ── 직업특화 페이지 ──
    elif btn == BTN_BARD_DECO:  Player.ChatSay("!디코")
    elif btn == BTN_BARD_PROVO: Player.ChatSay("!프로보")
    elif btn == BTN_BARD_PF:    Player.ChatSay("pf")
    elif btn == BTN_BARD_GOLD:  Player.ChatSay("!송금")
    elif btn == BTN_VAMP_FORM:  Player.ChatSay("!뱀폼")
    elif btn == BTN_FLY:        Player.ChatSay("!날아")

    Misc.Pause(50)
    draw_gump()
