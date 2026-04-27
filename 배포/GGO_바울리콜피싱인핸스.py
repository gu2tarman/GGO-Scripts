# -*- coding: utf-8 -*-

SCRIPT_ID = "GGO_RECALL_FISHING"
SCRIPT_NAME = "GGO_바울리콜피싱인핸스"
CURRENT_VERSION = "1.5"

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
from System import Byte, Int32, Environment, String
from System.IO import Directory, Path, File
from System.Net import WebClient
from System.Text import Encoding
from System.Threading import Thread, ThreadStart
import json
import time
import ctypes

# =============================================================================
# [GGO Project] 바울 리콜피싱 인핸스 v1.5
# - 원본 스크립트: 바다 낚시 리콜 매크로 by 바보울온
# =============================================================================

# -----------------------------------------------------------------------------
# [1] script_settings.json 기본값
# -----------------------------------------------------------------------------
#
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 사용자 설정은 스크립트 파일이 아니라
# GGO_Settings/GGO_바울리콜피싱인핸스/script_settings.json에서 수정하세요.
FishBucket = 1             # 피쉬 버켓 사용: 집/은행 귀환 시 물고기를 버켓에 초고속으로 수납
acientsosonly = 1          # 고대 SOS 전용: 일반 SOS 병은 버리고 고대 SOS만 가방에 보존
Demonsummon = 1            # 데몬 자동 소환: 시서펜트 조우 시 어그로 분산용 (필요 마법: Summon Daemon)
Trashpoint = 0             # 쓰레기 분리수거: 지정된 잡템(Trashpointitem)을 쓰레기통에 자동 폐기
specialfishingnettrash = 0 # 일반 그물망 폐기: (인핸스 버전에서는 바다에 자동 투척하므로 0 권장)
NotifySerpent = 0          # 현재 비활성 기능 기본값
BOD_COLLECT = 0            # BOD 자동 수거: 4시간 5분마다 홈 룬북을 이용해 NPC에게 수거 후 보관

# -----------------------------------------------------------------------------
# [2] 정밀 필터 및 통신 설정
# -----------------------------------------------------------------------------
# 어상인 퀘스트 대응 도축 필터 
FISH_CUTTING_MODE = 2      # 1: (무자비) 모든 물고기 도축 / 2: (스마트) 퀘스트 어종(10스톤) 보존

FISHING_SCRIPT_SETTINGS_DEFAULTS = {
    "fish_bucket": FishBucket,
    "ancient_sos_only": acientsosonly,
    "bod_collect": BOD_COLLECT,
    "fish_cutting_mode": FISH_CUTTING_MODE,
    "demon_summon": Demonsummon,
    "fcr_delay": 100
}

FISHING_SCRIPT_SETTINGS_ORDER = [
    "fish_bucket",
    "ancient_sos_only",
    "bod_collect",
    "fish_cutting_mode",
    "demon_summon",
    "fcr_delay"
]

FISHING_SCRIPT_SETTINGS_GUIDE = """GGO_바울리콜피싱인핸스 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 리콜피싱 운용 설정입니다.
값을 바꾼 뒤 리콜피싱 스크립트를 다시 실행하면 적용됩니다.

수정 시 주의:
- true / false 값은 반드시 소문자로 입력하세요.
- 각 줄 끝의 쉼표는 지우지 마세요.

fish_bucket
  1: 집/은행 귀환 시 피쉬 버켓에 물고기를 수납합니다.
  0: 피쉬 버켓을 사용하지 않습니다.

ancient_sos_only
  1: 고대 SOS만 보존하고 일반 SOS 병은 버립니다.
  0: 일반 SOS도 별도 보관함에 보존합니다.

bod_collect
  1: 4시간 5분마다 홈 룬북으로 BOD를 수거합니다.
  0: BOD 수거를 끕니다.

fish_cutting_mode
  1: 모든 물고기를 도축합니다.
  2: 퀘스트 어종은 보존하고 일반 물고기만 도축합니다.

demon_summon
  1: 바다에서 데몬이 소환 중이 아니면 자동으로 소환합니다.
  0: 데몬 자동 소환을 끕니다.

fcr_delay
  전투 캐스팅 딜레이(ms)입니다. 기본값: 100
"""

_GGO_CONFIG_READY = False
try:
    from GGO_user_config import get_discord_webhook, get_character_settings_path, load_script_settings, load_character_settings, save_character_settings, ensure_script_settings_guide
    _GGO_CONFIG_READY = True
except Exception:
    pass

if _GGO_CONFIG_READY:
    try:
        ensure_script_settings_guide(SCRIPT_NAME, FISHING_SCRIPT_SETTINGS_GUIDE)
        _script_settings = load_script_settings(SCRIPT_NAME, FISHING_SCRIPT_SETTINGS_DEFAULTS, FISHING_SCRIPT_SETTINGS_ORDER)
        FishBucket = int(_script_settings.get("fish_bucket", FishBucket))
        acientsosonly = int(_script_settings.get("ancient_sos_only", acientsosonly))
        BOD_COLLECT = int(_script_settings.get("bod_collect", BOD_COLLECT))
        FISH_CUTTING_MODE = int(_script_settings.get("fish_cutting_mode", FISH_CUTTING_MODE))
        Demonsummon = int(_script_settings.get("demon_summon", Demonsummon))
        FCR_DELAY = int(_script_settings.get("fcr_delay", 100))
    except Exception:
        FCR_DELAY = 100

# 디스코드 웹훅 알림 주소
WEBHOOK_URL = ""
try:
    if not WEBHOOK_URL:
        WEBHOOK_URL = get_discord_webhook(True)
except Exception:
    pass
# 전투 개틀링 딜레이 (서버 FCR에 맞춰 튜닝, 단위: ms)
if 'FCR_DELAY' not in globals():
    FCR_DELAY = 100

# -----------------------------------------------------------------------------
# [3] 고정 시스템 데이터 (수정 금지)
# -----------------------------------------------------------------------------
notoriety = [3, 4, 5, 6]   
scissors = 0x0F9F          
dagger = 0x0F52            
leather = 0x1079           
serpentcorpse = 0x2006     
shoes = [0x170F, 0x170B, 0x170D, 0x1711] 

Trashpointitem = [0x14EC]         
saveitem = [0x09CE, 0x09CC, 0x044C3, 0x09CD, 0x09CF, 0x3196, 0x44C4, 0x44C6, 0x44C5, 0x14EE, 0x09F1, 0xA306, 0x4303, 0x4307, 0x4306, 0x573A, 0xA421, 0x26B4, 0xF7A, 0x97A, 0xf8C, 0x1081, 0xEED, 0x97A]
seaserpentget = [0x1079, 0x4077, 0x26B4, 0x14EE, 0xdCA, 0x1081, 0xA421, 0x26B4, 0x99F, 0xF7A, 0x97A, 0xf8C, 0xEED, 0x09F1]

all_fish_ids = [0x44C4, 0x09CC, 0x09CD, 0x09CF, 0x4306, 0x09CE, 0x44C6, 0x44C3, 0x4307, 0x4303, 0x44C5] 
common_fish_ids = [0x09CC, 0x09CD, 0x09CE, 0x09CF] 
quest_fish_ids = [0x44C4, 0x4306, 0x44C6, 0x44C3, 0x4307, 0x4303, 0x44C5]

fishingpole = 0
largefishingnet = 0
homerune = 0
trashbag = 0
fishbox = 0
FishBucketSerial = 0
BodContainer = 0
NormalSosContainer = 0

DASHBOARD_GUMP_ID = 0x889922
if 'start_time' not in globals(): start_time = time.time()
if 'total_counts' not in globals(): total_counts = {'C': 0, 'Q': 0, 'S': 0, 'N': 0, 'A': 0}
if 'last_inventory' not in globals(): last_inventory = {}
if 'monitor_active' not in globals(): monitor_active = False
if 'is_paused' not in globals(): is_paused = False 
if 'looted_corpses' not in globals(): looted_corpses = {} 
if 'protected_items' not in globals(): protected_items = []
if 'snapshot_taken' not in globals(): snapshot_taken = False
if 'last_dashboard_time' not in globals(): last_dashboard_time = 0
if '_config_cache' not in globals(): _config_cache = {}
if '_config_cache_loaded' not in globals(): _config_cache_loaded = False

LastBodTime = 0 

# =============================================================================
# [웹훅 알림 및 방어 시스템]
# =============================================================================
def trim_working_set():
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
    except:
        pass

def SendDiscord(msg):
    if not WEBHOOK_URL: return
    def task():
        wc = None
        try:
            wc = WebClient()
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": msg}, ensure_ascii=False)
            wc.UploadString(WEBHOOK_URL, "POST", payload)
        except: pass
        finally:
            if wc: wc.Dispose()
    try: t = Thread(ThreadStart(task)); t.Start()
    except: pass

def GGO_EmergencyClear():
    journal_proof = Journal.Search("dragging an object") or Journal.Search("물건을 들고 있는 동안")
    if journal_proof:
        Player.HeadMessage(33, "🚨 [이머전시] 시스템 차단 감지! 손 비우기 강제 집행")
        Target.Cancel()
        Misc.Pause(200)
        try:
            Items.DropFromHand(Player.Backpack, Player.Backpack)
            Items.DropItemGroundSelf(Player.Backpack, 0)
        except:
            pass
        Journal.Clear()
        Player.HeadMessage(66, "✅ 정화 프로세스 완료")
        Misc.Pause(1000)
        return True
    return False

def HandleDeath():
    if Player.IsGhost:
        pos = Player.Position
        msg = "💀 **[사망 보고]** {0} 캐릭터가 바다에서 사망했습니다!\n- 위치: (X:{1}, Y:{2})\n- 조치: 낚시 매크로를 즉시 종료합니다.".format(Player.Name, pos.X, pos.Y)
        SendDiscord(msg)
        Misc.Pause(2000) 
        Misc.ScriptStopAll()

def TakeSnapshot():
    global protected_items, snapshot_taken
    protected_items = []
    if Player.Backpack:
        for item in Player.Backpack.Contains:
            # 물고기 종류(일반/퀘스트)와 병 등 처리해야 할 아이템은 보호 대상에서 제외
            if item.ItemID not in all_fish_ids and item.ItemID != 0x099F and item.ItemID != 0x14EE:
                protected_items.append(item.Serial)
    snapshot_taken = True
    Player.HeadMessage(66, "🛡️ [스냅샷] 백팩 클렌징 완료. {}개의 장비 절대 보호 명단 등록!".format(len(protected_items)))

# =============================================================================
# [대시보드 모니터링 모듈]
# =============================================================================
def UpdateStats():
    global total_counts, last_inventory
    if not monitor_active: return
    
    track_ids = common_fish_ids + quest_fish_ids + [0x14EE]
    current_inv = {}
    if Player.Backpack:
        for item in Player.Backpack.Contains:
            if item.ItemID in track_ids:
                if item.ItemID == 0x14EE:
                    key = "{}_{}".format(item.Serial, item.Hue)
                else:
                    key = item.Serial
                current_inv[key] = item.Amount
                
    for key, amount in current_inv.items():
        diff = amount - last_inventory.get(key, 0)
        if diff > 0:
            if type(key) is str and "_" in key: 
                serial_str, hue_str = key.split('_')
                if int(hue_str) == 0: total_counts['N'] += diff 
                else: total_counts['A'] += diff 
            else:
                item = Items.FindBySerial(key)
                if item:
                    if item.ItemID in common_fish_ids: total_counts['C'] += diff
                    elif item.ItemID in quest_fish_ids: total_counts['Q'] += diff
    last_inventory = current_inv

def _load_config_raw():
    """config JSON을 메모리 캐시에서 반환 (디스크 I/O 최소화)"""
    global _config_cache, _config_cache_loaded
    if _config_cache_loaded:
        return _config_cache
    try:
        if _GGO_CONFIG_READY:
            _config_cache = load_character_settings(
                SCRIPT_NAME,
                Player.Name,
                DEFAULT_CHARACTER_SETTINGS,
                [LEGACY_CONFIG_FILE]
            )
            _config_cache_loaded = True
            return _config_cache
        if File.Exists(CONFIG_FILE):
            _config_cache = json.loads(File.ReadAllText(CONFIG_FILE))
            _config_cache_loaded = True
            return _config_cache
    except: pass
    return {}

def _save_config(cfg):
    """config JSON 저장 + 메모리 캐시 동기화"""
    global _config_cache, _config_cache_loaded
    if _GGO_CONFIG_READY:
        save_character_settings(SCRIPT_NAME, Player.Name, cfg)
    else:
        if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
        File.WriteAllText(CONFIG_FILE, json.dumps(cfg, indent=4))
    _config_cache = cfg
    _config_cache_loaded = True

def GGO_GumpHandler():
    gd = Gumps.GetGumpData(DASHBOARD_GUMP_ID)
    if not gd or gd.buttonid <= 0:
        return False
    bid = gd.buttonid
    Gumps.SendAction(DASHBOARD_GUMP_ID, 0); Gumps.CloseGump(DASHBOARD_GUMP_ID)
    
    if bid == 100:
        ReturnHomeAndUnload(is_reset=True) 
        if File.Exists(CONFIG_FILE): File.Delete(CONFIG_FILE)
        _config_cache.clear(); globals()['_config_cache_loaded'] = False
        globals()['fishingpole'] = globals()['largefishingnet'] = globals()['homerune'] = globals()['trashbag'] = 0
        globals()['fishbox'] = globals()['FishBucketSerial'] = globals()['BodContainer'] = globals()['NormalSosContainer'] = 0
        SmartSetup()
        Initialize_Routine()
        return True
    elif bid == 200:
        cfg = _load_config_raw()
        cfg["use_protection"] = 0 if cfg.get("use_protection", 0) == 1 else 1
        _save_config(cfg)
        if cfg["use_protection"] == 1 and not Player.BuffsExist('Protection'):
            Player.HeadMessage(55, "프로텍션을 시전합니다."); Spells.CastMagery('Protection'); Misc.Pause(3000)
        else:
            Player.HeadMessage(55, "프로텍션 OFF")
        DrawDashboard(force=True)
        return True
    elif bid == 201:
        cfg = _load_config_raw()
        cfg["use_vamp_form"] = 0 if cfg.get("use_vamp_form", 0) == 1 else 1
        _save_config(cfg)
        if cfg["use_vamp_form"] == 1 and not Player.BuffsExist('Vampiric Embrace'):
            Player.HeadMessage(55, "뱀파이어 폼으로 변신합니다."); Spells.CastNecro('Vampiric Embrace'); Misc.Pause(3000)
        else:
            Player.HeadMessage(55, "뱀파이어폼 OFF")
        DrawDashboard(force=True)
        return True
    return False

def DrawDashboard(force=False):
    global last_dashboard_time
    GGO_GumpHandler()
    if not monitor_active: return
    
    # 1분 주기 갱신 제한 (force=True 시 즉시 갱신)
    now_db = time.time()
    if not force and (now_db - last_dashboard_time) < 60:
        return
    last_dashboard_time = now_db
    
    now = time.time(); elapsed = now - start_time
    
    title_text = "⏸️ 일시 정지 (!시작)" if is_paused else "BaUL Fishing Enhance"
    color_code = 33 if is_paused else 1152
    
    # 체크옵션 상태 읽기
    cfg = _load_config_raw()
    prot_on = cfg.get("use_protection", 0) == 1
    vamp_on = cfg.get("use_vamp_form", 0) == 1
    CHK_ON = 5845; CHK_OFF = 5844
    prot_art = CHK_ON if prot_on else CHK_OFF
    vamp_art = CHK_ON if vamp_on else CHK_OFF
    prot_hue = 167 if prot_on else 1152
    vamp_hue = 167 if vamp_on else 1152
    
    layout = ("{ resizepic 0 0 30546 260 270 }{ checkertrans 10 10 240 250 }"
              "{ text 25 15 " + str(color_code) + " 0 }{ text 190 15 1152 1 }{ text 25 35 1152 2 }"
              "{ text 25 55 1271 3 }{ text 165 55 1271 4 }"
              "{ text 25 75 1271 5 }{ text 165 75 1271 6 }"
              "{ text 25 95 1271 7 }{ text 165 95 1271 8 }"
              "{ text 25 115 1271 9 }{ text 165 115 1271 10 }"
              "{ button 25 145 " + str(prot_art) + " " + str(prot_art) + " 1 0 200 }{ text 50 147 " + str(prot_hue) + " 13 }"
              "{ button 25 170 " + str(vamp_art) + " " + str(vamp_art) + " 1 0 201 }{ text 50 172 " + str(vamp_hue) + " 14 }"
              "{ button 25 225 4005 4006 1 0 100 }{ text 60 227 1152 11 }"
              "{ text 190 227 1152 12 }") 
              
    texts = List[String]()
    texts.Add(title_text) 
    texts.Add("{:02d}:{:02d}".format(int(elapsed // 3600), int((elapsed % 3600) // 60))) 
    texts.Add("-" * 35) 
    texts.Add("Normal:"); texts.Add("{:,}".format(total_counts['C'])) 
    texts.Add("Quest:"); texts.Add("{:,}".format(total_counts['Q'])) 
    texts.Add("SOS Monster Kill:"); texts.Add("{:,}".format(total_counts['S'])) 
    texts.Add("SOS (Nor/Anc):"); texts.Add("{} / {}".format(total_counts['N'], total_counts['A'])) 
    texts.Add("RESET ALL (Setup)") 
    texts.Add("v" + CURRENT_VERSION) 
    texts.Add("프로텍션 유지" if prot_on else "프로텍션 OFF") 
    texts.Add("뱀파이어폼 유지" if vamp_on else "뱀파이어폼 OFF") 
    
    Gumps.SendGump(DASHBOARD_GUMP_ID, Player.Serial, 400, 400, layout, texts)

# =============================================================================
# [스마트 셋업 및 데이터 관리]
# =============================================================================
APPDATA = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "Fishing")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "Fish_{0}.json".format(Player.Name))
SAVE_DIR = LEGACY_SAVE_DIR
CONFIG_FILE = LEGACY_CONFIG_FILE

if _GGO_CONFIG_READY:
    try:
        CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
        SAVE_DIR = Path.GetDirectoryName(CONFIG_FILE)
    except Exception:
        pass

DEFAULT_CHARACTER_SETTINGS = {
    "fishingpole": 0,
    "largefishingnet": 0,
    "homerune": 0,
    "trashbag": 0,
    "fishbox": 0,
    "FishBucketSerial": 0,
    "BodContainer": 0,
    "NormalSosContainer": 0,
    "use_protection": 0,
    "use_vamp_form": 0
}

def check_possession(serial):
    item = Items.FindBySerial(serial)
    if not item: return False
    if item.RootContainer == Player.Serial: return True
    if Player.Backpack and item.RootContainer == Player.Backpack.Serial: return True
    return False

def save_json():
    global fishingpole, largefishingnet, homerune, trashbag, fishbox, FishBucketSerial, BodContainer, NormalSosContainer
    # 기존 설정 로드하여 체크옵션 보존
    existing = _load_config_raw()
    data = {
        "fishingpole": int(fishingpole), "largefishingnet": int(largefishingnet),
        "homerune": int(homerune), "trashbag": int(trashbag),
        "fishbox": int(fishbox), "FishBucketSerial": int(FishBucketSerial),
        "BodContainer": int(BodContainer), "NormalSosContainer": int(NormalSosContainer),
        "use_protection": existing.get("use_protection", 0),
        "use_vamp_form": existing.get("use_vamp_form", 0)
    }
    try: _save_config(data); Player.HeadMessage(66, "설정 저장 완료")
    except: pass

def load_json():
    global fishingpole, largefishingnet, homerune, trashbag, fishbox, FishBucketSerial, BodContainer, NormalSosContainer
    global _config_cache, _config_cache_loaded
    try:
        data = _load_config_raw()
        if not data:
            return False
        fishingpole = int(data.get("fishingpole", 0)); largefishingnet = int(data.get("largefishingnet", 0))
        homerune = int(data.get("homerune", 0)); trashbag = int(data.get("trashbag", 0))
        fishbox = int(data.get("fishbox", 0)); FishBucketSerial = int(data.get("FishBucketSerial", 0))
        BodContainer = int(data.get("BodContainer", 0)); NormalSosContainer = int(data.get("NormalSosContainer", 0))
        _config_cache = data; _config_cache_loaded = True
        return True
    except: return False

def SmartSetup():
    global fishingpole, largefishingnet, homerune, trashbag, fishbox, FishBucketSerial, BodContainer, NormalSosContainer
    changed = False

    items_to_check = [
        ('fishingpole', '[낚싯대]', True), ('largefishingnet', '[대형 그물망]', True),
        ('homerune', '[홈 & BOD수거용 룬북]', True), ('trashbag', '[쓰레기 가방]', True)
    ]

    for var_name, label, in_bag in items_to_check:
        curr_val = globals()[var_name]
        if not curr_val or (in_bag and not check_possession(curr_val)):
            Player.HeadMessage(33, "필수 아이템 유실: {} 선택".format(label))
            t = Target.PromptTarget("{} 지정 (ESC 취소)".format(label))
            if t > 0: globals()[var_name] = t; changed = True
            else: Misc.ScriptStopAll()

    if fishbox <= 0:
        t = Target.PromptTarget("[물고기 상자] 컨테이너 지정")
        if t > 0: fishbox = t; changed = True

    if FishBucket == 1 and FishBucketSerial <= 0:
        t = Target.PromptTarget("[피쉬 버켓] 지정")
        if t > 0: FishBucketSerial = t; changed = True
        
    if BOD_COLLECT == 1 and BodContainer <= 0:
        t = Target.PromptTarget("[BOD 보관 컨테이너] 지정")
        if t > 0: BodContainer = t; changed = True

    if acientsosonly == 0 and NormalSosContainer <= 0:
        t = Target.PromptTarget("[일반 SOS 보관함] 지정")
        if t > 0: NormalSosContainer = t; changed = True

    if changed: save_json()

# =============================================================================
# [BOD 자동 수거 모듈]
# =============================================================================
def CollectBOD(sn):
    for x in range(3):
        Journal.Clear()
        Target.TargetExecute(sn)
        Misc.WaitForContext(sn, 1000)
        Misc.ContextReply(sn, 1)
        Gumps.WaitForGump(2611865322, 1500)
        Gumps.SendAction(2611865322, 1)
        
        if Journal.Search("offer may be available"):
            Journal.Clear()
            break
        Misc.Pause(1000)

def ProcessBOD():
    global LastBodTime
    if BOD_COLLECT != 1 or BodContainer <= 0: return
    
    if LastBodTime == 0 or (time.time() - LastBodTime) >= 14700:
        Player.HeadMessage(66, "★ BOD 수거 사이클 시작 ★")
        SendDiscord("📦 **[BOD 수거]** {0} 캐릭터가 BOD 수거를 시작합니다.".format(Player.Name))
        
        Items.UseItem(homerune); Misc.Pause(1500)
        Gumps.WaitForGump(89, 2000); Gumps.SendAction(89, 11); Misc.Pause(4000)
        CollectBOD(0x0001BD87); CollectBOD(0x000000E3)
        
        Items.UseItem(homerune); Misc.Pause(1500)
        Gumps.WaitForGump(89, 2000); Gumps.SendAction(89, 12); Misc.Pause(4000)
        CollectBOD(0x0000023B); CollectBOD(0x0000023F); CollectBOD(0x0001BA3A)
        
        Items.UseItem(homerune); Misc.Pause(1500)
        Gumps.WaitForGump(89, 2000); Gumps.SendAction(89, 10); Misc.Pause(4000)
        
        loop_breaker = 0
        while Items.FindByID(0x2258, -1, Player.Backpack.Serial) and loop_breaker < 30:
            bod_item = Items.FindByID(0x2258, -1, Player.Backpack.Serial)
            if bod_item:
                Items.Move(bod_item, BodContainer, -1)
                Misc.Pause(1200)
            loop_breaker += 1
            
        LastBodTime = time.time()
        Player.HeadMessage(66, "★ BOD 수거 완료 ★")

def WaitForBackpack():
    for _ in range(10):
        if Player.Backpack: return True
        Misc.Pause(500)
    return False

# =============================================================================
# [인벤토리 정리 및 도축 모듈]
# =============================================================================
def Trashpoints():
    if not Player.Backpack: return
    if Trashpoint == 1:
        for i in Trashpointitem:
            loop_breaker = 0
            while Items.FindByID(i, -1, Player.Backpack.Serial) and loop_breaker < 20:
                movetrashitem = Items.FindByID(i, -1, Player.Backpack.Serial)
                if movetrashitem: Items.Move(movetrashitem, fishbox, -1); Misc.Pause(800)
                loop_breaker += 1

def shoestrash():
    if not Player.Backpack: return
    for s in shoes:
        loop_breaker = 0
        while Items.FindByID(s, 0x0000, Player.Backpack.Serial) and loop_breaker < 20:
            shoe = Items.FindByID(s, 0x0000, Player.Backpack.Serial)
            if shoe: Items.Move(shoe, trashbag, -1); Misc.Pause(500)
            loop_breaker += 1

def sosopen():
    if not Player.Backpack: return
    loop_breaker2 = 0
    while Items.FindByID(0x099F, -1, Player.Backpack.Serial) and loop_breaker2 < 10:
        sos = Items.FindByID(0x099F, -1, Player.Backpack.Serial)
        if sos:
            Items.UseItem(sos); Misc.Pause(800)
        loop_breaker2 += 1

    UpdateStats()
    DrawDashboard()

    if acientsosonly == 1:
        loop_breaker3 = 0
        while Items.FindByID(0x14EE, 0x0000, Player.Backpack.Serial) and loop_breaker3 < 10:
            nomalsospaper = Items.FindByID(0x14EE, 0x0000, Player.Backpack.Serial)
            if nomalsospaper: 
                Items.Move(nomalsospaper, trashbag, -1)
                Misc.Pause(600); Misc.IgnoreObject(nomalsospaper)
            loop_breaker3 += 1

def cuttingleather():
    if not Player.Backpack: return
    loop_breaker = 0
    while Items.FindByID(leather, -1, Player.Backpack.Serial) and loop_breaker < 20:
        leathers = Items.FindByID(leather, -1, Player.Backpack.Serial)
        scissor = Items.FindByID(scissors, -1, Player.Backpack.Serial)
        if scissor and leathers:
            Items.UseItem(scissor); Target.WaitForTarget(1500); Target.TargetExecute(leathers); Misc.Pause(1000); Target.Cancel()
        else: break
        loop_breaker += 1

def ThrowFishingNet():
    if not Player.Backpack: return
    nets = Items.FindAllByID(0xDCA, -1, Player.Backpack.Serial, -1, False)
    for net in nets:
        d_str = str(Player.Direction)
        dx, dy = 3, 0 
        
        if d_str == 'North' or d_str == '0':   dx = 3;  dy = 0   
        elif d_str == 'Right' or d_str == '1': dx = 2;  dy = -2  
        elif d_str == 'East' or d_str == '2':  dx = 0;  dy = 3   
        elif d_str == 'Down' or d_str == '3':  dx = -2; dy = 2   
        elif d_str == 'South' or d_str == '4': dx = -3; dy = 0   
        elif d_str == 'Left' or d_str == '5':  dx = -2; dy = -2  
        elif d_str == 'West' or d_str == '6':  dx = 0;  dy = -3  
        elif d_str == 'Up' or d_str == '7':    dx = 2;  dy = 2   
        
        Items.UseItem(net)
        Target.WaitForTarget(1500, False)
        Target.TargetExecute(Player.Position.X + dx, Player.Position.Y + dy, -1)
        Misc.Pause(1000)
        break 

def ProcessFish(force_all=False):
    if not Player.Backpack: return
    daggers = Items.FindByID(dagger, -1, Player.Backpack.Serial)
    if not daggers: return
    
    items_to_cut = []
    for item in Player.Backpack.Contains:
        if item.ItemID == 0x097A: continue 
        
        # [스냅샷 보호막] 초기 세팅 시 가방에 있던 장비는 무조건 패스
        if item.Serial in protected_items: continue
        
        should_cut = False
        item_name = item.Name.lower() if item.Name else ""
        if "steak" in item_name or "생선살" in item_name: continue
        
        Items.WaitForProps(item.Serial, 1000)
        if item.Properties:
            for prop in item.Properties:
                try:
                    prop_text = str(prop.ToString()).lower()
                    if "님이 낚음" in prop_text or "caught by" in prop_text:
                        should_cut = True
                        break
                except:
                    pass
        
        # [단위 무게 검증] 스냅샷이 활성화된 상태에서, 15스톤 대형 그물이 아니며 1마리당 11스톤 이상인 신규 유입 물고기 강제 도축
        if snapshot_taken and not should_cut and item.ItemID != 0x0DCA and item.Amount > 0 and (item.Weight / item.Amount) >= 11:
            should_cut = True
            
        if not should_cut:
            if force_all or FISH_CUTTING_MODE == 1:
                if item.ItemID in all_fish_ids: 
                    should_cut = True
            elif FISH_CUTTING_MODE == 2:
                if item.ItemID in all_fish_ids and item.ItemID not in quest_fish_ids:
                    should_cut = True
                
        if should_cut:
            items_to_cut.append(item)
            
    for target_item in items_to_cut:
        if Items.FindBySerial(target_item.Serial):
            Player.HeadMessage(55, '🔪 물고기 손질')
            Items.UseItem(daggers); Target.WaitForTarget(1500); Target.TargetExecute(target_item); Misc.Pause(1200); Target.Cancel()

# =============================================================================
# [전투 및 시체 루팅 모듈]
# =============================================================================
def Demonsumoning():
    if Demonsummon == 1 and Player.Followers == 0:
        Spells.CastMagery('Summon Daemon'); Misc.Pause(5000); Player.ChatSay('all guard me')

def CombatRoutine():
    fil = Mobiles.Filter()
    fil.Enabled = True
    fil.RangeMin = -1
    fil.RangeMax = 8
    fil.Notorieties = List[Byte]([Byte(c) for c in notoriety])
    fil.CheckIgnoreObject = True
    fil.IsGhost = 0
    target = Mobiles.Select(Mobiles.ApplyFilter(fil), 'Nearest')
    
    if target:
        name_lower = target.Name.lower() if target.Name else ""
        if 'dolphin' in name_lower or 'walrus' in name_lower:
            Misc.IgnoreObject(target)
            return False
            
        if NotifySerpent == 1:
            SendDiscord("🐉 **[전투 알림]** {0} 캐릭터가 적({1})과 조우하여 전투 시작.".format(Player.Name, target.Name))
        
        _vamp_active = _load_config_raw().get("use_vamp_form", 0) == 1
        while target and Mobiles.FindBySerial(target.Serial):
            Mobiles.Message(target, 55, '⚡ 록온!')
            
            if Player.Mana > 14: 
                Spells.Cast('Lightning')
                Target.WaitForTarget(2000, False)
                if Target.HasTarget():
                    if Mobiles.FindBySerial(target.Serial): 
                        Target.TargetExecute(target.Serial)
                        Misc.Pause(FCR_DELAY)
                    else:
                        Target.Cancel() 
                        break

            if Player.Poisoned and not _vamp_active: 
                Spells.Cast('Arch Cure'); Target.WaitForTarget(2000, False)
                if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(FCR_DELAY + 200)
            if Player.Hits < Player.HitsMax * 0.8: 
                Spells.Cast('Heal'); Target.WaitForTarget(2000, False)
                if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(FCR_DELAY)
            if Player.Poisoned and not _vamp_active: 
                Spells.Cast('Cure'); Target.WaitForTarget(2000, False)
                if Target.HasTarget(): Target.TargetExecute(Player.Serial); Misc.Pause(FCR_DELAY + 200)
            
            if not Mobiles.FindBySerial(target.Serial):
                Player.HeadMessage(66, "💀 타겟 처치! 즉각 전환!")
                break 
        return True
    return False

def get_valid_corpses(dist):
    all_c = Items.FindAllByID(serpentcorpse, -1, -1, dist, False)
    valid = [c for c in all_c if c.Serial not in looted_corpses]
    def sort_key(c):
        name = (c.Name.lower() if c.Name else "")
        if "sea serpent" in name or "deep sea" in name: return 0
        return 1
    valid.sort(key=sort_key)
    return valid

def corpsenet():
    corpses = get_valid_corpses(10)
    for corpse in corpses:
        if not Player.InRange(corpse, 2):
            Items.UseItem(largefishingnet)
            Target.WaitForTarget(1500)
            Target.TargetExecute(corpse)
            Misc.Pause(800)
            Target.Cancel()
            if Journal.Search('You can only use this in deep water!'):
                Misc.IgnoreObject(corpse)

def opencorpse():
    if not Player.Backpack: return
    cuttingleather(); Misc.Pause(500)
    corpses = get_valid_corpses(2)
    daggers = Items.FindByID(dagger, -1, Player.Backpack.Serial)
    for corpse in corpses:
        corpse_name = corpse.Name.lower() if corpse.Name else ""
        if "serpent" in corpse_name or "deep sea" in corpse_name:
            Player.HeadMessage(55, '해체 시작')
            if daggers:
                Items.UseItem(daggers)
                Target.WaitForTarget(1500)
                Target.TargetExecute(corpse)
                Misc.Pause(1000)
                Target.Cancel()

def lootcorpse():
    global total_counts, looted_corpses
    if not Player.Backpack: return
    corpses = get_valid_corpses(2)
    for corpse in corpses:
        corpse_name = corpse.Name.lower() if corpse.Name else ""
        is_sos_monster = ("sea serpent" in corpse_name or "deep sea serpent" in corpse_name or "kraken" in corpse_name)
        
        Player.HeadMessage(55, '루팅 시작')
        Items.UseItem(corpse); Misc.Pause(700)
        
        for i in seaserpentget:
            loop_breaker = 0
            while Items.FindByID(i, -1, corpse.Serial) and loop_breaker < 20:
                moveitem = Items.FindByID(i, -1, corpse.Serial)
                if moveitem: Items.Move(moveitem, Player.Backpack.Serial, -1); Misc.Pause(700)
                loop_breaker += 1
                
        Misc.Pause(500); cuttingleather(); Misc.IgnoreObject(corpse)
        
        looted_corpses[corpse.Serial] = time.time() 
        
        if is_sos_monster:
            total_counts['S'] += 1
            UpdateStats(); DrawDashboard()

def cleanup_looted_corpses():
    """5분 지난 시체 기록 자동 정리 (메모리 무한 성장 방지)"""
    now = time.time()
    expired = [s for s, t in looted_corpses.items() if now - t > 300]
    for s in expired:
        del looted_corpses[s]

# =============================================================================
# [귀환 및 보관(은행) 모듈]
# =============================================================================
def goship():
    if not Player.Backpack: return
    shipkey = Items.FindByID(0x100F, -1, Player.Backpack.Serial)
    box = Items.FindBySerial(fishbox)
    
    if shipkey:
        while True:
            GGO_EmergencyClear()
            Target.Cancel()
            Spells.CastMagery('Recall')
            Target.WaitForTarget(2500, False)
            if Target.HasTarget():
                Target.TargetExecute(shipkey)
                Misc.Pause(2500)
            Target.Cancel()
            WaitForBackpack()
            
            box = Items.FindBySerial(fishbox)
            if not box or abs(Player.Position.X - box.Position.X) > 3 or abs(Player.Position.Y - box.Position.Y) > 3:
                Player.HeadMessage(55, "바다 복귀 확인 완료")
                break
            else:
                Player.HeadMessage(33, "🚨 배 복귀 리콜 실패! 재시도 중...")
                Misc.Pause(2000)

def useFishBucket():
    if FishBucket == 1 and FishBucketSerial > 0:
        Items.UseItem(FishBucketSerial); Misc.Pause(1000)
        if Gumps.HasGump(0x06ABCE12):
            if len(Gumps.LastGumpGetLineList()) == 109: Gumps.SendAction(0x06ABCE12, 145); Misc.Pause(900)
        Gumps.WaitForGump(0x06ABCE12, 2500); Gumps.SendAdvancedAction(0x06ABCE12, 147, [], [0], ["100"]); Misc.Pause(1000)
        Gumps.WaitForGump(0x06ABCE12, 2500); Gumps.SendAction(0x06ABCE12, 0); Misc.Pause(1000)

def savingitem(is_reset=False):
    if not Player.Backpack: return 
    if fishbox > 0:
        # [1단계] 컨테이너 열기 + 렌더링 대기
        Items.UseItem(fishbox)
        _render_wait = 0
        while _render_wait < 10:
            _box_check = Items.FindBySerial(fishbox)
            if _box_check and _box_check.Contains is not None:
                break
            Misc.Pause(300)
            _render_wait += 1
        if _render_wait >= 10:
            Player.HeadMessage(33, "fishbox render delay! retry...")
            Items.UseItem(fishbox); Misc.Pause(2000)
        
        Misc.ClearIgnore(); Trashpoints(); Misc.Pause(500); useFishBucket(); Misc.Pause(800)
        if acientsosonly == 0 and NormalSosContainer > 0:
            Items.UseItem(NormalSosContainer); Misc.Pause(500)
        
        GGO_EmergencyClear()
        remaining_count = 0
        for attempt in range(5):
            items_to_store = [item for item in Player.Backpack.Contains if item.ItemID in saveitem] if Player.Backpack else []
            for item in items_to_store:
                if item.ItemID == 0x14EE and item.Hue == 0x0000:
                    if acientsosonly == 0 and NormalSosContainer > 0:
                        Items.Move(item.Serial, NormalSosContainer, -1); Misc.Pause(800)
                    continue 
                Items.Move(item.Serial, fishbox, -1); Misc.Pause(800)
            Misc.Pause(800)
            
            remaining_count = 0
            if Player.Backpack:
                for item in Player.Backpack.Contains:
                    if item.ItemID in saveitem:
                        if item.ItemID == 0x14EE and item.Hue == 0x0000:
                            if acientsosonly == 0 and NormalSosContainer > 0:
                                remaining_count += 1
                            else:
                                continue
                        else:
                            remaining_count += 1
                    
            if remaining_count == 0:
                break
            
            # [2단계] 잔여물 존재 시 컨테이너 재오픈 후 재시도
            if attempt < 4:
                Player.HeadMessage(33, "Remaining {}! Re-open container ({}/5)".format(remaining_count, attempt + 2))
                Items.UseItem(fishbox); Misc.Pause(1500)
                if acientsosonly == 0 and NormalSosContainer > 0:
                    Items.UseItem(NormalSosContainer); Misc.Pause(500)
                
        if remaining_count == 0:
            if not is_reset:
                Player.HeadMessage(66, "★ 하차 완료: 잔여물 없음. 바다로 복귀합니다. ★")
                goship()
            else:
                Player.HeadMessage(66, "★ 하차 완료 (리셋 모드): 바다 복귀 생략 ★")
        else:
            # [3단계] 최종 실패: 무한 대기 대신 안전 탈출
            Player.HeadMessage(33, "Storage failed ({}). Returning to sea.".format(remaining_count))
            SendDiscord("**[Storage Warning]** {0}: {1} items failed to store. Possible container render issue. Returning to sea.".format(Player.Name, remaining_count))
            if not is_reset:
                goship()


def ReturnHomeAndUnload(is_reset=False):
    ProcessFish(); cuttingleather(); Misc.Pause(400)
    ProcessBOD() 
    
    # 갇힘 방지: 리콜 루프 내 최상위 지능형 무게 감시 및 복구
    while True:
        if Player.Weight > Player.MaxWeight:
            Player.HeadMessage(33, "🚨 무게 초과! 1단계: Bless(스탯 뻥튀기) 캐스팅")
            Spells.CastMagery('Bless')
            Target.WaitForTarget(2500, False)
            if Target.HasTarget():
                Target.TargetExecute(Player.Serial)
                Misc.Pause(1000)
                
        if Player.Weight > Player.MaxWeight:
            Player.HeadMessage(33, "🚨 무게 초과! 2단계: 강제 전수 도축 시도")
            ProcessFish(force_all=True); Misc.Pause(1000)
            
        if Player.Weight > Player.MaxWeight:
            Player.HeadMessage(33, "🚨 무게 초과! 3단계: 생선살/신발 강제 투기")
            steaks = Items.FindAllByID(0x097A, -1, Player.Backpack.Serial, -1, False)
            for steak in steaks:
                Items.MoveOnGround(steak, 0, Player.Position.X, Player.Position.Y, Player.Position.Z); Misc.Pause(800)
                
            for shoe_id in shoes:
                shoelist = Items.FindAllByID(shoe_id, -1, Player.Backpack.Serial, -1, False)
                for shoe_item in shoelist: 
                    Items.MoveOnGround(shoe_item, 0, Player.Position.X, Player.Position.Y, Player.Position.Z); Misc.Pause(800)
                    
        if Player.Weight > Player.MaxWeight:
            Player.HeadMessage(33, "💀 4단계: 비상 탈출 실패. 스크립트 정지")
            SendDiscord("🚨 **[긴급]** 리콜 실패! 배 위에서 무게 초과 자가 복구에 실패했습니다. (X:{}, Y:{}) 수동 확인 요망.".format(Player.Position.X, Player.Position.Y))
            Misc.Pause(2000) 
            Misc.ScriptStopAll()

        GGO_EmergencyClear()
        Target.Cancel()
        Spells.CastMagery('Recall')
        Target.WaitForTarget(2500, False)
        if Target.HasTarget():
            Target.TargetExecute(homerune)
            Misc.Pause(2500)
        Target.Cancel()
        
        box = Items.FindBySerial(fishbox)
        if box and abs(Player.Position.X - box.Position.X) <= 3 and abs(Player.Position.Y - box.Position.Y) <= 3:
            Player.HeadMessage(55, "집 도착 확인 완료 (좌표 일치)")
            break
        else:
            Player.HeadMessage(33, "🚨 집 리콜 실패! 재시도 중...")
            Misc.Pause(2000)
            
    Player.ChatSay('bank'); Target.Cancel()
    WaitForBackpack() 
    Misc.Pause(500); savingitem(is_reset); Misc.Pause(500)

# =============================================================================
# [초기화 및 메인 루프]
# =============================================================================
def Initialize_Routine():
    global monitor_active, start_time, last_inventory
    monitor_active = True; start_time = time.time()
    track_ids = common_fish_ids + quest_fish_ids + [0x14EE]
    
    if Player.Backpack:
        last_inventory = {}
        for item in Player.Backpack.Contains:
            if item.ItemID in track_ids:
                if item.ItemID == 0x14EE:
                    key = "{}_{}".format(item.Serial, item.Hue)
                else:
                    key = item.Serial
                last_inventory[key] = item.Amount
    else:
        last_inventory = {}
    DrawDashboard(force=True)

try:
    Gumps.SendAction(DASHBOARD_GUMP_ID, 0); Gumps.CloseGump(DASHBOARD_GUMP_ID)
    
    if not load_json(): SmartSetup()
    SmartSetup() 

    Player.HeadMessage(66, "★ 스크립트 초기화 시작 ★")
    Initialize_Routine()
    
    # 봉인 상태의 최초 1회차 도축 및 하차 (안전 클렌징)
    ProcessFish()
    cuttingleather()
    shoestrash()
    sosopen()
    ReturnHomeAndUnload()
    
    Misc.Pause(2000)
    Target.Cancel()

    # 클렌징 직후, 출항 전 가장 깨끗한 상태에서 스마트 스냅샷 작동
    TakeSnapshot()

    if Player.IsGhost: Misc.Pause(10000)

    Player.HeadMessage(66, "🚀 쾌속 끌낚시(Trolling) 출항 준비 완료!")
    SendDiscord("🚀 **[작업 시작]** {0} 캐릭터가 낚시를 시작합니다.".format(Player.Name))

    # [유언 보장] 무한 루프
    while True:
        HandleDeath()
        cleanup_looted_corpses()
        
        if Journal.Search("!대기"):
            is_paused = True
            DrawDashboard(force=True)
            Player.HeadMessage(33, "스크립트 일시 정지 (재개: !시작)")
        
        if is_paused and Journal.Search("!시작"):
            is_paused = False
            DrawDashboard(force=True)
            Player.HeadMessage(66, "스크립트 작업 재개!")
            
        Journal.Clear()
        
        if GGO_GumpHandler(): continue
        
        if is_paused:
            Misc.Pause(500)
            continue
        
        if not Player.Backpack:
            Misc.Pause(1000); continue
        
        # [버프 자동 유지] 프로텍션 / 뱀파이어폼
        _buff_cfg = _load_config_raw()
        if _buff_cfg.get("use_protection", 0) == 1 and not Player.BuffsExist("Protection"):
            Player.HeadMessage(55, "프로텍션을 재시전합니다."); Spells.CastMagery('Protection'); Misc.Pause(3000)
        if _buff_cfg.get("use_vamp_form", 0) == 1 and not Player.BuffsExist("Vampiric Embrace"):
            Player.HeadMessage(55, "뱀파이어 폼으로 변신합니다."); Spells.CastNecro('Vampiric Embrace'); Misc.Pause(3000)
        
        if Player.Weight >= Player.MaxWeight - 10:
            ProcessFish(); cuttingleather(); Misc.Pause(800)
            
        if Player.Weight >= Player.MaxWeight - 60:
            ReturnHomeAndUnload(); Misc.Pause(2000); continue 

        if CombatRoutine(): continue 
        Demonsumoning(); Misc.Pause(100)
        
        shoestrash(); Misc.Pause(100); sosopen()

        smallfish = Items.FindByID(0x0DD6, -1, Player.Backpack.Serial)
        if smallfish: Items.UseItem(smallfish); Misc.Pause(500)

        has_unlooted = False
        for c in Items.FindAllByID(serpentcorpse, -1, -1, 10, False):
            if c.Serial not in looted_corpses:
                has_unlooted = True; break
                
        if has_unlooted:
            corpsenet(); Misc.Pause(500); opencorpse(); Misc.Pause(1300); lootcorpse()

        if Player.CheckLayer('LeftHand') == False:
            Player.EquipItem(fishingpole); Misc.Pause(1000) 
            
        ThrowFishingNet()
        
        Items.UseItem(fishingpole)
        Target.WaitForTarget(1800)
        Target.TargetExecute(Player.Position.X+3, Player.Position.Y, -1)
        Misc.Pause(1000) 
        Target.Cancel()
        
        action_start_time = time.time()
        
        UpdateStats(); DrawDashboard()
        ProcessFish()
        cuttingleather()
        sosopen()
        trim_working_set()

        while True:
            elapsed_ms = (time.time() - action_start_time) * 1000
            remaining_pause = 6200 - elapsed_ms
            
            if remaining_pause <= 0:
                break
            
            GGO_GumpHandler()  # 체크박스 즉시 반응
                
            if CombatRoutine(): 
                pass 
                
            sleep_time = 500 if remaining_pause > 500 else remaining_pause
            if sleep_time > 0:
                Misc.Pause(int(sleep_time))

        Player.ChatSay('One Forward')
        Misc.Pause(1000) 

        if Journal.Search('stopped sir.') or Journal.Search('can not make it'):
            Journal.Clear()
            Player.ChatSay('back')
            Misc.Pause(3000)
            Player.ChatSay('Turn Around')
            Misc.Pause(2000)
            Player.ChatSay('stop')

        if Journal.Search("The fish don't seem to be biting here."):
            Journal.Clear()
            Player.ChatSay('Forward')
            Misc.Pause(6000)
            Player.ChatSay('stop')
            
            if Journal.Search('stopped sir.'):
                Journal.Clear()
                Player.ChatSay('back')
                Misc.Pause(3000)
                Player.ChatSay('Turn Around')
                Misc.Pause(2000)
                Player.ChatSay('stop')

except Exception as e:
    error_msg = str(e)
    if "Thread was being aborted" in error_msg or "스레드가 중단되었습니다" in error_msg:
        Player.HeadMessage(55, "스크립트가 수동으로 종료되었습니다.")
        pass
    else:
        SendDiscord("🚨 **[긴급 오류 보고]** {0} 캐릭터의 낚시 스크립트가 비정상 종료되었습니다.\n- 에러 내용: {1}".format(Player.Name, error_msg))
        Player.HeadMessage(33, "스크립트 치명적 오류 발생! 디스코드로 알림을 전송했습니다.")
        Misc.Pause(2000) 
    Misc.ScriptStopAll()
