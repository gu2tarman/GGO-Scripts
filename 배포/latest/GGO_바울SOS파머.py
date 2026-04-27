# -*- coding: utf-8 -*-

SCRIPT_ID = "GGO_SOS_FARMER"
SCRIPT_NAME = "GGO_바울SOS파머"
CURRENT_VERSION = "0.6"

import os, sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from GGO_update_check import notify_update_async
    notify_update_async(SCRIPT_ID, SCRIPT_NAME, CURRENT_VERSION)
except Exception:
    pass

from System.Collections.Generic import List
from System import Int32, Byte, String, Environment
from System.IO import Directory, Path, File
from System.Net import WebClient
from System.Text import Encoding
from System.Threading import Thread, ThreadStart

import System
import re
import math
import os
import json
import time
import traceback
import ctypes

# -----------------------------------------------------------------------------
# [1] script_settings.json 기본값
# -----------------------------------------------------------------------------
#
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 사용자 설정은 스크립트 파일이 아니라
# GGO_Settings/GGO_바울SOS파머/script_settings.json에서 수정하세요.

# 월드맵 마커 표시를 위해 자신의 ClassicUO 설치 폴더 경로를 지정해주세요. (슬래시 '/' 사용 필수)
CUO_CLIENT_DIR = "C:/Users/USER/Downloads/ClassicUO"

# 외부 모니터 창 사용 여부 (True = 사용, False = 사용 안 함)
USE_MONITOR_WINDOW = True

# 파밍 모드 선택: True = 간소화 모드, False = 일반 모드
SIMPLE_MODE = True

SOS_SCRIPT_SETTINGS_DEFAULTS = {
    "simple_mode": SIMPLE_MODE,
    "use_monitor_window": USE_MONITOR_WINDOW,
    "cuo_client_dir": CUO_CLIENT_DIR
}

SOS_SCRIPT_SETTINGS_ORDER = [
    "simple_mode",
    "use_monitor_window",
    "cuo_client_dir"
]

SOS_SCRIPT_SETTINGS_GUIDE = """GGO_바울SOS파머 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 SOS 파머 운용 설정입니다.
값을 바꾼 뒤 SOS 파머 스크립트를 다시 실행하면 적용됩니다.

수정 시 주의:
- true / false 값은 반드시 소문자로 입력하세요.
- 각 줄 끝의 쉼표는 지우지 마세요.

simple_mode
  true: 간소화 모드. 상자째로 집 컨테이너에 던지고 복귀합니다.
  false: 일반 모드. 집에서 아이템을 직접 분류합니다.

use_monitor_window
  true: 외부 SOS Monitor 창을 사용합니다.
  false: 외부 모니터 창을 사용하지 않습니다.

cuo_client_dir
  ClassicUO 설치 폴더 경로입니다.
  월드맵 마커 CSV를 쓰려면 자신의 ClassicUO 경로로 수정하세요.
  예: C:/Users/USER/Downloads/ClassicUO
  경로의 역슬래시 표시는 / 로 바꿔 입력하세요.
"""

_GGO_CONFIG_READY = False
try:
    from GGO_user_config import get_discord_webhook, get_script_settings_dir, load_script_settings, ensure_script_settings_guide
    _GGO_CONFIG_READY = True
except Exception:
    pass

if _GGO_CONFIG_READY:
    try:
        ensure_script_settings_guide(SCRIPT_NAME, SOS_SCRIPT_SETTINGS_GUIDE)
        _script_settings = load_script_settings(SCRIPT_NAME, SOS_SCRIPT_SETTINGS_DEFAULTS, SOS_SCRIPT_SETTINGS_ORDER)
        SIMPLE_MODE = bool(_script_settings.get("simple_mode", SIMPLE_MODE))
        USE_MONITOR_WINDOW = bool(_script_settings.get("use_monitor_window", USE_MONITOR_WINDOW))
        CUO_CLIENT_DIR = str(_script_settings.get("cuo_client_dir", CUO_CLIENT_DIR) or CUO_CLIENT_DIR)
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
# [모듈] 외부 상태창 (Windows Forms - Multi-Thread Safe)
# -----------------------------------------------------------------------------
import clr
clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')
from System.Windows.Forms import Application, Form, Label, CheckBox, FormBorderStyle, FormStartPosition
from System.Drawing import Size, Point, Color, Font, FontStyle
from System.Threading import Thread, ThreadStart, ApartmentState # 스레드 분리용
from System import Action # 크로스 스레드 업데이트용

ggo_tracker = None

class TrackerForm(Form):
    def __init__(self):
        self.Text = "SOS Monitor"
        self.Size = Size(280, 150)
        self.TopMost = False 
        self.FormBorderStyle = FormBorderStyle.FixedToolWindow
        self.StartPosition = FormStartPosition.Manual
        self.Location = Point(50, 50)
        self.BackColor = Color.FromArgb(25, 25, 25)
        self.ForeColor = Color.White
        
        self.lbl_title = Label()
        self.lbl_title.Text = "⛵ GGO SOS Monitor"
        self.lbl_title.Font = Font("Malgun Gothic", 10, FontStyle.Bold)
        self.lbl_title.ForeColor = Color.LightSkyBlue
        self.lbl_title.Location = Point(10, 10)
        self.lbl_title.AutoSize = True
        self.Controls.Add(self.lbl_title)
        
        self.chk_topmost = CheckBox()
        self.chk_topmost.Text = "항상 위"
        self.chk_topmost.Font = Font("Malgun Gothic", 8)
        self.chk_topmost.Location = Point(200, 10)
        self.chk_topmost.AutoSize = True
        self.chk_topmost.CheckedChanged += self.OnTopMostChanged
        self.Controls.Add(self.chk_topmost)
        
        self.lbl_state = Label()
        self.lbl_state.Text = "▶ 상태: 대기중"
        self.lbl_state.Font = Font("Malgun Gothic", 10, FontStyle.Bold)
        self.lbl_state.Location = Point(12, 45)
        self.lbl_state.AutoSize = True
        self.Controls.Add(self.lbl_state)
        
        self.lbl_stats = Label()
        self.lbl_stats.Text = "✅ 처리: 0 장  |  📦 DB잔여: 0 장"
        self.lbl_stats.Font = Font("Malgun Gothic", 9)
        self.lbl_stats.Location = Point(12, 75)
        self.lbl_stats.AutoSize = True
        self.Controls.Add(self.lbl_stats)

        self.lbl_log = Label()
        self.lbl_log.Text = "로그: 스크립트 대기 중..."
        self.lbl_log.Font = Font("Malgun Gothic", 8)
        self.lbl_log.ForeColor = Color.DarkGray
        self.lbl_log.Location = Point(12, 100)
        self.lbl_log.AutoSize = True
        self.Controls.Add(self.lbl_log)

        self.lbl_error = Label()
        self.lbl_error.Text = ""
        self.lbl_error.Font = Font("Malgun Gothic", 8, FontStyle.Bold)
        self.lbl_error.ForeColor = Color.OrangeRed
        self.lbl_error.Location = Point(12, 125)
        self.lbl_error.Size = Size(255, 40)
        self.Controls.Add(self.lbl_error)

    def OnTopMostChanged(self, sender, event):
        self.TopMost = sender.Checked 

# UI 메시지 루프를 전담할 별도 스레드 함수
def _run_tracker_thread():
    global ggo_tracker
    ggo_tracker = TrackerForm()
    Application.Run(ggo_tracker) 

def InitTracker():
    global ggo_tracker
    if not USE_MONITOR_WINDOW:
        return
    if ggo_tracker is None or ggo_tracker.IsDisposed:
        t = Thread(ThreadStart(_run_tracker_thread))
        t.SetApartmentState(ApartmentState.STA)
        t.IsBackground = True
        t.Start()

def UpdateTracker(current_state, total_count, db_count, last_log=""):
    global ggo_tracker
    if not USE_MONITOR_WINDOW:
        return
    if ggo_tracker is not None and not ggo_tracker.IsDisposed and ggo_tracker.IsHandleCreated:
        try:
            def update_action():
                if current_state == "이동중":
                    ggo_tracker.lbl_state.ForeColor = Color.Gold
                elif current_state == "낚시중":
                    ggo_tracker.lbl_state.ForeColor = Color.DeepSkyBlue
                elif current_state == "정리중":
                    ggo_tracker.lbl_state.ForeColor = Color.LimeGreen
                else:
                    ggo_tracker.lbl_state.ForeColor = Color.White
                ggo_tracker.lbl_state.Text = "▶ 상태: " + current_state
                ggo_tracker.lbl_stats.Text = "✅ 처리: {} 장  |  📦 DB잔여: {} 장".format(total_count, db_count)
                if last_log:
                    ggo_tracker.lbl_log.Text = "로그: " + last_log
                ggo_tracker.lbl_error.Text = ""
            ggo_tracker.BeginInvoke(Action(update_action))
        except: pass

def UpdateTrackerError(error_msg):
    global ggo_tracker
    if not USE_MONITOR_WINDOW:
        return
    if ggo_tracker is not None and not ggo_tracker.IsDisposed and ggo_tracker.IsHandleCreated:
        try:
            def error_action():
                ggo_tracker.lbl_state.ForeColor = Color.OrangeRed
                ggo_tracker.lbl_state.Text = "▶ 상태: ⚠️ 오류"
                short_msg = error_msg[:60] + "..." if len(error_msg) > 60 else error_msg
                ggo_tracker.lbl_error.Text = "⚠️ " + short_msg
            ggo_tracker.BeginInvoke(Action(error_action))
        except: pass

def CloseTracker():
    global ggo_tracker
    if not USE_MONITOR_WINDOW:
        return
    if ggo_tracker is not None and not ggo_tracker.IsDisposed:
        try:
            def close_action():
                ggo_tracker.Close()
            ggo_tracker.Invoke(Action(close_action))
        except: pass
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

# =============================================================================
# ⛵ [BaUL SOS Farmer Official] ⛵
# =============================================================================
# 바보울온님의 소중한 원본 코드를 기반으로 GGO Project에서 재탄생시킨 공식 배포 버전입니다.
#
# [v0.43 패치노트 - 완벽 패스파인딩, 프로텍션/뱀파폼 토글 추가]
# 1. A* 패스파인딩 통합: 바다 지형 장애물 자동 우회 항해
# 2. 배 충돌 동적 우회: 좌/우/후진 다단계 회피 + 자동 경로 재계산
# 3. 진행 검프 리포트/스톱 버튼 추가
# 4. 해적모자 정밀 필터링 (찐 해적모자만 루팅)
#
# [v0.3 패치노트]
# 1. 좌표 50타일 이내 접근 시 낚시로 동선 최적화
# 2. 월드맵 마커 연동 (대기 : 녹색 / 진행 : 보라 / 스킵 : 빨강)
# 3. 수동 조작 모드 완벽 지원 (험한 지역이나 다른 방식 이동을 원하시면 사용하세요)
# 4. 스킵 / 오류 쪽지 보관 기능 및 쪽지 타겟팅 복구 기능 추가
# =============================================================================

# -----------------------------------------------------------------------------
# [전역 변수 및 설정 경로]
# -----------------------------------------------------------------------------
APPDATA = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "SOSBot")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "SOS_Config_{0}.json".format(Player.Name))
LEGACY_DB_FILE = Path.Combine(LEGACY_SAVE_DIR, "SOS_DB_{0}.json".format(Player.Name))
LEGACY_SKIP_DB_FILE = Path.Combine(LEGACY_SAVE_DIR, "SOS_SkipDB_{0}.json".format(Player.Name))
LEGACY_GRID_FILE = Path.Combine(LEGACY_SAVE_DIR, "sea_grid.bin")

SAVE_DIR = LEGACY_SAVE_DIR
if _GGO_CONFIG_READY:
    try:
        SAVE_DIR = get_script_settings_dir(SCRIPT_NAME)
    except Exception:
        SAVE_DIR = LEGACY_SAVE_DIR

CONFIG_FILE = Path.Combine(SAVE_DIR, "{0}.json".format(Player.Name))
DB_FILE = Path.Combine(SAVE_DIR, "SOS_DB_{0}.json".format(Player.Name))
SKIP_DB_FILE = Path.Combine(SAVE_DIR, "SOS_SkipDB_{0}.json".format(Player.Name))
GRID_FILE = Path.Combine(SAVE_DIR, "sea_grid.bin")

def _ensure_save_dir():
    if not Directory.Exists(SAVE_DIR):
        Directory.CreateDirectory(SAVE_DIR)

def _read_json_file(path, fallback):
    try:
        if File.Exists(path):
            return json.loads(File.ReadAllText(path))
    except:
        pass
    return fallback

def _write_json_file(path, data):
    _ensure_save_dir()
    File.WriteAllText(path, json.dumps(data, indent=4))

def _copy_legacy_file_if_needed(new_path, legacy_path):
    try:
        if not File.Exists(new_path) and File.Exists(legacy_path):
            _ensure_save_dir()
            File.Copy(legacy_path, new_path, False)
            return True
    except:
        pass
    return False

def _ensure_grid_file():
    _copy_legacy_file_if_needed(GRID_FILE, LEGACY_GRID_FILE)

# 시스템 및 보관함 변수
fishingpole = 0
Trashbag = 0
Homebook = 0
DoneBox = 0
ValuableBox = 0   # 환금(골드/보석/특수재료)
ByproductBox = 0  # 부산물(지도/빈상자/특수그물)
HighValueBox = 0  # 고가치(마법책/목걸이/해적모자 및 에러 쪽지 격리소)
SosChestContainer = 0  # [간소화 모드] 상자를 통째로 던질 컨테이너

# 분류별 아이템 ID 정의 (원작자 데이터 기반)
FishingTreasureBox = [0xa306, 0xa308, 0xe41, 0xe43, 0xA30A, 0x9a8]

# 루팅 카테고리 (화이트리스트) - 시간 단축을 위해 시약 제외
gold_id = [0x0EED]
gem_id = [0xf25,0xf13,0xf15,0xf0f,0xf11,0xf16,0x0F18,0xf10,0xf26,0x3192,0x3193,0x3194,0x3195,0x3197,0x3198,0x3199,0x1bf2]
etc_id = [0x142b,0x4cd9,0x4CD8,0x142A,0x2d61,0x4CDA,0x571c,0x1767]
byproduct_id = [0x14ec, 0xdca, 0x1ea5, 0xa414]
highvalue_id = [0xa34a, 0xa349, 0xe75]
pirate_hat_id = 0x171B

goldpocket = 0xA331
jewelpocket = 0xA333

SOSID = 0x14EE
SeaHorseID = 0x25BA
notoriety = [3, 4, 5, 6]

ThroneY = 1624
ThroneX = 1323
WorldSizeY = 4096
WorldSizeX = 5120
TilesdegreeY = 11.37777778
TilesdegreeX = 14.22222222

farmed_stats = [] 
start_time = time.time()
stuck_alert_sent = False
initial_backpack_items = [] # 스크립트 시작 시 가방 보호 목록
gate_cast_time = 0       # 게이트 시전 시각
gate_detected_time = 0   # 게이트 최초 감지 시각 (Items.FindByID 성공 시점, 시전보다 정확)
GATE_DURATION_SEC = 28   # 게이트 지속 시간 (초) - 서버별 조정 가능
GATE_MIDTASK_MARGIN = 8  # MidTask 리프레시 트리거 마진 (초) - 이 이하면 정리 중단 후 리프레시
GATE_EMERGENCY_SEC = 4   # 긴급 복귀 마진 (초) - 이 이하면 작업 중단 후 즉시 바다 복귀

def _gate_ref_time():
    """감지 시각 우선, 없으면 시전 시각 사용"""
    return gate_detected_time if gate_detected_time > 0 else gate_cast_time

def is_gate_expiring():
    """게이트 잔여시간이 긴급 마진 이하인지 체크 (True = 즉시 복귀 필요)"""
    ref = _gate_ref_time()
    if ref == 0:
        return False
    remaining = GATE_DURATION_SEC - (time.time() - ref)
    return remaining <= GATE_EMERGENCY_SEC

def is_gate_near_expiry():
    """정리 중 MidTask 리프레시 판단용 — 8초 이하면 True"""
    current_config = load_config()
    if current_config.get("gate_refresh", 0) != 1:
        return False
    ref = _gate_ref_time()
    if ref == 0:
        return False
    remaining = GATE_DURATION_SEC - (time.time() - ref)
    return remaining <= GATE_MIDTASK_MARGIN

# A* 패스파인딩 변수
SEA_GRID_LAYERS = []
SEA_GRID = None
SEA_GRID_W = 0
SEA_GRID_H = 0
SEA_GRID_BLOCK = 8
total_processed_count = 0

# -----------------------------------------------------------------------------
# [웹훅 및 통계 모듈]
# -----------------------------------------------------------------------------
looted_items_count = {}

def trim_working_set():
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
    except:
        pass

def SendDiscord(msg):
    if not WEBHOOK_URL: return
    def task():
        try:
            wc = WebClient()
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": "⛵ " + msg}, ensure_ascii=False)
            wc.UploadString(WEBHOOK_URL, "POST", payload)
        except: pass
    t = Thread(ThreadStart(task))
    t.IsBackground = True
    t.Start()

def SendSummaryReport():
    if not farmed_stats: 
        SendDiscord("**📊 [BaUL SOS Farmer Official v{0}] 종료 보고**\n파밍된 보물상자가 없습니다.".format(CURRENT_VERSION))
        return
    msg = "**📊 [BaUL SOS Farmer Official v{0}] 항해 종료 요약 보고**\n-------------------------------------------\n".format(CURRENT_VERSION)
    
    total_boxes = sum(stat['count'] for stat in farmed_stats)
    msg += "📍 총 획득 보물상자: **{}개**\n".format(total_boxes)
    msg += "📍 DB 잔여 쪽지: **{}개**\n".format(len(load_db()))
    
    msg += "-------------------------------------------\n"
    msg += "💎 **획득한 주요 전리품 요약**\n"
    if not looted_items_count:
        msg += "  - 획득한 귀중품이 없습니다.\n"
    else:
        priority_keys = ["[✨유니크 가방✨]", "[문어목걸이]", "[찐 해적모자]"]
        for key in priority_keys:
            if key in looted_items_count:
                msg += "  - **{}**: {}개\n".format(key, looted_items_count[key])
        for name, count in looted_items_count.items():
            if name not in priority_keys:
                msg += "  - {}: {}개\n".format(name, count)
            
    elapsed = int(time.time() - start_time)
    msg += "-------------------------------------------\n총 소요 시간: {0}분".format(elapsed // 60)
    SendDiscord(msg)

def HandleDeath():
    if Player.IsGhost:
        SendDiscord("💀 **[사망 경고]** {0} 캐릭터가 바다에서 사망했습니다!".format(Player.Name))
        Misc.ScriptStopAll()

# -----------------------------------------------------------------------------
# [설정 및 DB 관리]
# -----------------------------------------------------------------------------
def save_config(data):
    _write_json_file(CONFIG_FILE, data)
    Player.HeadMessage(68, "[시스템] 설정 저장 완료")

def load_config():
    if File.Exists(CONFIG_FILE): return _read_json_file(CONFIG_FILE, None)
    if _copy_legacy_file_if_needed(CONFIG_FILE, LEGACY_CONFIG_FILE):
        return _read_json_file(CONFIG_FILE, None)
    return None

def run_setup():
    Player.HeadMessage(158, "● [설정] 낚시대를 선택하세요")
    fp = Target.PromptTarget("Select Fishing Pole")
    Player.HeadMessage(158, "● [설정] 쓰레기통(가방 안)을 선택하세요")
    tb = Target.PromptTarget("Select Trashbag")
    Player.HeadMessage(158, "● [설정] 집 룬북을 선택하세요")
    hb = Target.PromptTarget("Select Homebook")
    Player.HeadMessage(158, "● [설정] 분석 완료된 쪽지가 보관된 '완료 보관함(DoneBox)'을 선택하세요")
    dbox = Target.PromptTarget("Select DoneBox")

    Player.HeadMessage(158, "● [설정] 환금 보관함(골드/보석/특수재료)을 선택하세요")
    vb = Target.PromptTarget("Valuable Box")
    Player.HeadMessage(158, "● [설정] SOS 부산물 보관함(지도/그물/빈상자)을 선택하세요")
    bpb = Target.PromptTarget("Byproduct Box")
    Player.HeadMessage(158, "● [설정] 고가치 보관함(마법책/목걸이/해적모자 및 스킵된 쪽지)을 선택하세요")
    hvb = Target.PromptTarget("HighValue Box")
    Player.HeadMessage(158, "● [간소화 모드용] 상자를 통째로 던질 컨테이너를 선택하세요")
    sos_chest = Target.PromptTarget("Select SosChestContainer")
    data = {"fishingpole": fp, "Trashbag": tb, "Homebook": hb, "DoneBox": dbox,
            "SosChestContainer": sos_chest,
            "ValuableBox": vb, "ByproductBox": bpb, "HighValueBox": hvb,
            "box_mode": 0, "loot_gems": 1, "gate_refresh": 0, "marker_maps": 0}

    save_config(data)
    return data

def load_db():
    if File.Exists(DB_FILE): return _read_json_file(DB_FILE, [])
    if _copy_legacy_file_if_needed(DB_FILE, LEGACY_DB_FILE):
        return _read_json_file(DB_FILE, [])
    return []

def save_db(data):
    _write_json_file(DB_FILE, data)

def load_skip_db():
    if File.Exists(SKIP_DB_FILE):
        return _read_json_file(SKIP_DB_FILE, [])
    if _copy_legacy_file_if_needed(SKIP_DB_FILE, LEGACY_SKIP_DB_FILE):
        return _read_json_file(SKIP_DB_FILE, [])
    return []

def save_skip_db(data):
    _write_json_file(SKIP_DB_FILE, data)

def get_map_coords(text):
    match = re.search(r"@([^@]+)@", text) 
    if not match: return None, None
    result = match.group(1)
    numbers = re.findall(r"\d+", result)   
    letters = re.findall(r"[a-zA-Z]", result)
    cardinalpoint = [char for char in letters if char.lower() != 'o']
    if len(numbers) >= 4 and len(cardinalpoint) >= 2:
        cy, cx = str(cardinalpoint[0]), str(cardinalpoint[1])
        mx1, mx2 = int(numbers[2]), int(numbers[3])
        my1, my2 = int(numbers[0]), int(numbers[1])
        if cx == 'W': tx = int(round(ThroneX - (mx2*0.016666)*TilesdegreeX - mx1*TilesdegreeX))
        else: tx = int(round(ThroneX + (mx2*0.016666)*TilesdegreeX + mx1*TilesdegreeX))
        if tx < 0: tx += WorldSizeX
        if cy == 'N': ty = int(round(ThroneY - (my2*0.016666)*TilesdegreeY - my1*TilesdegreeY))
        else: ty = int(round(ThroneY + (my2*0.016666)*TilesdegreeY + my1*TilesdegreeY))
        if ty < 0: ty += WorldSizeY
        return tx, ty
    return None, None

# -----------------------------------------------------------------------------
# [모드 A: DB 구축 및 양방향 무결성 검증]
# -----------------------------------------------------------------------------
def Build_Database():
    Player.HeadMessage(55, "▶ [DB구축/복구] 안 깐 쪽지가 든 '상자' 또는 개별 '쪽지' 선택")
    src = Target.PromptTarget("Source Box or SOS Note")
    if src <= 0: return
    if DoneBox <= 0: Player.HeadMessage(33, "설정 오류: DoneBox 없음"); return
    
    src_item = Items.FindBySerial(src)
    if not src_item: return
    
    db_data = load_db()
    skip_db = load_skip_db()
    
    if src_item.ItemID == SOSID:
        deeds = [src_item]
    else:
        Items.UseItem(src); Misc.Pause(1000)
        Items.UseItem(DoneBox); Misc.Pause(1000)
        if not src_item.Contains: return
        deeds = [item for item in src_item.Contains if item.ItemID == SOSID]
        
    count = 0
    recovered_count = 0
    for deed in deeds:
        deed_serial = deed.Serial
        
        if deed.Container != Player.Backpack.Serial:
            Items.Move(deed_serial, Player.Backpack, 1)
            timeout = 0
            while timeout < 15:
                chk = Items.FindBySerial(deed_serial)
                if chk and chk.Container == Player.Backpack.Serial:
                    break
                Misc.Pause(200)
                timeout += 1
            Misc.Pause(800)
            
        success = False
        for attempt in range(3):
            chk = Items.FindBySerial(deed_serial)
            if chk:
                Items.UseItem(chk)
            Gumps.WaitForGump(0x550a461b, 3000) 
            if Gumps.HasGump(0x550a461b):
                x, y = get_map_coords(Gumps.GetGumpRawLayout(0x550a461b))
                if x is not None:
                    is_danger = False
                    if SEA_GRID is not None:
                        bx, by = x // SEA_GRID_BLOCK, y // SEA_GRID_BLOCK
                        if 0 <= bx < SEA_GRID_W and 0 <= by < SEA_GRID_H:
                            if SEA_GRID[by * SEA_GRID_W + bx] == 1:
                                is_danger = True
                    
                    if is_danger:
                        if not any((item["serial"] == deed_serial) for item in skip_db):
                            skip_db.append({"serial": deed_serial, "x": x, "y": y})
                        Player.HeadMessage(33, "[위험구역] X:{} Y:{} 수동격리!".format(x, y))
                        Gumps.CloseGump(0x550a461b); Misc.Pause(500); success = "DANGER"; break
                        
                    # 메인 DB 추가
                    if not any((item["serial"] == deed_serial) for item in db_data):
                        db_data.append({"serial": deed_serial, "x": x, "y": y})
                        Player.HeadMessage(56, "[{}] X:{} Y:{} 저장!".format(len(db_data), x, y))
                    
                    # 스킵 DB 복구 (삭제) 처리
                    original_skip_len = len(skip_db)
                    skip_db = [s for s in skip_db if s['serial'] != deed_serial]
                    if len(skip_db) < original_skip_len:
                        recovered_count += 1
                    else:
                        count += 1
                        
                    Gumps.CloseGump(0x550a461b); Misc.Pause(500); success = True; break 
                else: Gumps.CloseGump(0x550a461b); Misc.Pause(500)
                
        chk = Items.FindBySerial(deed_serial)
        if chk:
            if success == "DANGER":
                if HighValueBox > 0:
                    Items.Move(chk, HighValueBox, 1)
                else:
                    Player.HeadMessage(33, "격리 보관함(HighValueBox) 설정 누락! 가방에 보관합니다.")
                Misc.Pause(1000)
            elif success == True:
                Items.Move(chk, DoneBox, 1); Misc.Pause(1000)
            elif not success and src_item.ItemID != SOSID:
                Items.Move(chk, src, 1); Misc.Pause(1000)
    save_db(db_data)
    save_skip_db(skip_db)
    
    try: update_cuo_markers()
    except: pass
    
    msg = "📂 **[DB 업데이트]** SOS 쪽지 {0}개 등록 (총 {1}개)".format(count, len(db_data))
    if recovered_count > 0: msg += " | ♻️ 스킵 복구 {0}개".format(recovered_count)
    SendDiscord(msg)
    Player.HeadMessage(68, "[완료] 신규 {}개 등록 / 복구 {}개 완료".format(count, recovered_count))

def Verify_Database():
    Player.HeadMessage(55, "▶ [DB 양방향 검증] 무결성 체크 및 에러 쪽지 격리 중...")
    if DoneBox <= 0 or HighValueBox <= 0: Player.HeadMessage(33, "설정 오류: DoneBox 또는 HighValueBox 없음"); return
    
    Items.UseItem(DoneBox); Misc.Pause(1000)
    Items.UseItem(HighValueBox); Misc.Pause(1000)
    
    db_data = load_db()
    skip_db = load_skip_db()
    
    if SEA_GRID is not None:
        safe_db = []
        danger_moved = False
        for u in db_data:
            is_danger = False
            bx, by = u['x'] // SEA_GRID_BLOCK, u['y'] // SEA_GRID_BLOCK
            if 0 <= bx < SEA_GRID_W and 0 <= by < SEA_GRID_H:
                if SEA_GRID[by * SEA_GRID_W + bx] == 1:
                    is_danger = True
            
            if is_danger:
                if not any(s['serial'] == u['serial'] for s in skip_db):
                    skip_db.append({"serial": u['serial'], "x": u['x'], "y": u['y']})
                danger_moved = True
            else:
                safe_db.append(u)
                
        if danger_moved:
            db_data = safe_db
            save_db(db_data)
            save_skip_db(skip_db)
            Player.HeadMessage(33, "[경고] 위험구역에 속하는 과거 쪽지를 적발하여 스킵함으로 추방합니다.")
            Misc.Pause(1500)
            
    db_serials = [item["serial"] for item in db_data]
    skip_serials = [item["serial"] for item in skip_db]
    
    dbox_obj = Items.FindBySerial(DoneBox)
    mismatch_count = 0
    skip_moved_count = 0
    total_normal_count = 0
    total_skipped_count = 0
    total_error_count = 0
    
    # 1. 두 함을 스캔하여 전체 통계 집계 및 필요 시 물리적 이동 (격리)
    for box_serial in [DoneBox, HighValueBox]:
        box_obj = Items.FindBySerial(box_serial)
        if box_obj and box_obj.Contains:
            for item in box_obj.Contains:
                if item.ItemID == SOSID:
                    if item.Serial in skip_serials:
                        total_skipped_count += 1
                        if box_serial == DoneBox:
                            Items.Move(item, HighValueBox, -1)
                            Misc.Pause(800)
                            skip_moved_count += 1
                    elif item.Serial in db_serials:
                        total_normal_count += 1
                        if box_serial == HighValueBox:
                            Items.Move(item, DoneBox, -1)
                            Misc.Pause(800)
                    else:
                        total_error_count += 1
                        if box_serial == DoneBox:
                            Items.Move(item, HighValueBox, -1)
                            Misc.Pause(800)
                            mismatch_count += 1
                    
    # 2. DB 유령 시리얼 소각 (DB엔 있는데 월드에 없는 놈 삭제, 스킵된 놈은 메인 DB에서 누락시킴)
    valid_db = []
    ghost_count = 0
    for entry in db_data:
        if entry['serial'] in skip_serials:
            pass # 스킵된 쪽지는 메인 DB가 아닌 Skip_DB에서 관리되므로 여기서 떨어뜨립니다.
        elif Items.FindBySerial(entry['serial']):
            valid_db.append(entry)
        else:
            ghost_count += 1
            
    save_db(valid_db)
    
    # 3. Skip DB 유령 시리얼 소각 (버려지거나 사용되어 월드에 없는 스킵 쪽지 소거)
    valid_skip_db = []
    ghost_skip_count = 0
    for entry in skip_db:
        if Items.FindBySerial(entry['serial']):
            valid_skip_db.append(entry)
        else:
            ghost_skip_count += 1
            
    save_skip_db(valid_skip_db)
    
    try: update_cuo_markers()
    except: pass
    
    Player.HeadMessage(68, "✅ 전체 정상 {} (격리 {} 이동) / 전체 스킵 {} (격리 {} 이동) / 전체 오류 {} (격리 {} 이동)".format(total_normal_count, 0, total_skipped_count, skip_moved_count, total_error_count, mismatch_count))

# -----------------------------------------------------------------------------
# [A* 바다 패스파인딩 모듈]
# -----------------------------------------------------------------------------
def load_sea_grid():
    global SEA_GRID, SEA_GRID_W, SEA_GRID_H, SEA_GRID_BLOCK
    global SEA_GRID_LAYERS
    _ensure_grid_file()
    if not File.Exists(GRID_FILE):
        Misc.SendMessage("[NavGrid] sea_grid.bin not found - straight-line mode", 33)
        return False
    try:
        raw = File.ReadAllBytes(GRID_FILE)
        if len(raw) < 5:
            Misc.SendMessage("[NavGrid] sea_grid.bin too small", 33)
            return False
        import struct
        magic = bytes(bytearray(raw[0:5]))

        if magic == b'SGRD2':
            # 멀티레이어 포맷
            layer_count = struct.unpack_from('<B', bytes(bytearray(raw)), 5)[0]
            SEA_GRID_LAYERS = []
            offset = 6
            headers = []
            for i in range(layer_count):
                w = struct.unpack_from('<H', bytes(bytearray(raw)), offset)[0]
                h = struct.unpack_from('<H', bytes(bytearray(raw)), offset+2)[0]
                b = struct.unpack_from('<H', bytes(bytearray(raw)), offset+4)[0]
                data_off = struct.unpack_from('<I', bytes(bytearray(raw)), offset+6)[0]
                headers.append((w, h, b, data_off))
                offset += 10
            for w, h, b, data_off in headers:
                layer_grid = bytearray(raw[data_off:data_off + w * h])
                SEA_GRID_LAYERS.append((layer_grid, w, h, b))
            SEA_GRID, SEA_GRID_W, SEA_GRID_H, SEA_GRID_BLOCK = SEA_GRID_LAYERS[0]
            Player.HeadMessage(68, "[NavGrid] Loaded {} layers (block={}~{}tile)".format(
                layer_count, SEA_GRID_LAYERS[0][3], SEA_GRID_LAYERS[-1][3]))
            

            return True

        elif bytes(bytearray(raw[0:4])) == b'SGRD':
            # 구버전 단일 레이어 호환
            SEA_GRID_W = struct.unpack_from('<H', bytes(bytearray(raw)), 4)[0]
            SEA_GRID_H = struct.unpack_from('<H', bytes(bytearray(raw)), 6)[0]
            SEA_GRID_BLOCK = struct.unpack_from('<H', bytes(bytearray(raw)), 8)[0]
            SEA_GRID = bytearray(raw[12:12 + SEA_GRID_W * SEA_GRID_H])
            SEA_GRID_LAYERS = [(SEA_GRID, SEA_GRID_W, SEA_GRID_H, SEA_GRID_BLOCK)]
            Player.HeadMessage(68, "[NavGrid] Loaded legacy grid (block={})".format(SEA_GRID_BLOCK))
            

            return True
        else:
            Misc.SendMessage("[NavGrid] Invalid grid file (bad magic)", 33)
            return False
    except Exception as e:
        Misc.SendMessage("[NavGrid] Load error: " + str(e), 33)
        return False

def astar_sea(sx, sy, gx, gy):
    """A* pathfinding on the sea grid. Returns list of (bx,by) block coords or None."""
    if SEA_GRID is None:
        return None
    B = SEA_GRID_BLOCK
    sbx, sby = sx // B, sy // B
    gbx, gby = gx // B, gy // B
    W, H = SEA_GRID_W, SEA_GRID_H
    # Bounds check
    if not (0 <= sbx < W and 0 <= sby < H): return None
    if not (0 <= gbx < W and 0 <= gby < H): return None
    # Start/goal must be navigable (or find nearest navigable)
    if SEA_GRID[sby * W + sbx] == 1:
        sbx, sby = find_nearest_navigable(sbx, sby)
        if sbx is None: return None
    if SEA_GRID[gby * W + gbx] == 1:
        gbx, gby = find_nearest_navigable(gbx, gby)
        if gbx is None: return None
    start = (sbx, sby)
    goal = (gbx, gby)
    if start == goal:
        return [start]
    # A* with simple open list
    g_score = {start: 0}
    came_from = {}
    open_set = [(max(abs(gbx-sbx), abs(gby-sby)), 0, sbx, sby)]  # (f, g, x, y)
    visited = set()
    dirs = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    max_iter = 50000  # Safety limit
    iterations = 0
    while open_set and iterations < max_iter:
        iterations += 1
        # Find best in open set
        best_i = 0
        for i in range(1, len(open_set)):
            if open_set[i][0] < open_set[best_i][0]:
                best_i = i
        f, g, cx, cy = open_set.pop(best_i)
        current = (cx, cy)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        if current in visited:
            continue
        visited.add(current)
        for ddx, ddy in dirs:
            nx, ny = cx + ddx, cy + ddy
            if 0 <= nx < W and 0 <= ny < H:
                if SEA_GRID[ny * W + nx] == 0:
                    neighbor = (nx, ny)
                    if neighbor in visited:
                        continue
                    mc = 1.414 if (ddx != 0 and ddy != 0) else 1.0
                    new_g = g + mc
                    if neighbor not in g_score or new_g < g_score[neighbor]:
                        g_score[neighbor] = new_g
                        h = max(abs(gbx-nx), abs(gby-ny))
                        open_set.append((new_g + h, new_g, nx, ny))
                        came_from[neighbor] = current
    return None  # No path

def find_nearest_navigable(bx, by):
    """Find nearest navigable block to (bx, by)."""
    W, H = SEA_GRID_W, SEA_GRID_H
    for r in range(1, 20):
        for ddx in range(-r, r+1):
            for ddy in range(-r, r+1):
                if abs(ddx) == r or abs(ddy) == r:
                    nx, ny = bx + ddx, by + ddy
                    if 0 <= nx < W and 0 <= ny < H:
                        if SEA_GRID[ny * W + nx] == 0:
                            return nx, ny
    return None, None

def simplify_path(path):
    """Remove intermediate waypoints on straight lines."""
    if len(path) <= 2:
        return path
    simplified = [path[0]]
    for i in range(1, len(path) - 1):
        prev = simplified[-1]
        curr = path[i]
        nxt = path[i + 1]
        dx1 = curr[0] - prev[0]
        dy1 = curr[1] - prev[1]
        dx2 = nxt[0] - curr[0]
        dy2 = nxt[1] - curr[1]
        if dx1 != dx2 or dy1 != dy2:
            simplified.append(curr)
    simplified.append(path[-1])
    return simplified

def _find_nav(bx, by, layer_grid, layer_w, layer_h):
    bx = max(0, min(bx, layer_w - 1))
    by = max(0, min(by, layer_h - 1))
    idx = by * layer_w + bx
    if idx >= len(layer_grid):
        Misc.SendMessage("[_find_nav] 범위초과! idx={} len={} bx={} by={} w={} h={}".format(
            idx, len(layer_grid), bx, by, layer_w, layer_h), 33)
        return None, None
    if layer_grid[idx] == 0:
        return bx, by
    for r in range(1, 10):
        for ddx in range(-r, r+1):
            for ddy in range(-r, r+1):
                if abs(ddx) == r or abs(ddy) == r:
                    nx, ny = bx+ddx, by+ddy
                    if 0 <= nx < layer_w and 0 <= ny < layer_h:
                        if layer_grid[ny * layer_w + nx] == 0:
                            return nx, ny
    return None, None

def get_waypoints(px, py, tx, ty):
    """A* 경로 계산. 실패 시 미리 준비된 압축 레이어로 단계적 재시도."""
    if SEA_GRID is None:
        return None

    for layer_idx, (layer_grid, layer_w, layer_h, layer_block) in enumerate(SEA_GRID_LAYERS):
        if layer_idx > 0:
            Player.HeadMessage(55, "[A*] 레이어 {} 재시도 (블록={}타일)...".format(layer_idx+1, layer_block))

        sbx = max(0, min(px // layer_block, layer_w - 1))
        sby = max(0, min(py // layer_block, layer_h - 1))
        gbx = max(0, min(tx // layer_block, layer_w - 1))
        gby = max(0, min(ty // layer_block, layer_h - 1))

        sbx, sby = _find_nav(sbx, sby, layer_grid, layer_w, layer_h)
        gbx, gby = _find_nav(gbx, gby, layer_grid, layer_w, layer_h)

        # [스냅 거리 검증] 스냅된 목표가 실제 목표에서 50타일 초과면 레이어 스킵
        if gbx is not None and gby is not None:
            half = layer_block // 2
            snapped_tx = gbx * layer_block + half
            snapped_ty = gby * layer_block + half
            snap_dist = math.sqrt((snapped_tx - tx)**2 + (snapped_ty - ty)**2)
            if snap_dist > 50:
                Player.HeadMessage(33, "[A*] L{} 스냅 거리 초과 ({:.0f}t) - 스킵".format(layer_idx+1, snap_dist))
                continue

        if sbx is None or gbx is None:
            continue

        if (sbx, sby) == (gbx, gby):
            half = layer_block // 2
            return [(sbx * layer_block + half, sby * layer_block + half)]

        g_score = {(sbx, sby): 0}
        came_from = {}
        open_set = [(max(abs(gbx-sbx), abs(gby-sby)), 0, sbx, sby)]
        visited = set()
        dirs = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        found = None
        iterations = 0
        
        dist_to_goal = max(abs(gbx-sbx), abs(gby-sby))
        weight = 3.0 if dist_to_goal >= 80 else 1.0 # 가중치 A*
        
        while open_set and iterations < 100000:
            iterations += 1
            best_i = 0
            for i in range(1, len(open_set)):
                if open_set[i][0] < open_set[best_i][0]:
                    best_i = i
            f, g, cx, cy = open_set.pop(best_i)
            if (cx, cy) == (gbx, gby):
                found = (cx, cy)
                break
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            for ddx, ddy in dirs:
                nx, ny = cx+ddx, cy+ddy
                if 0 <= nx < layer_w and 0 <= ny < layer_h:
                    if layer_grid[ny * layer_w + nx] == 0:
                        nb = (nx, ny)
                        if nb in visited: continue
                        mc = 1.414 if (ddx != 0 and ddy != 0) else 1.0
                        ng = g + mc
                        if nb not in g_score or ng < g_score[nb]:
                            g_score[nb] = ng
                            h = max(abs(gbx-nx), abs(gby-ny))
                            open_set.append((ng + h * weight, ng, nx, ny))
                            came_from[nb] = (cx, cy)

        if found:
            path = [found]
            cur = found
            while cur in came_from:
                cur = came_from[cur]
                path.append(cur)
            path.reverse()
            simplified = simplify_path(path)
            half = layer_block // 2
            waypoints = [(bx * layer_block + half, by * layer_block + half) for bx, by in simplified]
            if layer_idx > 0:
                Player.HeadMessage(68, "[A*] 레이어 {} 경로 발견! (블록={}타일, {}wp)".format(
                    layer_idx+1, layer_block, len(waypoints)))
            return waypoints

    Player.HeadMessage(33, "[A*] 모든 레이어 실패 - 직선 이동")
    return None

# -----------------------------------------------------------------------------
# [물리 행동 모듈]
# -----------------------------------------------------------------------------
def calculateDirection(dx, dy):
    if dx > 0 and dy > 0: return 'Down'
    elif dx > 0 and dy < 0: return 'Right'
    elif dx > 0: return 'East'
    elif dx < 0 and dy > 0: return 'Left'
    elif dx < 0 and dy < 0: return 'Up'
    elif dx < 0: return 'West'
    elif dy > 0: return 'South'
    elif dy < 0: return 'North'
    return None 

def update_cuo_markers(current_queue_serials=None):
    if current_queue_serials is None:
        current_queue_serials = []

    cfg = load_config()
    map_indices = [0] if cfg.get("marker_maps", 0) == 0 else [0, 1]

    db_data = load_db()
    skip_data = load_skip_db()

    csv_lines = []

    for i, entry in enumerate(db_data):
        serial = entry.get("serial", "")
        x = entry.get("x", 0)
        y = entry.get("y", 0)

        if serial in current_queue_serials:
            icon = ""
            lbl_type = "[Active]"
            color = "purple"
        else:
            icon = ""
            lbl_type = "[Waiting]"
            color = "green"

        label = "{} SOS_{}".format(lbl_type, i+1)
        for m_idx in map_indices:
            line = "{x},{y},{m_idx},{label},{icon},{color}".format(x=x, y=y, m_idx=m_idx, label=label, icon=icon, color=color)
            csv_lines.append(line)

    for i, entry in enumerate(skip_data):
        serial = entry.get("serial", "")
        x = entry.get("x", 0)
        y = entry.get("y", 0)

        icon = ""
        label = "[Skip] SOS_{}".format(i+1)
        color = "red"
        for m_idx in map_indices:
            line = "{x},{y},{m_idx},{label},{icon},{color}".format(x=x, y=y, m_idx=m_idx, label=label, icon=icon, color=color)
            csv_lines.append(line)

    try:
        csv_dir = CUO_CLIENT_DIR + "/Data/Client"
        if not Directory.Exists(csv_dir): Directory.CreateDirectory(csv_dir)
        csv_path = csv_dir + "/GGO_SOS_Markers.csv"
        
        f = open(csv_path, "wb")
        for l in csv_lines: 
            f.write((l + "\n").encode('utf-8'))
        f.close()
    except Exception as e:
        Misc.SendMessage("❌ CSV 쓰기 에러: " + str(e), 33)

def get_opposite_direction(d):
    opposites = {'North': 'South', 'South': 'North', 'East': 'West', 'West': 'East',
                 'Up': 'Down', 'Down': 'Up', 'Left': 'Right', 'Right': 'Left'}
    return opposites.get(d, 'South')

def get_perpendicular_directions(d):
    """이동 방향 기준 좌/우 직각 방향 반환 (배 충돌 우회용)"""
    perp_map = {
        'North': ('West', 'East'),
        'South': ('East', 'West'),
        'East':  ('North', 'South'),
        'West':  ('South', 'North'),
        'Up':    ('Left', 'Right'),    # NW -> SW, NE
        'Down':  ('Right', 'Left'),    # SE -> NE, SW
        'Left':  ('Up', 'Down'),       # SW -> NW, SE
        'Right': ('Down', 'Up'),       # NE -> SE, NW
    }
    return perp_map.get(d, ('West', 'East'))

def ShowReportGump():
    """현재까지 누적된 파밍 보고서를 별도 검프창으로 표시"""
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    
    # 보고서 내용 구성
    lines = []
    lines.append("=== 파밍 중간 보고서 ===")
    lines.append("")
    
    if farmed_stats:
        total_boxes = sum(stat['count'] for stat in farmed_stats)
        lines.append("총 획득 보물상자: {}개".format(total_boxes))
    else:
        lines.append("아직 획득한 보물상자가 없습니다.")
    
    lines.append("DB 잔여 쪽지: {}개".format(len(load_db())))
    lines.append("")
    lines.append("--- 획득 전리품 ---")
    
    if looted_items_count:
        priority_keys = ["[✨유니크 가방✨]", "[문어목걸이]", "[찐 해적모자]"]
        for key in priority_keys:
            if key in looted_items_count:
                lines.append("  {} : {}개".format(key, looted_items_count[key]))
        for name, count in looted_items_count.items():
            if name not in priority_keys:
                lines.append("  {} : {}개".format(name, count))
    else:
        lines.append("  획득한 귀중품이 없습니다.")
    
    lines.append("")
    elapsed = int(time.time() - start_time)
    lines.append("경과 시간: {}분".format(elapsed // 60))
    
    # 검프 크기 계산
    line_count = len(lines)
    gh = 60 + (line_count * 20) + 45
    gw = 320
    
    Gumps.AddBackground(gd, 0, 0, gw, gh, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, gw, gh)
    Gumps.AddLabel(gd, 15, 15, 53, "📊 SOS Farmer v{} 중간 보고".format(CURRENT_VERSION))
    
    y = 45
    for line in lines:
        hue = 1152
        if line.startswith("===") or line.startswith("---"):
            hue = 53
        elif "유니크" in line or "문어" in line or "해적" in line:
            hue = 1161
        Gumps.AddLabel(gd, 20, y, hue, line)
        y += 20
    
    # 닫기 버튼
    close_y = y + 5
    Gumps.AddButton(gd, 130, close_y, 40297, 40298, 1, 1, 0)
    Gumps.AddLabel(gd, 175, close_y + 2, 900, "닫기")
    
    Gumps.SendGump(REPORT_GUMP_ID, Player.Serial, 0, 0, gd.gumpDefinition, gd.gumpStrings)

def GGO_SubGumpHandler(queue_status):
    # 리포트 검프 닫기 처리
    rd = Gumps.GetGumpData(REPORT_GUMP_ID)
    if rd and rd.buttonid > 0:
        Gumps.SendAction(REPORT_GUMP_ID, 0)
        Gumps.CloseGump(REPORT_GUMP_ID)
    
    gd = Gumps.GetGumpData(STATUS_GUMP_ID)
    if gd and gd.buttonid > 0:
        bid = gd.buttonid
        Gumps.SendAction(STATUS_GUMP_ID, 0) 
        
        if bid == 101: 
            app_state["is_manual"] = not app_state["is_manual"]
            if app_state["is_manual"]:
                Player.HeadMessage(43, "⏸ [MANUAL] 수동 조타 모드 (자동 이동 정지)")
            else:
                Player.HeadMessage(68, "▶ [AUTO] 자동 항해 복귀")
            UpdateStatusGump(queue_status)
                
        elif bid == 102: 
            Player.HeadMessage(33, "⏭ [SKIP] 현재 타겟 스킵 요청!")
            app_state["skip_requested"] = True
            Gumps.CloseGump(STATUS_GUMP_ID)
        
        elif bid == 103:
            Player.HeadMessage(68, "📊 [REPORT] 중간 보고서를 표시합니다.")
            UpdateStatusGump(queue_status)  # 진행 검프 유지
            ShowReportGump()
            
        elif bid == 104:
            Player.HeadMessage(33, "🛑 [STOP] 작업 중단 요청!")
            app_state["stop_requested"] = True
            Gumps.CloseGump(STATUS_GUMP_ID)
            
def goMap(x, y, queue_status):
    global stuck_alert_sent

    # === [해마 탑승 필수 검증] 미탑승 시 반복 시도 ===
    mount_attempt = 0
    while not Player.Mount and mount_attempt < 5:
        sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
        if sh:
            Player.HeadMessage(55, "[해마] 탑승 시도 {}/5...".format(mount_attempt + 1))
            Items.UseItem(sh)
            wait = 0
            while not Player.Mount and wait < 15:
                Misc.Pause(200)
                wait += 1
            if Player.Mount:
                Player.HeadMessage(68, "[해마] 탑승 완료!")
                break
        else:
            Player.HeadMessage(33, "[해마] 가방에 해마 동상 없음!")
            break
        mount_attempt += 1
        Misc.Pause(1000)

    if not Player.Mount:
        Player.HeadMessage(33, "[해마] 탑승 최종 실패! 이동 불가 → 타겟 스킵")
        SendDiscord("**[경고]** 해마 탑승 실패로 이동 불가. 타겟을 스킵합니다. (X:{}, Y:{})".format(x, y))
        return False

    # === A* 경로 계산 시도 ===
    waypoints = None
    if SEA_GRID is not None:
        waypoints = get_waypoints(Player.Position.X, Player.Position.Y, x, y)
        if waypoints:
            Player.HeadMessage(68, "[A*] Route: {} waypoints".format(len(waypoints)))
        else:
            Player.HeadMessage(33, "[A*] No path - skip fallback")
    
    # 웨이포인트가 여전히 없다면 직선 박치기를 하지 않고 이번 타겟은 즉시 스킵
    if not waypoints:
        Player.HeadMessage(33, "[오류] 경로 생성 한계 초과 - 타겟 일시 스킵")
        SendDiscord("⚠️ [경고] 복잡한 경로 및 연산 한계 초과로 이동을 스킵합니다. (X:{0}, Y:{1})".format(x, y))
        return "SKIP"
    
    wp_idx = 0
    stuck_retry_count = 0
    MAX_STUCK_RETRIES = 5
    
    while wp_idx < len(waypoints):
        wx, wy = waypoints[wp_idx]
        
        # 이 웨이포인트로 직선 이동
        result = _goToWaypoint(wx, wy, x, y, wp_idx, len(waypoints), queue_status)
        
        if result == "SKIP":
            return "SKIP"
        elif result == "STOP":
            return "STOP"
        elif result == "ARRIVED_FINAL":
            return True
        elif result == "ARRIVED_WP":
            wp_idx += 1
            stuck_retry_count = 0
            continue
        elif result == "STUCK":
            stuck_retry_count += 1

            # [해마 재확인] 크라켄 디스마운트 등으로 하차되었을 수 있음
            if not Player.Mount:
                Player.HeadMessage(33, "[해마] 이동 중 하차 감지! 재탑승 시도...")
                sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
                if sh:
                    Items.UseItem(sh)
                    wait = 0
                    while not Player.Mount and wait < 15:
                        Misc.Pause(200)
                        wait += 1

            if stuck_retry_count > MAX_STUCK_RETRIES:
                Player.HeadMessage(33, "[SOS] 최대 재시도 초과! 구조 요청 발송...")
                SendDiscord("🚨 **[SOS 구조요청]** 경로 이탈 반복 ({}회). 수동 조치 필요! (X:{}, Y:{})".format(
                    MAX_STUCK_RETRIES, Player.Position.X, Player.Position.Y))
                return False

            # 끼임 발생 → A* 재계산 시도
            if SEA_GRID is not None:
                Player.HeadMessage(55, "[A*] Recalculating route... (retry {}/{})".format(stuck_retry_count, MAX_STUCK_RETRIES))
                new_wps = get_waypoints(Player.Position.X, Player.Position.Y, x, y)
                if new_wps and len(new_wps) > 1:
                    # [재계산 경로 검증] 마지막 웨이포인트가 목표에서 50타일 초과면 스킵
                    last_wp = new_wps[-1]
                    last_wp_dist = math.sqrt((last_wp[0] - x)**2 + (last_wp[1] - y)**2)
                    if last_wp_dist > 50:
                        Player.HeadMessage(33, "[A*] 재계산 경로도 도달 불가 ({:.0f}t). 스킵.".format(last_wp_dist))
                        return "SKIP"
                    waypoints = new_wps
                    wp_idx = 0
                    stuck_alert_sent = False
                    Player.HeadMessage(68, "[A*] New route: {} waypoints".format(len(new_wps)))
                    continue
            # A* 재계산 실패 또는 그리드 없음 → 기존 끼임 처리
            Player.HeadMessage(33, "[SOS] 경로 재계산 실패. 구조 요청 발송...")
            SendDiscord("🚨 **[SOS 구조요청]** A* 경로 재계산 실패! (X:{}, Y:{})".format(
                Player.Position.X, Player.Position.Y))
            return False
        elif result == False:
            return False
    
    return True

def _try_perpendicular_escape(d, escape_tiles=18):
    """이동 방향 기준 좌/우 직각으로 우회 시도. 성공 시 True 반환."""
    left_dir, right_dir = get_perpendicular_directions(d)
    
    # 1차: 왼쪽 직각 방향 우회
    before_x, before_y = Player.Position.X, Player.Position.Y
    Player.HeadMessage(55, "[우회] 좌측 {}타일 이동 시도...".format(escape_tiles))
    for _ in range(escape_tiles):
        Player.Run(left_dir)
        Misc.Pause(120)
    if abs(Player.Position.X - before_x) > 3 or abs(Player.Position.Y - before_y) > 3:
        Player.HeadMessage(68, "[우회] 좌측 우회 성공!")
        return True
    
    # 2차: 오른쪽 직각 방향 우회
    before_x, before_y = Player.Position.X, Player.Position.Y
    Player.HeadMessage(55, "[우회] 우측 {}타일 이동 시도...".format(escape_tiles))
    for _ in range(escape_tiles):
        Player.Run(right_dir)
        Misc.Pause(120)
    if abs(Player.Position.X - before_x) > 3 or abs(Player.Position.Y - before_y) > 3:
        Player.HeadMessage(68, "[우회] 우측 우회 성공!")
        return True
    
    # 3차: 후진 시도
    opp_dir = get_opposite_direction(d)
    before_x, before_y = Player.Position.X, Player.Position.Y
    Player.HeadMessage(55, "[우회] 후진 {}타일 이동 시도...".format(escape_tiles))
    for _ in range(escape_tiles):
        Player.Run(opp_dir)
        Misc.Pause(120)
    if abs(Player.Position.X - before_x) > 3 or abs(Player.Position.Y - before_y) > 3:
        Player.HeadMessage(68, "[우회] 후진 우회 성공!")
        return True
    
    return False

def _goToWaypoint(wx, wy, final_x, final_y, wp_idx, wp_total, queue_status):
    """단일 웨이포인트까지 직선 이동. 최종 목표 50타일 이내면 ARRIVED_FINAL 반환."""
    global stuck_alert_sent
    timeout = 0
    last_px, last_py = Player.Position.X, Player.Position.Y
    last_nav_msg_time = 0
    
    while True:
        # 최종 목표까지 50타일 이내면 완료
        final_dist = int(math.sqrt((Player.Position.X - final_x)**2 + (Player.Position.Y - final_y)**2))
        if final_dist <= 50:
            Player.HeadMessage(68, "Arrived near target (<=50 tiles)")
            return "ARRIVED_FINAL"
        
        # 현재 웨이포인트까지 거리
        wp_dist = int(math.sqrt((Player.Position.X - wx)**2 + (Player.Position.Y - wy)**2))
        
        # 웨이포인트 도착 판정 (8타일 = 1블록 이내)
        if wp_dist <= 10:
            return "ARRIVED_WP"
        
        if app_state["skip_requested"]:
            return "SKIP"
        if app_state.get("stop_requested", False):
            return "STOP"

        HandleDeath()
        GGO_SubGumpHandler(queue_status)
        
        current_time = time.time()
        if current_time - last_nav_msg_time >= 3:
            nav_dir = calculateDirection(wx - Player.Position.X, wy - Player.Position.Y)
            if wp_total > 1:
                Player.HeadMessage(89, "WP {}/{} | {} | D:{}".format(wp_idx+1, wp_total, nav_dir, wp_dist))
            else:
                Player.HeadMessage(89, "Target: {} | Dist: {}".format(nav_dir, final_dist))
            last_nav_msg_time = current_time
        
        if not Player.Mount:
            sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
            if sh:
                Items.UseItem(sh)
                wait = 0
                while not Player.Mount and wait < 10:
                    Misc.Pause(200)
                    wait += 1
            
        dx_w, dy_w = wx - Player.Position.X, wy - Player.Position.Y
        d = calculateDirection(dx_w, dy_w)
        
        if not app_state["is_manual"]:
            if d: Player.Run(d)
            Misc.Pause(100)
            timeout += 1
        else:
            Misc.Pause(100)
        
        # 끼임 감지 (30틱마다)
        if not app_state["is_manual"] and timeout > 0 and timeout % 30 == 0: 
            if Player.Position.X == last_px and Player.Position.Y == last_py:
                if not stuck_alert_sent:
                    # === 동적 장애물 (배 등) 우회 시도 ===
                    Player.HeadMessage(55, "[SOS] 장애물 감지! 우회 시도 중...")
                    
                    if _try_perpendicular_escape(d):
                        # 우회 성공 → A* 재계산 요청
                        Player.HeadMessage(68, "[SOS] 우회 성공! 경로 재계산 요청")
                        return "STUCK"
                    
                    # 모든 우회 실패
                    if SEA_GRID is not None:
                        # A* 있으면 현 위치에서 재계산 시도
                        Player.HeadMessage(55, "[SOS] 우회 실패 - A* 재계산 시도...")
                        return "STUCK"
                    
                    # A* 없음 → 기존 후진+대기 로직 + 디스코드 알림
                    Player.HeadMessage(33, "[SOS] Stuck! Backing up 12 tiles, waiting 30s")
                    SendDiscord("**[SOS] Stuck!** Manual steering needed. (X:{0}, Y:{1})".format(last_px, last_py))
                    stuck_alert_sent = True
                    
                    opp_dir = get_opposite_direction(d)
                    if opp_dir:
                        for _ in range(12):
                            Player.Run(opp_dir)
                            Misc.Pause(150)
                            
                    backstep_x, backstep_y = Player.Position.X, Player.Position.Y
                    manual_steered = False
                    
                    wait_start = time.time()
                    while time.time() - wait_start < 30:
                        attackSeaserpent()
                        GGO_SubGumpHandler(queue_status)
                        if app_state["skip_requested"]: return "SKIP"
                        if app_state.get("stop_requested", False): return "STOP"
                        if not app_state["is_manual"]:
                            manual_steered = True
                            break
                        Misc.Pause(500)
                        if abs(Player.Position.X - backstep_x) > 2 or abs(Player.Position.Y - backstep_y) > 2:
                            manual_steered = True
                            break
                            
                    if manual_steered:
                        Player.HeadMessage(68, "Manual steer detected! Resuming route.")
                        stuck_alert_sent = False
                        timeout = 0
                        last_px, last_py = Player.Position.X, Player.Position.Y
                        continue
                    else:
                        Player.HeadMessage(33, "No manual steer. Skipping.")
                        return False
            else:
                last_px, last_py = Player.Position.X, Player.Position.Y
                stuck_alert_sent = False 
    return "ARRIVED_WP"

def Wait_For_Container_Render(container_serial, timeout_ms=5000):
    wait_time = 0
    while wait_time < timeout_ms:
        if Items.FindBySerial(container_serial): return True
        Misc.Pause(200)
        wait_time += 200
    return False

def VerifyHomeArrival():
    box = Items.FindBySerial(ValuableBox)
    if box and abs(Player.Position.X - box.Position.X) <= 3 and abs(Player.Position.Y - box.Position.Y) <= 3:
        return True
    return False

def EnsureMount():
    """해마 탑승을 보장하는 헬퍼. 탑승 실패 시 최대 5회 재시도."""
    for attempt in range(5):
        if Player.Mount:
            return True
        sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
        if sh:
            Items.UseItem(sh)
            Misc.Pause(1500)
            if Player.Mount:
                return True
            Player.HeadMessage(33, "[해마] 탑승 실패! 재시도 {}/5".format(attempt + 1))
            Misc.Pause(1000)
        else:
            Player.HeadMessage(33, "[해마] 가방에 해마 없음!")
            return False
    Player.HeadMessage(33, "[해마] 탑승 최종 실패!")
    return False

def SweepSkipNotes():
    """집 귀환 직후 무조건 스킵/오류 쪽지를 청소하여 배낭을 비움"""
    if HighValueBox > 0:
        skip_data = load_skip_db()
        skip_serials = [s['serial'] for s in skip_data] if skip_data else []
        swept_any = False
        if Player.Backpack and Player.Backpack.Contains:
            for item in Player.Backpack.Contains:
                if item.ItemID == SOSID and item.Serial in skip_serials:
                    if not swept_any:
                        Player.HeadMessage(55, "스킵/오류 쪽지를 고가치함으로 우선 이동합니다.")
                        swept_any = True
                    Items.Move(item, HighValueBox, 1)
                    Misc.Pause(800)

def SafeGoHome():
    global gate_cast_time, gate_detected_time
    # 기존 게이트 잔여시간이 충분할 때만 진입 시도 (왕복 가용 시간 확보)
    ref = _gate_ref_time()
    if ref > 0:
        remaining = GATE_DURATION_SEC - (time.time() - ref)
        if remaining > GATE_MIDTASK_MARGIN:
            if EnterGate():
                Misc.Pause(1000)
                Wait_For_Container_Render(ValuableBox, 2000)
                if VerifyHomeArrival():
                    SweepSkipNotes()
                    return True
    else:
        # 시전 기록 없음 → 기존 게이트가 있으면 시도
        if EnterGate():
            Misc.Pause(1000)
            Wait_For_Container_Render(ValuableBox, 2000)
            if VerifyHomeArrival():
                SweepSkipNotes()
                return True

    wait_for_gate_clear()
    Spells.CastMagery('Gate Travel')
    Target.WaitForTarget(3500)
    Target.TargetExecute(Homebook)
    gate_cast_time = time.time()
    gate_detected_time = 0  # 새 게이트: 감지 시각 초기화
    Misc.Pause(4000)
    
    if EnterGate():
        Misc.Pause(1000)
        Wait_For_Container_Render(ValuableBox, 3000)
        if VerifyHomeArrival(): 
            SweepSkipNotes()
            return True
        
    return False

def MidTaskGateRefresh():
    """정리 중 게이트 만료 임박 시 호출: 즉시 바다 복귀 → 만료 대기 → 재시전 → 집 복귀"""
    global gate_cast_time, gate_detected_time
    Player.HeadMessage(55, "[MidTask] 게이트 만료 임박! 정리 일시 중단, 리프레시 중...")

    # 1. 즉시 바다 복귀
    if not ReturnToSea():
        Player.HeadMessage(33, "[MidTask] 바다 복귀 실패! 리프레시 중단.")
        return False

    # 2. 기존 게이트 소멸 대기 (물리 감지)
    wait_for_gate_clear()

    # 3. 새 게이트 시전
    Spells.CastMagery('Gate Travel')
    Target.WaitForTarget(3500)
    Target.TargetExecute(Homebook)
    gate_cast_time = time.time()
    gate_detected_time = 0  # 새 게이트: 감지 시각 초기화
    Misc.Pause(4000)

    # 4. 게이트 진입 → 집 복귀 (EnterGate 내부에서 gate_detected_time 갱신)
    if EnterGate():
        Misc.Pause(1000)
        Wait_For_Container_Render(ValuableBox, 3000)
        if VerifyHomeArrival():
            Player.HeadMessage(68, "[MidTask] 게이트 리프레시 완료. 정리 재개.")
            return True

    Player.HeadMessage(33, "[MidTask] 집 복귀 실패!")
    return False

def ReturnToSea():
    global gate_cast_time
    Target.Cancel()
    EnterGate()
    Misc.Pause(1000)

    retry = 0
    while retry < 3:
        box = Items.FindBySerial(ValuableBox)
        if box and abs(Player.Position.X - box.Position.X) <= 10 and abs(Player.Position.Y - box.Position.Y) <= 10:
            Player.HeadMessage(33, "바다 복귀 실패! 즉각 게이트 재탑승 시도...")
            Target.Cancel()
            EnterGate()
            Misc.Pause(1500)
            retry += 1
        else:
            break

    box = Items.FindBySerial(ValuableBox)
    if box and abs(Player.Position.X - box.Position.X) <= 10 and abs(Player.Position.Y - box.Position.Y) <= 10:
        # 게이트 닫힘 → 집에서 Homebook으로 Gate Travel 재시전은 집→집이라 무의미
        Player.HeadMessage(33, "[치명적] 게이트 소멸! 바다 복귀 불가 (집→집 게이트는 무의미)")
        SendDiscord("**[긴급]** 게이트 소멸로 바다 복귀 실패. 스크립트가 재시도합니다.")
        return False
        
    Player.HeadMessage(66, "바다 복귀 완료. 해마에 탑승합니다.")
    sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
    if sh:
        Items.UseItem(sh)
        wait = 0
        while not Player.Mount and wait < 10:
            Misc.Pause(200)
            wait += 1
    return True

def selfcare(): 
    global config
    vamp_on = config.get("use_vamp_form", 0) == 1
    if Player.Poisoned and not vamp_on: Spells.CastMagery('Arch Cure', Player.Serial, 3500); Misc.Pause(1500)
    elif Player.Hits < Player.HitsMax*0.85: Spells.CastMagery('Greater Heal', Player.Serial, 3500); Misc.Pause(1000)      

def attackSeaserpent():
    Target.Cancel()
    f = Mobiles.Filter()
    f.Enabled, f.RangeMax, f.Notorieties = True, 10, List[Byte]([Byte(c) for c in notoriety])
    
    while True:
        t = Mobiles.Select(Mobiles.ApplyFilter(f), 'Nearest')
        if not t:
            Target.Cancel() 
            break
            
        Spells.CastMagery("Lightning")
        Target.WaitForTarget(3000)
        
        if Mobiles.FindBySerial(t.Serial):
            Target.TargetExecute(t)
            Misc.Pause(1000)
        else:
            Target.Cancel()
            
        selfcare()

def get_boxes_in_bag():
    boxes = []
    for bid in FishingTreasureBox:
        items = Items.FindAllByID(bid, -1, Player.Backpack.Serial, -1)
        for item in items:
            boxes.append(item.Serial)
    return boxes

def Trashing():    
    if Player.Backpack and Player.Backpack.Contains:
        safe_item_ids = [0xa306, 0x3196, 0xa308, 0xe41, 0xe43, 0xA30A, 0x9a8, SOSID, SeaHorseID]
        safe_serials = [Player.Backpack.Serial, Trashbag, fishingpole, Homebook, DoneBox, ValuableBox, ByproductBox, HighValueBox]
        
        for item in Player.Backpack.Contains:
            if item.Serial not in initial_backpack_items:
                if item.ItemID not in safe_item_ids and item.Serial not in safe_serials:
                    Items.Move(item, Trashbag, -1)
                    Misc.Pause(600)

def EnterGate():
    global gate_detected_time
    Target.Cancel()
    gate = Items.FindByID(0x0F6C, -1, -1, 2, True) or Items.FindByID(0x0DDA, -1, -1, 2, True)
    if gate:
        if gate_detected_time == 0:  # 이번 시전 후 최초 감지 시각 기록
            gate_detected_time = time.time()
        Items.UseItem(gate); Misc.Pause(800)
        if Gumps.WaitForGump(0xdd8b146a, 1500): Gumps.SendAction(0xdd8b146a, 1)
        Misc.Pause(1500); return True
    return False

def wait_for_gate_clear(timeout=35):
    """주변에 기존 게이트가 있으면 사라질 때까지 대기. Gate Travel 시전 전 호출."""
    gate = Items.FindByID(0x0F6C, -1, -1, 2, True) or Items.FindByID(0x0DDA, -1, -1, 2, True)
    if not gate:
        return True
    Player.HeadMessage(55, "[Gate] 기존 게이트 감지. 만료 대기 중...")
    waited = 0
    while waited < timeout:
        Misc.Pause(1000)
        waited += 1
        gate = Items.FindByID(0x0F6C, -1, -1, 2, True) or Items.FindByID(0x0DDA, -1, -1, 2, True)
        if not gate:
            Player.HeadMessage(68, "[Gate] 기존 게이트 소멸 확인. 시전 준비 완료.")
            return True
    Player.HeadMessage(33, "[Gate] 대기 시간 초과! 강제 시전 시도.")
    return False

# -----------------------------------------------------------------------------
# [루팅 및 보관 모듈 (Phase 2)]
# -----------------------------------------------------------------------------
def safe_move_box(tbox_serial, dst_container, max_retry=3):
    """상자(시리얼 기반) 이동 + 검증. 실패 시 재시도. 성공 True / 최종 실패 False."""
    for attempt in range(max_retry):
        tbox = Items.FindBySerial(tbox_serial)
        if not tbox:
            return True  # 이미 사라짐 (이동됨 또는 소멸)
        if tbox.Container == dst_container:
            return True  # 이미 목적지에 있음
        Items.Move(tbox, dst_container, -1)
        timeout = 0
        while timeout < 15:
            check = Items.FindBySerial(tbox_serial)
            if not check or check.Container == dst_container:
                return True
            Misc.Pause(200)
            timeout += 1
        Player.HeadMessage(33, "[상자이동] 실패! 재시도 {}/{}".format(attempt + 1, max_retry))
        Misc.Pause(500)
    Player.HeadMessage(33, "[상자이동] 최종 실패! 시리얼: {}".format(tbox_serial))
    return False

def safe_move(item_id, src_container, dst_container, is_high_value=False):
    while Items.FindByID(item_id, -1, src_container):
        # ── 게이트 만료 임박 시 정리 중단 후 리프레시 ──────────────
        if is_gate_near_expiry():
            if not MidTaskGateRefresh():
                return  # 리프레시 실패 → 이 아이템 타입 스킵
        # ──────────────────────────────────────────────────────────
        item = Items.FindByID(item_id, -1, src_container)
        if item:
            # 해적모자 이름 필터 - 찐 해적모자(plunderin/약탈)만 이동, 일반 해적모자는 무시
            if item_id == pirate_hat_id:
                hat_name = str(item.Name).lower() if item.Name else ""
                if "plunderin" not in hat_name and "약탈" not in hat_name:
                    break  # 일반 해적모자 → 루프 탈출 (이동하지 않음)
            
            item_serial = item.Serial
            item_name = str(item.Name) if item.Name else "알 수 없는 아이템(ID:{})".format(item.ItemID)
            count = 1
            match = re.match(r'^(\d+)\s+(.+)', item_name)
            if match:
                count = int(match.group(1))
                pure_name = match.group(2)
            else:
                pure_name = item_name
                
            Items.Move(item, dst_container, -1)
            
            timeout = 0
            while timeout < 15:
                check_item = Items.FindBySerial(item_serial)
                if not check_item or check_item.Container == dst_container:
                    break
                Misc.Pause(200)
                timeout += 1
                
            if timeout >= 15:
                Target.Cancel()
                Items.DropFromHand(Player.Backpack, Player.Backpack)
                Misc.Pause(600)
                continue 
                
            # 보고서 범주화 로직
            pure_name_lower = pure_name.lower()
            if item_id == 0x0E75 or item_id == 0xe75:
                pure_name = "[✨유니크 가방✨]"
            elif item_id == 0xa349 or "octopus" in pure_name_lower or "문어" in pure_name_lower:
                pure_name = "[문어목걸이]"
            elif item_id == 0x171B and ("plunderin" in pure_name_lower or "약탈" in pure_name_lower):
                pure_name = "[찐 해적모자]"
            elif " of " in pure_name_lower and "essence" not in pure_name_lower and "에센스" not in pure_name_lower:
                pure_name = "[리파인먼트 소재]"
            elif "essence" in pure_name_lower or "에센스" in pure_name_lower:
                pure_name = "[에센스]"
            elif item_id in gem_id:
                pure_name = "[보석류]"
                
            if is_high_value:
                Player.HeadMessage(1161, "✨ [대박!] 귀중품 획득: {}".format(pure_name))
            else:
                Player.HeadMessage(68, "[보관] {}".format(pure_name))
                
            if pure_name in looted_items_count:
                looted_items_count[pure_name] += count
            else:
                looted_items_count[pure_name] = count
        else: break

def ExtractValuables(tbox):
    Items.UseItem(tbox); Misc.Pause(1000)
    
    p_gold = Items.FindByID(goldpocket, -1, tbox.Serial)
    if p_gold:
        Items.UseItem(p_gold); Misc.Pause(600)
        for i in gold_id: safe_move(i, p_gold.Serial, ValuableBox)
    
    p_gem = Items.FindByID(jewelpocket, -1, tbox.Serial)
    if p_gem:
        Items.UseItem(p_gem); Misc.Pause(600)
        current_config = load_config()
        if current_config.get("loot_gems", 1) == 1:
            for i in gem_id: safe_move(i, p_gem.Serial, ValuableBox)
        else:
            Player.HeadMessage(33, "[다이어트] 보석 루팅을 스킵합니다.")
        
    for i in etc_id: safe_move(i, tbox.Serial, ValuableBox)
    
    for i in highvalue_id: safe_move(i, tbox.Serial, HighValueBox, True)
    
    box_obj = Items.FindBySerial(tbox.Serial)
    if box_obj and box_obj.Contains:
        for item in box_obj.Contains:
            if item.ItemID == pirate_hat_id:
                name = str(item.Name).lower()
                if "plunderin" in name or "약탈" in name:
                    # '찐 해적모자'만 safe_move 처리를 위해 임시로 highvalue_id 등록과 동일한 효과를 냅니다.
                    # 단, safe_move는 ID 기반 이동이므로 해당 상자 안의 해당 ID를 모두 옮깁니다.
                    # 해적 상자에는 모자가 1개만 나오거나 찐 해적모자만 주워도 되므로 safe_move 호출
                    # 이름에 "plunderin"이나 "약탈"이 있을 때만 ID를 넘겨 safe_move가 처리하도록 함.
                    # 주의: safe_move 내부에 해적모자 이름 처리가 이미 들어있으므로 중복 카운팅 방지.
                    safe_move(pirate_hat_id, tbox.Serial, HighValueBox, True)
                    break 
                    
    for i in byproduct_id: safe_move(i, tbox.Serial, ByproductBox)

def EmptyBoxAtSea(tbox):
    Items.UseItem(tbox); Misc.Pause(600)
    while True:
        box_obj = Items.FindBySerial(tbox.Serial)
        if not box_obj or not box_obj.Contains: break
        if len(box_obj.Contains) == 0: break
        item = box_obj.Contains[0]
        Items.Move(item, Trashbag, -1)
        Misc.Pause(600)
    Player.HeadMessage(66, "상자를 비웠습니다.")

# -----------------------------------------------------------------------------
# [현황판 모듈]
# -----------------------------------------------------------------------------
STATUS_GUMP_ID = 777777
REPORT_GUMP_ID = 666666
app_state = {
    "is_manual": False,
    "skip_requested": False,
    "stop_requested": False
}

def UpdateStatusGump(queue_status):
    global total_processed_count
    
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    
    h = 60 + (max(5, len(queue_status)) * 20) + 100
    
    Gumps.AddBackground(gd, 300, 0, 300, h, 30546)
    Gumps.AddAlphaRegion(gd, 300, 0, 300, h)
    Gumps.AddLabel(gd, 315, 15, 53, "GGO SOS Farmer Official v{}".format(CURRENT_VERSION))
    
    db_count = len(load_db())
    y = 45
    
    for i, stat in enumerate(queue_status):
        c = 1152
        if stat['state'] in ('완료', '교차소비'): c = 68
        elif '스킵' in stat['state'] or '실패' in stat['state']: c = 33
        elif stat['state'] == '진행 중': c = 1152
        
        txt = "[{}] X:{} Y:{}".format(stat['state'], stat['x'], stat['y'])
        Gumps.AddLabel(gd, 315, y, c, txt)
        
        if i == 1:
            Gumps.AddLabel(gd, 490, y, 68, " 진행중: {}".format(total_processed_count))
        elif i == 3:
            Gumps.AddLabel(gd, 490, y, 68, " 잔여량: {}".format(db_count))
            
        y += 20
        
    ctrl_y = y + 5
    Gumps.AddImageTiled(gd, 315, ctrl_y, 270, 2, 9107)

    btn_left_x = 315  
    btn_right_x = 460 
    
    BTN_GREEN_N = 40030
    BTN_GREEN_P = 40031
    BTN_RED_N   = 40297
    BTN_RED_P   = 40298
    BTN_GOLD_N  = 40299
    BTN_GOLD_P  = 40300
    BTN_BLUE_N  = 40021
    BTN_BLUE_P  = 40031
    WHITE_TXT   = 900    
    
    if app_state["is_manual"]:
        Gumps.AddButton(gd, btn_left_x, ctrl_y + 12, BTN_GOLD_N, BTN_GOLD_P, 101, 1, 0)
        Gumps.AddLabel(gd, btn_left_x + 38, ctrl_y + 14, WHITE_TXT, "MANUAL")
    else:
        Gumps.AddButton(gd, btn_left_x, ctrl_y + 12, BTN_GREEN_N, BTN_GREEN_P, 101, 1, 0)
        Gumps.AddLabel(gd, btn_left_x + 45, ctrl_y + 14, WHITE_TXT, "AUTO")

    Gumps.AddButton(gd, btn_right_x, ctrl_y + 12, BTN_RED_N, BTN_RED_P, 102, 1, 0)
    Gumps.AddLabel(gd, btn_right_x + 49, ctrl_y + 14, WHITE_TXT, "SKIP")
    
    # 2행: REPORT / STOP 버튼
    row2_y = ctrl_y + 42
    Gumps.AddButton(gd, btn_left_x, row2_y, BTN_BLUE_N, BTN_BLUE_P, 103, 1, 0)
    Gumps.AddLabel(gd, btn_left_x + 38, row2_y + 2, WHITE_TXT, "REPORT")
    
    Gumps.AddButton(gd, btn_right_x, row2_y, BTN_RED_N, BTN_RED_P, 104, 1, 0)
    Gumps.AddLabel(gd, btn_right_x + 49, row2_y + 2, WHITE_TXT, "STOP")
    
    # 스폰서 텍스트 (L1186)
    sponsor_y = row2_y + 32
    Gumps.AddLabel(gd, 340, sponsor_y, 99, "Sponsored by Bongguri & Only for U")

    Gumps.CloseGump(STATUS_GUMP_ID)
    Gumps.SendGump(STATUS_GUMP_ID, Player.Serial, 0, 0, gd.gumpDefinition, gd.gumpStrings)
def get_next_targets(start_x, start_y, count=5):
    """샘플링 block_count 패널티 기반 TSP."""
    db = load_db()
    if not db: return []
    
    # --- [위험 구역 사전 필터링 (구버전 DB 호환)] ---
    if SEA_GRID is not None:
        safe_db = []
        danger_moved = False
        skip_db = None
        for u in db:
            is_danger = False
            bx, by = u['x'] // SEA_GRID_BLOCK, u['y'] // SEA_GRID_BLOCK
            if 0 <= bx < SEA_GRID_W and 0 <= by < SEA_GRID_H:
                if SEA_GRID[by * SEA_GRID_W + bx] == 1:
                    is_danger = True
            
            if is_danger:
                if skip_db is None: skip_db = load_skip_db()
                if not any(s['serial'] == u['serial'] for s in skip_db):
                    skip_db.append({"serial": u['serial'], "x": u['x'], "y": u['y']})
                danger_moved = True
                Player.HeadMessage(33, "[사전 필터링] 육지/위험구역 쪽지 감지! (스킵 처리됨)")
                Misc.Pause(100)
            else:
                safe_db.append(u)
                
        if danger_moved:
            save_db(safe_db)
            save_skip_db(skip_db)
            db = safe_db
            if not db: return []
    # ------------------------------------------------
    
    px, py = start_x, start_y
    target_queue = []
    unvisited = list(db)

    def pick_nearest(px, py):
        best_serial = None
        best_score = 999999999
        for u in unvisited:
            dx = u['x'] - px
            dy = u['y'] - py
            d = math.sqrt(dx*dx + dy*dy)
            if SEA_GRID is not None:
                B = SEA_GRID_BLOCK
                block_count = 0
                bx0, by0 = int(px) // B, int(py) // B
                bx1, by1 = int(u['x']) // B, int(u['y']) // B
                dx_b = abs(bx1 - bx0)
                dy_b = abs(by1 - by0)
                sx_b = 1 if bx0 < bx1 else -1
                sy_b = 1 if by0 < by1 else -1
                err = dx_b - dy_b
                
                while True:
                    if 0 <= bx0 < SEA_GRID_W and 0 <= by0 < SEA_GRID_H:
                        if SEA_GRID[by0 * SEA_GRID_W + bx0] == 1:
                            block_count += 1
                    if bx0 == bx1 and by0 == by1:
                        break
                    e2 = 2 * err
                    if e2 > -dy_b:
                        err -= dy_b
                        bx0 += sx_b
                    if e2 < dx_b:
                        err += dx_b
                        by0 += sy_b
                
                if block_count > 0:
                    d += block_count * 50  # 겹친 육지 블록 수만큼 비례 페널티 부여
            if d < best_score:
                best_score = d
                best_serial = u.get('serial', '')
        for u in unvisited:
            if u.get('serial', '') == best_serial:
                return u
        return unvisited[0]

    try:
        for _ in range(min(count, len(unvisited))):
            nearest = pick_nearest(px, py)
            target_queue.append(nearest)
            unvisited.remove(nearest)
            px, py = nearest['x'], nearest['y']
    except Exception as e:
        Misc.SendMessage("[TSP오류] " + str(e), 33)
        unvisited2 = list(db)
        px2, py2 = start_x, start_y
        for _ in range(min(count, len(unvisited2))):
            nearest = min(unvisited2, key=lambda u: (u['x']-px2)**2 + (u['y']-py2)**2)
            target_queue.append(nearest)
            unvisited2.remove(nearest)
            px2, py2 = nearest['x'], nearest['y']
    return target_queue

# -----------------------------------------------------------------------------
# [전자동 무한 파밍 사이클 (TSP 적용 및 동선 통합)]
# -----------------------------------------------------------------------------
def InfiniteAutoFarm():
    global start_time, initial_backpack_items, total_processed_count, config, gate_cast_time
    InitTracker()  # <--- [추가] 모니터 창 띄우기
    UpdateTracker("대기중", total_processed_count, len(load_db()), "파밍 준비 완료") # <--- [추가]
    start_time = time.time()
    
    initial_backpack_items = []
    if Player.Backpack and Player.Backpack.Contains:
        for item in Player.Backpack.Contains:
            initial_backpack_items.append(item.Serial)
            
    Player.HeadMessage(66, "Bag protection: {} items".format(len(initial_backpack_items)))
    Player.HeadMessage(66, "Starting farming...")
    
    pre_fetched_targets = None
    while True:

        if config.get("use_protection", 0) == 1 and not Player.BuffsExist("Protection"):
            Player.HeadMessage(55, "프로텍션을 시전하여 유지합니다.")
            Spells.CastMagery('Protection')
            Misc.Pause(3000)

        if config.get("use_vamp_form", 0) == 1 and not Player.BuffsExist("Vampiric Embrace"):
            Player.HeadMessage(55, "뱀파이어 폼으로 변신합니다.")
            Spells.CastNecro('Vampiric Embrace')
            Misc.Pause(3000)
            
        if pre_fetched_targets:
            target_queue = pre_fetched_targets
            pre_fetched_targets = None
        else:
            target_queue = get_next_targets(Player.Position.X, Player.Position.Y, 5)
        if not target_queue: 
            Player.HeadMessage(70, "DB 종료"); SendSummaryReport(); break
            
        queue_status = [{'serial': t['serial'], 'x': t['x'], 'y': t['y'], 'state': '진행 예정'} for t in target_queue]
        update_cuo_markers([t['serial'] for t in target_queue])

        need_pickup = False
        for t in target_queue:
            if not Items.FindBySerial(t['serial']): need_pickup = True; break

        if need_pickup:
            Player.HeadMessage(55, "게이트를 열어 쪽지 5장을 수거하러 갑니다.")
            Target.Cancel()

            if SafeGoHome():
                Items.UseItem(DoneBox); Misc.Pause(1000)
                dbox_item = Items.FindBySerial(DoneBox)
                t_serials = [t['serial'] for t in target_queue]

                if dbox_item and dbox_item.Contains:
                    for item in dbox_item.Contains:
                        if item.Serial in t_serials: Items.Move(item, Player.Backpack, 1); Misc.Pause(800)

                Player.HeadMessage(55, "핀포인트 수거 검증 중...")
                wait_count = 0
                all_picked = False
                while not all_picked and wait_count < 3:
                    # [게이트 시간 체크] 게이트 닫히기 전에 바다 복귀 우선
                    if is_gate_expiring():
                        Player.HeadMessage(33, "[긴급] 게이트 시간 부족! 수거 중단, 바다 복귀 우선")
                        break

                    missing_serials = []
                    for ts in t_serials:
                        if not Items.FindBySerial(ts):
                            missing_serials.append(ts)

                    if not missing_serials:
                        all_picked = True
                    else:
                        Player.HeadMessage(33, "누락 발생! 재수거 시도: {}장".format(len(missing_serials)))
                        Items.UseItem(DoneBox); Misc.Pause(1000)
                        dbox_item = Items.FindBySerial(DoneBox)
                        if dbox_item and dbox_item.Contains:
                            for item in dbox_item.Contains:
                                if item.Serial in missing_serials:
                                    Items.Move(item, Player.Backpack, 1)
                                    timeout = 0
                                    while timeout < 15:
                                        check_item = Items.FindBySerial(item.Serial)
                                        if not check_item or check_item.Container == Player.Backpack.Serial:
                                            break
                                        Misc.Pause(200)
                                        timeout += 1
                                    if timeout >= 15:
                                        Target.Cancel()
                                        Items.DropFromHand(Player.Backpack, Player.Backpack)
                                    Misc.Pause(800)
                        wait_count += 1

                if not all_picked:
                    # 긴급 탈출 직후 missing_serials 재계산 (stale 방지)
                    missing_serials = [ts for ts in t_serials if not Items.FindBySerial(ts)]
                    if not missing_serials:
                        all_picked = True  # 실제로는 전부 수거됨 (긴급 break 전에 완료)
                    else:
                        Player.HeadMessage(33, "수거 실패 {}장! 해당 쪽지를 스킵 처리합니다.".format(len(missing_serials)))

                    for qi, qs in enumerate(queue_status):
                        if qs['serial'] in missing_serials:
                            queue_status[qi]['state'] = '오류 스킵'
                            total_processed_count += 1
                    UpdateStatusGump(queue_status)

                    db = load_db()
                    db = [d for d in db if d['serial'] not in missing_serials]
                    save_db(db)

                    skip_db = load_skip_db()
                    for s_ts in missing_serials:
                        skip_db.append({"serial": s_ts, "x": 0, "y": 0})
                    save_skip_db(skip_db)

                Misc.Pause(1000)
                if not ReturnToSea():
                    Player.HeadMessage(33, "[치명적] 게이트 소멸! 집에서 안전 대기합니다.")
                    SendDiscord("**[긴급]** 게이트 소멸로 바다 복귀 불가. 집에서 안전 대기 중입니다.")
                    SendSummaryReport()
                    return
            else:
                Player.HeadMessage(33, "귀환 치명적 실패. 수거를 포기하고 대기합니다.")

        if not Player.Mount:
            sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
            if sh:
                Items.UseItem(sh)
                wait = 0
                while not Player.Mount and wait < 10:
                    Misc.Pause(200)
                    wait += 1

        trim_working_set()
        for idx, t_entry in enumerate(target_queue):
            # 교차소비 또는 수거 실패로 이미 처리된 쪽지는 스킵
            if queue_status[idx]['state'] in ('교차소비', '완료', '오류 스킵'):
                continue

            findSOS = Items.FindBySerial(t_entry['serial'])
            retry_find = 0
            while not findSOS and retry_find < 15:
                Misc.Pause(200)
                findSOS = Items.FindBySerial(t_entry['serial'])
                retry_find += 1

            if not findSOS:
                queue_status[idx]['state'] = '오류 스킵'
                total_processed_count += 1
                UpdateStatusGump(queue_status)
                continue
            
            queue_status[idx]['state'] = '진행 중'
            UpdateStatusGump(queue_status)

            # === [방어 체크 1] 백팩에 SOS 상자가 남아있으면 먼저 정리 ===
            leftover_boxes = get_boxes_in_bag()
            if leftover_boxes:
                Player.HeadMessage(33, "[정리] 백팩에 SOS 상자 {}개 잔류! 기존 게이트 만료 후 새 게이트로 귀환합니다.".format(len(leftover_boxes)))
                Target.Cancel()

                # 기존 게이트 만료 대기 (실물 감지)
                wait_for_gate_clear()

                # 새 게이트 시전 → 귀환
                home_success = False
                for home_retry in range(3):
                    wait_for_gate_clear()
                    Spells.CastMagery('Gate Travel')
                    Target.WaitForTarget(3500)
                    Target.TargetExecute(Homebook)
                    gate_cast_time = time.time()
                    Misc.Pause(4000)

                    if EnterGate():
                        Misc.Pause(1000)
                        Wait_For_Container_Render(ValuableBox, 2000)
                        if VerifyHomeArrival():
                            # 상자 정리
                            current_config = load_config()
                            if SIMPLE_MODE:
                                if SosChestContainer > 0:
                                    for lb_serial in leftover_boxes:
                                        safe_move_box(lb_serial, SosChestContainer)
                            else:
                                box_mode = current_config.get("box_mode", 0)
                                for lb_serial in leftover_boxes:
                                    lb_obj = Items.FindBySerial(lb_serial)
                                    if lb_obj:
                                        ExtractValuables(lb_obj)
                                        if box_mode == 0:
                                            safe_move_box(lb_serial, Trashbag)
                            Misc.Pause(500)
                            if ReturnToSea():
                                home_success = True
                                break
                    Player.HeadMessage(33, "[정리] 귀환 재시도 {}/3...".format(home_retry + 1))
                    Misc.Pause(2000)

                if not home_success:
                    Player.HeadMessage(33, "[치명적] 상자 정리 불가! 안전 정지합니다.")
                    SendDiscord("**[긴급]** SOS 상자 정리 실패 (3회 재시도). 안전 정지.")
                    SendSummaryReport()
                    return

            attackSeaserpent()
            
            tx, ty = None, None
            retry_count = 0
            retry_start_time = time.time()
            while tx is None and retry_count < 10:
                note_in_bag = Items.FindBySerial(findSOS.Serial) and (Items.FindBySerial(findSOS.Serial).Container == Player.Backpack.Serial)
                if note_in_bag:
                    elapsed = time.time() - retry_start_time
                    if elapsed > 15:
                        Player.HeadMessage(33, "[쪽지] 15초 재시도 초과. 스킵합니다.")
                        break
                Items.UseItem(findSOS)
                Gumps.WaitForGump(0x550a461b, 3000)
                if Gumps.HasGump(0x550a461b):
                    tx, ty = get_map_coords(Gumps.GetGumpRawLayout(0x550a461b))
                    Gumps.CloseGump(0x550a461b)
                    if tx is not None:
                        break
                retry_count += 1
                remaining = max(0, int(15 - (time.time() - retry_start_time)))
                Player.HeadMessage(33, "[로딩중] 쪽지 인식 재시도 중... ({}/10, 잔여{}초)".format(retry_count, remaining))
                Misc.Pause(1500)
                
            if tx is None: 
                Player.HeadMessage(33, "[치명적 오류] 쪽지가 완전히 유실되었습니다. 스킵합니다.")
                queue_status[idx]['state'] = '오류 스킵'
                total_processed_count += 1
                UpdateStatusGump(queue_status)
                
                skip_db = load_skip_db()
                skip_db.append({"serial": t_entry['serial'], "x": 0, "y": 0})
                save_skip_db(skip_db)
                
                db_data = load_db()
                db_data = [d for d in db_data if d['serial'] != t_entry['serial']]
                save_db(db_data)
                continue

            old_boxes = get_boxes_in_bag()
            box_stored = False
            Journal.Clear()  # 어류 고갈 감지용 — 포인트 단위 클리어
            fish_fail_count = 0  # 연속 고갈 메시지 카운트
            while not box_stored:
                HandleDeath()
                
                # 진행 검프 동작 확인 및 수동 모드(일시정지) 대기
                GGO_SubGumpHandler(queue_status)
                if app_state.get("is_manual", False):
                    Player.HeadMessage(33, "⚠ 수동 조타 모드 활성화 중... (자동 낚시 일시정지)")
                    Misc.Pause(1000)
                    continue
                    
                if app_state.get("skip_requested", False):
                    Player.HeadMessage(33, "⏭ [낚시 정지] 현재 타겟 낚시를 포기하고 스킵합니다.")
                    Target.Cancel()
                    queue_status[idx]['state'] = '수동 스킵'
                    total_processed_count += 1
                    UpdateStatusGump(queue_status)
                    app_state["skip_requested"] = False
                    
                    skip_db = load_skip_db()
                    if tx is not None and ty is not None:
                        skip_db.append({"serial": t_entry['serial'], "x": tx, "y": ty})
                    save_skip_db(skip_db)
                    
                    db_data = load_db()
                    db_data = [d for d in db_data if d['serial'] != t_entry['serial']]
                    save_db(db_data)
                    update_cuo_markers([t['serial'] for t in target_queue])
                    break

                if int(math.sqrt((Player.Position.X - tx)**2 + (Player.Position.Y - ty)**2)) <= 50:
                    if Player.GetItemOnLayer('RightHand') == None: Player.EquipItem(fishingpole); Misc.Pause(500)             
                    if not Timer.Check('countdown'): Timer.Create('countdown', 3500); Misc.Pause(500) 
                    if Player.Followers == 1: Mobiles.UseMobile(Player.Serial); Misc.Pause(500)
                    
                    attackSeaserpent()
                    Trashing() 
                    
                    current_boxes = get_boxes_in_bag()
                    new_boxes = [b for b in current_boxes if b not in old_boxes]
                    
                    if new_boxes:
                        # === [교차오염 검증] 타겟 쪽지가 실제로 소비되었는지 확인 ===
                        Misc.Pause(500)
                        target_note_check = Items.FindBySerial(t_entry['serial'])

                        if target_note_check is not None:
                            # ★ 교차오염 감지: 다른 쪽지의 보물이 인양됨
                            Player.HeadMessage(33, "[교차오염] 대상 쪽지 미소비! 실제 소비 쪽지 탐색...")

                            # 배낭 내 쪽지만 대상으로 소비 여부 확인 (이미 처리된 쪽지 제외)
                            consumed_serial = None
                            for qi_idx, other_t in enumerate(target_queue):
                                if other_t['serial'] == t_entry['serial']:
                                    continue
                                # 이미 교차소비/완료/오류스킵된 쪽지는 탐색 대상에서 제외
                                if queue_status[qi_idx]['state'] in ('교차소비', '완료', '오류 스킵'):
                                    continue
                                other_item = Items.FindBySerial(other_t['serial'])
                                if other_item is None:
                                    consumed_serial = other_t['serial']
                                    break

                            if consumed_serial:
                                Player.HeadMessage(55, "[교차오염] 실제 소비: {} → 성공 처리".format(consumed_serial))
                                current_db = load_db()
                                current_db = [i for i in current_db if i["serial"] != consumed_serial]
                                save_db(current_db)

                                for qi, qs in enumerate(queue_status):
                                    if qs.get('serial') == consumed_serial and qs['state'] != '교차소비':
                                        queue_status[qi]['state'] = '교차소비'
                                        total_processed_count += 1
                                        UpdateStatusGump(queue_status)
                                        break
                                update_cuo_markers([t['serial'] for t in target_queue])
                            else:
                                Player.HeadMessage(33, "[교차오염] 큐 외부 쪽지 소비 감지")

                            # 상자 무게 제한 → 집에 가서 상자 정리 후 복귀
                            Target.Cancel()
                            home_ok = SafeGoHome()
                            if home_ok:
                                current_config = load_config()
                                box_mode = current_config.get("box_mode", 0)
                                if SIMPLE_MODE:
                                    if SosChestContainer > 0:
                                        for tbox_serial in new_boxes:
                                            safe_move_box(tbox_serial, SosChestContainer)
                                else:
                                    for tbox_serial in new_boxes:
                                        tbox = Items.FindBySerial(tbox_serial)
                                        if tbox:
                                            ExtractValuables(tbox)
                                            if box_mode == 0:
                                                Items.Move(tbox, Trashbag, -1); Misc.Pause(800)
                                Misc.Pause(1000)
                                if not ReturnToSea():
                                    Player.HeadMessage(33, "[교차오염] 게이트 소멸! 집에서 안전 대기")
                                    SendDiscord("**[긴급]** 교차오염 처리 중 게이트 소멸. 집 안전 대기.")
                                    SendSummaryReport()
                                    return
                            else:
                                # 귀환 실패 → 상자는 다음 정상 귀환 때 처리됨
                                Player.HeadMessage(33, "[교차오염] 귀환 실패! 현재 위치에서 낚시 재개")

                            # 현재 타겟 미완료 → 스냅샷 갱신 후 동일 좌표에서 계속 낚시
                            old_boxes = get_boxes_in_bag()
                            continue

                        # === [정상] 타겟 쪽지 소비 확인 → 기존 완료 로직 ===
                        stat = next((s for s in farmed_stats if s['x']==tx), None)
                        if stat: stat['count']+=len(new_boxes)
                        else: farmed_stats.append({'x':tx, 'y':ty, 'count':len(new_boxes)})

                        queue_status[idx]['state'] = '완료'
                        total_processed_count += 1
                        UpdateStatusGump(queue_status)

                        current_db = load_db()
                        current_db = [i for i in current_db if i["serial"] != t_entry['serial']]
                        save_db(current_db)

                        Target.Cancel()
                        if SafeGoHome():
                            Player.HeadMessage(55, "집에서 전리품을 정밀 분류합니다.")
                            UpdateTracker("정리중", total_processed_count, len(load_db()), "전리품 분류 및 보관 중") # <--- [추가]
                            

                            current_config = load_config()
                            box_mode = current_config.get("box_mode", 0)
                            
                            if SIMPLE_MODE:
                                # 간소화 모드: 상자째로 SosChestContainer에 던지기 (검증 포함)
                                if SosChestContainer > 0:
                                    for tbox_serial in new_boxes:
                                        safe_move_box(tbox_serial, SosChestContainer)
                                    Player.HeadMessage(68, "[간소화] 상자 {}개를 컨테이너에 보관했습니다.".format(len(new_boxes)))
                                else:
                                    Player.HeadMessage(33, "[간소화] SosChestContainer 미설정! 재설정이 필요합니다.")
                            else:
                                # 일반 모드: 기존 분류 처리 (검증 포함)
                                for tbox_serial in new_boxes:
                                    tbox = Items.FindBySerial(tbox_serial)
                                    if tbox:
                                        ExtractValuables(tbox)
                                        if box_mode == 0:
                                            safe_move_box(tbox_serial, Trashbag)
                                
                                if box_mode == 1:
                                    current_boxes = get_boxes_in_bag()
                                    for b_serial in current_boxes:
                                        if b_serial not in new_boxes: 
                                            b_obj = Items.FindBySerial(b_serial)
                                            if b_obj:
                                                Items.Move(b_obj, ByproductBox, -1)
                                                Misc.Pause(600)

                            if idx == len(target_queue) - 1:
                                next_targets = get_next_targets(tx, ty, 5)
                                if next_targets:
                                    Items.UseItem(DoneBox); Misc.Pause(1000)
                                    dbox_item = Items.FindBySerial(DoneBox)
                                    n_serials = [nt['serial'] for nt in next_targets]
                                    if dbox_item and dbox_item.Contains:
                                        for item in dbox_item.Contains:
                                            if item.Serial in n_serials: Items.Move(item, Player.Backpack, 1); Misc.Pause(800)

                                    Player.HeadMessage(55, "핀포인트 리필 검증 중...")
                                    wait_count = 0
                                    all_picked = False
                                    while not all_picked and wait_count < 3:
                                        # [게이트 시간 체크] 게이트 닫히기 전에 바다 복귀 우선
                                        if is_gate_expiring():
                                            Player.HeadMessage(33, "[긴급] 게이트 시간 부족! 리필 중단, 바다 복귀 우선")
                                            break

                                        missing_serials = []
                                        for ts in n_serials:
                                            if not Items.FindBySerial(ts):
                                                missing_serials.append(ts)

                                        if not missing_serials:
                                            all_picked = True
                                        else:
                                            Player.HeadMessage(33, "리필 누락 발생! 재수거: {}장".format(len(missing_serials)))
                                            Items.UseItem(DoneBox); Misc.Pause(1000)
                                            dbox_item = Items.FindBySerial(DoneBox)
                                            if dbox_item and dbox_item.Contains:
                                                for item in dbox_item.Contains:
                                                    if item.Serial in missing_serials:
                                                        Items.Move(item, Player.Backpack, 1)
                                                        timeout = 0
                                                        while timeout < 15:
                                                            check_item = Items.FindBySerial(item.Serial)
                                                            if not check_item or check_item.Container == Player.Backpack.Serial:
                                                                break
                                                            Misc.Pause(200)
                                                            timeout += 1
                                                        if timeout >= 15:
                                                            Target.Cancel()
                                                            Items.DropFromHand(Player.Backpack, Player.Backpack)
                                                        Misc.Pause(800)
                                            wait_count += 1

                                    if not all_picked:
                                        # 긴급 탈출 직후 missing_serials 재계산 (stale 방지)
                                        missing_serials = [ts for ts in n_serials if not Items.FindBySerial(ts)]
                                        if not missing_serials:
                                            all_picked = True  # 실제로는 전부 수거됨
                                        else:
                                            Player.HeadMessage(33, "리필 실패 {}장! 해당 쪽지를 제외합니다.".format(len(missing_serials)))
                                        db = load_db()
                                        db = [d for d in db if d['serial'] not in missing_serials]
                                        save_db(db)

                                        skip_db = load_skip_db()
                                        for s_ts in missing_serials:
                                            skip_db.append({"serial": s_ts, "x": 0, "y": 0})
                                        save_skip_db(skip_db)

                                        pre_fetched_targets = [nt for nt in next_targets if nt['serial'] not in missing_serials]
                                    else:
                                        pre_fetched_targets = next_targets

                            Misc.Pause(1000)
                            if not ReturnToSea():
                                Player.HeadMessage(33, "[치명적] 게이트 소멸! 집에서 안전 대기합니다.")
                                SendDiscord("**[긴급]** 게이트 소멸로 바다 복귀 불가. 집 안전 대기.")
                                SendSummaryReport()
                                return
                            trim_working_set()

                            if box_mode == 1:
                                Player.HeadMessage(55, "바다에서 빈 상자의 쓰레기를 비웁니다.")
                                for tbox_serial in new_boxes:
                                    tbox = Items.FindBySerial(tbox_serial)
                                    if tbox: EmptyBoxAtSea(tbox)

                            db_data = load_db()
                            db_data = [d for d in db_data if d['serial'] != t_entry['serial']]
                            save_db(db_data)
                            update_cuo_markers([t['serial'] for t in target_queue])
                                    
                        box_stored = True; break
                    
                    # ... (루프 안쪽) ...
                    # [어류 고갈 감지] 잘못된 포인트에서 무한 낚시 방지
                    if Journal.Search("The fish don't seem to be biting") or Journal.Search("여긴 물고기가 입질을 안하는 것 같습니다"):
                        fish_fail_count += 1
                        Journal.Clear()
                        if fish_fail_count >= 3:
                            Player.HeadMessage(33, "[어류 고갈] 3회 연속 감지! 이 포인트를 스킵합니다.")
                            queue_status[idx]['state'] = '오류 스킵'
                            total_processed_count += 1
                            UpdateStatusGump(queue_status)

                            current_db = load_db()
                            current_db = [d for d in current_db if d['serial'] != t_entry['serial']]
                            save_db(current_db)

                            skip_db = load_skip_db()
                            skip_db.append({"serial": t_entry['serial'], "x": tx, "y": ty})
                            save_skip_db(skip_db)
                            update_cuo_markers([t['serial'] for t in target_queue])
                            break

                    Target.Cancel()
                    UpdateTracker("낚시중", total_processed_count, len(load_db()), "포인트 도착, 보물 인양 중") # <--- [추가]
                    Items.UseItem(fishingpole); Target.WaitForTarget(2000); Target.TargetExecute(Player.Position.X, Player.Position.Y, -1); Misc.Pause(1000)
                else:    
                    if not Player.Mount:
                        sh = Items.FindByID(SeaHorseID, -1, Player.Backpack.Serial)
                        if sh:
                            Items.UseItem(sh)
                            wait = 0
                            while not Player.Mount and wait < 10:
                                Misc.Pause(200)
                                wait += 1
                        
                    UpdateTracker("이동중", total_processed_count, len(load_db()), "다음 타겟으로 항해 중") # <--- [추가]
                    nav_result = goMap(tx, ty, queue_status)
                    if nav_result == "SKIP":
                        Target.Cancel()
                        queue_status[idx]['state'] = '수동 스킵'
                        total_processed_count += 1
                        UpdateStatusGump(queue_status)
                        app_state["skip_requested"] = False
                        
                        skip_db = load_skip_db()
                        skip_db.append({"serial": t_entry['serial'], "x": tx, "y": ty})
                        save_skip_db(skip_db)
                        
                        db_data = load_db()
                        db_data = [d for d in db_data if d['serial'] != t_entry['serial']]
                        save_db(db_data)
                        update_cuo_markers([t['serial'] for t in target_queue])
                        break
                    elif nav_result == "STOP":
                        Target.Cancel()
                        Player.HeadMessage(33, "🛑 작업 중단! 메인 메뉴로 복귀합니다.")
                        app_state["stop_requested"] = False
                        SendSummaryReport()
                        Gumps.CloseGump(STATUS_GUMP_ID)
                        return
                    elif nav_result == False:
                        Target.Cancel()
                        queue_status[idx]['state'] = '오류 스킵'
                        total_processed_count += 1
                        UpdateStatusGump(queue_status)
                        
                        skip_db = load_skip_db()
                        skip_db.append({"serial": t_entry['serial'], "x": tx, "y": ty})
                        save_skip_db(skip_db)
                        
                        db_data = load_db()
                        db_data = [d for d in db_data if d['serial'] != t_entry['serial']]
                        save_db(db_data)
                        update_cuo_markers([t['serial'] for t in target_queue])
                        break
                    Misc.Pause(100)
# -----------------------------------------------------------------------------
# [Dashboard UI 및 메인 루프] 
# -----------------------------------------------------------------------------
DASHBOARD_GUMP_ID = 888888

def GGO_GumpHandler():
    gd = Gumps.GetGumpData(DASHBOARD_GUMP_ID)
    if gd and gd.buttonid > 0:
        bid = gd.buttonid
        Gumps.SendAction(DASHBOARD_GUMP_ID, 0)
        Gumps.CloseGump(DASHBOARD_GUMP_ID)
        return bid
    return 0

def ShowDashboard():
    global config
    while True:
        gd = Gumps.CreateGump(movable=True)
        Gumps.AddPage(gd, 0)
        Gumps.AddBackground(gd, 0, 0, 310, 490, 30546)
        Gumps.AddAlphaRegion(gd, 0, 0, 310, 490)
        Gumps.AddLabel(gd, 45, 15, 53, "⛵ BaUL SOS Farmer Official v{}".format(CURRENT_VERSION))
        # 버튼 상수 (Grid Mover 기준)
        HEADER_BAR      = 55
        BTN_GREEN_N     = 40030
        BTN_GREEN_P     = 40031
        BTN_GOLD_N      = 40299
        BTN_GOLD_P      = 40300
        BTN_RED_N       = 40297
        BTN_RED_P       = 40298
        BTN_BLUE_N      = 40021
        BTN_BLUE_P      = 40031
        CHK_GEM_OFF     = 5844
        CHK_GEM_ON      = 5845
        
        LABEL_HUE    = 1152  # 백색/은색
        GRAY_HUE     = 99    # 회색 (설명용)
        GOLD_HUE     = 52    # 금색
        GREEN_HUE    = 167   # 녹색
        
        # 1. 쪽지 등록 (새 DB 구축 -> SOS DB 추가)
        Gumps.AddButton(gd, 25, 55, BTN_GOLD_N, BTN_GOLD_P, 1, 1, 0)
        Gumps.AddLabel(gd, 55, 59, GOLD_HUE, "쪽지 등록")
        Gumps.AddLabel(gd, 170, 58, GRAY_HUE, "SOS DB 우선 추가")
        
        # 2. 파밍 시작 (전자동 파밍 시작 -> 바다에서 해마타고!)
        Gumps.AddButton(gd, 25, 88, BTN_GREEN_N, BTN_GREEN_P, 2, 1, 0)
        Gumps.AddLabel(gd, 55, 92, GREEN_HUE, "파밍 시작")
        Gumps.AddLabel(gd, 170, 91, GRAY_HUE, "바다에서 해마타고!")
        
        Gumps.AddImageTiled(gd, 20, 125, 270, 2, HEADER_BAR)
        
        # 3 & 4. 체크박스 옵션 (상자 보관 / 보석 루팅)
        box_mode = config.get("box_mode", 0)
        box_hue = GREEN_HUE if box_mode == 1 else LABEL_HUE
        box_art = CHK_GEM_ON if box_mode == 1 else CHK_GEM_OFF
        Gumps.AddButton(gd, 25, 140, box_art, box_art, 3, 1, 0)
        Gumps.AddLabel(gd, 55, 144, box_hue, "상자 보관")
        Gumps.AddLabel(gd, 170, 143, GRAY_HUE, "빈 상자 챙기기")
        
        loot_gems = config.get("loot_gems", 1)
        gem_hue = GREEN_HUE if loot_gems == 1 else LABEL_HUE
        gem_art = CHK_GEM_ON if loot_gems == 1 else CHK_GEM_OFF
        Gumps.AddButton(gd, 25, 170, gem_art, gem_art, 4, 1, 0)
        Gumps.AddLabel(gd, 55, 174, gem_hue, "보석 루팅")
        Gumps.AddLabel(gd, 170, 173, GRAY_HUE, "보석 챙기기")
        
        gate_refresh = config.get("gate_refresh", 0)
        gate_hue = GREEN_HUE if gate_refresh == 1 else LABEL_HUE
        gate_art = CHK_GEM_ON if gate_refresh == 1 else CHK_GEM_OFF
        Gumps.AddButton(gd, 25, 200, gate_art, gate_art, 9, 1, 0)
        Gumps.AddLabel(gd, 55, 204, gate_hue, "게이트 리프")
        Gumps.AddLabel(gd, 170, 203, GRAY_HUE, "게이트 만료 방지")
        
        Gumps.AddImageTiled(gd, 20, 230, 270, 2, HEADER_BAR)
        
        # 10, 11 추가 (프로텍션 / 뱀파폼)
        use_prot = config.get("use_protection", 0)
        prot_hue = GREEN_HUE if use_prot == 1 else LABEL_HUE
        prot_art = CHK_GEM_ON if use_prot == 1 else CHK_GEM_OFF
        Gumps.AddButton(gd, 25, 240, prot_art, prot_art, 10, 1, 0)
        Gumps.AddLabel(gd, 55, 244, prot_hue, "프로텍션 유지")
        Gumps.AddLabel(gd, 170, 243, GRAY_HUE, "물리 맞음 캔슬비방")
        
        use_vamp = config.get("use_vamp_form", 0)
        vamp_hue = GREEN_HUE if use_vamp == 1 else LABEL_HUE
        vamp_art = CHK_GEM_ON if use_vamp == 1 else CHK_GEM_OFF
        Gumps.AddButton(gd, 25, 270, vamp_art, vamp_art, 11, 1, 0)
        Gumps.AddLabel(gd, 55, 274, vamp_hue, "뱀파폼 유지")
        Gumps.AddLabel(gd, 170, 273, GRAY_HUE, "해독스킵/피흡효과")
        
        marker_maps = config.get("marker_maps", 0)
        marker_hue = GREEN_HUE if marker_maps == 1 else LABEL_HUE
        marker_art = CHK_GEM_ON if marker_maps == 1 else CHK_GEM_OFF
        Gumps.AddButton(gd, 25, 300, marker_art, marker_art, 12, 1, 0)
        Gumps.AddLabel(gd, 55, 304, marker_hue, "마커 트라멜")
        Gumps.AddLabel(gd, 170, 303, GRAY_HUE, "펠+트라 마커 표시")

        Gumps.AddImageTiled(gd, 20, 335, 270, 2, HEADER_BAR)
        
        # 5. DB 오류 체크 (무결성 검증)
        Gumps.AddButton(gd, 25, 350, BTN_BLUE_N, BTN_BLUE_P, 5, 1, 0)
        Gumps.AddLabel(gd, 55, 354, LABEL_HUE, "DB 검사")
        Gumps.AddLabel(gd, 170, 353, GRAY_HUE, "DB 오류 체크")

        # 6. DB 초기화
        Gumps.AddButton(gd, 25, 383, BTN_RED_N, BTN_RED_P, 6, 1, 0)
        Gumps.AddLabel(gd, 55, 387, 33, "DB 초기화")
        Gumps.AddLabel(gd, 170, 386, GRAY_HUE, "많이 꼬이면 사용")

        # 7. 재설정
        Gumps.AddButton(gd, 25, 416, BTN_BLUE_N, BTN_BLUE_P, 7, 1, 0)
        Gumps.AddLabel(gd, 55, 420, LABEL_HUE, "재설정")
        Gumps.AddLabel(gd, 170, 419, GRAY_HUE, "세팅 다시 하기")

        # 8. 마커 갱신 (현재 DB 기반으로 CSV 강제 재생성)
        Gumps.AddButton(gd, 25, 449, BTN_GOLD_N, BTN_GOLD_P, 8, 1, 0)
        Gumps.AddLabel(gd, 55, 453, GOLD_HUE, "마커 갱신")
        Gumps.AddLabel(gd, 170, 452, GRAY_HUE, "마커 다시 그리기")
        
        Gumps.SendGump(DASHBOARD_GUMP_ID, Player.Serial, 0, 0, gd.gumpDefinition, gd.gumpStrings)
        
        waiting = True
        res = 0
        while waiting:
            Misc.Pause(100)
            res = GGO_GumpHandler()
            if res > 0: waiting = False
            
        if res == 3:
            config["box_mode"] = 1 if config.get("box_mode", 0) == 0 else 0
            save_config(config)
        elif res == 4:
            config["loot_gems"] = 1 if config.get("loot_gems", 1) == 0 else 0
            save_config(config)
        elif res == 5:
            Verify_Database()
        elif res == 8:
            update_cuo_markers()
            Player.HeadMessage(68, "✅ 맵 마커(CSV) 갱신 완료! UOMap이나 CUO 월드맵을 켜보세요.")
        elif res == 9:
            config["gate_refresh"] = 1 if config.get("gate_refresh", 0) == 0 else 0
            save_config(config)
        elif res == 10:
            config["use_protection"] = 1 if config.get("use_protection", 0) == 0 else 0
            save_config(config)
            if config["use_protection"] == 1 and not Player.BuffsExist('Protection'):
                Player.HeadMessage(55, "프로텍션을 시전하여 유지합니다.")
                Spells.CastMagery('Protection')
                Misc.Pause(3000)
        elif res == 11:
            config["use_vamp_form"] = 1 if config.get("use_vamp_form", 0) == 0 else 0
            save_config(config)
            if config["use_vamp_form"] == 1 and not Player.BuffsExist('Vampiric Embrace'):
                Player.HeadMessage(55, "뱀파이어 폼으로 변신합니다.")
                Spells.CastNecro('Vampiric Embrace')
                Misc.Pause(3000)
        elif res == 12:
            config["marker_maps"] = 1 if config.get("marker_maps", 0) == 0 else 0
            save_config(config)
            label = "펠루카 + 트라멜" if config["marker_maps"] == 1 else "펠루카만"
            Player.HeadMessage(68, "마커 맵: {} 으로 변경".format(label))
        else:
            return res

# -----------------------------------------------------------------------------
# [메인 실행부 - 연속성 확보]
# -----------------------------------------------------------------------------
try:
    Journal.Clear()
    config = load_config()
    if not config: config = run_setup()
    
    # A* 네비게이션 그리드 1회 전역 로딩 (대시보드 표시 이전)
    load_sea_grid()

    fishingpole = config.get("fishingpole", 0)
    Trashbag = config.get("Trashbag", 0)
    Homebook = config.get("Homebook", 0)
    DoneBox = config.get("DoneBox", 0)
    ValuableBox = config.get("ValuableBox", 0)
    ByproductBox = config.get("ByproductBox", 0)
    HighValueBox = config.get("HighValueBox", 0)
    SosChestContainer = config.get("SosChestContainer", 0)

    while True:
        choice = ShowDashboard()

        if choice == 1: 
            Build_Database()
        elif choice == 2: 
            InfiniteAutoFarm()
        elif choice == 6: 
            save_db([])
            save_skip_db([])
            try: update_cuo_markers()
            except: pass
            Player.HeadMessage(66, "🚨 DB 및 스킵 데이터가 완전히 초기화되었습니다.")
        elif choice == 7: 
            config = run_setup()
            fishingpole = config.get("fishingpole", 0)
            Trashbag = config.get("Trashbag", 0)
            Homebook = config.get("Homebook", 0)
            DoneBox = config.get("DoneBox", 0)
            ValuableBox = config.get("ValuableBox", 0)
            ByproductBox = config.get("ByproductBox", 0)
            HighValueBox = config.get("HighValueBox", 0)
            SosChestContainer = config.get("SosChestContainer", 0)

except BaseException as e:
    CloseTracker() # <--- 추가
    error_msg = str(e)
    # 기존 종료 로직 유지...
    if "SystemError" in error_msg or "스레드가 중단되었습니다" in error_msg or "Thread was being aborted" in error_msg:
        Player.HeadMessage(55, "스크립트가 수동으로 종료되었습니다.")
        SendSummaryReport() 
    else:
        error_detail = traceback.format_exc() 
        print("======== CRASH LOG ========")
        print(error_detail)
        print("===========================")
        UpdateTrackerError("치명적 오류: " + str(e)[:60])
        Misc.Pause(3000)
        SendSummaryReport() 
        clean_detail = error_detail[-1500:] if len(error_detail) > 1500 else error_detail
        SendDiscord("🚨 **[긴급 오류 추적 보고]** SOS 매크로 중단\n```python\n{0}\n```".format(clean_detail))
        Misc.ScriptStopAll()
