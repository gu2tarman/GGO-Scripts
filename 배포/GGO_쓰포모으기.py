# -*- coding: utf-8 -*-

SCRIPT_ID = "GGO_TRASH_POINT"
SCRIPT_NAME = "GGO_쓰포모으기"
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
# GGO_Settings/GGO_쓰포모으기/script_settings.json에서 수정하세요.

# 자원 보충 설정 (가방에 재료가 바닥났을 때 보관함에서 꺼내올 수량)
INGOT_REFILL_AMOUNT = 500   # 철 잉곳 한 번에 가져올 수량 (가방에 10개 미만일 때)
BOARD_REFILL_AMOUNT = 6000  # 일반 판자 한 번에 가져올 수량 (가방에 15개 미만일 때)
AMBER_REFILL_AMOUNT = 100   # 호박 한 번에 가져올 수량 (가방에 2개 미만일 때)

TRASH_POINT_SCRIPT_SETTINGS_DEFAULTS = {
    "ingot_refill_amount": INGOT_REFILL_AMOUNT,
    "board_refill_amount": BOARD_REFILL_AMOUNT,
    "amber_refill_amount": AMBER_REFILL_AMOUNT
}

TRASH_POINT_SCRIPT_SETTINGS_ORDER = [
    "ingot_refill_amount",
    "board_refill_amount",
    "amber_refill_amount"
]

TRASH_POINT_SCRIPT_SETTINGS_GUIDE = """GGO_쓰포모으기 script_settings.json 설명

이 파일은 업데이트되어도 유지되는 쓰포모으기 운용 설정입니다.
값을 바꾼 뒤 쓰포모으기 스크립트를 다시 실행하면 적용됩니다.

ingot_refill_amount
  철 잉곳을 한 번에 가져올 수량입니다. 기본값: 500

board_refill_amount
  일반 판자를 한 번에 가져올 수량입니다. 기본값: 6000

amber_refill_amount
  호박을 한 번에 가져올 수량입니다. 기본값: 100
"""

_GGO_CONFIG_READY = False
try:
    from GGO_user_config import get_discord_webhook, get_character_settings_path, load_script_settings, ensure_script_settings_guide
    _GGO_CONFIG_READY = True
except Exception:
    pass

if _GGO_CONFIG_READY:
    try:
        ensure_script_settings_guide(SCRIPT_NAME, TRASH_POINT_SCRIPT_SETTINGS_GUIDE)
        _script_settings = load_script_settings(SCRIPT_NAME, TRASH_POINT_SCRIPT_SETTINGS_DEFAULTS, TRASH_POINT_SCRIPT_SETTINGS_ORDER)
        INGOT_REFILL_AMOUNT = int(_script_settings.get("ingot_refill_amount", INGOT_REFILL_AMOUNT))
        BOARD_REFILL_AMOUNT = int(_script_settings.get("board_refill_amount", BOARD_REFILL_AMOUNT))
        AMBER_REFILL_AMOUNT = int(_script_settings.get("amber_refill_amount", AMBER_REFILL_AMOUNT))
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
LEGACY_SAVE_DIR = Path.Combine(APPDATA, "GGO_Project", "SlayerBow")
LEGACY_CONFIG_FILE = Path.Combine(LEGACY_SAVE_DIR, "SlayerBow_Config_{0}.json".format(Player.Name))
SAVE_DIR = LEGACY_SAVE_DIR
CONFIG_FILE = LEGACY_CONFIG_FILE

if _GGO_CONFIG_READY:
    try:
        CONFIG_FILE = get_character_settings_path(SCRIPT_NAME, Player.Name)
        SAVE_DIR = Path.GetDirectoryName(CONFIG_FILE)
    except Exception:
        pass

RESOURCE_CHEST = 0
TRASH_BIN = 0
sorter = None

try:
    sorter = SosChestSorter()
except:
    pass

is_running = False
crafted_count = 0
start_time = time.time()

TINKER_TOOL_ID = 0x1EB8
FLETCHING_TOOL_ID = 0x1022
BOARD_ID = 0x1BD7
PLAIN_WOOD_COLOR = 0x0000
AMBER_ID = 0x3199
INGOT_ID = 0x1BF2
IRON_COLOR = 0x0000
OUTPUT_BOW_ID = 0x2D1E

ACTION_DELAY = 1000  
MOVE_DELAY = 1000    
SCAN_INTERVAL = 100 

def SendDiscord(msg):
    if not WEBHOOK_URL: return
    def task():
        try:
            wc = WebClient()
            wc.Encoding = Encoding.UTF8
            wc.Headers.Add("Content-Type", "application/json")
            payload = json.dumps({"content": "🏹 " + msg}, ensure_ascii=False)
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
    global RESOURCE_CHEST, TRASH_BIN
    Player.HeadMessage(158, "● [설정] 재료(철 잉곳, 판자, 호박) 보관함을 선택하세요")
    rc = Target.PromptTarget("Select Resource Chest")
    Player.HeadMessage(158, "● [설정] 장궁을 버릴 쓰레기통을 선택하세요")
    tb = Target.PromptTarget("Select Trash Bin")

    data = {
        "RESOURCE_CHEST": rc,
        "TRASH_BIN": tb
    }
    save_config(data)
    RESOURCE_CHEST = rc
    TRASH_BIN = tb
    return data

MAIN_GUMP_ID = 0x47471240
REPORT_GUMP_ID = 0x47471241

def show_main_gump():
    Gumps.CloseGump(MAIN_GUMP_ID)
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 280, 220, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 280, 220)

    Gumps.AddLabel(gd, 15, 12, 53, "🏹 학살자 장궁 쓰포 & 정리꼬붕")
    Gumps.AddImageTiled(gd, 10, 32, 260, 2, 9107)

    elapsed = int(time.time() - start_time)
    status_hue = 68 if is_running else 33
    status_txt = "▶ 작동 중 (무한)" if is_running else "■ 대기 중"
    
    trash_points = crafted_count * 1000
    
    Gumps.AddLabel(gd, 15, 38, status_hue, status_txt)
    Gumps.AddLabel(gd, 15, 58, 1152, "누적 Trash Point: {:,} Pt".format(trash_points))
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
    """정리꼬붕 모듈과 연결된 보고서 UI"""
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

def safe_move_item(item_id, color, amount, dest_serial, src_container, label):
    existing_items = Items.FindByID(item_id, color, dest_serial)
    existing_amount = existing_items.Amount if existing_items else 0
    
    src_item = Items.FindByID(item_id, color, src_container)
    if not src_item:
        Player.HeadMessage(33, "!!! [재료 부족] 상자에 {} (ID:{:X})가 없거나 인식이 안됩니다 !!!".format(label, item_id))
        return "RETRY"
        
    Player.HeadMessage(68, "[보충] {} {}개 확보 중 (랙 대기/검증)...".format(label, amount))
    Items.Move(src_item, dest_serial, amount)
    
    timeout = 0
    while timeout < 15:
        Misc.Pause(200)
        verify_items = Items.FindByID(item_id, color, dest_serial)
        if verify_items and verify_items.Amount >= min(amount, src_item.Amount):
            return "SUCCESS"
        timeout += 1

    Target.Cancel()
    Player.HeadMessage(33, "[경고] {} 이동 타임아웃! 렉 걸림. 손을 털고 재시도합니다.".format(label))
    Items.DropFromHand(Player.Backpack, Player.Backpack)
    Misc.Pause(600)
    return "RETRY"

def ensure_tools_and_materials():
    if RESOURCE_CHEST == 0:
        Player.HeadMessage(33, "[경고] 자원 상자 타겟이 비어있습니다. 재설정을 누르세요.")
        return "RETRY"
        
    Items.UseItem(RESOURCE_CHEST)
    Misc.Pause(600)

    ingots_in_pack = Items.FindByID(INGOT_ID, IRON_COLOR, Player.Backpack.Serial)
    if not ingots_in_pack or ingots_in_pack.Amount < 10:
        res = safe_move_item(INGOT_ID, IRON_COLOR, INGOT_REFILL_AMOUNT, Player.Backpack.Serial, RESOURCE_CHEST, "철 잉곳")
        if res != "SUCCESS": return res
        Misc.Pause(MOVE_DELAY)

    boards_in_pack = Items.FindByID(BOARD_ID, PLAIN_WOOD_COLOR, Player.Backpack.Serial)
    if not boards_in_pack or boards_in_pack.Amount < 15:
        res = safe_move_item(BOARD_ID, PLAIN_WOOD_COLOR, BOARD_REFILL_AMOUNT, Player.Backpack.Serial, RESOURCE_CHEST, "일반 판자")
        if res != "SUCCESS": return res
        Misc.Pause(MOVE_DELAY)

    amber_in_pack = Items.FindByID(AMBER_ID, -1, Player.Backpack.Serial)
    if not amber_in_pack or amber_in_pack.Amount < 2:
        res = safe_move_item(AMBER_ID, -1, AMBER_REFILL_AMOUNT, Player.Backpack.Serial, RESOURCE_CHEST, "호박")
        if res != "SUCCESS": return res
        Misc.Pause(MOVE_DELAY)

    # [수정] 팅커툴 자가 생산 및 3개 유지 로직
    while Items.BackpackCount(TINKER_TOOL_ID, -1) < 3:
        # 팅커툴 제작 전 잉곳 체크 및 보충
        ingots_in_pack = Items.FindByID(INGOT_ID, IRON_COLOR, Player.Backpack.Serial)
        if not ingots_in_pack or ingots_in_pack.Amount < 2:
            res = safe_move_item(INGOT_ID, IRON_COLOR, INGOT_REFILL_AMOUNT, Player.Backpack.Serial, RESOURCE_CHEST, "철 잉곳")
            if res != "SUCCESS": return res
            Misc.Pause(MOVE_DELAY)

        t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
        if not t_tool:
            # 아예 없는 경우에만 보관함에서 1개 확보 (생산 체인 시작용)
            res = safe_move_item(TINKER_TOOL_ID, -1, 1, Player.Backpack.Serial, RESOURCE_CHEST, "팅커 도구")
            if res != "SUCCESS": return res
            Misc.Pause(MOVE_DELAY)
            t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
        
        if t_tool:
            Player.HeadMessage(55, "[제작] 팅커 도구 자가 보충 중 (3개 유지)...")
            Gumps.CloseGump(0x38920ABD)
            Misc.Pause(200)
            Items.UseItem(t_tool)
            Misc.Pause(500)
            if Gumps.WaitForGump(0x38920ABD, 2500):
                Gumps.SendAction(0x38920ABD, 15) # Tools
                Misc.Pause(500)
                Gumps.SendAction(0x38920ABD, 23) # Tinker's Toolkit
                Misc.Pause(2000)
                Gumps.CloseGump(0x38920ABD)
        else:
            break

    # 마이닝 인핸스 벤치마킹: 도구를 여러 번 확실하게 제작/검증하는 while 루프
    loop_breaker = 0
    while not Items.FindByID(FLETCHING_TOOL_ID, -1, Player.Backpack.Serial) and loop_breaker < 10:
        t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
        if not t_tool:
            res = safe_move_item(TINKER_TOOL_ID, -1, 1, Player.Backpack.Serial, RESOURCE_CHEST, "팅커 도구")
            if res != "SUCCESS": return res
            Misc.Pause(MOVE_DELAY)
            t_tool = Items.FindByID(TINKER_TOOL_ID, -1, Player.Backpack.Serial)
        
        if t_tool:
            Player.HeadMessage(55, "[제작] 화살대 깎기 도구 조달 중...")
            Gumps.CloseGump(0x38920ABD) # 꼬여있을 수 있는 검프 미리 닫기
            Misc.Pause(200)
            Items.UseItem(t_tool)
            Misc.Pause(500)
            if Gumps.WaitForGump(0x38920ABD, 2500):
                Gumps.SendAction(0x38920ABD, 142) 
                Misc.Pause(2000) # 제작 완료 넉넉한 대기 (마이닝 인핸스 참조)
                Gumps.CloseGump(0x38920ABD) # 검프 확실하게 닫아주기
        loop_breaker += 1
        
    if loop_breaker >= 10:
        Player.HeadMessage(33, "[경고] 도구 제작 루프 무한 반복 감지 (재시도)")
        return "RETRY"

    return "SUCCESS"

def craft_one_bow_cycle():
    global crafted_count
    
    chk = ensure_tools_and_materials()
    if chk != "SUCCESS":
        return chk 

    f_tool = Items.FindByID(FLETCHING_TOOL_ID, -1, Player.Backpack.Serial)
    if not f_tool:
        Player.HeadMessage(33, "[경고] 도구가 인벤토리에 없습니다! (렉 의심, 재시도)")
        return "RETRY"

    Items.UseItem(f_tool)
    if Gumps.WaitForGump(0x38920ABD, 2500):
        Gumps.SendAction(0x38920ABD, 15)
        Misc.Pause(ACTION_DELAY) 
        
        Journal.Clear()
        Gumps.SendAction(0x38920ABD, 100)
        
        success = False
        bow_found = None
        for i in range(25): 
            bow_found = Items.FindByID(OUTPUT_BOW_ID, -1, Player.Backpack.Serial)
            if bow_found:
                success = True
                break
            
            if Journal.SearchByType("You fail", "Regular") or Journal.SearchByType("failed", "Regular"):
                return "FAIL_CRAFT" 
            Misc.Pause(SCAN_INTERVAL)

        if success and bow_found:
            if TRASH_BIN != 0:
                Items.Move(bow_found, TRASH_BIN, 1)
                timeout = 0
                while timeout < 10:
                    Misc.Pause(200)
                    if Items.FindBySerial(bow_found.Serial) is None or Items.FindBySerial(bow_found.Serial).Container == TRASH_BIN:
                        break
                    timeout += 1
                Target.Cancel()
                
            crafted_count += 1
            # 검프 업데이트는 지시대로 모듈 실행 이후로 미룸
        else:
            return "RETRY"
    else:
        return "RETRY"
            
    return "SUCCESS"

def main():
    global is_running, RESOURCE_CHEST, TRASH_BIN
    
    Journal.Clear()
    config = load_config()
    if not config:
        run_setup()
    else:
        RESOURCE_CHEST = config.get("RESOURCE_CHEST", 0)
        TRASH_BIN = config.get("TRASH_BIN", 0)

    show_main_gump()
    last_sos_check_time = time.time()
    
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
                Player.HeadMessage(55, "[정리꼬붕] 모듈 초기 설정이 비어있습니다. 최초 1회 설정을 진행합니다.")
                sorter.run_setup()
                
            last_sos_check_time = 0  # <--- 매번 시작 시 즉각 꼬붕 발동!
            Player.HeadMessage(68, "[시작] 무한 장궁 제작 가동")
            show_main_gump()
        elif btn == 6:  
            is_running = False
            Player.HeadMessage(33, "[정지] 장궁 제작 중지")
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
            # [결합 포인트] 상자 정리 꼬붕 구동간격 체크 (최우선 순위로 실행)
            if time.time() - last_sos_check_time >= 180:
                if sorter:
                    processed = sorter.process_if_boxes_exist()
                    if processed > 0:
                        show_main_gump() # 상자를 처리했을 경우에만 메인 갱신
                
                # 작업이 모두 끝난 직후의 시간을 기록하여, 완료 시점으로부터 3분을 잽니다.
                last_sos_check_time = time.time()
            
            # 수량 제한 삭제 및 무한 반복
            craft_res = craft_one_bow_cycle()
            
            if craft_res == "FATAL":
                is_running = False
                SendDiscord("⚠️ 장궁 제작: 재료 바닥 (철 잉곳, 판자, 팅커 도구 등) 발생하여 매크로 자동 정지.")
                show_main_gump()
                continue
            elif craft_res == "RETRY":
                Misc.Pause(1500) 
                continue
            elif craft_res == "FAIL_CRAFT":
                pass
            elif craft_res == "SUCCESS":
                pass

if __name__ == "__main__":
    main()
