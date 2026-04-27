# -*- coding: utf-8 -*-
# 06 마법 잔류물 생성기 (Ultimate High-Speed & Batch Sweep Edition)

SCRIPT_ID = "GGO_RESIDUE_CRAFTER"
SCRIPT_NAME = "GGO_레지듀제작기"
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
from System import Environment
from System.IO import Directory, Path, File
from System.Net import WebClient
from System.Text import Encoding
from System.Threading import Thread, ThreadStart

import json
import time
import re
import sys
import os
import ctypes

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from 정리꼬붕_모듈 import SosChestSorter
except:
    pass

# -----------------------------------------------------------------------------
# [1] script_settings.json 기본값
# -----------------------------------------------------------------------------
#
# 이 영역은 script_settings.json 자동 생성 및 공통 설정 모듈 실패 시 fallback용입니다.
# 사용자 설정은 스크립트 파일이 아니라
# GGO_Settings/GGO_레지듀제작기/script_settings.json에서 수정하세요.

INGOT_REFILL_AMOUNT = 5000  # 철 잉곳 한 번에 가져올 수량

RESIDUE_SCRIPT_SETTINGS_DEFAULTS = {
    "ingot_refill_amount": INGOT_REFILL_AMOUNT
}

RESIDUE_SCRIPT_SETTINGS_ORDER = [
    "ingot_refill_amount"
]

RESIDUE_SCRIPT_SETTINGS_GUIDE = """GGO_레지듀제작기 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 레지듀 제작기 운용 설정입니다.
값을 바꾼 뒤 레지듀 제작기 스크립트를 다시 실행하면 적용됩니다.

ingot_refill_amount
  철 잉곳을 한 번에 가져올 수량입니다. 기본값: 5000
"""

_GGO_CONFIG_READY = False
try:
    from GGO_user_config import get_discord_webhook, get_character_settings_path, load_script_settings, ensure_script_settings_guide
    _GGO_CONFIG_READY = True
except Exception:
    pass

if _GGO_CONFIG_READY:
    try:
        ensure_script_settings_guide(SCRIPT_NAME, RESIDUE_SCRIPT_SETTINGS_GUIDE)
        _script_settings = load_script_settings(SCRIPT_NAME, RESIDUE_SCRIPT_SETTINGS_DEFAULTS, RESIDUE_SCRIPT_SETTINGS_ORDER)
        INGOT_REFILL_AMOUNT = int(_script_settings.get("ingot_refill_amount", INGOT_REFILL_AMOUNT))
    except Exception:
        pass

WEBHOOK_URL = ""
try:
    if not WEBHOOK_URL:
        WEBHOOK_URL = get_discord_webhook(True)
except Exception:
    pass

# -----------------------------------------------------------------------------
# 전역 변수 및 설정 경로
# -----------------------------------------------------------------------------
APPDATA = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "ResidueMaker")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "ResidueMaker_Config_{0}.json".format(Player.Name))
SAVE_DIR = LEGACY_SAVE_DIR
CONFIG_FILE = LEGACY_CONFIG_FILE

if _GGO_CONFIG_READY:
    try:
        CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
        SAVE_DIR = Path.GetDirectoryName(CONFIG_FILE)
    except Exception:
        pass

RESOURCE_CHEST = 0
RECYCLE_BAG = 0
RESIDUE_CHEST = 0
sorter = None

try:
    sorter = SosChestSorter()
except:
    pass

is_running = False
residue_count = 0
start_time = time.time()
unravel_fail_count = 0

# 아이템 ID
TINKER_TOOL_ID = 0x1EB8
SMITH_HAMMER_ID = 0x13E3
DAGGER_ID = 0x0F52
RESIDUE_ID = 0x2DB1
INGOT_ID = 0x1BF2
IRON_COLOR = 0x0000

ACTION_DELAY = 1000  
MOVE_DELAY = 1000    

def trim_working_set():
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
    except:
        pass

def find_smallest_stack(item_id, color, container):
    chest = Items.FindBySerial(container)
    if not chest or not chest.Contains:
        return None
    candidates = [i for i in chest.Contains if i.ItemID == item_id and (color == -1 or i.Hue == color)]
    if not candidates:
        return None
    return min(candidates, key=lambda i: i.Amount)

def SendDiscord(msg):
    if not WEBHOOK_URL: return
    def task():
        try:
            wc = WebClient()
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": "🔮 " + msg}, ensure_ascii=False)
            wc.UploadString(WEBHOOK_URL, "POST", payload)
        except: pass
    t = Thread(ThreadStart(task))
    t.IsBackground = True
    t.Start()

def save_config(data):
    if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
    File.WriteAllText(CONFIG_FILE, json.dumps(data, indent=4))
    Player.HeadMessage(68, "[시스템] 설정 저장 완료")

def load_config():
    if not File.Exists(CONFIG_FILE) and File.Exists(LEGACY_CONFIG_FILE):
        try:
            if not Directory.Exists(SAVE_DIR): Directory.CreateDirectory(SAVE_DIR)
            File.Copy(LEGACY_CONFIG_FILE, CONFIG_FILE, False)
        except:
            pass
    if File.Exists(CONFIG_FILE): return json.loads(File.ReadAllText(CONFIG_FILE))
    return None

def run_setup():
    global RESOURCE_CHEST, RECYCLE_BAG, RESIDUE_CHEST
    Player.HeadMessage(158, "● [설정] 잉곳 보관함을 선택하세요")
    rc = Target.PromptTarget("Select Ingot Chest")
    Player.HeadMessage(158, "● [설정] 대거 제작 및 해체용 가방을 선택하세요")
    rb = Target.PromptTarget("Select Recycle Bag")
    Player.HeadMessage(158, "● [설정] 잔류물을 모을 상자를 선택하세요")
    resc = Target.PromptTarget("Select Residue Chest")

    data = {
        "RESOURCE_CHEST": rc,
        "RECYCLE_BAG": rb,
        "RESIDUE_CHEST": resc
    }
    save_config(data)
    RESOURCE_CHEST = rc
    RECYCLE_BAG = rb
    RESIDUE_CHEST = resc
    return data

MAIN_GUMP_ID = 0x47471250
REPORT_GUMP_ID = 0x47471251

def show_main_gump():
    Gumps.CloseGump(MAIN_GUMP_ID)
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 280, 220, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 280, 220)

    Gumps.AddLabel(gd, 15, 12, 53, "🔮 마법 잔류물 생성기 & 정리꼬붕")
    Gumps.AddImageTiled(gd, 10, 32, 260, 2, 9107)

    elapsed = int(time.time() - start_time)
    status_hue = 68 if is_running else 33
    status_txt = "▶ 작동 중 (무한)" if is_running else "■ 대기 중"
    
    Gumps.AddLabel(gd, 15, 38, status_hue, status_txt)
    Gumps.AddLabel(gd, 15, 58, 1152, "누적 레지듀 획득: {:,} 개".format(residue_count))
    Gumps.AddLabel(gd, 15, 78, 1152, "구동 시간: {}분".format(elapsed // 60))

    Gumps.AddImageTiled(gd, 10, 98, 260, 2, 9107)

    if is_running:
        Gumps.AddButton(gd, 15,  110, 40297, 40298, 6, 1, 0) # 정지
        Gumps.AddLabel(gd, 53,  112, 33,   "정지")
    else:
        Gumps.AddButton(gd, 15,  110, 40030, 40031, 1, 1, 0) # 시작
        Gumps.AddLabel(gd, 53,  112, 68,   "시작")
        
    Gumps.AddButton(gd, 150, 110, 40297, 40298, 2, 1, 0) # 종료
    Gumps.AddLabel(gd, 188, 112, 33,   "종료")

    Gumps.AddButton(gd, 15,  150, 40021, 40031, 3, 1, 0) # 셋업
    Gumps.AddLabel(gd, 53,  152, 1152, "재설정")
    
    unravel_hue = 1152
    unravel_txt = "임뷰 OFF"
    if sorter and getattr(sorter, "unravel_mode", False):
        unravel_hue = 68
        unravel_txt = "임뷰 ON"
    Gumps.AddButton(gd, 150, 150, 40299, 40300, 4, 1, 0) # 임뷰 토글
    Gumps.AddLabel(gd, 188, 152, unravel_hue, unravel_txt)
    
    Gumps.AddButton(gd, 15, 180, 40021, 40031, 5, 1, 0) # 보고서
    Gumps.AddLabel(gd, 53, 182, 53, "정리 보고서")

    Gumps.SendGump(MAIN_GUMP_ID, Player.Serial, 100, 100, gd.gumpDefinition, gd.gumpStrings)

def show_report_gump():
    Gumps.CloseGump(REPORT_GUMP_ID)
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)

    lines = [
        "=== 정리 시스템 보고서 ===",
        "",
        "경과 시간: {}분".format(int(time.time() - start_time) // 60),
        ""
    ]
    
    if sorter:
        lines.extend(sorter.get_report_lines())
    else:
        lines.append("⚠️ 오류: 정리꼬붕 모듈 파일을 찾을 수 없습니다.")

    gh = 60 + (len(lines) * 20) + 45
    gw = 300
    Gumps.AddBackground(gd, 0, 0, gw, gh, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, gw, gh)
    Gumps.AddLabel(gd, 15, 15, 53, "📊 SOS 정리기 중간 보고")

    y = 45
    for line in lines:
        hue = 1152
        if line.startswith("===") or line.startswith("---"):
            hue = 53
        Gumps.AddLabel(gd, 20, y, hue, line)
        y += 20

    close_y = y + 5
    Gumps.AddButton(gd, 120, close_y, 40297, 40298, 1, 1, 0)
    Gumps.AddLabel(gd, 165, close_y + 2, 900, "닫기")
    Gumps.SendGump(REPORT_GUMP_ID, Player.Serial, 420, 100, gd.gumpDefinition, gd.gumpStrings)

def safe_move_item(item_id, color, amount, dest_serial, src_container, label, src_item=None):
    if src_item is None:
        src_item = Items.FindByID(item_id, color, src_container)
    if not src_item:
        Player.HeadMessage(33, "!!! [재료 부족] 상자에 {} 가 없거나 인식이 안됩니다 !!!".format(label))
        return "RETRY"
        
    Player.HeadMessage(68, "[보충] {} 확보 중 (랙 대기/검증)...".format(label))
    Items.Move(src_item, dest_serial, amount)
    
    timeout = 0
    while timeout < 15:
        Misc.Pause(200)
        verify_items = Items.FindByID(item_id, color, dest_serial)
        if verify_items and verify_items.Amount >= min(amount, src_item.Amount):
            return "SUCCESS"
        timeout += 1

    Target.Cancel()
    Player.HeadMessage(33, "[경고] {} 이동 타임아웃! 렉 걸림.".format(label))
    Items.DropFromHand(Player.Backpack, Player.Backpack)
    Misc.Pause(600)
    return "RETRY"

def ensure_tools_and_materials():
    if RESOURCE_CHEST == 0:
        Player.HeadMessage(33, "[경고] 자원 상자 타겟이 비어있습니다. 재설정을 누르세요.")
        return "RETRY"
        
    ingots = Items.FindByID(INGOT_ID, IRON_COLOR, Player.Backpack.Serial)
    tools_count = Items.BackpackCount(TINKER_TOOL_ID, -1)
    hammer = Items.FindByID(SMITH_HAMMER_ID, -1, Player.Backpack.Serial)
    if not hammer:
        hammer = Items.FindByID(SMITH_HAMMER_ID, -1, RECYCLE_BAG)

    needs_refill = (not ingots or ingots.Amount < 20) or (tools_count < 2) or (not hammer)
    
    if needs_refill:
        Items.UseItem(RESOURCE_CHEST)
        Misc.Pause(600)

        if not ingots or ingots.Amount < 20:
            smallest_ingot = find_smallest_stack(INGOT_ID, IRON_COLOR, RESOURCE_CHEST)
            res = safe_move_item(INGOT_ID, IRON_COLOR, INGOT_REFILL_AMOUNT, Player.Backpack.Serial, RESOURCE_CHEST, "철 잉곳", src_item=smallest_ingot)
            if res != "SUCCESS": return res
            Misc.Pause(MOVE_DELAY)

        while Items.BackpackCount(TINKER_TOOL_ID, -1) < 2:
            t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
            if not t_tool:
                res = safe_move_item(TINKER_TOOL_ID, -1, 1, Player.Backpack.Serial, RESOURCE_CHEST, "비상용 팅커 도구")
                if res != "SUCCESS": return res
                Misc.Pause(MOVE_DELAY)
                t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
            
            if t_tool:
                Player.HeadMessage(55, "[제작] 팅커 도구 자가 보충 중...")
                Gumps.CloseGump(0x38920ABD)
                Misc.Pause(200)
                Items.UseItem(t_tool)
                if Gumps.WaitForGump(0x38920ABD, 2500):
                    Gumps.SendAction(0x38920ABD, 15)
                    Gumps.WaitForGump(0x38920ABD, 2000)
                    Gumps.SendAction(0x38920ABD, 23)
                    Gumps.WaitForGump(0x38920ABD, 2000)
                    Gumps.CloseGump(0x38920ABD)
            else:
                break

        loop_breaker = 0
        while (not Items.FindByID(SMITH_HAMMER_ID, -1, Player.Backpack.Serial) and
               not Items.FindByID(SMITH_HAMMER_ID, -1, RECYCLE_BAG) and loop_breaker < 10):
            t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
            if not t_tool: break
            
            Player.HeadMessage(55, "[제작] 대장장이 망치 조달 중...")
            Gumps.CloseGump(0x38920ABD) 
            Misc.Pause(200)
            Items.UseItem(t_tool)
            if Gumps.WaitForGump(0x38920ABD, 2500):
                Gumps.SendAction(0x38920ABD, 15) 
                Gumps.WaitForGump(0x38920ABD, 2000)
                Gumps.SendAction(0x38920ABD, 93) 
                Gumps.WaitForGump(0x38920ABD, 2000)
                Gumps.CloseGump(0x38920ABD) 
            loop_breaker += 1
            
        if loop_breaker >= 10:
            return "RETRY"

    # 망치를 RECYCLE_BAG 안으로 이동 — 중복 검증 루프
    if RECYCLE_BAG != 0:
        for attempt in range(5):
            hammer_in_pack = Items.FindByID(SMITH_HAMMER_ID, -1, Player.Backpack.Serial)
            if not hammer_in_pack:
                break  # 백팩에 없으면 루프 종료
            Player.HeadMessage(55, "[검증] 망치 → RECYCLE_BAG 이동 시도 ({}/5)...".format(attempt + 1))
            Items.Move(hammer_in_pack, RECYCLE_BAG, -1)
            Misc.Pause(MOVE_DELAY)

        # 최종 확인: 망치가 실제로 RECYCLE_BAG 안에 있는지 검증
        if not Items.FindByID(SMITH_HAMMER_ID, -1, RECYCLE_BAG):
            Player.HeadMessage(33, "[경고] 망치 이동 최종 실패 — 재시도 필요")
            return "RETRY"

    return "SUCCESS"

def craft_daggers():
    # ★ 사용자 제공 로직: 레지듀 추적 룰 준수를 위한 카운트 제외 완벽 1:1 이식
    chk = ensure_tools_and_materials()
    if chk != "SUCCESS":
        return chk 

    hammer = Items.FindByID(SMITH_HAMMER_ID, -1, RECYCLE_BAG)
    if not hammer:
        # 혹시 백팩에 남아있으면 즉시 이동 후 재확인
        stray = Items.FindByID(SMITH_HAMMER_ID, -1, Player.Backpack.Serial)
        if stray:
            Items.Move(stray, RECYCLE_BAG, -1)
            Misc.Pause(MOVE_DELAY)
            hammer = Items.FindByID(SMITH_HAMMER_ID, -1, RECYCLE_BAG)
        if not hammer:
            return "RETRY"

    Gumps.CloseGump(0x38920ABD)
    Misc.Pause(200)
    Items.UseItem(hammer)
    
    if Gumps.WaitForGump(0x38920ABD, 2500):
        Gumps.SendAction(0x38920ABD, 22) # Blades
        Gumps.WaitForGump(0x38920ABD, 2000)
        Gumps.SendAction(0x38920ABD, 30) # Dagger
        Misc.Pause(1000)
        Gumps.CloseGump(0x38920ABD)
        # 대거가 RECYCLE_BAG에 바로 생성됨 — 별도 이동 불필요
    else:
        return "RETRY"

    return "SUCCESS"

def _do_stuck_recovery():
    global unravel_fail_count, is_running
    Player.HeadMessage(33, "[복구] 임뷰잉 창 멈춤 감지 — 강제 초기화 중...")
    Gumps.CloseGump(0x65290b89)
    Gumps.CloseGump(0xb73e81bb)
    Gumps.CloseGump(0x38920ABD)
    Target.Cancel()
    Misc.Pause(2000)
    unravel_fail_count = 0
    Player.HeadMessage(68, "[복구] 초기화 완료 — 재시도합니다.")

def unravel_and_cleanup():
    global residue_count, unravel_fail_count

    # [0] 사전 싹쓸이: 해체 전 백팩에 남아있는 대거를 수거 가방으로 일괄 몰아넣기
    leftovers = Items.FindByID(DAGGER_ID, -1, Player.Backpack.Serial)
    if leftovers:
        Player.HeadMessage(55, "[시스템] 백팩 내 미수거 대거 싹쓸이 중...")
        breaker = 0
        while leftovers and breaker < 20:
            Items.Move(leftovers, RECYCLE_BAG, -1)
            Misc.Pause(600)
            leftovers = Items.FindByID(DAGGER_ID, -1, Player.Backpack.Serial)
            breaker += 1

    # [1] 해체 (Unravel)
    if Items.ContainerCount(RECYCLE_BAG, DAGGER_ID) > 0:
        dagger_before = Items.ContainerCount(RECYCLE_BAG, DAGGER_ID)

        Player.HeadMessage(68, "[임뷰] 대거 해체 작업 시작")

        # 사전 검프 클리어
        Gumps.CloseGump(0x65290b89)
        Gumps.CloseGump(0xb73e81bb)
        Target.Cancel()
        Misc.Pause(300)

        Player.UseSkill("Imbuing")
        if Gumps.WaitForGump(0x65290b89, 2000):
            Gumps.SendAction(0x65290b89, 10011) # Unravel Container
            Target.WaitForTarget(3000)
            Target.TargetExecute(RECYCLE_BAG)

            if Gumps.WaitForGump(0xb73e81bb, 5000):
                Gumps.SendAction(0xb73e81bb, 1) # OK
                Misc.Pause(2000)

        # 사후 검프 클리어
        Gumps.CloseGump(0x65290b89)
        Gumps.CloseGump(0xb73e81bb)
        Target.Cancel()

        # 막힘 감지: 대거 수량이 줄지 않으면 실패
        dagger_after = Items.ContainerCount(RECYCLE_BAG, DAGGER_ID)
        if dagger_after >= dagger_before:
            unravel_fail_count += 1
            Player.HeadMessage(33, "[경고] 해체 실패 감지 ({}/10)".format(unravel_fail_count))
            if unravel_fail_count >= 10:
                is_running = False
                SendDiscord("🚨 임뷰잉 해체 10회 연속 실패 — 자동 정지. 수동 확인 필요.")
                Player.HeadMessage(33, "[긴급 정지] 해체 10회 연속 실패. 스크립트를 멈춥니다.")
                show_main_gump()
                return
            _do_stuck_recovery()
            return
        else:
            unravel_fail_count = 0
            # 익셉셔널 망치가 함께 해체됐을 경우 즉시 재제작
            if not Items.FindByID(SMITH_HAMMER_ID, -1, RECYCLE_BAG):
                Player.HeadMessage(55, "[복구] 익셉셔널 망치 소실 감지 — 재제작 중...")
                ensure_tools_and_materials()

    # [2] 잔류물 정리 및 수량 갱신
    res = Items.FindByID(RESIDUE_ID, -1, Player.Backpack.Serial)
    if res:
        Player.HeadMessage(55, "[정리] 생성된 잔류물 이동 및 카운트 중...")
        gained = 0
        while res:
            gained += res.Amount
            Items.Move(res, RESIDUE_CHEST, -1)
            Misc.Pause(800)
            res = Items.FindByID(RESIDUE_ID, -1, Player.Backpack.Serial)
        
        if gained > 0:
            residue_count += gained
            show_main_gump() 

def main():
    global is_running, RESOURCE_CHEST, RECYCLE_BAG, RESIDUE_CHEST
    
    Journal.Clear()
    config = load_config()
    if not config:
        run_setup()
    else:
        RESOURCE_CHEST = config.get("RESOURCE_CHEST", 0)
        RECYCLE_BAG = config.get("RECYCLE_BAG", 0)
        RESIDUE_CHEST = config.get("RESIDUE_CHEST", 0)

    show_main_gump()
    
    while True:
        Misc.Pause(100)
        
        gd = Gumps.GetGumpData(MAIN_GUMP_ID)
        btn = 0
        if gd and gd.buttonid > 0:
            btn = gd.buttonid
            Gumps.SendAction(MAIN_GUMP_ID, 0)
            Gumps.CloseGump(MAIN_GUMP_ID)

        rd = Gumps.GetGumpData(REPORT_GUMP_ID)
        if rd and rd.buttonid > 0:
            Gumps.SendAction(REPORT_GUMP_ID, 0)
            Gumps.CloseGump(REPORT_GUMP_ID)

        if btn == 2:  
            Player.HeadMessage(33, "[시스템] 스크립트를 종료합니다.")
            Gumps.CloseGump(REPORT_GUMP_ID)
            break
        elif btn == 1:  
            is_running = True
            if sorter and not sorter.load_config():
                Player.HeadMessage(55, "[정리꼬붕] 모듈 초기 설정을 진행합니다.")
                sorter.run_setup()
            Player.HeadMessage(68, "[시작] 작업 가동 (초기 싹쓸이 및 정리 진행)")
            show_main_gump()
            
            # [최초 실행 시 1회 강제 전처리 및 상자 스캔]
            unravel_and_cleanup()
            if sorter:
                processed = sorter.process_if_boxes_exist()
                if processed > 0:
                    show_main_gump()
            trim_working_set()

        elif btn == 6:  
            is_running = False
            Player.HeadMessage(33, "[정지] 작업 중지")
            show_main_gump()
        elif btn == 3:  
            was_running = is_running
            is_running = False
            run_setup()
            if sorter:
                Player.HeadMessage(55, "[정리꼬붕] 이어서 정리 모듈의 타겟도 재설정합니다!")
                sorter.run_setup()
            is_running = was_running
            show_main_gump()
        elif btn == 4:  
            if sorter:
                state = sorter.toggle_unravel_mode()
                Player.HeadMessage(68 if state else 33, "[정리꼬붕] 임뷰 모드: " + ("ON" if state else "OFF"))
            show_main_gump()
        elif btn == 5:  
            show_report_gump()
            show_main_gump()

        if is_running:
            # [1] 70개 달성까지 초고속 생산 루프
            while is_running and Items.ContainerCount(RECYCLE_BAG, DAGGER_ID) < 70:
                craft_res = craft_daggers()
                
                if craft_res == "FATAL":
                    is_running = False
                    SendDiscord("⚠️ 잔류물 작업: 재료 바닥 발생. 자동 정지.")
                    show_main_gump()
                    break
                elif craft_res == "RETRY":
                    Misc.Pause(1000) 
                    
                # ★ 속도 저하(렉) 해결의 핵심: 클라이언트 숨고르기
                Misc.Pause(100)

                dagger_count = Items.ContainerCount(RECYCLE_BAG, DAGGER_ID)
                if dagger_count > 0 and dagger_count % 10 == 0:
                    trim_working_set()
                
                # 긴급 정지 버튼 감지
                gd_inner = Gumps.GetGumpData(MAIN_GUMP_ID)
                if gd_inner and gd_inner.buttonid == 6:
                    is_running = False
                    Player.HeadMessage(33, "[정지] 작업 중지")
                    show_main_gump()
                    break

            if is_running and Items.ContainerCount(RECYCLE_BAG, DAGGER_ID) >= 70:
                # [2] 70개 도달 시 해체 및 잔류물 정리
                unravel_and_cleanup()
                
                # [3] 한 사이클 종료 시 즉각 정리 모듈 호출
                if sorter:
                    processed = sorter.process_if_boxes_exist()
                    if processed > 0:
                        show_main_gump()
                trim_working_set()

if __name__ == "__main__":
    main()
