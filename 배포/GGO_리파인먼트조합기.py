# -*- coding: utf-8 -*-
# ==============================================================================
# [GGO 리파인먼트 조합기] v1.1
# ==============================================================================

SCRIPT_ID = "GGO_REFINEMENT"
SCRIPT_NAME = "GGO_리파인먼트조합기"
CURRENT_VERSION = "1.1"

import os, sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from GGO_update_check import notify_update_async
    notify_update_async(SCRIPT_ID, SCRIPT_NAME, CURRENT_VERSION)
except Exception:
    pass

# [기능]
# 1. 메인 검프 메뉴 : 시작/설정/수량체크/종료
# 2. JSON 설정 저장 : 기본 보관함 + 최고등급 보관함
# 3. 다중 상자 지원 : 시작 시 추가 컨테이너 지정 (ESC = 없음)
# 4. 조합 결과 반납 : 최상위 등급 → 최고등급 보관함, 나머지 → 기본 보관함
# 5. 수량 체크      : 분류별 통계 + Windows Forms 팝업, 아이템 꺼내기 지원
# ==============================================================================

import clr
import System
import json
import time

from System import Environment
from System.IO import Directory, Path, File
from System.Threading import Thread, ThreadStart, ThreadAbortException

clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')

from System.Drawing import Point, Color, Size, Font, FontStyle
from System.Windows.Forms import (
    Form, ListView, Panel, Button, ListViewItem,
    Application, DockStyle, View, ColumnHeader,
    FormStartPosition, Label, FlowLayoutPanel,
    ScrollBars, BorderStyle, Padding, MessageBox,
    DialogResult, NumericUpDown
)

# ==============================================================================
# script_settings.json 기본값
# ------------------------------------------------------------------------------
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 실제 사용자 설정은 스크립트 파일을 직접 수정하지 말고
# GGO_Settings/GGO_리파인먼트조합기/script_settings.json에서 수정하세요.
# ==============================================================================
AMALGAMATOR_ID = 0x9966

# 아이템 이동 후 다음 이동 전 대기시간 (ms)
# 너무 짧으면 서버 행동제한 발생, 너무 길면 느려짐
MOVE_DELAY = 500

# 개량혼합기 타겟 대기 시간 (ms)
AMALG_TARGET_TIMEOUT = 4000

# 개량혼합기 타겟 수신 최대 재시도 횟수
AMALG_MAX_RETRIES = 3

# 아이템 도착 확인 최대 대기 (ms)
MOVE_VERIFY_TIMEOUT = 3000

REFINE_SCRIPT_SETTINGS_DEFAULTS = {
    "amalgamator_id": AMALGAMATOR_ID,
    "move_delay": MOVE_DELAY,
    "amalg_target_timeout": AMALG_TARGET_TIMEOUT,
    "amalg_max_retries": AMALG_MAX_RETRIES,
    "move_verify_timeout": MOVE_VERIFY_TIMEOUT
}

REFINE_SCRIPT_SETTINGS_ORDER = [
    "amalgamator_id",
    "move_delay",
    "amalg_target_timeout",
    "amalg_max_retries",
    "move_verify_timeout"
]

REFINE_SCRIPT_SETTINGS_GUIDE = """GGO_리파인먼트조합기 script_settings.json 설명

이 파일은 리파인먼트 조합기의 공용 설정 파일입니다.
숫자는 숫자로 입력하세요.
쉼표는 지우지 마세요.

amalgamator_id:
  개량혼합기 아이템 ID입니다.
  예: 39270
  16진수로 넣을 경우 큰따옴표로 감싸세요. 예: "0x9966"

move_delay:
  아이템 이동 후 다음 이동 전 대기시간(ms)입니다.

amalg_target_timeout:
  개량혼합기 타겟 대기 시간(ms)입니다.

amalg_max_retries:
  개량혼합기 타겟 수신 최대 재시도 횟수입니다.

move_verify_timeout:
  아이템 도착 확인 최대 대기시간(ms)입니다.
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
    ensure_script_settings_guide(SCRIPT_NAME, REFINE_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, REFINE_SCRIPT_SETTINGS_DEFAULTS, REFINE_SCRIPT_SETTINGS_ORDER)
    AMALGAMATOR_ID = _setting_int(_script_settings.get("amalgamator_id", AMALGAMATOR_ID), AMALGAMATOR_ID)
    MOVE_DELAY = _setting_int(_script_settings.get("move_delay", MOVE_DELAY), MOVE_DELAY)
    AMALG_TARGET_TIMEOUT = _setting_int(_script_settings.get("amalg_target_timeout", AMALG_TARGET_TIMEOUT), AMALG_TARGET_TIMEOUT)
    AMALG_MAX_RETRIES = _setting_int(_script_settings.get("amalg_max_retries", AMALG_MAX_RETRIES), AMALG_MAX_RETRIES)
    MOVE_VERIFY_TIMEOUT = _setting_int(_script_settings.get("move_verify_timeout", MOVE_VERIFY_TIMEOUT), MOVE_VERIFY_TIMEOUT)
except Exception:
    load_character_settings = None
    save_character_settings = None
    get_character_settings_path = None

# ==============================================================================
# [아이템 정의]
# ==============================================================================

CATEGORIES = [
    {
        "name":  "세척제(Wash)",
        "id":    0x142A,
        "types": ['Hide', 'Bone', 'Studded Samurai', 'Studded Leather']
    },
    {
        "name":  "중화제(Cure)",
        "id":    0x142B,
        "types": ['Hide', 'Bone', 'Studded Samurai', 'Studded Leather']
    },
    {
        "name":  "윤택제(Scour)",
        "id":    0x4CD9,
        "types": ['Chainmail', 'Dragon', 'Gargish Platemail', 'Samurai', 'Ringmail', 'Armor Type: Platemail']
    },
    {
        "name":  "유악제(Varnish)",
        "id":    0x2D61,
        "types": ['Gargish Stone', 'Woodland']
    },
    {
        "name":  "광택제(Polish)",
        "id":    0x4CD8,
        "types": ['Chainmail', 'Dragon', 'Gargish Platemail', 'Samurai', 'Ringmail', 'Armor Type: Platemail']
    },
    {
        "name":  "접착제(Gloss)",
        "id":    0x4CDA,
        "types": ['Gargish Stone', 'Woodland']
    }
]

LEVELS = {
    'Defense':      2,
    'Protection':   3,
    'Hardening':    4,
    'Fortification':5
}

# 최고 등급 완성품 (이 등급의 아이템은 최고등급 보관함으로)
# Fortification은 조합 재료의 최상위 등급이며,
# 조합 완성품의 최고 등급은 Invulnerability임
TOP_LEVEL = 'Invulnerability'

# ==============================================================================
# [설정 저장/불러오기] - 레지듀모듈버전 패턴
# ==============================================================================
APPDATA     = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
LEGACY_SAVE_DIR    = Path.Combine(APPDATA, "GGO_Project", "Refine")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "Refine_Config_{0}.json".format(Player.Name))
if get_character_settings_path:
    CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
    SAVE_DIR = os.path.dirname(CONFIG_FILE)
else:
    SAVE_DIR = LEGACY_SAVE_DIR
    CONFIG_FILE = LEGACY_CONFIG_FILE

def save_config(data):
    if save_character_settings:
        save_character_settings(SCRIPT_NAME, Player.Name, data)
    else:
        if not Directory.Exists(SAVE_DIR):
            Directory.CreateDirectory(SAVE_DIR)
        File.WriteAllText(CONFIG_FILE, json.dumps(data, indent=4))
    Player.HeadMessage(68, "[리파인] 설정 저장 완료")

def load_config():
    if load_character_settings:
        try:
            data = load_character_settings(SCRIPT_NAME, Player.Name, {}, [LEGACY_CONFIG_FILE])
            return data if data else None
        except:
            pass
    if File.Exists(CONFIG_FILE):
        return json.loads(File.ReadAllText(CONFIG_FILE))
    return None

# ==============================================================================
# [전역 상태]
# ==============================================================================
state = {
    'is_running':   False,
    'default_box':  0,    # 기본 보관함
    'best_box':     0,    # 최고등급 보관함
    'extra_boxes':  [],   # 시작 시 추가 지정한 컨테이너 목록
}

MAIN_GUMP_ID = 0x47473001

# ==============================================================================
# [메인 검프]
# ==============================================================================
def show_main_gump():
    Gumps.CloseGump(MAIN_GUMP_ID)
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 280, 200, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 280, 200)

    Gumps.AddLabel(gd, 15, 12, 53, "🔮 GGO 리파인먼트 조합기 v1.1")
    Gumps.AddImageTiled(gd, 10, 32, 260, 2, 9107)

    # 상태 표시
    status_hue = 68 if state['is_running'] else 33
    status_txt = "▶ 실행 중" if state['is_running'] else "■ 대기 중"
    Gumps.AddLabel(gd, 15, 38, status_hue, status_txt)

    # 보관함 정보
    db_txt = "기본함: 0x{:X}".format(state['default_box']) if state['default_box'] else "기본함: [미설정]"
    bb_txt = "최고함: 0x{:X}".format(state['best_box'])    if state['best_box']    else "최고함: [미설정]"
    Gumps.AddLabel(gd, 15, 56, 1152, db_txt)
    Gumps.AddLabel(gd, 15, 74, 1152, bb_txt)

    Gumps.AddImageTiled(gd, 10, 96, 260, 2, 9107)

    # [버튼 레이아웃]
    # 행1: [시작/정지]  [설정]
    # 행2: [수량체크]   [종료]
    y1, y2 = 108, 152

    if state['is_running']:
        Gumps.AddButton(gd, 15,  y1, 40297, 40298, 1, 1, 0)
        Gumps.AddLabel(gd, 53,   y1 + 2, 33,   "정지")
    else:
        Gumps.AddButton(gd, 15,  y1, 40030, 40031, 1, 1, 0)
        Gumps.AddLabel(gd, 53,   y1 + 2, 68,   "시작")

    Gumps.AddButton(gd, 148, y1, 40021, 40031, 2, 1, 0)
    Gumps.AddLabel(gd, 188,  y1 + 2, 1152, "설정")

    Gumps.AddButton(gd, 15,  y2, 40021, 40031, 3, 1, 0)
    Gumps.AddLabel(gd, 53,   y2 + 2, 53,   "수량체크")

    Gumps.AddButton(gd, 148, y2, 40297, 40298, 4, 1, 0)
    Gumps.AddLabel(gd, 188,  y2 + 2, 33,   "종료")

    Gumps.SendGump(MAIN_GUMP_ID, Player.Serial, 100, 100,
                   gd.gumpDefinition, gd.gumpStrings)

# ==============================================================================
# [설정] - 기본 보관함 + 최고등급 보관함 타겟팅 후 JSON 저장
# ==============================================================================
def run_setup():
    Player.HeadMessage(158, "[설정] 기본 보관함을 선택하세요")
    db = Target.PromptTarget("기본 보관함 선택 (ESC=취소)")
    if db <= 0:
        Player.HeadMessage(33, "[설정] 취소됨 - 기본 보관함 변경 없음")
        db = state['default_box']

    Player.HeadMessage(158, "[설정] 최고등급 보관함을 선택하세요")
    bb = Target.PromptTarget("최고등급 보관함 선택 (ESC=취소)")
    if bb <= 0:
        Player.HeadMessage(33, "[설정] 취소됨 - 최고등급 보관함 변경 없음")
        bb = state['best_box']

    data = {"default_box": db, "best_box": bb}
    save_config(data)
    state['default_box'] = db
    state['best_box']    = bb

# ==============================================================================
# [조합 로직] 프로퍼티 체크
# ==============================================================================
def check_properties(item, armor_type, level_name):
    props      = Items.GetPropStringList(item.Serial)
    has_type   = False
    has_level  = False
    has_samurai = False

    for p in props:
        p_lower = p.lower()
        if armor_type.lower() in p_lower:
            has_type = True
        if level_name.lower() in p_lower:
            has_level = True
        if "samurai" in p_lower:
            has_samurai = True

    # Platemail 판별 시 Samurai 제외
    if armor_type == 'Armor Type: Platemail' and has_samurai:
        return False

    return has_type and has_level

def is_top_level(item):
    """Fortification(최고등급) 여부"""
    props = Items.GetPropStringList(item.Serial)
    for p in props:
        if TOP_LEVEL.lower() in p.lower():
            return True
    return False

# ==============================================================================
# [아이템 이동 헬퍼]
# ==============================================================================
def dump_refinements_from_backpack(all_boxes):
    """가방에 있는 모든 리파인먼트를 적절한 상자로 반납.
    Invulnerability(최고등급) → best_box, 나머지 → default_box(첫 번째 박스)
    """
    best_box    = state['best_box']
    default_box = all_boxes[0] if all_boxes else 0

    for cat in CATEGORIES:
        for item in list(Player.Backpack.Contains):
            if item.ItemID != cat["id"]:
                continue
            dest = best_box if (best_box and is_top_level(item)) else default_box
            if dest:
                Items.Move(item, dest, -1)
                Misc.Pause(600)


def safe_move_to_pack(item, max_wait_ms=None):
    """아이템을 백팩으로 이동 후 실제 도착을 검증.
    성공 : MOVE_DELAY ms 대기 후 True 반환
    실패 : False 반환 (조합 스킵 신호)
    """
    if max_wait_ms is None:
        max_wait_ms = MOVE_VERIFY_TIMEOUT

    serial = item.Serial
    Items.Move(item, Player.Backpack.Serial, -1)

    interval = 200
    elapsed  = 0
    while elapsed < max_wait_ms:
        Misc.Pause(interval)
        elapsed += interval
        verify = Items.FindBySerial(serial)
        if verify and verify.RootContainer == Player.Backpack.Serial:
            Misc.Pause(MOVE_DELAY)  # 서버 행동제한 회피
            return True

    # 타임아웃 - 손에 든 채로 걸렸을 가능성이 있으므로 강제 드롭
    Items.DropFromHand(Player.Backpack, Player.Backpack)
    Misc.Pause(400)
    verify = Items.FindBySerial(serial)
    if verify and verify.RootContainer == Player.Backpack.Serial:
        return True

    Player.HeadMessage(33, "[리파인] ⚠ 아이템 이동 실패 (시리얼: 0x{:X}) - 이번 조합 스킵".format(serial))
    return False


def try_use_amalgamator(amalg, max_retries=3, timeout_ms=4000):
    """개량혼합기 사용 후 타겟 커서 수신을 재시도 포함하여 안정적으로 대기.
    타겟 수신 성공 : True 반환
    max_retries 회 모두 실패 : False 반환
    
    서버 렉으로 타겟 커서가 늦게 도착하는 경우가 많으므로
    UseItem 후 잔류 타겟 정리, 충분한 대기, 재시도 순으로 처리.
    """
    for attempt in range(1, max_retries + 1):
        # 혹시 남아있는 타겟 커서 먼저 정리
        if Target.HasTarget():
            Target.Cancel()
            Misc.Pause(300)

        Items.UseItem(amalg.Serial)
        Misc.Pause(500)  # 서버 처리 여유 시간

        if Target.WaitForTarget(timeout_ms, False):
            return True

        Player.HeadMessage(33, "[리파인] 혼합기 타겟 미수신 ({}/{}) - {}ms 후 재시도".format(
            attempt, max_retries, 1000))
        Misc.Pause(1000)

    Player.HeadMessage(33, "[리파인] ⚠ 혼합기 타겟 {}회 모두 실패 - 이번 조합 스킵".format(max_retries))
    return False


def reorganize_boxes(all_boxes):
    """박스 내 아이템을 올바른 위치로 정리.

    1. 모든 박스(default + extra) 안의 Invulnerability → best_box
    2. extra_boxes 안의 남은 리파인먼트 → default_box
    """
    best_box    = state['best_box']
    default_box = all_boxes[0] if all_boxes else 0
    extra_boxes = all_boxes[1:]  # default_box 제외 추가 박스들

    cat_ids = {cat["id"] for cat in CATEGORIES}

    # 1단계: 모든 박스에서 Invulnerability → best_box
    if best_box:
        for box_serial in all_boxes:
            if box_serial == best_box:
                continue  # best_box 자체는 스킵
            box_obj = Items.FindBySerial(box_serial)
            if not box_obj:
                continue
            Items.UseItem(box_serial)
            Misc.Pause(800)
            if not box_obj.Contains:
                continue
            for item in list(box_obj.Contains):
                if item.ItemID in cat_ids and is_top_level(item):
                    Misc.SendMessage("[정리] Invulnerability → 최고등급 보관함: {}".format(
                        item.Name), 1271)
                    Items.Move(item, best_box, -1)
                    Misc.Pause(600)

    # 2단계: extra_boxes 잔여 리파인먼트 → default_box
    if default_box and extra_boxes:
        for box_serial in extra_boxes:
            box_obj = Items.FindBySerial(box_serial)
            if not box_obj:
                continue
            Items.UseItem(box_serial)
            Misc.Pause(800)
            if not box_obj.Contains:
                continue
            for item in list(box_obj.Contains):
                if item.ItemID in cat_ids and not is_top_level(item):
                    Misc.SendMessage("[정리] 자투리 → 기본 보관함: {}".format(
                        item.Name), 89)
                    Items.Move(item, default_box, -1)
                    Misc.Pause(600)

# ==============================================================================
# [수량 체크 Windows Forms]  꼬오거나이저 패턴 참조
# ==============================================================================
class CountCheckForm(Form):
    """리파인먼트 분류별 수량 현황 및 꺼내기 팝업"""

    def __init__(self, item_data):
        Form.__init__(self)
        self.item_data   = item_data
        self.sort_col    = 2   # 기본: 등급열
        self.sort_asc    = True
        self.Text        = "GGO 리파인먼트 수량 체크"
        self.Size        = Size(700, 520)
        self.BackColor   = Color.FromArgb(25, 25, 25)
        self.ForeColor   = Color.FromArgb(231, 231, 231)
        self.StartPosition = FormStartPosition.CenterScreen
        self._init_ui()

    def _init_ui(self):
        # 타이틀 라벨
        title = Label()
        title.Text      = "분류별 리파인먼트 현황  (행 선택 후 꺼내기)"
        title.Dock      = DockStyle.Top
        title.Height    = 34
        title.ForeColor = Color.Gold
        title.Font      = Font("Malgun Gothic", 11, FontStyle.Bold)
        title.TextAlign = System.Drawing.ContentAlignment.MiddleCenter

        # 리스트뷰
        self.lv = ListView()
        self.lv.Dock          = DockStyle.Fill
        self.lv.View          = View.Details
        self.lv.FullRowSelect  = True
        self.lv.MultiSelect    = True
        self.lv.GridLines      = True
        self.lv.BackColor      = Color.FromArgb(30, 30, 30)
        self.lv.ForeColor      = Color.White
        self.lv.Font           = Font("Malgun Gothic", 9)

        self.lv.Columns.Add("카테고리",     160)
        self.lv.Columns.Add("종류(갑옷)",   160)
        self.lv.Columns.Add("등급",          110)
        self.lv.Columns.Add("수량",           60)
        self.lv.Columns.Add("보관함",        140)

        # 컨럼 헤더 클릭 정렬 연결
        self.lv.ColumnClick += self._on_column_click

        self._populate()

        # 하단 버튼 패널
        bottom = Panel()
        bottom.Dock      = DockStyle.Bottom
        bottom.Height    = 46
        bottom.BackColor = Color.FromArgb(32, 32, 32)
        bottom.Padding   = Padding(6)

        take_btn = Button()
        take_btn.Text      = "📦 꺼내기"
        take_btn.Dock      = DockStyle.Left
        take_btn.Width     = 100
        take_btn.BackColor = Color.FromArgb(0, 122, 204)
        take_btn.ForeColor = Color.White
        take_btn.Font      = Font("Malgun Gothic", 9, FontStyle.Bold)
        take_btn.Click    += self._on_take

        # 수량 입력 라벨
        qty_label = Label()
        qty_label.Text      = "수량:"
        qty_label.Dock      = DockStyle.Left
        qty_label.Width     = 38
        qty_label.ForeColor = Color.White
        qty_label.Font      = Font("Malgun Gothic", 9)
        qty_label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter

        # 수량 입력 NumericUpDown
        self.qty_input = NumericUpDown()
        self.qty_input.Dock      = DockStyle.Left
        self.qty_input.Width     = 65
        self.qty_input.Minimum   = 1
        self.qty_input.Maximum   = 9999
        self.qty_input.Value     = 1
        self.qty_input.BackColor = Color.FromArgb(50, 50, 50)
        self.qty_input.ForeColor = Color.White
        self.qty_input.Font      = Font("Malgun Gothic", 10, FontStyle.Bold)

        close_btn = Button()
        close_btn.Text      = "닫기"
        close_btn.Dock      = DockStyle.Right
        close_btn.Width     = 80
        close_btn.BackColor = Color.FromArgb(80, 80, 80)
        close_btn.ForeColor = Color.White
        close_btn.Click    += self._on_close

        # DockStyle.Left는 추가 순서대로 왼쪽 → 오른쪽 배치
        bottom.Controls.Add(take_btn)
        bottom.Controls.Add(qty_label)
        bottom.Controls.Add(self.qty_input)
        bottom.Controls.Add(close_btn)

        # 행 선택 이벤트: 선택한 행의 수량으로 최대값 갱신
        self.lv.SelectedIndexChanged += self._on_selection_changed

        self.Controls.Add(self.lv)
        self.Controls.Add(title)
        self.Controls.Add(bottom)

    def _populate(self):
        # 정렬
        col_keys = ['cat_name', 'armor_type', 'level_name', 'count', 'box_label']
        key      = col_keys[self.sort_col] if self.sort_col < len(col_keys) else 'level_name'
        self.item_data.sort(key=lambda r: r[key], reverse=not self.sort_asc)

        # 등급 정렬 시 슈퍼블 순서
        LEVEL_ORDER = {'Defense':1,'Protection':2,'Hardening':3,'Fortification':4,'Invulnerability':5}
        if key == 'level_name':
            self.item_data.sort(
                key=lambda r: LEVEL_ORDER.get(r['level_name'], 0),
                reverse=not self.sort_asc
            )

        self.lv.Items.Clear()
        self.lv.BeginUpdate()
        for row in self.item_data:
            lv_item = ListViewItem(row['cat_name'])
            lv_item.SubItems.Add(row['armor_type'])
            lv_item.SubItems.Add(row['level_name'])
            lv_item.SubItems.Add(str(row['count']))
            lv_item.SubItems.Add(row['box_label'])
            lv_item.Tag = row

            # 등급에 따른 색상
            lvl = row['level_name']
            if lvl == 'Invulnerability':
                lv_item.ForeColor = Color.FromArgb(255, 100, 100)  # 연합금
            elif lvl == 'Fortification':
                lv_item.ForeColor = Color.Gold
            elif lvl == 'Hardening':
                lv_item.ForeColor = Color.Orange
            elif lvl == 'Protection':
                lv_item.ForeColor = Color.LightSkyBlue
            else:
                lv_item.ForeColor = Color.White

            self.lv.Items.Add(lv_item)
        self.lv.EndUpdate()

    def _on_column_click(self, sender, e):
        """컬럼 헤더 클릭 시 오름차순/내림차순 토글 정렬"""
        if self.sort_col == e.Column:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = e.Column
            self.sort_asc = True
        self._populate()


    def _on_selection_changed(self, sender, e):
        """행 선택 시 수량 입력칸의 최대값을 해당 행의 재고 수량으로 갱신"""
        if self.lv.SelectedItems.Count == 1:
            row = self.lv.SelectedItems[0].Tag
            max_qty = row['count']
            self.qty_input.Maximum = max_qty
            if self.qty_input.Value > max_qty:
                self.qty_input.Value = max_qty
        elif self.lv.SelectedItems.Count == 0:
            self.qty_input.Maximum = 9999

    def _on_take(self, sender, e):
        if self.lv.SelectedItems.Count == 0:
            MessageBox.Show("꺼낼 항목을 선택하세요.", "알림")
            return

        want = int(self.qty_input.Value)
        moved_total = 0

        for sel in self.lv.SelectedItems:
            row = sel.Tag
            # 이 행에서 꺼낼 수량 = 입력값과 재고 중 작은 값
            to_take = min(want, len(row['serials']))
            for serial in row['serials'][:to_take]:
                item = Items.FindBySerial(serial)
                if item:
                    Items.Move(item, Player.Backpack.Serial, -1)
                    Misc.Pause(600)
                    moved_total += 1

        Player.HeadMessage(68, "[리파인] 꺼내기 완료! ({}개)".format(moved_total))
        # 데이터 갱신
        new_data = scan_all_boxes()
        self.item_data = new_data
        self._populate()

    def _on_close(self, sender, e):
        self.Close()


def scan_all_boxes():
    """모든 지정 상자를 스캔하여 분류별 통계 집계
    - default_box + extra_boxes : LEVELS 등급(Defense~Fortification) 및 Invulnerability 모두 스캔
    - best_box                  : Invulnerability 등급만 스캔
    """
    default_box = state['default_box']
    best_box    = state['best_box']
    extra_boxes = state['extra_boxes']

    # 일반 박스 목록 (default + extra, 중복 제거)
    normal_boxes = []
    seen = set()
    for b in ([default_box] + extra_boxes):
        if b and b not in seen:
            normal_boxes.append(b)
            seen.add(b)

    # 박스 레이블
    def box_label(b):
        if b == default_box:   return "기본함"
        if b == best_box:      return "최고함"
        return "추가함-0x{:X}".format(b)

    # 스캔 대상 등급 = LEVELS 키 + TOP_LEVEL
    all_level_names = list(LEVELS.keys()) + [TOP_LEVEL]

    result = []

    # 일반 박스: 모든 등급 스캔
    for box_serial in normal_boxes:
        box_obj = Items.FindBySerial(box_serial)
        if not box_obj:
            continue
        Items.UseItem(box_serial)
        Misc.Pause(800)
        if not box_obj.Contains:
            continue
        for cat in CATEGORIES:
            for a_type in cat["types"]:
                for level_name in all_level_names:
                    matching = [
                        item.Serial for item in box_obj.Contains
                        if item.ItemID == cat["id"] and check_properties(item, a_type, level_name)
                    ]
                    if matching:
                        result.append({
                            'cat_name':   cat["name"],
                            'armor_type': a_type,
                            'level_name': level_name,
                            'count':      len(matching),
                            'serials':    matching,
                            'box_serial': box_serial,
                            'box_label':  box_label(box_serial),
                        })

    # 최고등급 박스: Invulnerability만 스캔
    if best_box and best_box not in seen:
        box_obj = Items.FindBySerial(best_box)
        if box_obj:
            Items.UseItem(best_box)
            Misc.Pause(800)
            if box_obj.Contains:
                for cat in CATEGORIES:
                    for a_type in cat["types"]:
                        matching = [
                            item.Serial for item in box_obj.Contains
                            if item.ItemID == cat["id"] and check_properties(item, a_type, TOP_LEVEL)
                        ]
                        if matching:
                            result.append({
                                'cat_name':   cat["name"],
                                'armor_type': a_type,
                                'level_name': TOP_LEVEL,
                                'count':      len(matching),
                                'serials':    matching,
                                'box_serial': best_box,
                                'box_label':  "최고함",
                            })

    # 백팩도 체크
    for cat in CATEGORIES:
        for a_type in cat["types"]:
            for level_name in all_level_names:
                matching = [
                    item.Serial for item in Player.Backpack.Contains
                    if item.ItemID == cat["id"] and check_properties(item, a_type, level_name)
                ]
                if matching:
                    result.append({
                        'cat_name':   cat["name"],
                        'armor_type': a_type,
                        'level_name': level_name,
                        'count':      len(matching),
                        'serials':    matching,
                        'box_serial': Player.Backpack.Serial,
                        'box_label':  "가방",
                    })

    return result


def show_count_check():
    """수량 체크 팝업 실행"""
    Player.HeadMessage(53, "[리파인] 수량 체크 중... 잠시 기다려주세요.")
    data = scan_all_boxes()
    if not data:
        Player.HeadMessage(33, "[리파인] 지정된 상자에 리파인먼트가 없습니다.")
        return

    def _run():
        try:
            Application.Run(CountCheckForm(data))
        except:
            pass

    t = Thread(ThreadStart(_run))
    t.IsBackground = True
    t.Start()

# ==============================================================================
# [조합 루프] - 다중 박스 지원
# ==============================================================================
def run_combine_loop():
    """모든 지정 박스를 대상으로 무한 조합 루프 실행"""
    amalg = Items.FindByID(AMALGAMATOR_ID, -1, Player.Backpack.Serial)
    if not amalg:
        Player.HeadMessage(33, "[리파인] 가방에 개량혼합기가 없습니다!")
        return

    default_box = state['default_box']
    best_box    = state['best_box']
    extra_boxes = state['extra_boxes']

    # 사용할 모든 박스 목록
    all_boxes = []
    seen = set()
    for b in ([default_box] + extra_boxes):
        if b and b not in seen:
            all_boxes.append(b)
            seen.add(b)

    if not all_boxes:
        Player.HeadMessage(33, "[리파인] 보관함이 설정되지 않았습니다!")
        return

    # 초기화: 가방에 굴러다니는 잔여물 상자로 이동
    for b in all_boxes:
        Items.UseItem(b)
        Misc.Pause(800)
    dump_refinements_from_backpack(all_boxes)

    # 초기 정리: 기존 박스 내 Invulnerability → best_box, 추가박스 자투리 → default_box
    Misc.SendMessage("[리파인] 초기 박스 정리 중...", 89)
    reorganize_boxes(all_boxes)

    Misc.SendMessage("=== [리파인] 다중 박스 조합 시작 ({0}개 박스) ===".format(len(all_boxes)), 68)

    cycle_count = 1
    keep_running = True

    while keep_running and state['is_running']:
        keep_running = False
        Misc.SendMessage("▶ [사이클 {}] 전체 검사 시작...".format(cycle_count), 89)

        for cat in CATEGORIES:
            if not state['is_running']:
                break
            cat_name  = cat["name"]
            cat_id    = cat["id"]
            cat_types = cat["types"]

            for a_type in cat_types:
                if not state['is_running']:
                    break
                for level_name, req_count in LEVELS.items():
                    if not state['is_running']:
                        break

                    # 모든 박스에서 해당 조건 아이템 수집
                    matching_items = []
                    for box_serial in all_boxes:
                        box_obj = Items.FindBySerial(box_serial)
                        if not box_obj or not box_obj.Contains:
                            continue
                        for item in box_obj.Contains:
                            if item.ItemID == cat_id:
                                if check_properties(item, a_type, level_name):
                                    matching_items.append(item)

                    # 필요 개수 충족 시 조합
                    while len(matching_items) >= req_count and state['is_running']:
                        keep_running = True

                        to_combine    = matching_items[:req_count]
                        matching_items = matching_items[req_count:]

                        Misc.SendMessage("[{}] {} - {} {}개 조합!".format(
                            cat_name, a_type, level_name, req_count), 55)

                        # 1. 가방으로 꺼내기 (도착 검증 포함)
                        arrived = []
                        for c_item in to_combine:
                            if safe_move_to_pack(c_item, max_wait_ms=3000):
                                arrived.append(c_item)
                            else:
                                # 이동 실패한 아이템이 있으면 이번 조합 전체 스킵
                                break

                        if len(arrived) < req_count:
                            # 일부만 도착 → 가방 정리 후 다음 사이클로
                            Player.HeadMessage(33, "[리파인] 재료 이동 불완전 ({}/{}개) - 이번 조합 스킵".format(
                                len(arrived), req_count))
                            dump_refinements_from_backpack(all_boxes)
                            Misc.Pause(500)
                            continue

                        # 2. 개량혼합기 사용 (재시도 포함)
                        if not try_use_amalgamator(amalg, max_retries=3, timeout_ms=4000):
                            dump_refinements_from_backpack(all_boxes)
                            continue

                        # 3. 순서대로 타겟팅 (백팩에 도착한 것만)
                        for c_item in arrived:
                            verify = Items.FindBySerial(c_item.Serial)
                            if verify and verify.RootContainer == Player.Backpack.Serial:
                                Target.TargetExecute(c_item.Serial)
                                Target.WaitForTarget(1500, False)
                                Misc.Pause(600)
                            else:
                                Player.HeadMessage(33, "[리파인] ⚠ 타겟 시점에 아이템 미존재 - 스킵")

                        Target.Cancel()
                        Misc.Pause(800)

                        # 4. 결과물 반납 (최고등급 → best_box, 나머지 → default_box)
                        dump_refinements_from_backpack(all_boxes)

        cycle_count += 1

    # 종료 후 최종 정리
    reorganize_boxes(all_boxes)

    if state['is_running']:
        Player.HeadMessage(68, "✅ 더 이상 조합할 항목이 없습니다. 정리 완료!")
        Misc.SendMessage("=== [리파인] 조합 루프 종료 ===", 68)

    state['is_running'] = False

# ==============================================================================
# [시작 동작] - 추가 컨테이너 지정 + 조합 루프
# ==============================================================================
def start_action():
    # 설정이 없으면 먼저 설정
    if not state['default_box']:
        Player.HeadMessage(33, "[리파인] 기본 보관함이 설정되지 않았습니다. 설정을 먼저 진행합니다.")
        run_setup()
        if not state['default_box']:
            return

    # 추가 컨테이너 지정 루프
    state['extra_boxes'] = []
    Player.HeadMessage(158, "[리파인] 추가 컨테이너를 선택하세요. (없으면 ESC)")
    slot_num = 1
    while True:
        Player.HeadMessage(158, "[추가박스 #{0}] 타겟팅 (없으면 ESC)".format(slot_num))
        serial = Target.PromptTarget("추가 박스 #{0} (ESC=완료)".format(slot_num))
        if serial <= 0:
            break
        if serial == state['default_box'] or serial == state['best_box']:
            Player.HeadMessage(33, "[리파인] 이미 등록된 상자입니다.")
            continue
        state['extra_boxes'].append(serial)
        Player.HeadMessage(1271, "[리파인] 추가 박스 #{0} 등록 (0x{1:X})".format(
            slot_num, serial))
        slot_num += 1

    extra_count = len(state['extra_boxes'])
    total_count = 1 + extra_count
    Player.HeadMessage(68, "[리파인] 총 {0}개 박스로 조합 시작".format(total_count))

    state['is_running'] = True
    show_main_gump()

    # 조합 루프 실행 (메인 스레드에서 실행 - 검프 폴링과 병행)
    try:
        run_combine_loop()
    except ThreadAbortException:
        raise
    except Exception as ex:
        Player.HeadMessage(33, "[리파인] 오류: {0}".format(str(ex)))

    state['is_running'] = False
    show_main_gump()

# ==============================================================================
# [메인]
# ==============================================================================
def main():
    # 설정 불러오기
    config = load_config()
    if config:
        state['default_box'] = config.get("default_box", 0)
        state['best_box']    = config.get("best_box",    0)

    show_main_gump()
    Misc.SendMessage("[리파인] v1.1 시작 - 메뉴에서 작업을 선택하세요.", 68)

    while True:
        Misc.Pause(200)

        gd = Gumps.GetGumpData(MAIN_GUMP_ID)
        if gd and gd.buttonid > 0:
            btn = gd.buttonid
            Gumps.SendAction(MAIN_GUMP_ID, 0)
            Gumps.CloseGump(MAIN_GUMP_ID)

            if btn == 4:          # 종료
                state['is_running'] = False
                Player.HeadMessage(33, "[리파인] 스크립트 종료.")
                break

            elif btn == 1:        # 시작/정지
                if state['is_running']:
                    state['is_running'] = False
                    Player.HeadMessage(33, "[리파인] 정지 요청됨.")
                    show_main_gump()
                else:
                    start_action()   # 블로킹 실행 (완료 후 검프 갱신)

            elif btn == 2:        # 설정
                run_setup()
                show_main_gump()

            elif btn == 3:        # 수량 체크
                if not state['default_box']:
                    Player.HeadMessage(33, "[리파인] 먼저 설정에서 기본 보관함을 지정하세요.")
                    show_main_gump()
                else:
                    show_count_check()
                    show_main_gump()

if __name__ == '__main__':
    main()
