# -*- coding: utf-8 -*-
"""
=============================================================================
  GGO SOS 상자 정리기 플러그인 모듈 (SosChestSorter)
=============================================================================
[사용법]
1. 본인 매크로(본업 스크립트) 상단에 아래처럼 import 합니다.
   from 정리꼬붕_모듈 import SosChestSorter

2. 메인 스크립트 시작 부분에서 객체를 생성합니다.
   sorter = SosChestSorter()

3. 주기적으로 실행하고 싶은 곳(예: 3분, 은행 들를 때 등)에서 호출합니다.
   sorter.process_if_boxes_exist()
=============================================================================
"""

SCRIPT_ID = "GGO_SORTER_MODULE"
SCRIPT_NAME = "정리꼬붕_모듈"
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

from System import Environment
from System.IO import Directory, Path, File
import json
import time

try:
    from GGO_user_config import get_character_settings_path
except:
    get_character_settings_path = None

class SosChestSorter:
    def __init__(self, notify_func=None):
        self.notify_func = notify_func
        self.APPDATA = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
        self.LEGACY_SAVE_DIR = Path.Combine(self.APPDATA, "GGO_Project", "SOSBot")
        self.LEGACY_CONFIG_FILE = Path.Combine(self.LEGACY_SAVE_DIR, "SOS_Sorter_{0}.json".format(Player.Name))

        self.SAVE_DIR = self.LEGACY_SAVE_DIR
        self.CONFIG_FILE = self.LEGACY_CONFIG_FILE
        if get_character_settings_path:
            try:
                self.CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
                self.SAVE_DIR = Path.GetDirectoryName(self.CONFIG_FILE)
            except:
                self.SAVE_DIR = self.LEGACY_SAVE_DIR
                self.CONFIG_FILE = self.LEGACY_CONFIG_FILE
        
        self.SosChestContainer = 0
        self.ValuableBox = 0
        self.HighValueBox = 0
        self.ByproductBox = 0
        self.ScrollReagentBox = 0
        self.TrashContainer = 0
        self.ResidueBox = 0
        
        self.unravel_mode = False
        self.processed_count = 0
        self.looted_items_count = {}
        
        self.FishingTreasureBox = [0xa306, 0xa308, 0xe41, 0xe43, 0xA30A, 0x9a8]
        self.gold_id = [0x0EED]
        self.gem_id = [0xf25,0xf13,0xf15,0xf0f,0xf11,0xf16,0x0F18,0xf10,0xf26,0x3192,0x3193,0x3194,0x3195,0x3197,0x3198,0x3199,0x1bf2]
        self.etc_id = [0x142b,0x4cd9,0x4CD8,0x142A,0x2d61,0x4CDA,0x571c,0x1767]
        self.byproduct_id = [0x14ec, 0xdca, 0x1ea5, 0xa414]
        self.highvalue_id = [0xa34a, 0xa349, 0xe75]
        self.pirate_hat_id = 0x171B
        
        self.reagent_id = [0xf7a,0xf8e,0xf86,0xf8c,0xf7d,0xf7b,0xf85,
                           0xf84,0xf8d,0xf8a,0xf8f,0xf78,0xf88]
        
        self.scroll_id = [0x1f53,0x1f32,0x1f6c,0x1f31,0x1f48,0x1f51,0x1f38,0x1f69,0x1F34,
                          0x1f5c,0x1f56,0x1f5b,0x1f45,0x1f2d,0x1f54,0x1f5f,0x1f39,0x1f3f,0x1F4C,
                          0x1f3c,0x1f41,0x1f40,0x1f55,0x1f5d,0x1f58,0x1f3b,0x1f6a,0x1f44,0x1f68,0x1F4F,0x1F63,
                          0x1f30,0x1f4d,0x1f49,0x1F61,0x1F6B,0x1F4E,0x1F2F,0x1F57,0x1F43,0x1F66,0x1F37,0x1F52,
                          0x2D5A,0x2D51,0x2D54,0x2D59,0x2D55,0x2D56,0x2D5D,0x2D5F,0x2D52,0x2D5E,0x2D53,0x2D5C,
                          0x2265,0x226B,0x2263,0x226E,0x2268,0x2261,0x2266,0x226C,0x226D,0x226F,0x2270,
                          0x2262,0x2267,0x226A,0x2269,0x2260,
                          0x2D9F,0x2DA1,0x2DAD,0x2DA6,0x2DA4,0x2D9E,0x2DA7,0x2DA9,0x2DA5,0x2DA8,0x2DAA,
                          0x2DAC,0x2DAB,0x2DA2,0x2DA3]
                          
        self.goldpocket = 0xA331
        self.jewelpocket = 0xA333
        self.reagentpocket = 0xA32F
        self.ResidueID = 0x2DB1
        self.EnchantedEssence = 0x2DB2
        self.RelicFragment = 0x2DB3
        self.UnravelIDs = [self.ResidueID, self.EnchantedEssence, self.RelicFragment]

        self.load_config()

    def save_config(self, data):
        if not Directory.Exists(self.SAVE_DIR):
            Directory.CreateDirectory(self.SAVE_DIR)
        File.WriteAllText(self.CONFIG_FILE, json.dumps(data, indent=4))

    def load_config_raw(self):
        if not File.Exists(self.CONFIG_FILE) and File.Exists(self.LEGACY_CONFIG_FILE):
            try:
                if not Directory.Exists(self.SAVE_DIR):
                    Directory.CreateDirectory(self.SAVE_DIR)
                File.Copy(self.LEGACY_CONFIG_FILE, self.CONFIG_FILE, False)
            except:
                pass
        if File.Exists(self.CONFIG_FILE):
            return json.loads(File.ReadAllText(self.CONFIG_FILE))
        return None

    def load_config(self):
        cfg = self.load_config_raw()
        if cfg:
            self.SosChestContainer = cfg.get("SosChestContainer", 0)
            self.ValuableBox = cfg.get("ValuableBox", 0)
            self.HighValueBox = cfg.get("HighValueBox", 0)
            self.ByproductBox = cfg.get("ByproductBox", 0)
            self.ScrollReagentBox = cfg.get("ScrollReagentBox", 0)
            self.TrashContainer = cfg.get("TrashContainer", 0)
            self.ResidueBox = cfg.get("ResidueBox", 0)
            self.unravel_mode = cfg.get("unravel_mode", False)
            return True
        return False

    def run_setup(self):
        Player.HeadMessage(158, "● [정리모듈] 파머가 상자를 던진 컨테이너(SosChestContainer)를 선택하세요")
        self.SosChestContainer = Target.PromptTarget("SosChestContainer")
        Player.HeadMessage(158, "● [정리모듈] 환금 보관함(골드/보석/특수재료)을 선택하세요")
        self.ValuableBox = Target.PromptTarget("ValuableBox")
        Player.HeadMessage(158, "● [정리모듈] 고가치 보관함(유니크/해적모자 등)을 선택하세요")
        self.HighValueBox = Target.PromptTarget("HighValueBox")
        Player.HeadMessage(158, "● [정리모듈] 부산물 보관함(지도/그물 등)을 선택하세요")
        self.ByproductBox = Target.PromptTarget("ByproductBox")
        Player.HeadMessage(158, "● [정리모듈] 시약 보관함을 선택하세요")
        self.ScrollReagentBox = Target.PromptTarget("ScrollReagentBox")
        Player.HeadMessage(158, "● [정리모듈] 빈 상자를 버릴 쓰레기통을 선택하세요")
        self.TrashContainer = Target.PromptTarget("TrashContainer")
        
        cfg = self.load_config_raw() or {}
        cfg["SosChestContainer"] = self.SosChestContainer
        cfg["ValuableBox"] = self.ValuableBox
        cfg["HighValueBox"] = self.HighValueBox
        cfg["ByproductBox"] = self.ByproductBox
        cfg["ScrollReagentBox"] = self.ScrollReagentBox
        cfg["TrashContainer"] = self.TrashContainer
        cfg["ResidueBox"] = self.ResidueBox
        cfg["unravel_mode"] = self.unravel_mode
        self.save_config(cfg)
        Player.HeadMessage(68, "[정리모듈] 컨테이너 설정이 기본 저장되었습니다.")

    def toggle_unravel_mode(self):
        self.unravel_mode = not self.unravel_mode
        if self.unravel_mode and self.ResidueBox == 0:
            Player.HeadMessage(158, "● [임뷰 모드] 임뷰 재료 보관함을 선택하세요")
            self.ResidueBox = Target.PromptTarget("ResidueBox")
        
        cfg = self.load_config_raw() or {}
        cfg["unravel_mode"] = self.unravel_mode
        cfg["ResidueBox"] = self.ResidueBox
        self.save_config(cfg)
        return self.unravel_mode

    def record_item(self, name):
        if name in self.looted_items_count:
            self.looted_items_count[name] += 1
        else:
            self.looted_items_count[name] = 1

    def _cleanup_stuck_state(self):
        if Gumps.HasGump(0x65290b89):
            Gumps.CloseGump(0x65290b89); Misc.Pause(300)
        if Gumps.HasGump(0xb73e81bb):
            Gumps.CloseGump(0xb73e81bb); Misc.Pause(300)
        Items.DropFromHand(Player.Backpack, Player.Backpack); Misc.Pause(400)

    def move_item(self, item, dst):
        if not item: return False
        item_serial = item.Serial
        Items.Move(item, dst, -1)
        timeout = 0
        while timeout < 15:
            check = Items.FindBySerial(item_serial)
            if not check or check.Container == dst:
                return True
            Misc.Pause(200)
            timeout += 1
        Target.Cancel()
        Items.DropFromHand(Player.Backpack, Player.Backpack)
        Misc.Pause(600)
        return False

    def move_all_by_id(self, item_id, src_container, dst_container, label=None):
        while True:
            item = Items.FindByID(item_id, -1, src_container)
            if not item: break
            if item_id == self.pirate_hat_id:
                name = str(item.Name).lower() if item.Name else ""
                if "plunderin" not in name and "약탈" not in name:
                    break
            if self.move_item(item, dst_container) and label:
                self.record_item(label)
                hue = 1161 if label in ["[고가치]", "[찐 해적모자]"] else 68
                item_name = str(item.Name) if item.Name else label
                Player.HeadMessage(hue, "[보관] {}".format(item_name))
            Misc.Pause(600)

    def extract_valuables(self, tbox):
        Items.UseItem(tbox); Misc.Pause(800)

        Player.HeadMessage(55, "[정리] 골드 수거 중...")
        p_gold = Items.FindByID(self.goldpocket, -1, tbox.Serial)
        if p_gold:
            Items.UseItem(p_gold); Misc.Pause(500)
            for i in self.gold_id:
                self.move_all_by_id(i, p_gold.Serial, self.ValuableBox, "[골드]")

        Player.HeadMessage(55, "[정리] 보석 수거 중...")
        p_gem = Items.FindByID(self.jewelpocket, -1, tbox.Serial)
        if p_gem:
            Items.UseItem(p_gem); Misc.Pause(500)
            for i in self.gem_id:
                self.move_all_by_id(i, p_gem.Serial, self.ValuableBox, "[보석류]")

        Player.HeadMessage(55, "[정리] 시약 수거 중...")
        p_reagent = Items.FindByID(self.reagentpocket, -1, tbox.Serial)
        if p_reagent:
            Items.UseItem(p_reagent); Misc.Pause(500)
            for i in self.reagent_id:
                self.move_all_by_id(i, p_reagent.Serial, self.ScrollReagentBox, "[시약]")

        Player.HeadMessage(55, "[정리] 특수재료 수거 중...")
        for i in self.etc_id:
            self.move_all_by_id(i, tbox.Serial, self.ValuableBox, "[특수재료]")

        Player.HeadMessage(55, "[정리] 고가치 아이템 파악 중...")
        for i in self.highvalue_id:
            self.move_all_by_id(i, tbox.Serial, self.HighValueBox, "[고가치]")

        box_obj = Items.FindBySerial(tbox.Serial)
        if box_obj and box_obj.Contains:
            for item in box_obj.Contains:
                if item.ItemID == self.pirate_hat_id:
                    name = str(item.Name).lower() if item.Name else ""
                    if "plunderin" in name or "약탈" in name:
                        Player.HeadMessage(1161, "✨ [대박!] 찐 해적모자 발견!")
                        self.move_all_by_id(self.pirate_hat_id, tbox.Serial, self.HighValueBox, "[찐 해적모자]")
                        break

        Player.HeadMessage(55, "[정리] 부산물 수거 중...")
        for i in self.byproduct_id:
            self.move_all_by_id(i, tbox.Serial, self.ByproductBox, "[부산물]")

    def unravel_box(self, tbox):
        Player.HeadMessage(68, "[임뷰] 컨테이너 해체 중...")
        Player.UseSkill("Imbuing")
        if Gumps.WaitForGump(0x65290b89, 3000):
            Gumps.SendAction(0x65290b89, 10011)
            Target.WaitForTarget(5000)
            Target.TargetExecute(tbox.Serial)
            if Gumps.WaitForGump(0xb73e81bb, 5000):
                Gumps.SendAction(0xb73e81bb, 1)
                Misc.Pause(2000)
        
        for uid in self.UnravelIDs:
            while True:
                res = Items.FindByID(uid, -1, Player.Backpack.Serial)
                if not res: break
                if self.move_item(res, self.ResidueBox):
                    self.record_item("[임뷰 재료]")
                    Player.HeadMessage(68, "[임뷰] 재료 보관: {}".format(str(res.Name) if res.Name else "ID:{:X}".format(uid)))
                Misc.Pause(600)

    def process_one_box(self, tbox_serial):
        tbox = Items.FindBySerial(tbox_serial)
        if not tbox: return
        Player.HeadMessage(55, "[정리모듈] 상자를 백팩으로 꺼내는 중...")
        Items.Move(tbox, Player.Backpack, -1)
        Misc.Pause(1000)
        
        tbox = Items.FindBySerial(tbox_serial)
        if not tbox:
            Player.HeadMessage(33, "[정리모듈] 상자를 백팩으로 가져오지 못했습니다.")
            return

        Player.HeadMessage(68, "[정리모듈] 상자 파헤치기 시작!")
        self.extract_valuables(tbox)

        if self.unravel_mode:
            tbox = Items.FindBySerial(tbox_serial)
            if tbox:
                self.unravel_box(tbox)
            else:
                Player.HeadMessage(33, "[임뷰] 상자가 이미 없어졌습니다. 임뷰 스킵.")
        
        tbox = Items.FindBySerial(tbox_serial)
        if tbox:
            Player.HeadMessage(55, "[정리모듈] 다 턴 빈 상자는 쓰레기통으로...")
            self.move_item(tbox, self.TrashContainer)
            Misc.Pause(600)
            
        self.processed_count += 1
        Player.HeadMessage(68, "[정리모듈] ✅ 상자 1개 처리 완료!")

    def process_if_boxes_exist(self):
        if self.SosChestContainer == 0 or not self.load_config():
            Player.HeadMessage(33, "[정리모듈] 첫 실행이므로 초기 타겟을 설정해야 합니다.")
            self.run_setup()
            
        cont = Items.FindBySerial(self.SosChestContainer)
        if not cont:
            return 0 
            
        Items.UseItem(cont); Misc.Pause(800)
        cont = Items.FindBySerial(self.SosChestContainer)
        
        boxes = []
        if cont and cont.Contains:
            boxes = [item.Serial for item in cont.Contains if item.ItemID in self.FishingTreasureBox]
            
        if not boxes:
            return 0 
            
        Player.HeadMessage(68, "[정리모듈] 상자 {}개 발견! 정리 루틴으로 진입합니다.".format(len(boxes)))
        for tbox_serial in boxes:
            try:
                self.process_one_box(tbox_serial)
                Misc.Pause(500)
            except Exception as e:
                Player.HeadMessage(33, "[정리모듈] 오류 발생: " + str(e))
                Misc.Pause(1000)
                
        # --- Pass 1: 백팩 잔류 상자 처리 ---
        while True:
            leftover = None
            for fid in self.FishingTreasureBox:
                leftover = Items.FindByID(fid, -1, Player.Backpack.Serial)
                if leftover: break
            if not leftover: break
            Player.HeadMessage(33, "[정리모듈] 백팩 잔류 상자 재처리 중...")
            self._cleanup_stuck_state()
            self.process_one_box(leftover.Serial)
            Misc.Pause(500)

        # --- Pass 2: 컨테이너 잔류 상자 재처리 (최대 3회) ---
        for attempt in range(3):
            Items.UseItem(cont); Misc.Pause(800)
            cont = Items.FindBySerial(self.SosChestContainer)
            remaining = []
            if cont and cont.Contains:
                remaining = [item.Serial for item in cont.Contains
                             if item.ItemID in self.FishingTreasureBox]
            if not remaining:
                break
            Player.HeadMessage(33, "[정리모듈] 잔류 {}개 재처리 ({}회차)...".format(len(remaining), attempt + 1))
            self._cleanup_stuck_state()
            for tbox_serial in remaining:
                try:
                    self.process_one_box(tbox_serial)
                    Misc.Pause(500)
                except Exception as e:
                    Player.HeadMessage(33, "[정리모듈] 재처리 오류: " + str(e))
        else:
            msg = "[정리모듈] ⚠️ 재시도 3회 후에도 잔류 상자 존재! 수동 확인 필요."
            Player.HeadMessage(33, msg)
            if self.notify_func:
                self.notify_func(msg)

        Player.HeadMessage(68, "[정리모듈] 일괄 처리 및 폐기 완료. 본업 매크로로 복귀합니다.")
        return len(boxes)
        
    def get_report_lines(self):
        lines = [
            "총 처리 상자: {}개".format(self.processed_count),
            "모드: {}".format("임뷰 재료수집" if self.unravel_mode else "일반 쓰레기통 투기"),
            "--- 수집 전리품 ---"
        ]
        priority_keys = ["[고가치]", "[찐 해적모자]", "[임뷰 재료]"]
        if self.looted_items_count:
            for key in priority_keys:
                if key in self.looted_items_count:
                    lines.append("  {} : {}개".format(key, self.looted_items_count[key]))
            for name, count in self.looted_items_count.items():
                if name not in priority_keys:
                    lines.append("  {} : {}개".format(name, count))
        else:
            lines.append("  아직 수집한 아이템이 없습니다.")
            
        return lines
