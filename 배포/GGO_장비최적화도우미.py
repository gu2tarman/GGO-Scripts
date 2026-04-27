SCRIPT_ID = "GGO_EQUIP_OPTIMIZER"
SCRIPT_NAME = "GGO_장비최적화도우미"
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

from System.Collections.Generic import List
import clr
import System
import System.Threading as Threading
import re

clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')
from System.Windows.Forms import *
from System.Drawing import *

# ── 슬롯 설정 ──────────────────────────────────────────────────
SLOTS = ["Necklace", "Ring", "Bracelet", "Shield",
         "Helm", "Chest", "Arms", "Gloves", "Legs"]

SLOT_KEYWORDS = {
    # 악세사리
    "Necklace": ["necklace", "gorget", "amulet"],
    "Ring":     ["ring"],
    "Bracelet": ["bracelet", "bangle"],
    "Shield":   ["shield", "buckler", "heater", "kite"],
    # 갑옷
    "Helm":     ["helm", "helmet", "cap", "hat", "bascinet",
                 "close helm", "orc helm", "bone helm", "dragon helm",
                 "horned", "crown", "circlet", "coif", "kabuto"],
    "Chest":    ["chest", "breastplate", "tunic", "hauberk", "surcoat",
                 "doublet", "plate chest", "dragon chest", "bone chest",
                 "leather chest", "studded chest", "ringmail chest",
                 "chainmail tunic", "plate tunic", "do"],
    "Arms":     ["arms", "sleeves", "vambraces", "plate arms",
                 "dragon arms", "bone arms", "leather arms",
                 "studded arms", "ringmail arms", "kote"],
    "Gloves":   ["gloves", "gauntlets", "plate gloves",
                 "dragon gloves", "bone gloves", "leather gloves",
                 "studded gloves", "ringmail gloves"],
    "Legs":     ["legs", "leggings", "skirt", "kilt",
                 "plate legs", "dragon legs", "bone legs",
                 "leather legs", "studded legs", "ringmail legs",
                 "suneate", "haidate"],
}
STAT_KEYS = ["hci", "dci", "ssi", "di", "fc", "fcr", "stam", "dex", "str", "hp", "lmc", "lrc", "int"]

EQUIP_LAYERS = [
    "RightHand", "LeftHand", "Shoes", "Pants", "Shirt",
    "Head", "Gloves", "Ring", "Talisman", "Neck",
    "Waist", "InnerTorso", "Bracelet", "MiddleTorso",
    "Earrings", "Arms", "Cloak", "OuterTorso",
    "OuterLegs", "InnerLegs",
]

TOP_N = 100   # 슬롯별 결과 최대 표시 개수 (일반 / Antique 각각)

GOAL_DEFAULTS = {
    "hci":"50","di":"100","ssi":"55","fc":"2","fcr":"6",
    "str":"150","stam":"213",
    "dci":"20","lmc":"45","lrc":"100","mana":"100",
}

EQUIP_SCRIPT_SETTINGS_DEFAULTS = {
    "top_n": TOP_N,
    "goal_defaults": GOAL_DEFAULTS
}

EQUIP_SCRIPT_SETTINGS_ORDER = [
    "top_n",
    "goal_defaults"
]

EQUIP_SCRIPT_SETTINGS_GUIDE = """GGO_장비최적화도우미 script_settings.json 설명

이 파일은 장비최적화도우미의 공용 설정 파일입니다.
숫자는 숫자로 입력하세요.
쉼표는 지우지 마세요.

top_n:
  슬롯별 후보 결과 최대 표시 개수입니다.

goal_defaults:
  목표 스탯 입력칸의 기본값입니다.
"""

try:
    from GGO_user_config import load_script_settings, ensure_script_settings_guide
    ensure_script_settings_guide(SCRIPT_NAME, EQUIP_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, EQUIP_SCRIPT_SETTINGS_DEFAULTS, EQUIP_SCRIPT_SETTINGS_ORDER)
    TOP_N = int(_script_settings.get("top_n", TOP_N))
    GOAL_DEFAULTS = dict(_script_settings.get("goal_defaults", GOAL_DEFAULTS))
except Exception:
    pass

EMPTY_ENTRY = {
    "item": None, "serial": None,
    "stats": {k: 0 for k in STAT_KEYS + ["antique"]}
}

# ── 유틸 ───────────────────────────────────────────────────────
def extract_val(text):
    m = re.search(r'\d+', text)
    return int(m.group()) if m else 0

def parse_prop_list(props):
    """프로퍼티 문자열 리스트에서 스탯 딕셔너리 추출 (아이템/플레이어 공용)."""
    stats = {k: 0 for k in STAT_KEYS + ["antique"]}
    for prop in props:
        p = prop.lower()
        if   "hit chance increase"     in p: stats["hci"]  = extract_val(p)
        elif "defense chance increase" in p: stats["dci"]  = extract_val(p)
        elif "swing speed increase"    in p: stats["ssi"]  = extract_val(p)
        elif "faster cast recovery"    in p: stats["fcr"]  = extract_val(p)
        elif "faster casting"          in p: stats["fc"]   = extract_val(p)
        elif "stamina increase"        in p: stats["stam"] = extract_val(p)
        elif "dexterity bonus"         in p: stats["dex"]  = extract_val(p)
        elif "strength bonus"          in p: stats["str"]  = extract_val(p)
        elif "hit point increase"      in p: stats["hp"]   = extract_val(p)
        elif "lower mana cost"         in p: stats["lmc"]  = extract_val(p)
        elif "lower reagent cost"      in p: stats["lrc"]  = extract_val(p)
        elif "intelligence bonus"      in p: stats["int"]  = extract_val(p)
        elif "spell damage increase"   in p: pass           # SDI 무시
        elif "damage increase"         in p: stats["di"]   = extract_val(p)
        elif "antique"                 in p: stats["antique"] = True
    return stats

def prune_dominated(entries):
    """같은 슬롯 내에서 모든 스탯이 다른 아이템보다 낮거나 같은 아이템 제거."""
    keep = []
    for i, a in enumerate(entries):
        if a["item"] is None:
            keep.append(a)
            continue
        dominated = False
        for j, b in enumerate(entries):
            if i == j or b["item"] is None:
                continue
            a_vals = [a["stats"].get(k, 0) for k in STAT_KEYS]
            b_vals = [b["stats"].get(k, 0) for k in STAT_KEYS]
            if all(bv >= av for bv, av in zip(b_vals, a_vals)) and \
               any(bv >  av for bv, av in zip(b_vals, a_vals)):
                dominated = True
                break
        if not dominated:
            keep.append(a)
    return keep


class GearOptimizerForm(Form):
    def __init__(self):
        Form.__init__(self)
        self.found_items  = {s: [] for s in SLOTS}
        self.all_results  = []
        self.stat_expand  = False   # True = 확장 검색(스탯 재분배) 결과 표시 중
        self.moved_serials    = set()
        self.current_page     = 0
        self.ITEMS_PER_PAGE   = 20
        self.exp_inputs       = {}
        self._build_ui()

    # ── UI 구성 ────────────────────────────────────────────────
    def _build_ui(self):
        self.Text = "GGO Gear Optimizer v1.1"
        self.Size = Size(1050, 720)
        self.BackColor  = Color.FromArgb(28, 28, 28)
        self.ForeColor  = Color.White
        self.StartPosition = FormStartPosition.CenterScreen

        left = Panel()
        left.Size = Size(295, 720)
        left.Dock = DockStyle.Left
        left.AutoScroll = True
        left.BackColor = Color.FromArgb(35, 35, 35)

        self.curr_inputs = {}
        self.goal_inputs = {}
        y = 8

        # 자동 읽기 버튼
        btn_auto = Button(Text="★ 현재 스탯 자동 읽기",
                          Location=Point(8, y), Size=Size(272, 32),
                          BackColor=Color.FromArgb(0, 128, 64),
                          ForeColor=Color.White, FlatStyle=FlatStyle.Flat)
        btn_auto.Click += self.auto_scan_player
        left.Controls.Add(btn_auto)
        y += 40

        # 현재 스탯
        self._section_label(left, "현재 스탯  (가고일은 hci 5더해주세요)", y); y += 22
        curr_fields = [
            ("STR",      "str"),  ("DEX",  "dex"),  ("Stam Max","stam"),
            ("INT",      "int"),  ("Mana Max","mana"),
            ("HP Max",   "hp"),   ("HCI",  "hci"),  ("DCI",    "dci"),
            ("SSI",      "ssi"),  ("DI",   "di"),   ("FC",     "fc"),
            ("FCR",      "fcr"),  ("LMC",  "lmc"),  ("LRC",    "lrc"),
        ]
        for lbl_text, key in curr_fields:
            self._row(left, lbl_text, key, "0", self.curr_inputs, y); y += 24
        y += 6

        # 목표 스탯
        self._section_label(left, "목표 스탯", y); y += 22
        goal_fields = [
            ("HCI ★", "hci"), ("DI ★",  "di"),   ("SSI ★","ssi"),
            ("FC ★",  "fc"),  ("FCR ★", "fcr"),  ("STR ★","str"),
            ("STAM ★","stam"),
            ("DCI",   "dci"), ("LMC",   "lmc"),  ("LRC",  "lrc"),
            ("Mana",  "mana"),
        ]
        for lbl_text, key in goal_fields:
            self._row(left, lbl_text, key, GOAL_DEFAULTS.get(key,"0"), self.goal_inputs, y); y += 24
        y += 8

        # 슬롯 선택
        self._section_label(left, "스캔 슬롯 선택", y); y += 22
        # 악세사리 기본 ON, 갑옷 기본 OFF
        SLOT_DEFAULTS = {
            "Necklace": True, "Ring": True, "Bracelet": True, "Shield": True,
            "Helm": False, "Chest": False, "Arms": False, "Gloves": False, "Legs": False,
        }
        self.slot_checks = {}
        for slot in SLOTS:
            chk = CheckBox(Text=slot, Location=Point(12, y), AutoSize=True,
                           Checked=SLOT_DEFAULTS.get(slot, False),
                           ForeColor=Color.LightGray)
            self.slot_checks[slot] = chk
            left.Controls.Add(chk)
            y += 22
        y += 4

        self.chk_no_antique = CheckBox(Text="Antique 아이템 제외", Location=Point(12, y),
                                       AutoSize=True, Checked=True, ForeColor=Color.LightGray)
        left.Controls.Add(self.chk_no_antique)
        y += 30

        self.btn_scan = Button(Text="컨테이너 스캔 & 최적화",
                               Location=Point(8, y), Size=Size(272, 38),
                               BackColor=Color.SteelBlue, FlatStyle=FlatStyle.Flat)
        self.btn_scan.Click += self.start_optimization
        left.Controls.Add(self.btn_scan)
        y += 46

        # ── 확장 검색 섹션 ─────────────────────────────────────
        self._section_label(left, "확장 검색 (스탯 재분배)", y); y += 22

        self.chk_expand = CheckBox(
            Text="확장 검색 포함 (스탯 재분배)",
            Location=Point(12, y), AutoSize=True,
            Checked=True, ForeColor=Color.LightGray)
        self.chk_expand.CheckedChanged += self._on_expand_toggled
        left.Controls.Add(self.chk_expand)
        y += 24

        # 리얼 스탯 추정 버튼
        btn_estimate = Button(Text="리얼 스탯 자동 추정",
                              Location=Point(8, y), Size=Size(272, 28),
                              BackColor=Color.FromArgb(60, 80, 60),
                              FlatStyle=FlatStyle.Flat)
        btn_estimate.Click += self._estimate_real_stats
        left.Controls.Add(btn_estimate)
        self.btn_estimate    = btn_estimate
        self._exp_controls   = [btn_estimate]
        y += 32

        exp_fields = [
            ("리얼 STR", "real_str", "0"),
            ("리얼 DEX", "real_dex", "0"),
            ("리얼 INT", "real_int", "0"),
            ("최소 INT",  "min_int",  "20"),
        ]
        for lbl_text, key, default in exp_fields:
            lbl = Label(Text=lbl_text, Location=Point(10, y+2), Width=85, ForeColor=Color.Silver)
            txt = TextBox(Location=Point(100, y), Width=60, Text=default,
                          BackColor=Color.FromArgb(55, 55, 55), ForeColor=Color.White)
            self.exp_inputs[key] = txt
            left.Controls.Add(lbl)
            left.Controls.Add(txt)
            self._exp_controls += [lbl, txt]
            y += 24

        # 확장 검색 설명 레이블
        hint = Label(
            Text="STR/DEX/INT 간 자유 재분배.\n예) STR↓→DEX↑, INT↓→STR↑\n하늘색 = 스탯 조정 필요 조합.",
            Location=Point(10, y), Size=Size(265, 50),
            ForeColor=Color.FromArgb(150, 150, 150))
        left.Controls.Add(hint)
        self._exp_controls.append(hint)

        # 초기 상태: 활성화 (기본 ON)
        self._set_expand_controls(True)

        # 폼이 완전히 표시된 뒤 리얼 스탯 자동 추정 실행
        self.Shown += self._on_shown

        # 결과 리스트
        self.res_list = ListView()
        self.res_list.Dock = DockStyle.Fill
        self.res_list.View = View.Details
        self.res_list.FullRowSelect = True
        self.res_list.BackColor = Color.FromArgb(38, 38, 38)
        self.res_list.ForeColor = Color.White
        self.res_list.GridLines  = True
        self.res_list.Columns.Add("#",      40)
        self.res_list.Columns.Add("슬롯  |  HCI / DCI / SSI / DI / FC / FCR / STR / Stam  |  (+HP LMC LRC)", 530)
        self.res_list.Columns.Add("Score",  60)
        self.res_list.Columns.Add("상태",    60)

        # 하단 컨트롤
        bot = Panel()
        bot.Dock   = DockStyle.Bottom
        bot.Height = 48
        bot.BackColor = Color.FromArgb(28, 28, 28)

        self.btn_prev = Button(Text="◀ 이전", Location=Point(8, 9), Size=Size(75, 30),
                               BackColor=Color.DimGray, FlatStyle=FlatStyle.Flat)
        self.btn_prev.Click += self.prev_page
        self.btn_prev.Enabled = False

        self.lbl_page = Label(Text="─", Location=Point(92, 14), AutoSize=True, ForeColor=Color.Gold)

        self.btn_next = Button(Text="다음 ▶", Location=Point(195, 9), Size=Size(75, 30),
                               BackColor=Color.DimGray, FlatStyle=FlatStyle.Flat)
        self.btn_next.Click += self.next_page
        self.btn_next.Enabled = False

        btn_move = Button(Text="★ 선택 조합 → 가방으로 꺼내기",
                          Location=Point(285, 9), Size=Size(230, 30),
                          BackColor=Color.FromArgb(80, 50, 20), FlatStyle=FlatStyle.Flat)
        btn_move.Click += self.move_selected_combo

        bot.Controls.Add(self.btn_prev)
        bot.Controls.Add(self.lbl_page)
        bot.Controls.Add(self.btn_next)
        bot.Controls.Add(btn_move)

        self.Controls.Add(self.res_list)
        self.Controls.Add(bot)
        self.Controls.Add(left)

    def _section_label(self, parent, text, y):
        lbl = Label(Text="── %s ──" % text, Location=Point(5, y),
                    AutoSize=True, ForeColor=Color.Gold)
        parent.Controls.Add(lbl)

    def _row(self, parent, label_text, key, default, store, y):
        lbl = Label(Text=label_text, Location=Point(10, y+2), Width=85, ForeColor=Color.Silver)
        txt = TextBox(Location=Point(100, y), Width=60, Text=default,
                      BackColor=Color.FromArgb(55, 55, 55), ForeColor=Color.White)
        store[key] = txt
        parent.Controls.Add(lbl)
        parent.Controls.Add(txt)

    # ── 자동 스탯 읽기 ─────────────────────────────────────────
    def _set_expand_controls(self, enabled):
        for ctrl in self._exp_controls:
            ctrl.Enabled = enabled
            if hasattr(ctrl, 'ForeColor'):
                ctrl.ForeColor = Color.Silver if enabled else Color.FromArgb(80, 80, 80)

    def _on_expand_toggled(self, sender, args):
        self._set_expand_controls(self.chk_expand.Checked)

    def _on_shown(self, sender, args):
        """폼이 완전히 표시된 직후 리얼 스탯 자동 추정."""
        self._estimate_real_stats(None, None)

    def _estimate_real_stats(self, sender, args):
        """백그라운드 스레드에서 장비 스탯 합산 → BeginInvoke로 UI 업데이트."""
        btn = self.btn_estimate

        # 버튼 비활성화 (중복 클릭 방지)
        try:
            btn.Enabled = False
            btn.Text    = "추정 중..."
        except:
            pass

        def worker():
            total_str = total_dex = total_int = 0
            for layer in EQUIP_LAYERS:
                try:
                    item = Player.GetItemOnLayer(layer)
                    if item is None: continue
                    props = Items.GetPropStringList(item.Serial)
                    for prop in props:
                        p = prop.lower()
                        if   "strength bonus"     in p: total_str += extract_val(p)
                        elif "dexterity bonus"    in p: total_dex += extract_val(p)
                        elif "intelligence bonus" in p: total_int += extract_val(p)
                except:
                    continue

            rs = Player.Str - total_str
            rd = Player.Dex - total_dex
            ri = Player.Int - total_int

            def apply_ui():
                self.exp_inputs["real_str"].Text = str(rs)
                self.exp_inputs["real_dex"].Text = str(rd)
                self.exp_inputs["real_int"].Text = str(ri)
                btn.Text    = "리얼 스탯 자동 추정"
                btn.Enabled = True
                Misc.SendMessage(
                    "[최적검색] 리얼 스탯 추정: STR=%d DEX=%d INT=%d (합계=%d)" % (
                        rs, rd, ri, rs + rd + ri), 66)

            # UI 업데이트는 반드시 메인 스레드에서
            self.BeginInvoke(System.Action(apply_ui))

        t = Threading.Thread(Threading.ThreadStart(worker))
        t.IsBackground = True
        t.Start()

    def auto_scan_player(self, sender, args):
        # 기본 수치: Player 직접 속성
        try: self.curr_inputs["str"].Text  = str(int(Player.Str))
        except: pass
        try: self.curr_inputs["dex"].Text  = str(int(Player.Dex))
        except: pass
        try: self.curr_inputs["stam"].Text = str(int(Player.StamMax))
        except: pass
        try: self.curr_inputs["int"].Text  = str(int(Player.Int))
        except: pass
        try: self.curr_inputs["mana"].Text = str(int(Player.ManaMax))
        except: pass
        try: self.curr_inputs["hp"].Text   = str(int(Player.HitsMax))
        except: pass

        # 전투 수치: SumAttribute (장착 장비 합산값)
        combat_map = [
            ("hci",  "Hit Chance Increase"),
            ("dci",  "Defense Chance Increase"),
            ("ssi",  "Swing Speed Increase"),
            ("di",   "Damage Increase"),
            ("fc",   "Faster Casting"),
            ("fcr",  "Faster Cast Recovery"),
            ("lmc",  "Lower Mana Cost"),
            ("lrc",  "Lower Reagent Cost"),
        ]
        for field, attr_name in combat_map:
            try:
                val = int(Player.SumAttribute(attr_name))
                self.curr_inputs[field].Text = str(val)
            except:
                pass

        Misc.SendMessage("[최적검색] 스탯 자동 읽기 완료.", 66)

    # ── 아이템 파싱 ────────────────────────────────────────────
    def parse_item(self, item):
        props = Items.GetPropStringList(item.Serial)
        return parse_prop_list(props)

    # ── 재귀 컨테이너 스캔 (antique 필터 없이 전체 수집) ──────
    def scan_recursive(self, container, active_slots, depth=0):
        if depth > 5: return
        Items.WaitForContents(container, 2000)
        Application.DoEvents()
        for item in container.Contains:
            name = (item.Name or "").lower()
            for slot in active_slots:
                if any(kw in name for kw in SLOT_KEYWORDS[slot]):
                    self.found_items[slot].append({
                        "item": item, "serial": item.Serial,
                        "stats": self.parse_item(item)
                    })
                    break
            if item.IsContainer:
                try:
                    self.scan_recursive(item, active_slots, depth + 1)
                except:
                    pass

    # ── 조합 계산 (순수 계산, antique 필터 여부 파라미터) ──────
    def _search(self, items_dict, c, g, dex_headroom,
                expand=False, pool_int=0, max_str_gain=0, max_dex_gain=0):
        """
        단일 루프로 일반 결과 + 확장(스탯 재분배) 결과를 동시에 수집.
        expand=False : STR/STAM 포함 모든 목표를 장비만으로 충족해야 통과.
        expand=True  : STR/STAM은 재분배로 보완 가능한 조합도 포함.
        """
        results = []
        for n in items_dict["Necklace"]:
            Application.DoEvents()
            ns = n["stats"]
            for r in items_dict["Ring"]:
                rs = r["stats"]
                for b in items_dict["Bracelet"]:
                    bs = b["stats"]
                    for s in items_dict["Shield"]:
                        ss = s["stats"]

                        e_hci  = ns["hci"]  + rs["hci"]  + bs["hci"]  + ss["hci"]
                        e_dci  = ns["dci"]  + rs["dci"]  + bs["dci"]  + ss["dci"]
                        e_ssi  = ns["ssi"]  + rs["ssi"]  + bs["ssi"]  + ss["ssi"]
                        e_di   = ns["di"]   + rs["di"]   + bs["di"]   + ss["di"]
                        e_fc   = ns["fc"]   + rs["fc"]   + bs["fc"]   + ss["fc"]
                        e_fcr  = ns["fcr"]  + rs["fcr"]  + bs["fcr"]  + ss["fcr"]
                        e_str  = ns["str"]  + rs["str"]  + bs["str"]  + ss["str"]
                        e_dex  = ns["dex"]  + rs["dex"]  + bs["dex"]  + ss["dex"]
                        e_stam = ns["stam"] + rs["stam"] + bs["stam"] + ss["stam"]
                        e_hp   = ns["hp"]   + rs["hp"]   + bs["hp"]   + ss["hp"]
                        e_lmc  = ns["lmc"]  + rs["lmc"]  + bs["lmc"]  + ss["lmc"]
                        e_lrc  = ns["lrc"]  + rs["lrc"]  + bs["lrc"]  + ss["lrc"]

                        e_int  = ns["int"]  + rs["int"]  + bs["int"]  + ss["int"]

                        eff_dex = min(e_dex, dex_headroom)
                        int_headroom = max(0, 150 - c["int"])
                        eff_int = min(e_int, int_headroom)

                        t_hci  = c["hci"]  + e_hci
                        t_dci  = c["dci"]  + e_dci
                        t_ssi  = c["ssi"]  + e_ssi
                        t_di   = c["di"]   + e_di
                        t_fc   = c["fc"]   + e_fc
                        t_fcr  = c["fcr"]  + e_fcr
                        t_str  = c["str"]  + e_str
                        t_stam = c["stam"] + e_stam + eff_dex
                        t_mana = c["mana"] + eff_int
                        t_lmc  = c["lmc"]  + e_lmc
                        t_lrc  = c["lrc"]  + e_lrc

                        # 장비로만 해결해야 하는 조건 (스탯 재분배 무관)
                        if (t_hci < g["hci"] or t_di  < g["di"] or
                            t_ssi < g["ssi"] or t_fc  < g["fc"] or
                            t_fcr < g["fcr"]):
                            continue

                        # STR / STAM 부족분
                        str_need  = max(0, g["str"]  - t_str)
                        stam_need = max(0, g["stam"] - t_stam)

                        if str_need == 0 and stam_need == 0:
                            # 조정 불필요 — 일반 결과
                            stat_adj = (0, 0)
                            adj_note = ""
                        elif expand:
                            # 재분배로 보완 가능한지 검사
                            # 이 콤보의 장비 보너스가 이미 캡을 채운 만큼 실질 상한 축소
                            combo_str_ceiling = max(0, 150 - c["str"] - e_str)
                            combo_dex_ceiling = max(0, dex_headroom - eff_dex)
                            combo_max_str_gain = min(max_str_gain, combo_str_ceiling)
                            combo_max_dex_gain = min(max_dex_gain, combo_dex_ceiling)
                            if str_need  > combo_max_str_gain: continue
                            if stam_need > combo_max_dex_gain: continue

                            str_surplus  = max(0, t_str  - g["str"])
                            stam_surplus = max(0, t_stam - g["stam"])

                            if str_need > 0 and stam_need > 0:
                                available = pool_int
                            elif str_need > 0:
                                available = pool_int + stam_surplus
                            else:
                                available = pool_int + str_surplus

                            if str_need + stam_need > available: continue

                            stat_adj = (str_need, stam_need)
                            adj_parts = []
                            if str_need  > 0: adj_parts.append("STR+%d" % str_need)
                            if stam_need > 0: adj_parts.append("DEX+%d" % stam_need)
                            adj_parts.append("INT-%d" % (str_need + stam_need))
                            adj_note = " [%s]" % " ".join(adj_parts)
                        else:
                            continue  # 확장 OFF → 조건 미달 skip

                        # INT 재분배 비용만큼 마나 감소 반영 (일반 결과는 int_cost=0)
                        int_cost = str_need + stam_need

                        # 캡(150) 초과 STR/DEX 실수치 → INT 역전용으로 마나 보정
                        # expand 모드에서만: 실수치 재분배를 허용하는 경우에 한함
                        if expand:
                            str_waste  = max(0, c["str"] + e_str - 150)
                            dex_waste  = max(0, c["dex"] + e_dex - 150)
                            int_room   = max(0, 150 - c["int"] - e_int)
                            bonus_mana = min(str_waste + dex_waste, int_room)
                        else:
                            bonus_mana = 0

                        eff_mana = t_mana + bonus_mana - int_cost

                        fc_bonus = max(0, min(t_fc, 4) - g["fc"])

                        score = (
                            min(t_dci,   g["dci"])  *  5 +
                            min(t_lmc,   g["lmc"])  *  8 +
                            min(t_lrc,   g["lrc"])  *  2 +
                            min(eff_mana,g["mana"]) *  5 +
                            e_hp                    *  5 +
                            fc_bonus                * 10
                        )

                        slots_used = []
                        for slot, gear in zip(SLOTS, [n, r, b, s]):
                            if gear["item"]:
                                slots_used.append(slot[:4])

                        has_antique = any(
                            gear["stats"].get("antique", False)
                            for gear in [n, r, b, s] if gear["item"]
                        )

                        summary = "[%s] H%d D%d S%d DI%d FC%d FCR%d STR%d Stam%d  (+hp%d mana%d lmc%d lrc%d)%s" % (
                            ",".join(slots_used) if slots_used else "맨몸",
                            t_hci, t_dci, t_ssi, t_di, t_fc, t_fcr,
                            t_str + str_need, t_stam + stam_need,
                            e_hp, eff_mana, t_lmc, t_lrc, adj_note
                        )

                        results.append({
                            "items":       [n["item"],  r["item"],  b["item"],  s["item"]],
                            "serials":     [n["serial"], r["serial"], b["serial"], s["serial"]],
                            "summary":     summary,
                            "score":       score,
                            "has_antique": has_antique,
                            "stat_adj":    stat_adj,
                        })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:TOP_N]

    # ── 메인: 스캔 & 최적화 ────────────────────────────────────
    def start_optimization(self, sender, args):
        active_slots = [s for s in SLOTS if self.slot_checks[s].Checked]
        if not active_slots:
            Misc.SendMessage("[최적검색] 슬롯을 1개 이상 선택하세요.", 33)
            return

        self.btn_scan.Text = "타겟 선택 중... (ESC = 완료)"
        self.btn_scan.BackColor = Color.Orange
        Application.DoEvents()

        self.found_items  = {s: [] for s in SLOTS}
        self.all_results  = []
        self.antique_fallback = False
        self.res_list.Items.Clear()

        scanned = []
        Misc.SendMessage("[최적검색] 스캔할 컨테이너 선택 → ESC로 완료", 66)
        while True:
            Application.DoEvents()
            serial = Target.PromptTarget()
            if serial <= 0: break
            cont = Items.FindBySerial(serial)
            if cont:
                scanned.append(cont)
                Misc.SendMessage("[최적검색] 추가됨. 계속 선택하거나 ESC", 66)
            else:
                Misc.SendMessage("[최적검색] 유효하지 않은 대상", 33)

        if not scanned:
            self._reset_btn(); return

        self.btn_scan.Text = "스캔 중..."
        self.btn_scan.BackColor = Color.Crimson
        Application.DoEvents()

        for cont in scanned:
            self.scan_recursive(cont, active_slots)

        # 빈 슬롯(없음) 옵션 추가
        for s in SLOTS:
            if s in active_slots:
                self.found_items[s].append(dict(EMPTY_ENTRY))
            else:
                self.found_items[s] = [dict(EMPTY_ENTRY)]

        no_antique = self.chk_no_antique.Checked

        # antique 필터 적용된 items_dict 구성
        def apply_filter(all_items, exclude_antique):
            filtered = {}
            for slot in SLOTS:
                if exclude_antique:
                    filtered[slot] = [
                        e for e in all_items[slot]
                        if e["item"] is None or not e["stats"].get("antique", False)
                    ]
                else:
                    filtered[slot] = list(all_items[slot])
            return filtered

        # 지배 아이템 제거 (antique 제외 여부와 무관하게 전체 대상으로)
        for s in active_slots:
            self.found_items[s] = prune_dominated(self.found_items[s])

        # 현재 스탯
        try:
            c = {k: int(self.curr_inputs[k].Text) for k in self.curr_inputs}
        except:
            Misc.SendMessage("[최적검색] 현재 스탯 입력값 오류", 33)
            self._reset_btn(); return

        # 목표 스탯
        try:
            g = {k: int(self.goal_inputs[k].Text) for k in self.goal_inputs}
        except:
            Misc.SendMessage("[최적검색] 목표 스탯 입력값 오류", 33)
            self._reset_btn(); return

        dex_headroom = max(0, 150 - c["dex"])

        self.btn_scan.Text = "조합 계산 중..."
        Application.DoEvents()

        self.stat_expand = False

        # 확장 검색 파라미터 준비
        expand = self.chk_expand.Checked
        pool_int = max_str_gain = max_dex_gain = 0
        if expand:
            try:
                real_str = int(self.exp_inputs["real_str"].Text)
                real_dex = int(self.exp_inputs["real_dex"].Text)
                real_int = int(self.exp_inputs["real_int"].Text)
                min_int  = int(self.exp_inputs["min_int"].Text)
                pool_int     = max(0, real_int - min_int)
                max_str_gain = 125 - real_str
                max_dex_gain = 125 - real_dex
            except:
                Misc.SendMessage("[최적검색] 확장 검색: 리얼 스탯 입력값 오류", 33)
                self._reset_btn(); return

        # ── 일반 결과 (antique 제외 여부 그대로 적용)
        items_to_use    = apply_filter(self.found_items, no_antique)
        regular_results = self._search(items_to_use, c, g, dex_headroom,
                                       expand, pool_int, max_str_gain, max_dex_gain)

        # ── Antique 포함 결과를 하단에 추가 (no_antique 체크 시에만 별도 수집)
        antique_section = []
        if no_antique:
            items_all   = apply_filter(self.found_items, exclude_antique=False)
            all_results = self._search(items_all, c, g, dex_headroom,
                                       expand, pool_int, max_str_gain, max_dex_gain)
            antique_section = [r for r in all_results if r.get("has_antique", False)]
            for r in antique_section:
                r["antique_group"] = True

        # ── stat_expand 플래그 (구분선 제외한 모든 결과 기준)
        all_flat = regular_results + antique_section
        if expand and any(r.get("stat_adj", (0, 0)) != (0, 0) for r in all_flat):
            self.stat_expand = True

        # ── 최종 결합: 일반 결과 + [구분선] + antique 결과
        combined = list(regular_results)
        if antique_section:
            if regular_results:
                combined.append({"is_separator": True})
            combined.extend(antique_section)

        if not regular_results and antique_section:
            Misc.SendMessage("[최적검색] 일반 결과 없음 — Antique 포함 조합만 표시 (주황색)", 33)

        self.all_results  = combined
        self.current_page = 0
        self.display_page()
        self._reset_btn()
        Misc.SendMessage("[최적검색] 완료: 일반 %d개 / Antique포함 %d개 조합" % (
            len(regular_results), len(antique_section)), 66)

    # ── 결과 표시 ──────────────────────────────────────────────
    def display_page(self):
        self.res_list.Items.Clear()
        total = len(self.all_results)

        if total == 0:
            self.lbl_page.Text = "조건 충족 조합 없음"
            self.btn_prev.Enabled = False
            self.btn_next.Enabled = False
            return

        total_pages = (total + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        start = self.current_page * self.ITEMS_PER_PAGE
        end   = min(start + self.ITEMS_PER_PAGE, total)

        for i in range(start, end):
            res = self.all_results[i]

            # ── 구분선 행
            if res.get("is_separator"):
                lvi = ListViewItem("")
                lvi.SubItems.Add("▼  Antique 포함 조합  (아래 결과에 Antique 아이템 포함됨, 주황색)")
                lvi.SubItems.Add("")
                lvi.SubItems.Add("")
                lvi.BackColor = Color.FromArgb(60, 35, 0)
                lvi.ForeColor = Color.Gold
                lvi.Tag = None
                self.res_list.Items.Add(lvi)
                continue

            moved = any(s in self.moved_serials for s in res["serials"] if s is not None)

            lvi = ListViewItem(str(i + 1))
            lvi.SubItems.Add(res["summary"])
            lvi.SubItems.Add(str(res["score"]))
            lvi.SubItems.Add("꺼냄" if moved else "")
            lvi.Tag = i

            if moved:
                lvi.ForeColor = Color.FromArgb(90, 90, 90)
            elif res.get("antique_group"):
                lvi.ForeColor = Color.Orange                   # Antique 포함 조합
            elif self.stat_expand and res.get("stat_adj", (0, 0)) != (0, 0):
                lvi.ForeColor = Color.SkyBlue                  # 스탯 조정 필요

            self.res_list.Items.Add(lvi)

        regular_count = sum(1 for r in self.all_results if not r.get("is_separator") and not r.get("antique_group"))
        antique_count = sum(1 for r in self.all_results if r.get("antique_group"))
        page_info = "%d / %d 페이지" % (self.current_page + 1, total_pages)
        if antique_count > 0:
            page_info += "  (일반 %d / Antique %d)" % (regular_count, antique_count)
        else:
            page_info += "  (총 %d개)" % regular_count
        self.lbl_page.Text = page_info
        self.btn_prev.Enabled = self.current_page > 0
        self.btn_next.Enabled = self.current_page < total_pages - 1

    def prev_page(self, sender, args):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()

    def next_page(self, sender, args):
        total_pages = (len(self.all_results) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_page()

    # ── 아이템 이동 ────────────────────────────────────────────
    def move_selected_combo(self, sender, args):
        if self.res_list.SelectedItems.Count == 0: return
        tag = self.res_list.SelectedItems[0].Tag
        if tag is None: return          # 헤더 행 클릭 방지
        combo = self.all_results[tag]

        for item, serial in zip(combo["items"], combo["serials"]):
            if item and serial:
                self._move_safely(serial, Player.Backpack.Serial)
                self.moved_serials.add(serial)

        self.display_page()
        Misc.SendMessage("[최적검색] 선택 조합 아이템 이동 완료", 66)

    def _move_safely(self, serial, dest):
        try:
            item = Items.FindBySerial(serial)
            if not item: return
            src = item.Container
            Items.Move(serial, dest, 0)
            for _ in range(30):
                Misc.Pause(100)
                Application.DoEvents()
                cur = Items.FindBySerial(serial)
                if cur and cur.Container != src:
                    Misc.Pause(300)
                    return
                if Journal.Search("You must wait"):
                    Misc.Pause(1000)
                    Journal.Clear()
                    Items.Move(serial, dest, 0)
        except:
            pass

    def _reset_btn(self):
        self.btn_scan.Text = "컨테이너 스캔 & 최적화"
        self.btn_scan.BackColor = Color.SteelBlue


def main():
    Application.Run(GearOptimizerForm())

if __name__ == "__main__":
    main()
