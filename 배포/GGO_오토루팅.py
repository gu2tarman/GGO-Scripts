# Razor Enhanced Python 3.4
# [Official v0.7] - GGO Auto Loot (Dashboard Enhance & Manual Loot)
# ================================================================
# [모드 설명 (Mode Description)]
# 0: 집중 루팅 (550점 이상 명품 + 전설 아티팩트만 루팅)
# 1: 지원템 루팅 (0번 + 운 150이상 / FC1 FCR3 악세서리 포함)
# 2: 임뷰 루팅 (1번 + 무게 2스톤 이하 매직 아이템 갈갈이용)
# 3: 극한 노가다 (3번 + 무게 4스톤 이하 매직 아이템 갈갈이용)
# ----------------------------------------------------------------
# [품질 조정 (Quality Control)]
# THRESHOLD 값을 수정하여 루팅할 아이템의 최소 점수를 변경하세요.
# (기본값: 550 - 높을수록 더 좋은 아이템만 줍습니다.)
THRESHOLD = 550
# ================================================================

SCRIPT_ID = "GGO_AUTO_LOOT"
SCRIPT_NAME = "GGO_오토루팅"
CURRENT_VERSION = "0.7"

import os, sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from GGO_update_check import notify_update_async
    notify_update_async(SCRIPT_ID, SCRIPT_NAME, CURRENT_VERSION)
except Exception:
    pass

import re
import time
import json
import clr
import System.IO
from System.IO import Path, Directory, File, FileInfo
from System import Environment
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
from System.Windows.Forms import Application, Form, Label, RadioButton, CheckBox, Button, MessageBox, FormBorderStyle, GroupBox, FormStartPosition, ListView, View, ColumnHeader, ListViewItem, DialogResult, SelectionMode, ListBox
from System.Drawing import Point, Size, Font, FontStyle, Color
from System.Collections.Generic import List
from System import Byte

AUTO_LOOT_SCRIPT_SETTINGS_DEFAULTS = {
    "threshold": THRESHOLD
}

AUTO_LOOT_SCRIPT_SETTINGS_ORDER = [
    "threshold"
]

AUTO_LOOT_SCRIPT_SETTINGS_GUIDE = """GGO_오토루팅 script_settings.json 설명

이 파일은 오토루팅의 공용 설정 파일입니다.
숫자는 숫자로 입력하세요.
쉼표는 지우지 마세요.

threshold:
  루팅할 장비의 최소 점수입니다.
  기본값은 550이며, 높을수록 더 좋은 아이템만 줍습니다.
"""

try:
    from GGO_user_config import get_script_settings_dir, load_script_settings, ensure_script_settings_guide
    ensure_script_settings_guide(SCRIPT_NAME, AUTO_LOOT_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, AUTO_LOOT_SCRIPT_SETTINGS_DEFAULTS, AUTO_LOOT_SCRIPT_SETTINGS_ORDER)
    THRESHOLD = int(_script_settings.get("threshold", THRESHOLD))
except Exception:
    get_script_settings_dir = None

# ================= [ 시스템 경로 및 스마트 마이그레이션 ] =================
APP_DATA = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
OLD_CONFIG_DIR = Path.Combine(APP_DATA, "GGO_AutoLoot")
LEGACY_CONFIG_DIR = Path.Combine(APP_DATA, "GGO_Project", "AutoLoot")
if get_script_settings_dir:
    CONFIG_DIR = get_script_settings_dir(SCRIPT_NAME)
else:
    CONFIG_DIR = LEGACY_CONFIG_DIR

def _copy_config_dir_if_needed(src_dir, dst_dir):
    try:
        copied = 0
        if Directory.Exists(src_dir):
            if not Directory.Exists(dst_dir):
                Directory.CreateDirectory(dst_dir)
            for f in Directory.GetFiles(src_dir):
                dst_file = Path.Combine(dst_dir, Path.GetFileName(f))
                if not File.Exists(dst_file):
                    File.Copy(f, dst_file)
                    copied += 1
            return copied > 0
    except:
        pass
    return False

if _copy_config_dir_if_needed(LEGACY_CONFIG_DIR, CONFIG_DIR):
    try: Misc.SendMessage("▶ [시스템] GGO_Project AutoLoot 데이터가 GGO_Settings로 이전되었습니다.", 68)
    except: pass
elif _copy_config_dir_if_needed(OLD_CONFIG_DIR, CONFIG_DIR):
    try: Misc.SendMessage("▶ [시스템] 구버전 GGO_AutoLoot 데이터가 GGO_Settings로 이전되었습니다.", 68)
    except: pass

def GetSafeFileName(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name)

CHAR_NAME = GetSafeFileName(Player.Name)
CONFIG_FILE = Path.Combine(CONFIG_DIR, "config_" + CHAR_NAME + ".ini")
CUSTOM_FILE = Path.Combine(CONFIG_DIR, "custom_" + CHAR_NAME + ".txt")
MASTER_CONFIG = Path.Combine(CONFIG_DIR, "config_Master.ini")
MASTER_CUSTOM = Path.Combine(CONFIG_DIR, "custom_Master.txt")
PROFILE_FILE = Path.Combine(CONFIG_DIR, CHAR_NAME + ".json")
MASTER_PROFILE = Path.Combine(CONFIG_DIR, "Master.json")
LEGACY_ARCHIVE_DIR = Path.Combine(CONFIG_DIR, "_legacy_ini_txt")

CURRENT_CONFIG = {
    "loot_mode": 1,      
    "do_gold": True,
    "do_mats": True,
    "do_custom": False,
    "bag_lux": 0,
    "bag_res": 0,
    "bag_jnk": 0,
    "max_score": 0
}

PERMANENT_CUSTOM_LIST = {} 
SESSION_CUSTOM_LIST = {}   

RE_LOOT_DELAY = 10
MAX_CHECK = 1
ACTION_DELAY = 1100

LOOTED_TOTAL = 0
FARMING_SCORE = 0  
current_looted_items = []
loot_stats = {"planet": 0, "zizon": 0, "transcend": 0, "legend": 0, "rare": 0, "normal": 0, "treasure": 0, "legend_arti": 0}
SESSION_RECENT_LOGS = []
MANUAL_LOOT_QUEUE = [] # [New] 수동 루팅 지정 대기열

GUMP_ID = 797979
GUMP_X = 10
GUMP_Y = 10
DETAIL_GUMP_ID = 797980

# ================= [ 가중치 엔진 (Base Logic) ] =================
WAR_W = {"strength bonus": 5, "dexterity bonus": 5, "intelligence bonus": 5, "hit point increase": 5, "mana increase": 5, "stamina increase": 5, "lower mana cost": 9, "swing speed increase": 18, "hit chance increase": 13, "defense chance increase": 9, "damage increase": 4, "swordsmanship": 4, "fencing": 4, "mace fighting": 4, "archery": 4, "throwing": 4, "tactics": 4, "anatomy": 4, "healing": 4, "bushido": 4, "chivalry": 4, "parrying": 4, "resisting spells": 4, "necromancy": 4}
MAG_W = {"strength bonus": 6, "dexterity bonus": 6, "intelligence bonus": 6, "hit point increase": 6, "mana increase": 6, "stamina increase": 6, "lower mana cost": 12, "faster casting": 45, "faster cast recovery": 25, "spell damage increase": 18, "lower reagent cost": 3, "mana regeneration": 15, "magery": 5, "evaluating intelligence": 5, "meditation": 5, "inscription": 5, "resisting spells": 5, "spirit speak": 5, "necromancy": 5, "mysticism": 5, "spellweaving": 5, "taming": 5, "animal lore": 5, "veterinary": 5, "musicianship": 5, "provocation": 5, "peacemaking": 5, "discordance": 5, "wrestling": 5}
WAR_MAX = {"strength bonus": 10, "dexterity bonus": 10, "intelligence bonus": 10, "hit point increase": 5, "mana increase": 5, "stamina increase": 5, "lower mana cost": 10, "swing speed increase": 10, "hit chance increase": 20, "defense chance increase": 20, "damage increase": 35, "swordsmanship": 20, "fencing": 20, "mace fighting": 20, "archery": 20, "throwing": 20, "tactics": 20, "anatomy": 20, "healing": 20, "bushido": 20, "chivalry": 20, "parrying": 20, "resisting spells": 20, "necromancy": 20}
MAG_MAX = {"strength bonus": 10, "weighted dexterity bonus": 10, "intelligence bonus": 10, "hit point increase": 5, "mana increase": 5, "stamina increase": 5, "lower mana cost": 10, "faster casting": 1, "faster cast recovery": 3, "spell damage increase": 18, "lower reagent cost": 25, "mana regeneration": 4, "magery": 20, "evaluating intelligence": 20, "meditation": 20, "inscription": 20, "resisting spells": 20, "spirit speak": 20, "necromancy": 20, "mysticism": 20, "spellweaving": 20, "taming": 20, "animal lore": 20, "veterinary": 20, "musicianship": 20, "provocation": 20, "peacemaking": 20, "discordance": 20, "wrestling": 20}

LOOT_GOLD_ID = [0x0EED] 
IMBUING_MATS = [
    0x2DB1, 0x2DB2, 0x2DB3,
    0x5721, 0x5730, 0x572D, 0x5741, 0x572A, 0x571C, 0x5722, 0x5740, 0x573C,
    0x5719, 0x5718, 0x5720, 0x5726, 0x573E, 0x5734, 0x573A,
    0x5736, 0x571D, 0x5732, 0x5738, 0x5728,
    0x2D83, 0x2D84, 0x2D85, 0x2D86, 0x2D87, 0x2D88, 0x2D89,
    0x2D8A, 0x2D8B, 0x2D8C, 0x2D8D, 0x2D8E, 0x2D8F, 0x2D90, 0x2D91, 0x2D92, 0x2D93
]

FORBIDDEN = [0x2DAD, 0x13B1, 0x13B2, 0x26BD, 0x2D32, 0x2D33, 0x0F47, 0x0F49, 0x0F4B, 0x0F45, 0x13FB, 0x1443, 0x13B9, 0x1441]

last_check_time, check_count = {}, {}

# ================= [ 저장/로드 및 프로필 함수 ] =================
def _default_profile():
    return {
        "config": dict(CURRENT_CONFIG),
        "custom_items": {}
    }

def _read_json_file(path, default_value=None):
    try:
        if File.Exists(path):
            raw = File.ReadAllText(path)
            if raw:
                return json.loads(raw)
    except:
        pass
    return default_value

def _write_json_file(path, data):
    if not Directory.Exists(CONFIG_DIR):
        Directory.CreateDirectory(CONFIG_DIR)
    File.WriteAllText(path, json.dumps(data, indent=4, ensure_ascii=False))

def _parse_ini_config(path):
    data = {}
    try:
        if File.Exists(path):
            lines = File.ReadAllText(path).split('\n')
            for line in lines:
                parts = line.split(':')
                if len(parts) < 2:
                    continue
                key = parts[0].strip()
                val = parts[1].strip()
                if key in ["loot_mode", "bag_lux", "bag_res", "bag_jnk", "max_score"]:
                    data[key] = int(val)
                elif key in ["do_gold", "do_mats", "do_custom"]:
                    data[key] = (val == "True")
    except:
        pass
    return data

def _parse_custom_txt(path):
    data = {}
    try:
        if File.Exists(path):
            lines = File.ReadAllText(path).split('\n')
            for line in lines:
                if ":" in line:
                    parts = line.split(':')
                    try:
                        data[int(parts[0])] = parts[1].strip()
                    except:
                        pass
    except:
        pass
    return data

def _normalize_custom_items(value):
    result = {}
    try:
        for k, v in value.items():
            result[int(k)] = str(v)
    except:
        pass
    return result

def _load_profile(path):
    profile = _read_json_file(path, None)
    if not isinstance(profile, dict):
        return None
    return {
        "config": profile.get("config", {}),
        "custom_items": _normalize_custom_items(profile.get("custom_items", {}))
    }

def _current_profile():
    return {
        "config": dict(CURRENT_CONFIG),
        "custom_items": dict(PERMANENT_CUSTOM_LIST)
    }

def _safe_profile_name(name):
    return re.sub(r'[\\/:*?"<>|]', '_', str(name or "Unknown"))

def _write_migrated_profile(profile_name, config_data, custom_data):
    profile_name = _safe_profile_name(profile_name)
    profile_path = Path.Combine(CONFIG_DIR, profile_name + ".json")
    if File.Exists(profile_path):
        return False
    profile = _default_profile()
    if config_data:
        profile["config"].update(config_data)
    if custom_data:
        profile["custom_items"] = custom_data
    if config_data or custom_data:
        _write_json_file(profile_path, profile)
        return True
    return False

def _archive_legacy_file(path):
    try:
        if not File.Exists(path):
            return
        if not Directory.Exists(LEGACY_ARCHIVE_DIR):
            Directory.CreateDirectory(LEGACY_ARCHIVE_DIR)
        dst = Path.Combine(LEGACY_ARCHIVE_DIR, Path.GetFileName(path))
        if File.Exists(dst):
            File.Delete(path)
        else:
            File.Move(path, dst)
    except:
        pass

def _migrate_all_legacy_profiles():
    try:
        if not Directory.Exists(CONFIG_DIR):
            return
        names = {}
        for f in Directory.GetFiles(CONFIG_DIR, "config_*.ini"):
            names[Path.GetFileNameWithoutExtension(f).replace("config_", "")] = True
        for f in Directory.GetFiles(CONFIG_DIR, "custom_*.txt"):
            names[Path.GetFileNameWithoutExtension(f).replace("custom_", "")] = True

        migrated = 0
        for name in names.keys():
            cfg = _parse_ini_config(Path.Combine(CONFIG_DIR, "config_" + name + ".ini"))
            custom = _parse_custom_txt(Path.Combine(CONFIG_DIR, "custom_" + name + ".txt"))
            target_name = "Master" if name == "Master" else name
            if _write_migrated_profile(target_name, cfg, custom):
                migrated += 1

        for f in Directory.GetFiles(CONFIG_DIR, "config_*.ini"):
            _archive_legacy_file(f)
        for f in Directory.GetFiles(CONFIG_DIR, "custom_*.txt"):
            _archive_legacy_file(f)

        if migrated > 0:
            try: Misc.SendMessage("▶ [시스템] 오토루팅 기존 ini/txt 프로필 " + str(migrated) + "개를 JSON으로 정리했습니다.", 68)
            except: pass
    except:
        pass

def _migrate_legacy_profile_if_needed():
    _migrate_all_legacy_profiles()
    if File.Exists(PROFILE_FILE):
        return
    profile = _default_profile()
    legacy_config = _parse_ini_config(CONFIG_FILE)
    legacy_custom = _parse_custom_txt(CUSTOM_FILE)
    if not legacy_config and File.Exists(MASTER_CONFIG):
        legacy_config = _parse_ini_config(MASTER_CONFIG)
    if not legacy_custom and File.Exists(MASTER_CUSTOM):
        legacy_custom = _parse_custom_txt(MASTER_CUSTOM)
    if legacy_config:
        profile["config"].update(legacy_config)
    if legacy_custom:
        profile["custom_items"] = legacy_custom
    if legacy_config or legacy_custom:
        _write_json_file(PROFILE_FILE, profile)
        try: Misc.SendMessage("▶ [시스템] 오토루팅 설정이 JSON으로 이전되었습니다.", 68)
        except: pass

def CheckInheritance():
    if not File.Exists(PROFILE_FILE) and File.Exists(MASTER_PROFILE):
        try: File.Copy(MASTER_PROFILE, PROFILE_FILE); Misc.SendMessage("▶ [시스템] Master 설정을 상속받았습니다.", 68)
        except: pass

def LoadConfig():
    try:
        if not Directory.Exists(CONFIG_DIR): Directory.CreateDirectory(CONFIG_DIR)
        _migrate_legacy_profile_if_needed()
        CheckInheritance()
        profile = _load_profile(PROFILE_FILE)
        if profile:
            CURRENT_CONFIG.update(profile.get("config", {}))
            PERMANENT_CUSTOM_LIST.clear()
            PERMANENT_CUSTOM_LIST.update(profile.get("custom_items", {}))
            count = len(PERMANENT_CUSTOM_LIST)
            if count > 0: Misc.SendMessage("▶ [" + CHAR_NAME + "] 커스텀 아이템 " + str(count) + "종 로드됨", 68)
            SaveConfig()
    except Exception as e:
        Misc.SendMessage("▶ 설정 로드 실패: " + str(e), 33)

def SaveConfig():
    try:
        _write_json_file(PROFILE_FILE, _current_profile())
    except: pass

def SaveCustomList():
    try:
        SaveConfig()
    except: pass

# ================= [ UI 클래스 ] =================
class ProfileSelectorForm(Form):
    def __init__(self):
        self.Text = "프로필 선택 (Select Profile)"
        self.Size = Size(300, 350)
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        lbl = Label(); lbl.Text = "병합할 프로필을 선택하세요:"; lbl.Location = Point(10, 10); lbl.AutoSize = True; self.Controls.Add(lbl)
        self.lstFiles = ListBox(); self.lstFiles.Location = Point(10, 35); self.lstFiles.Size = Size(265, 230); self.Controls.Add(self.lstFiles)
        files = Directory.GetFiles(CONFIG_DIR, "*.json")
        for f in files:
            fname = Path.GetFileName(f)
            if fname not in [CHAR_NAME + ".json", "Master.json", "script_settings.json"]:
                self.lstFiles.Items.Add(fname.replace(".json", ""))
        btnLoad = Button(); btnLoad.Text = "병합 (Merge)"; btnLoad.Location = Point(10, 275); btnLoad.Size = Size(125, 30); btnLoad.DialogResult = DialogResult.OK; self.Controls.Add(btnLoad)
        btnCancel = Button(); btnCancel.Text = "취소"; btnCancel.Location = Point(150, 275); btnCancel.Size = Size(125, 30); btnCancel.DialogResult = DialogResult.Cancel; self.Controls.Add(btnCancel)
    def GetSelectedProfile(self): return self.lstFiles.SelectedItem if self.lstFiles.SelectedItem else None

class CustomManagerForm(Form):
    def __init__(self):
        self.Text = "커스텀 아이템 관리 (Manager) - " + CHAR_NAME
        self.Size = Size(400, 520) 
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        lbl = Label(); lbl.Text = "관리 목록 (Blue: Session / Black: Perm)"; lbl.Location = Point(20, 15); lbl.AutoSize = True; lbl.Font = Font("Segoe UI", 10, FontStyle.Bold); self.Controls.Add(lbl)
        self.lv = ListView(); self.lv.Location = Point(20, 40); self.lv.Size = Size(345, 230); self.lv.View = View.Details; self.lv.GridLines = True; self.lv.FullRowSelect = True; self.lv.MultiSelect = False
        self.lv.Columns.Add("ID", 80); self.lv.Columns.Add("Item Name", 240); self.UpdateList(); self.Controls.Add(self.lv)
        btnAddPerm = Button(); btnAddPerm.Text = "영구 추가 (Add)"; btnAddPerm.Location = Point(20, 280); btnAddPerm.Size = Size(170, 35); btnAddPerm.BackColor = Color.LightSkyBlue; btnAddPerm.Click += self.BtnAddPerm_Click; self.Controls.Add(btnAddPerm)
        btnAddSess = Button(); btnAddSess.Text = "1회성 추가 (Sess)"; btnAddSess.Location = Point(200, 280); btnAddSess.Size = Size(165, 35); btnAddSess.BackColor = Color.LightYellow; btnAddSess.Click += self.BtnAddSess_Click; self.Controls.Add(btnAddSess)
        btnDel = Button(); btnDel.Text = "선택 삭제 (Delete Selected)"; btnDel.Location = Point(20, 320); btnDel.Size = Size(345, 30); btnDel.ForeColor = Color.Red; btnDel.Click += self.BtnDel_Click; self.Controls.Add(btnDel)
        grpProf = GroupBox(); grpProf.Text = " 프로필 관리 (Profile) "; grpProf.Location = Point(20, 360); grpProf.Size = Size(345, 80); self.Controls.Add(grpProf)
        btnSaveMaster = Button(); btnSaveMaster.Text = "현재 설정을 Master로 저장"; btnSaveMaster.Location = Point(15, 20); btnSaveMaster.Size = Size(315, 25); btnSaveMaster.Click += self.BtnSaveMaster_Click; grpProf.Controls.Add(btnSaveMaster)
        btnMerge = Button(); btnMerge.Text = "다른 프로필 병합 (Merge)"; btnMerge.Location = Point(15, 50); btnMerge.Size = Size(315, 25); btnMerge.Click += self.BtnMerge_Click; grpProf.Controls.Add(btnMerge)
        btnClose = Button(); btnClose.Text = "닫 기"; btnClose.Location = Point(140, 450); btnClose.Size = Size(100, 25); btnClose.Click += self.BtnClose_Click; self.Controls.Add(btnClose)
    def UpdateList(self):
        self.lv.Items.Clear()
        for k, v in SESSION_CUSTOM_LIST.items():
            lvi = ListViewItem(str(k)); lvi.SubItems.Add(v + " (Session)"); lvi.ForeColor = Color.Blue; self.lv.Items.Add(lvi)
        for k, v in PERMANENT_CUSTOM_LIST.items():
            lvi = ListViewItem(str(k)); lvi.SubItems.Add(v); lvi.ForeColor = Color.Black; self.lv.Items.Add(lvi)
    def BtnAddPerm_Click(self, sender, args):
        self.TopMost = False
        Misc.SendMessage("▶ [영구 추가] 아이템을 연속해서 선택하세요. (ESC: 종료)", 68)
        while True:
            t = Target.PromptTarget("Permanent Add (ESC to Stop)")
            if t == -1: break
            try:
                item = Items.FindBySerial(t)
                if item:
                    if item.ItemID not in PERMANENT_CUSTOM_LIST:
                        PERMANENT_CUSTOM_LIST[item.ItemID] = str(item.Name); SaveCustomList(); Misc.SendMessage("▶ 영구 등록: " + item.Name, 68); self.UpdateList()
                    else: Misc.SendMessage("▶ 이미 등록됨.", 33)
            except: pass
        self.TopMost = True
    def BtnAddSess_Click(self, sender, args):
        self.TopMost = False
        Misc.SendMessage("▶ [1회성 추가] 아이템을 연속해서 선택하세요. (ESC: 종료)", 68)
        while True:
            t = Target.PromptTarget("Session Add (ESC to Stop)")
            if t == -1: break
            try:
                item = Items.FindBySerial(t)
                if item:
                    if item.ItemID not in SESSION_CUSTOM_LIST:
                        SESSION_CUSTOM_LIST[item.ItemID] = str(item.Name); Misc.SendMessage("▶ 1회성 등록: " + item.Name, 68); self.UpdateList()
                    else: Misc.SendMessage("▶ 이미 등록됨.", 33)
            except: pass
        self.TopMost = True
    def BtnDel_Click(self, sender, args):
        if self.lv.SelectedItems.Count > 0:
            sel_id = int(self.lv.SelectedItems[0].Text)
            if sel_id in SESSION_CUSTOM_LIST: del SESSION_CUSTOM_LIST[sel_id]
            elif sel_id in PERMANENT_CUSTOM_LIST: del PERMANENT_CUSTOM_LIST[sel_id]; SaveCustomList()
            self.UpdateList(); Misc.SendMessage("▶ 삭제 완료.", 33)
    def BtnSaveMaster_Click(self, sender, args):
        try:
            master = _current_profile()
            master["config"]["bag_lux"] = 0
            master["config"]["bag_res"] = 0
            master["config"]["bag_jnk"] = 0
            master["config"]["max_score"] = 0
            _write_json_file(MASTER_PROFILE, master)
            MessageBox.Show("현재 설정과 리스트가 Master로 저장되었습니다.\n신규 캐릭터 생성 시 이 설정이 적용됩니다.", "Master Saved")
        except Exception as e: MessageBox.Show("Error: " + str(e))
    def BtnMerge_Click(self, sender, args):
        selForm = ProfileSelectorForm()
        if selForm.ShowDialog() == DialogResult.OK:
            target = selForm.GetSelectedProfile()
            if target:
                targetFile = Path.Combine(CONFIG_DIR, target + ".json")
                profile = _load_profile(targetFile)
                if profile:
                    added = 0
                    for pid, pname in profile.get("custom_items", {}).items():
                        if pid not in PERMANENT_CUSTOM_LIST:
                            PERMANENT_CUSTOM_LIST[pid] = pname
                            added += 1
                    if added > 0: SaveCustomList(); self.UpdateList(); MessageBox.Show(str(added) + "개의 새로운 아이템을 병합했습니다.", "Merge Complete")
                    else: MessageBox.Show("추가할 새로운 아이템이 없습니다. (중복)", "Merge Result")
        selForm.Dispose()
    def BtnClose_Click(self, sender, args): self.Close()

class SetupForm(Form):
    def __init__(self):
        self.Text = "GGO Auto Loot v0.7 - " + CHAR_NAME
        self.Size = Size(350, 480)
        self.StartPosition = FormStartPosition.CenterScreen 
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        lbl = Label(); lbl.Text = "GGO Project: Auto Loot"; lbl.Location = Point(20, 20); lbl.AutoSize = True; lbl.Font = Font("Segoe UI", 14, FontStyle.Bold); lbl.ForeColor = Color.DarkBlue; self.Controls.Add(lbl)
        grpMode = GroupBox(); grpMode.Text = " 루팅 모드 "; grpMode.Location = Point(20, 60); grpMode.Size = Size(290, 150); self.Controls.Add(grpMode)
        self.rdo0 = RadioButton(); self.rdo0.Text = "0: 집중 루팅"; self.rdo0.Location = Point(15, 25); self.rdo0.AutoSize = True; grpMode.Controls.Add(self.rdo0)
        self.rdo1 = RadioButton(); self.rdo1.Text = "1: 지원템 루팅"; self.rdo1.Location = Point(15, 55); self.rdo1.AutoSize = True; grpMode.Controls.Add(self.rdo1)
        self.rdo2 = RadioButton(); self.rdo2.Text = "2: 임뷰 루팅"; self.rdo2.Location = Point(15, 85); self.rdo2.AutoSize = True; grpMode.Controls.Add(self.rdo2)
        self.rdo3 = RadioButton(); self.rdo3.Text = "3: 극한 노가다"; self.rdo3.Location = Point(15, 115); self.rdo3.AutoSize = True; grpMode.Controls.Add(self.rdo3)
        grpOpt = GroupBox(); grpOpt.Text = " 루팅 대상 설정 "; grpOpt.Location = Point(20, 220); grpOpt.Size = Size(290, 110); self.Controls.Add(grpOpt)
        self.chkGold = CheckBox(); self.chkGold.Text = "골드 (Gold)"; self.chkGold.Location = Point(15, 25); self.chkGold.AutoSize = True; grpOpt.Controls.Add(self.chkGold)
        self.chkMats = CheckBox(); self.chkMats.Text = "임뷰 재료 (Materials)"; self.chkMats.Location = Point(15, 50); self.chkMats.AutoSize = True; grpOpt.Controls.Add(self.chkMats)
        self.chkCustom = CheckBox(); self.chkCustom.Text = "커스텀 아이템 (Custom)"; self.chkCustom.Location = Point(15, 75); self.chkCustom.AutoSize = True; self.chkCustom.ForeColor = Color.DarkRed; grpOpt.Controls.Add(self.chkCustom)
        btnStart = Button(); btnStart.Text = "사냥 시작 (Start)"; btnStart.Location = Point(60, 350); btnStart.Size = Size(200, 40); btnStart.BackColor = Color.LightGreen; btnStart.Click += self.BtnStart_Click; self.Controls.Add(btnStart)
        btnSettings = Button(); btnSettings.Text = "커스텀 설정 (Manager)"; btnSettings.Location = Point(20, 400); btnSettings.Size = Size(150, 30); btnSettings.Click += self.BtnSettings_Click; self.Controls.Add(btnSettings)
        btnResetBag = Button(); btnResetBag.Text = "가방 초기화"; btnResetBag.Location = Point(180, 400); btnResetBag.Size = Size(130, 30); btnResetBag.ForeColor = Color.Red; btnResetBag.Click += self.BtnResetBag_Click; self.Controls.Add(btnResetBag)
        mode = CURRENT_CONFIG["loot_mode"]
        if mode == 0: self.rdo0.Checked = True
        elif mode == 1: self.rdo1.Checked = True
        elif mode == 2: self.rdo2.Checked = True
        elif mode == 3: self.rdo3.Checked = True
        self.chkGold.Checked = CURRENT_CONFIG["do_gold"]
        self.chkMats.Checked = CURRENT_CONFIG["do_mats"]
        self.chkCustom.Checked = CURRENT_CONFIG["do_custom"]
    def BtnStart_Click(self, sender, args):
        global CURRENT_CONFIG
        if self.rdo0.Checked: CURRENT_CONFIG["loot_mode"] = 0
        elif self.rdo1.Checked: CURRENT_CONFIG["loot_mode"] = 1
        elif self.rdo2.Checked: CURRENT_CONFIG["loot_mode"] = 2
        elif self.rdo3.Checked: CURRENT_CONFIG["loot_mode"] = 3
        CURRENT_CONFIG["do_gold"] = self.chkGold.Checked
        CURRENT_CONFIG["do_mats"] = self.chkMats.Checked
        CURRENT_CONFIG["do_custom"] = self.chkCustom.Checked
        SaveConfig() 
        self.Close()
    def BtnSettings_Click(self, sender, args): f = CustomManagerForm(); f.ShowDialog()
    def BtnResetBag_Click(self, sender, args):
        global CURRENT_CONFIG
        CURRENT_CONFIG["bag_lux"] = 0; CURRENT_CONFIG["bag_res"] = 0; CURRENT_CONFIG["bag_jnk"] = 0; SaveConfig(); Misc.SendMessage("▶ [설정] 가방 설정이 초기화되었습니다.", 33)

def GetGradeInfo(score):
    if score >= 1050: return "[★★★★★★] 행성파괴급", 33, "planet"
    elif score >= 950: return "[★★★★★] Zi존급", 1161, "zizon"
    elif score >= 850: return "[★★★★] 초월급", 1159, "transcend"
    elif score >= 750: return "[★★★] 신화급", 53, "legend"
    elif score >= 650: return "[★★] 명품급", 0x44, "rare"
    else: return "[★] 득템", 68, "normal"

# ================= [ 대시보드 및 조작 기능 ] =================
def UpdateGump():
    try:
        gd = Gumps.CreateGump(movable=True)
        Gumps.AddPage(gd, 0)
        main_logs = SESSION_RECENT_LOGS[:2]
        bg_h = 45 + (max(1, len(main_logs)) * 45) + 60 
        Gumps.AddBackground(gd, 0, 0, 310, bg_h, 30546)
        Gumps.AddAlphaRegion(gd, 0, 0, 310, bg_h)
        Gumps.AddLabel(gd, 15, 15, 68, "GGO Auto Loot v0.7")
        
        Gumps.AddLabel(gd, 160, 15, 55, "Tot: " + str(LOOTED_TOTAL))
        
        Gumps.AddButton(gd, 240, 15, 4005, 4006, 101, 1, 0)
        Gumps.AddLabel(gd, 275, 15, 1152, "Perm")
        Gumps.AddButton(gd, 240, 35, 4005, 4006, 102, 1, 0)
        Gumps.AddLabel(gd, 275, 35, 1271, "Sess")
        Gumps.AddButton(gd, 240, 55, 4011, 4012, 103, 1, 0)
        Gumps.AddLabel(gd, 275, 55, 945, "Det")
        
        # [New] 수동 루팅(Loot) 버튼 추가
        Gumps.AddButton(gd, 240, 75, 4005, 4006, 104, 1, 0)
        Gumps.AddLabel(gd, 275, 75, 53, "Loot")

        y = 45
        if not main_logs: Gumps.AddLabel(gd, 15, y, 945, "득템 대기중..")
        else:
            for log in main_logs:
                disp_name = log['name'][:18] + "..." if len(log['name']) > 18 else log['name']
                Gumps.AddLabel(gd, 15, y, log['color'], log['grade_str'])
                Gumps.AddLabel(gd, 15, y + 20, 999, disp_name + " (" + str(log['score']) + "pts)")
                y += 45
                
        global FARMING_SCORE
        current_level = (FARMING_SCORE // 1000) + 1
        current_exp = FARMING_SCORE % 1000
        percent = current_exp / 1000.0
        
        bar_y = bg_h - 25
        Gumps.AddLabel(gd, 15, bar_y - 20, 53, "Lv." + str(current_level) + " 파밍 레벨 (" + str(current_exp) + "/1000) Max: " + str(CURRENT_CONFIG["max_score"]) + "pts")
        Gumps.AddBackground(gd, 15, bar_y, 280, 12, 9350)
        bar_w = int(2.8 * (percent * 100))
        if bar_w > 5:
            Gumps.AddBackground(gd, 15, bar_y, bar_w, 12, 9300)

        Gumps.SendGump(GUMP_ID, Player.Serial, GUMP_X, GUMP_Y, gd.gumpDefinition, gd.gumpStrings)
    except: pass

def ShowDetailGump():
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 450, 480, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 450, 480)
    Gumps.AddLabel(gd, 15, 15, 53, "최근 획득 장비 옵션 판정 상세 (THRESHOLD 통과)")
    Gumps.AddButton(gd, 410, 15, 4005, 4006, 0, 1, 0)
    
    y = 45
    gear_logs = [l for l in SESSION_RECENT_LOGS if l.get('is_gear')][:3]
    
    if not gear_logs:
        Gumps.AddLabel(gd, 15, y, 945, "최근 획득한 장비 내역이 없습니다.")
    else:
        for log in gear_logs:
            Gumps.AddLabel(gd, 15, y, log['color'], log['name'] + " (" + str(log['score']) + "pts)")
            y += 20
            if 'details' in log and log['details']:
                for d in log['details']:
                    Gumps.AddLabel(gd, 25, y, 945, d)
                    y += 18
            y += 10
            
    Gumps.SendGump(DETAIL_GUMP_ID, Player.Serial, GUMP_X + 320, GUMP_Y, gd.gumpDefinition, gd.gumpStrings)

def CheckDashboardActions():
    gd = Gumps.GetGumpData(GUMP_ID)
    if gd and gd.buttonid > 0:
        btn = gd.buttonid
        Gumps.SendAction(GUMP_ID, 0)
        
        if btn == 101 or btn == 102: 
            is_perm = (btn == 101)
            list_name = "영구 목록" if is_perm else "1회성 목록"
            Target.Cancel()
            Player.HeadMessage(68, "[{0}] 추가할 아이템을 타겟팅하세요 (ESC 취소)".format(list_name))
            t = Target.PromptTarget("Add Quick Item")
            if t > -1:
                item = Items.FindBySerial(t)
                if item:
                    if is_perm:
                        if item.ItemID not in PERMANENT_CUSTOM_LIST:
                            PERMANENT_CUSTOM_LIST[item.ItemID] = str(item.Name)
                            SaveCustomList()
                            Player.HeadMessage(68, "영구 등록됨: " + str(item.Name))
                        else: Player.HeadMessage(33, "이미 등록됨.")
                    else:
                        if item.ItemID not in SESSION_CUSTOM_LIST:
                            SESSION_CUSTOM_LIST[item.ItemID] = str(item.Name)
                            Player.HeadMessage(68, "1회성 등록됨: " + str(item.Name))
                        else: Player.HeadMessage(33, "이미 등록됨.")
            UpdateGump()
        elif btn == 103: 
            ShowDetailGump()
            UpdateGump()
        elif btn == 104: # [New] 수동 타겟 루팅
            Target.Cancel()
            Player.HeadMessage(68, "[수동 루팅] 상자나 시체를 타겟팅하세요 (ESC 취소)")
            t = Target.PromptTarget("Select Container to Loot")
            if t > -1:
                MANUAL_LOOT_QUEUE.append(t)
                if t in check_count: del check_count[t] # 한 번 털었던 것도 다시 검사하도록 초기화
                if t in last_check_time: del last_check_time[t]
                Items.UseItem(t) # 즉시 더블클릭하여 서버에 내용물 요청
                Misc.Pause(400)
                Player.HeadMessage(53, "대상을 열고 루팅을 시도합니다.")
            UpdateGump()

# ================= [ 메인 로직 ] =================
LoadConfig()
form = SetupForm()
form.ShowDialog()

Misc.SendMessage("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", 68)
Misc.SendMessage(" 🔥 GGO Auto Loot Official v0.7 🔥 ", 68)
Misc.SendMessage("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", 68)

LOOT_MODE = CURRENT_CONFIG["loot_mode"]
DO_GOLD = CURRENT_CONFIG["do_gold"]
DO_MATS = CURRENT_CONFIG["do_mats"]
DO_CUSTOM = CURRENT_CONFIG["do_custom"]

mode_info = ["0: 집중 루팅", "1: 지원템 루팅", "2: 임뷰 루팅", "3: 극한 노가다"]
Misc.SendMessage("▶ 접속 캐릭터: [" + CHAR_NAME + "]", 1161)
Misc.SendMessage("▶ 활성화 모드: " + mode_info[LOOT_MODE], 170)
Misc.SendMessage("▶ 골드: " + str(DO_GOLD) + " / 임뷰재료: " + str(DO_MATS) + " / 커스텀: " + str(DO_CUSTOM), 68)

Misc.SendMessage("▶ [v0.7 Update] 수동 타겟 루팅 기능 추가!", 1161)
Misc.SendMessage("   - 대시보드의 [Loot] 버튼으로 트레져 상자나 남겨진 시체를 즉시 루팅할 수 있습니다.", 68)
Misc.SendMessage("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", 68)

max_s = CURRENT_CONFIG["max_score"]
max_lv = (max_s // 1000) + 1
Player.HeadMessage(53, "★ [최고 기록: Lv." + str(max_lv) + " (" + str(max_s) + "pts)] 어제의 나를 뛰어넘어 봅시다! ★")

def GetBag(bag_key, prompt_msg):
    bag_serial = CURRENT_CONFIG[bag_key]
    valid = False
    if bag_serial > 0:
        item = Items.FindBySerial(bag_serial)
        if item and Player.Backpack:
            if item.Serial == Player.Backpack.Serial or item.IsChildOf(Player.Backpack): valid = True
            if valid: Misc.SendMessage("▶ 저장된 가방 사용: " + item.Name, 68)
    if not valid:
        Target.Cancel()
        new_serial = Target.PromptTarget(prompt_msg)
        if new_serial > -1:
            CURRENT_CONFIG[bag_key] = new_serial
            SaveConfig()
            return new_serial
        return 0
    return bag_serial

lux_bag = GetBag("bag_lux", "Select Luxury Bag (장비)")
if lux_bag:
    res_bag = lux_bag
    jnk_bag = lux_bag
    if DO_MATS or DO_CUSTOM or DO_GOLD:
        rb = GetBag("bag_res", "Select Resource Bag (자원/재료/커스텀)")
        if rb > 0: res_bag = rb
    if LOOT_MODE >= 2:
        jb = GetBag("bag_jnk", "Select Junk Bag (갈갈이)")
        if jb > 0: jnk_bag = jb

    UpdateGump()

    try:
        while True:
            CheckDashboardActions() 
            
            f = Items.Filter(); f.Graphics.Add(0x2006); f.RangeMax = 2
            # [Update] Filter 결과를 Python List로 치환하고, 수동 타겟을 병합
            base_corpses = Items.ApplyFilter(f)
            corpses = list(base_corpses)
            
            if MANUAL_LOOT_QUEUE:
                for mt in MANUAL_LOOT_QUEUE:
                    m_item = Items.FindBySerial(mt)
                    if m_item: corpses.append(m_item)
                MANUAL_LOOT_QUEUE.clear()
                
            curr_time = time.time()

            for corpse in corpses:
                s = corpse.Serial
                if s in check_count and check_count[s] >= MAX_CHECK: continue
                if s in last_check_time and curr_time - last_check_time[s] < RE_LOOT_DELAY: continue

                if current_looted_items:
                    for old_item_serial in current_looted_items: Items.SetColor(old_item_serial, 0)
                    current_looted_items = []

                check_count[s] = check_count.get(s, 0) + 1
                last_check_time[s] = time.time()

                if not corpse.IsContainer: Items.UseItem(s); Misc.Pause(600)
                Items.WaitForContents(corpse, 1000)
                items = corpse.Contains

                is_heavy = Player.Weight >= (Player.MaxWeight * 0.8)
                if is_heavy: Player.HeadMessage(33, "!!! 무게 초과 (80% 이상) / 잡템 수집 중단 !!!")

                if items:
                    for item in items:
                        CheckDashboardActions() 
                        
                        if not item or item.ItemID in FORBIDDEN: continue
                        Items.WaitForProps(item.Serial, 800)
                        name = str(item.Name).upper()
                        
                        def CheckBagLimit(itm_weight):
                            w_ok = (Player.Weight + itm_weight) <= (Player.MaxWeight - 5)
                            c_ok = True
                            if Player.Backpack: c_ok = len(Player.Backpack.Contains) < 124
                            return w_ok, c_ok

                        weapon_names = ["AXE", "HATCHET", "SWORD", "BLADE", "HAMMER", "STAFF", "MACE", "DAGGER", "BOW", "HALBERD", "SPEAR", "KNIFE", "SCEPTER", "CLEAVER", "CLUB", "MAUL", "LANCE", "PIKE", "BOKUTO", "KATANA", "KRYSS", "YUMI", "CROSSBOW", "BOOMERANG", "CYCLONE", "GLAIVE", "SAI", "TEKAGI", "TESSEN", "DAISHO", "NO-DACHI", "WAKIZASHI", "PICKAXE", "BUTCHER", "SKINNING", "SCYTHE", "SCIMITAR", "SICKLE", "KATAR", "MACHETE", "HARVESTER", "BARDICHE", "WAR FORK", "SHEPHERD", "CROOK"]
                        if any(wn in name for wn in weapon_names) and not any(ex in name for ex in ["BOOK", "TALISMAN", "TOTEM"]): continue
                        
                        is_target = False
                        if DO_GOLD and item.ItemID in LOOT_GOLD_ID: is_target = True
                        elif DO_MATS and item.ItemID in IMBUING_MATS: is_target = True
                        elif DO_CUSTOM and (item.ItemID in PERMANENT_CUSTOM_LIST or item.ItemID in SESSION_CUSTOM_LIST): is_target = True

                        if is_target:
                            w_ok, c_ok = CheckBagLimit(item.Weight)
                            if w_ok and c_ok:
                                Items.Move(item.Serial, res_bag, 0); Misc.Pause(ACTION_DELAY); continue
                            else:
                                Player.HeadMessage(33, "Skip: " + item.Name + ("(무게)" if not w_ok else "(개수)"))
                                continue

                        if item.ItemID == 0x14EC:
                            props = Items.GetProperties(item.Serial, False)
                            if props:
                                txt = " ".join([str(p) for p in props]).lower()
                                lvl = 0
                                if any(kw in txt for kw in ["사악한", "ingenious"]): lvl = 6
                                elif any(kw in txt for kw in ["악랄한", "diabolical"]): lvl = 7
                                
                                if lvl > 0:
                                    w_ok, c_ok = CheckBagLimit(item.Weight)
                                    if w_ok and c_ok:
                                        Items.Move(item.Serial, lux_bag, 0); Misc.Pause(150); Items.SetColor(item.Serial, 33)
                                        current_looted_items.append(item.Serial)
                                        map_name = str(lvl) + "Lv 트레져 맵"
                                        Player.HeadMessage(33, "!!! [" + map_name + " 획득] !!!")
                                        LOOTED_TOTAL += 1
                                        FARMING_SCORE += 300
                                        if FARMING_SCORE > CURRENT_CONFIG["max_score"]: CURRENT_CONFIG["max_score"] = FARMING_SCORE
                                        loot_stats["treasure"] += 1
                                        SESSION_RECENT_LOGS.insert(0, {'grade_str': "[■ 보물지도]", 'name': map_name, 'score': 300, 'color': 33, 'is_gear': False})
                                        if len(SESSION_RECENT_LOGS) > 10: SESSION_RECENT_LOGS.pop()
                                        UpdateGump()
                                        Misc.Pause(ACTION_DELAY - 150)
                                    else: Player.HeadMessage(33, "!!! [LIMIT] 보물지도 !!!")
                                    continue

                        props = Items.GetProperties(item.Serial, False)
                        if not props: continue
                        txt = " ".join([str(p) for p in props]).lower()

                        w_base, m_base = 0, 0
                        w_bonus, m_bonus = 0, 0
                        w_det, m_det = [], []
                        luck_val, has_fc1, has_fcr3 = 0, False, False

                        for wk, wv in WAR_W.items():
                            m = re.search(re.escape(wk) + r"[:\s\+]*(\d+)", txt)
                            if m:
                                v = int(m.group(1)); p = v * wv; mark = ""; temp_bonus = 0
                                if v >= WAR_MAX.get(wk, 999): temp_bonus = 50; mark = "☆"
                                w_base += p; w_bonus += temp_bonus
                                w_det.append(wk.upper() + " (" + str(v) + ") -> " + str(p + temp_bonus) + "pts" + mark)

                        for mk, mv in MAG_W.items():
                            m = re.search(re.escape(mk) + r"[:\s\+]*(\d+)", txt)
                            if m:
                                v = int(m.group(1)); p = v * mv
                                if mk == "faster casting" and v >= 1: has_fc1 = True
                                if mk == "faster cast recovery" and v >= 3: has_fcr3 = True
                                mark = ""; temp_bonus = 0; trigger = 3 if mk == "faster cast recovery" else MAG_MAX.get(mk, 999)
                                if v >= trigger: temp_bonus = 50; mark = "☆"
                                m_base += p; m_bonus += temp_bonus
                                m_det.append(mk.upper() + " (" + str(v) + ") -> " + str(p + temp_bonus) + "pts" + mark)

                        luck_m = re.search(r"luck[:\s\+]*(\d+)", txt)
                        if luck_m: luck_val = int(luck_m.group(1))

                        w_sc = w_base
                        if w_base >= 350: w_sc += w_bonus
                        m_sc = m_base
                        if m_base >= 350: m_sc += m_bonus

                        target_job = ""
                        if w_sc >= THRESHOLD and w_sc >= m_sc: target_job = "전사"; f_score = w_sc; f_color = 33; final_det = w_det
                        elif m_sc >= THRESHOLD: target_job = "마법"; f_score = m_sc; f_color = 88; final_det = m_det

                        if target_job != "":
                            res_sum = 0
                            res_matches = re.findall(r"(physical|fire|cold|poison|energy) resist[:\s\+]*(\d+)%", txt)
                            for rm in res_matches: res_sum += int(rm[1])
                            final_luck_pts = int(luck_val * 0.5)
                            f_score = int(f_score + res_sum + final_luck_pts)
                            grade_str, grade_color, grade_key = GetGradeInfo(f_score)
                            
                            display_grade_str = grade_str + "(" + target_job + ")"
                            w_ok, c_ok = CheckBagLimit(item.Weight)

                            if w_ok and c_ok:
                                Items.Move(item.Serial, lux_bag, 0); Misc.Pause(150); Items.SetColor(item.Serial, grade_color)
                                current_looted_items.append(item.Serial)
                                Player.HeadMessage(grade_color, display_grade_str + " " + str(f_score) + "pts")
                                Misc.SendMessage("┌──────────────────", f_color)
                                Misc.SendMessage("│ " + grade_str + ": [" + target_job + "] - " + name, f_color)
                                Misc.SendMessage("│ 최종 점수: " + str(f_score) + " pts", grade_color)
                                Misc.SendMessage("├──────────────────", f_color)
                                for d in final_det: Misc.SendMessage("│ > " + d, 945)
                                Misc.SendMessage("│ ------------------", f_color)
                                if res_sum > 0: Misc.SendMessage("│ + RESIST (" + str(res_sum) + ")", 945)
                                if final_luck_pts > 0: Misc.SendMessage("│ + LUCK (" + str(final_luck_pts) + ")", 945)
                                Misc.SendMessage("└──────────────────", f_color)
                                LOOTED_TOTAL += 1; loot_stats[grade_key] += 1
                                FARMING_SCORE += f_score
                                if FARMING_SCORE > CURRENT_CONFIG["max_score"]: CURRENT_CONFIG["max_score"] = FARMING_SCORE
                                SESSION_RECENT_LOGS.insert(0, {'grade_str': display_grade_str, 'name': name, 'score': f_score, 'color': grade_color, 'details': final_det, 'is_gear': True})
                                if len(SESSION_RECENT_LOGS) > 10: SESSION_RECENT_LOGS.pop()
                                UpdateGump()
                                Misc.Pause(ACTION_DELAY - 150); continue
                            else:
                                Player.HeadMessage(33, "!!! [LIMIT] " + display_grade_str + " 발견 !!!")
                                Items.SetColor(item.Serial, 33)
                                continue

                        if "legendary artifact" in txt:
                            w_ok, c_ok = CheckBagLimit(item.Weight)
                            if w_ok and c_ok:
                                Items.Move(item.Serial, lux_bag, 0); Misc.Pause(150); Items.SetColor(item.Serial, 0x21)
                                current_looted_items.append(item.Serial)
                                Player.HeadMessage(0x21, "!!![전설 아티팩트 " + name + "]!!!")
                                LOOTED_TOTAL += 1; loot_stats["legend_arti"] += 1; FARMING_SCORE += 400
                                if FARMING_SCORE > CURRENT_CONFIG["max_score"]: CURRENT_CONFIG["max_score"] = FARMING_SCORE
                                SESSION_RECENT_LOGS.insert(0, {'grade_str': "[◆ 전설 아티]", 'name': name, 'score': 400, 'color': 0x21, 'is_gear': False})
                                if len(SESSION_RECENT_LOGS) > 10: SESSION_RECENT_LOGS.pop()
                                UpdateGump()
                                Misc.Pause(ACTION_DELAY - 150); continue
                            else:
                                Player.HeadMessage(33, "!!! [LIMIT] 전설 발견 !!!")
                                Items.SetColor(item.Serial, 33)
                                continue

                        if LOOT_MODE >= 1:
                            if luck_val >= 150 or (has_fc1 and has_fcr3):
                                msg = "★[운템]" if luck_val >= 150 else "★[빠주]"
                                w_ok, c_ok = CheckBagLimit(item.Weight)
                                if w_ok and c_ok:
                                    Items.Move(item.Serial, lux_bag, 0); Misc.Pause(150); Items.SetColor(item.Serial, 0x21)
                                    current_looted_items.append(item.Serial)
                                    Player.HeadMessage(68, msg)
                                    Misc.Pause(ACTION_DELAY - 150); continue
                                else:
                                    Player.HeadMessage(33, "LIMIT (" + msg + ")")
                                    continue

                        if not is_heavy and LOOT_MODE >= 2 and item.Weight <= (2.0 if LOOT_MODE == 2 else 4.0):
                             if any(tier in txt for tier in ["lesser", "greater", "major", "minor", "artifact"]):
                                 w_ok, c_ok = CheckBagLimit(item.Weight)
                                 if w_ok and c_ok:
                                    Player.HeadMessage(945, "쓰레기 줍는중.."); Items.Move(item.Serial, jnk_bag, 0); Misc.Pause(ACTION_DELAY); continue
                                 else:
                                    continue 

                    Player.HeadMessage(945, "좋은 아이템이 없네..")
                    Misc.Pause(600)
    finally:
        try: SaveConfig()
        except: pass
        try: Gumps.CloseGump(GUMP_ID)
        except: pass
            
        Misc.SendMessage("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", 68)
        Misc.SendMessage(" ✨ [ 오늘의 사냥 정산 보고서 ] ✨ ", 170)
        Misc.SendMessage(" [■] 특급 보물지도 : " + str(loot_stats["treasure"]) + " 개", 33)
        Misc.SendMessage(" [◆] 전설 아티팩트 : " + str(loot_stats["legend_arti"]) + " 개", 0x21)
        Misc.SendMessage(" --------------------------------", 68)
        Misc.SendMessage(" [★★★★★★] 행성파괴급 : " + str(loot_stats["planet"]) + " 개", 33)
        Misc.SendMessage(" [★★★★★] Zi존급 : " + str(loot_stats["zizon"]) + " 개", 1161)
        Misc.SendMessage(" [★★★★] 초월급 : " + str(loot_stats["transcend"]) + " 개", 1159)
        Misc.SendMessage(" [★★★] 신화급 : " + str(loot_stats["legend"]) + " 개", 53)
        Misc.SendMessage(" [★★] 명품급 : " + str(loot_stats["rare"]) + " 개", 0x44)
        Misc.SendMessage(" [★] 득템 : " + str(loot_stats["normal"]) + " 개", 68)
        Misc.SendMessage(" --------------------------------", 68)
        Misc.SendMessage(" ◈ 획득한 명품 총계 : " + str(LOOTED_TOTAL) + " 개", 68)
        Misc.SendMessage("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
