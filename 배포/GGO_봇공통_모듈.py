# -*- coding: utf-8 -*-
# =============================================================================
# GGO_봇공통_모듈 — 바드봇 / 쓰로잉봇 / 기타 봇 공용 유틸리티
# RE IronPython: Player, Items 등 RE API는 __builtins__에 자동 주입됨
# 사용법:
#   import sys, os
#   _dir = os.path.dirname(os.path.abspath(__file__))
#   if _dir not in sys.path: sys.path.insert(0, _dir)
#   from GGO_봇공통_모듈 import trim_working_set, collect_all_items, ...
# =============================================================================

SCRIPT_ID = "GGO_COMMON"
SCRIPT_NAME = "GGO_봇공통_모듈"
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
from System import Int32
import ctypes
import time

_bos_recharge_fail_streak = 0


# =============================================================================
# [메모리 최적화]
# =============================================================================
def trim_working_set():
    """프로세스 메모리 워킹셋 최적화 (Windows 전용)"""
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
    except:
        pass


# =============================================================================
# [상하차 유틸리티]
# =============================================================================
def collect_all_items(container_serial):
    """컨테이너 및 모든 하위 컨테이너의 아이템 시리얼을 재귀적으로 수집"""
    result = set()
    container = Items.FindBySerial(container_serial)
    if not container or not container.Contains:
        return result
    for item in container.Contains:
        result.add(item.Serial)
        if item.Contains and len(item.Contains) > 0:
            result.update(collect_all_items(item.Serial))
    return result


def get_movable_items(container_serial, protected, food_ids=None):
    """
    보호 리스트에 없는 아이템 시리얼만 수집 (재귀).
    food_ids: 이동 제외할 먹이 ItemID 리스트 (None이면 먹이 필터 없음)
    """
    result = []
    container = Items.FindBySerial(container_serial)
    if not container or not container.Contains:
        return result
    for item in container.Contains:
        if item.Serial not in protected:
            if food_ids is None or item.ItemID not in food_ids:
                result.append(item.Serial)
        if item.Contains and len(item.Contains) > 0:
            result.extend(get_movable_items(item.Serial, protected, food_ids))
    return result


def do_sanghacha(target_container_serial, protected_serials, food_ids=None):
    """
    보호 리스트에 없는 모든 아이템을 목표 컨테이너로 이동.
    sanghacha_mode 상태 관리는 호출 측에서 담당 (함수 종료 후 False로 리셋할 것).
    food_ids: 이동 제외할 먹이 ItemID 리스트 (None이면 먹이 필터 없음)
    """
    moved = 0
    failed = 0
    all_items = get_movable_items(Player.Backpack.Serial, protected_serials, food_ids)
    if not all_items:
        Player.ChatSay(158, "★상하차: 이동할 아이템 없음★")
        return
    Player.ChatSay(68, "★상하차 시작: {}개 이동 대상★".format(len(all_items)))
    target_item = Items.FindBySerial(target_container_serial)
    if target_item:
        for _approach in range(5):
            ti = Items.FindBySerial(target_container_serial)
            if not ti:
                break
            dx = abs(Player.Position.X - ti.Position.X)
            dy = abs(Player.Position.Y - ti.Position.Y)
            if max(dx, dy) <= 2:
                break
            Player.PathFindTo(ti.Position.X, ti.Position.Y, ti.Position.Z)
            Misc.Pause(1000)
    for item_serial in all_items:
        item = Items.FindBySerial(item_serial)
        if not item:
            continue
        success = False
        for attempt in range(3):
            Items.Move(item, target_container_serial, 0)
            Misc.Pause(600)
            remaining = collect_all_items(Player.Backpack.Serial)
            if item_serial not in remaining:
                success = True
                break
            Misc.Pause(400)
        if success:
            moved += 1
        else:
            failed += 1
    if failed > 0:
        Player.ChatSay(33, "★상하차 완료: {}개 이동 / {}개 실패★".format(moved, failed))
    else:
        Player.ChatSay(68, "★상하차 완료: {}개 이동★".format(moved))


# =============================================================================
# [방향 계산]
# =============================================================================
def calculateDirection(dx, dy):
    if   dx > 0 and dy > 0: return 'Down'
    elif dx > 0 and dy < 0: return 'Right'
    elif dx > 0:             return 'East'
    elif dx < 0 and dy > 0: return 'Left'
    elif dx < 0 and dy < 0: return 'Up'
    elif dx < 0:             return 'West'
    elif dy > 0:             return 'South'
    elif dy < 0:             return 'North'
    return None


# =============================================================================
# [아이템 정리]
# =============================================================================
def do_skull_sort(target_serial):
    """해골 아이템 정리 (검프 버튼 17번)"""
    for _approach in range(5):
        ti = Items.FindBySerial(target_serial)
        if not ti:
            Player.ChatSay(33, "★아이템을 찾을 수 없음★")
            return
        if max(abs(Player.Position.X - ti.Position.X), abs(Player.Position.Y - ti.Position.Y)) <= 2:
            break
        Player.PathFindTo(ti.Position.X, ti.Position.Y, ti.Position.Z)
        Misc.Pause(1000)
    ti = Items.FindBySerial(target_serial)
    if not ti:
        Player.ChatSay(33, "★아이템을 찾을 수 없음★")
        return
    Items.UseItem(ti)
    if Gumps.WaitForGump(0x6abce12, 3000):
        Gumps.SendAction(0x6abce12, 17)
        Misc.Pause(500)
        Gumps.CloseGump(0x6abce12)
        Player.ChatSay(68, "★해골정리 완료★")
    else:
        Player.ChatSay(33, "★검프 응답 없음★")


def do_item_sort(item_id, item_color, target_serial):
    """지정 아이디/색상 아이템을 목표 컨테이너로 이동 (재시도 3회)"""
    found = Items.FindAllByID([item_id], item_color, Player.Backpack.Serial, True)
    if not found:
        Player.ChatSay(33, "★정리할 아이템 없음★")
        return
    for _approach in range(5):
        ti = Items.FindBySerial(target_serial)
        if not ti:
            break
        if max(abs(Player.Position.X - ti.Position.X), abs(Player.Position.Y - ti.Position.Y)) <= 2:
            break
        Player.PathFindTo(ti.Position.X, ti.Position.Y, ti.Position.Z)
        Misc.Pause(1000)
    Player.ChatSay(68, "★정리 시작: {}개★".format(len(found)))
    moved = 0
    failed = 0
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
        Player.ChatSay(33, "★정리 완료: {}개 이동 / {}개 실패★".format(moved, failed))
    else:
        Player.ChatSay(68, "★정리 완료: {}개 이동★".format(moved))


# =============================================================================
# [전송가방 (Bag of Sending)]
# =============================================================================
def find_bag_of_sending():
    """백팩에서 A Bag Of Sending을 툴팁 이름으로 찾아 반환"""
    for item in Player.Backpack.Contains:
        if item.ItemID == 0x0E76:
            try:
                name = Items.GetPropStringByIndex(item, 0) or ""
            except:
                name = item.Name or ""
            if "bag of sending" in name.lower():
                return item
    return None


def get_bos_charges(bos):
    """A Bag Of Sending의 현재 charges 반환. 파싱 실패 시 -1"""
    try:
        for line in Items.GetPropStringList(bos):
            if "charges" in line.lower():
                return int(line.split(":")[-1].strip())
    except:
        pass
    return -1


def recharge_bos(bos):
    """전송가루(0x26B8)로 A Bag Of Sending 충전"""
    global _bos_recharge_fail_streak
    powder = Items.FindByID(0x26B8, -1, Player.Backpack.Serial)
    if not powder:
        Player.ChatSay(33, "★전송가루 없음★")
        return False
    charges_before = get_bos_charges(bos)
    powder_before = Items.BackpackCount(0x26B8, -1)
    Items.UseItem(powder)
    if Target.WaitForTarget(2000, False):
        Target.TargetExecute(bos)
        Misc.Pause(1200)
        charges_after = get_bos_charges(bos)
        powder_after = Items.BackpackCount(0x26B8, -1)
        charge_changed = (charges_before != -1 and charges_after != -1 and charges_after > charges_before)
        powder_used = powder_after < powder_before
        if charge_changed or powder_used:
            _bos_recharge_fail_streak = 0
            Player.ChatSay(68, "★전송가방 충전 완료★")
            return True

        _bos_recharge_fail_streak += 1
        Player.ChatSay(33, "★전송가방 충전 확인 실패 ({}/3)★".format(_bos_recharge_fail_streak))
        if _bos_recharge_fail_streak >= 3:
            Player.ChatSay(33, "★전송가방 수명 종료 의심 - 교체 필요★")
        return False
    return False


# =============================================================================
# [골드 수집 / 전송]
# =============================================================================
def handle_loot(start_msg="★송금 시작★", end_msg="★송금 완료★"):
    """
    주변 골드를 수집하여 전송가방으로 전송.
    start_msg, end_msg: 봇마다 다른 메시지를 전달할 수 있음
      - 바드봇: 기본값 사용
      - 쓰로잉봇: handle_loot("★앵벌이 시작★", "★골드 수집 완료★")
    """
    Journal.Clear()
    Player.ChatSay(68, start_msg)
    skip_serials = set()
    while True:
        items = Items.ApplyFilter(Items.Filter(Graphics=List[Int32]([0x0EED]), RangeMax=12, OnGround=True))
        items = sorted([i for i in items if i.Serial not in skip_serials], key=lambda i: Player.DistanceTo(i))
        if not items:
            break
        tgt = items[0]
        if Player.DistanceTo(tgt) > 2:
            reached = False
            for _ in range(5):
                PathFinding.RunPath(PathFinding.GetPath(tgt.Position.X, tgt.Position.Y, -1), 1500)
                if Player.DistanceTo(tgt) <= 2:
                    reached = True
                    break
                Misc.Pause(300)
            if not reached:
                Player.ChatSay(33, "★골드 접근 실패, 스킵★")
                skip_serials.add(tgt.Serial)
                continue
        Items.Move(tgt, Player.Backpack, 0)
        Misc.Pause(650)
        if Player.Gold >= 60000:
            st = sorted([i for i in Player.Backpack.Contains if i.ItemID == 0x0EED], key=lambda x: x.Amount, reverse=True)
            m = next((s for s in st if s.Amount < 60000), None)
            if m:
                for s in st:
                    if s.Serial == m.Serial:
                        continue
                    Items.Move(s, m.Serial, min(s.Amount, 60000 - m.Amount))
                    Misc.Pause(800)
                    if m.Amount >= 60000:
                        break
            f = next((i for i in Player.Backpack.Contains if i.ItemID == 0x0EED and i.Amount == 60000), None)
            bos = find_bag_of_sending()
            if f and bos:
                Items.UseItem(bos)
                Target.WaitForTarget(2000, False)
                Target.TargetExecute(f)
                Misc.Pause(1500)
                charges = get_bos_charges(bos)
                if charges != -1 and charges <= 10:
                    Player.ChatSay(33, "★전송가방 잔여 charges: {}★ → 충전".format(charges))
                    recharge_bos(bos)
    Player.ChatSay(158, end_msg)


# =============================================================================
# [파워스크롤 판매]
# =============================================================================
def sell_powerscrolls(npc_sell, list_name, use_sell_agent=False):
    """
    파워스크롤 판매 루틴.
    npc_sell      : 판매 NPC 시리얼
    list_name     : Vendor Sell 에이전트 목록 이름
    use_sell_agent: True면 함수 내에서 SellAgent 활성화
                    (봇들은 시작 시 이미 활성화하므로 False,
                     리더컨트롤은 True로 호출)
    """
    if use_sell_agent:
        try:
            SellAgent.ChangeList(list_name)
            SellAgent.Enable()
        except:
            pass

    bank_box = 0
    for attempt in range(3):
        Player.ChatSay(0, "bank")
        Misc.Pause(1500)
        bank_box = Player.Bank.Serial if Player.Bank else 0
        if bank_box:
            break
        Player.ChatSay(33, "★은행 열기 실패 재시도 ({}/3)★".format(attempt + 1))
    if not bank_box:
        Player.ChatSay(33, "★은행 열기 실패 → 판매 중단★")
        return

    Player.ChatSay(158, "★파워스크롤 판매 시작★")
    Mobiles.UseMobile(npc_sell)
    Misc.Pause(400)
    Misc.WaitForContext(npc_sell, 2000)
    Misc.ContextReply(npc_sell, 2)
    Misc.Pause(1500)

    Player.ChatSay(158, "★골드 입금 중★")
    while True:
        gold = Items.FindByID(0x0EED, -1, Player.Backpack.Serial)
        if not gold:
            break
        Items.Move(gold, bank_box, 0)
        Misc.Pause(700)

    filt = Items.Filter()
    filt.Graphics = List[Int32]([0x0EED])
    filt.RangeMax = 2
    filt.OnGround = True
    px, py = Player.Position.X, Player.Position.Y
    while True:
        ground_golds = Items.ApplyFilter(filt)
        exact = [g for g in ground_golds if g.Position.X == px and g.Position.Y == py]
        if not exact:
            break
        Items.Move(exact[0], bank_box, 0)
        Misc.Pause(700)

    Player.ChatSay(68, "★파워스크롤 판매 완료★")


# =============================================================================
# [게이트 이동]
# =============================================================================
def do_gate(gate_serial):
    """지정 시리얼의 게이트를 찾아 이동/진입"""
    gate = Items.FindBySerial(gate_serial)
    if not gate:
        Player.ChatSay(33, "★게이트를 찾을 수 없음★")
        return
    for _ in range(15):
        gate = Items.FindBySerial(gate_serial)
        if not gate:
            break
        if Player.DistanceTo(gate) <= 0:
            break
        PathFinding.RunPath(PathFinding.GetPath(gate.Position.X, gate.Position.Y, -1), 500)
        Misc.Pause(500)
    gate = Items.FindBySerial(gate_serial)
    if not gate:
        Player.ChatSay(33, "★게이트가 사라졌음★")
        return
    Items.UseItem(gate)
    if Gumps.WaitForGump(0xdd8b146a, 1500):
        Gumps.SendAction(0xdd8b146a, 1)
    Misc.IgnoreObject(gate)
    Player.ChatSay(68, "★게이트 진입★")


# =============================================================================
# [헬프 탈출]
# =============================================================================
def do_help_escape():
    """[stuck 채팅 → 검프 버튼 1 클릭으로 스턱 탈출"""
    Player.ChatSay("[stuck")
    if Gumps.WaitForGump(0x1e88ca33, 5000):
        Gumps.SendAction(0x1e88ca33, 1)
        Misc.Pause(500)
        Player.ChatSay(68, "★헬프 탈출 완료★")
    else:
        Player.ChatSay(33, "★헬프 검프 응답 없음★")


# =============================================================================
# [파티 자동 수락]
# =============================================================================
def autoparty():
    """파티 초대 검프 자동 수락"""
    if Gumps.GetGumpData(0x45dd3aa):
        Gumps.SendAction(0x45dd3aa, 1)
        Gumps.CloseGump(0x45dd3aa)
        Misc.Pause(500)


# =============================================================================
# [백팩 하위 컨테이너 동기화]
# =============================================================================
def init_backpack_containers():
    """하위 가방들을 열어 아이템 목록을 클라이언트에 로드 (상하차 보호 등록 전 필수)"""
    if not getattr(Player, 'Backpack', None):
        return
    Player.ChatSay(68, "★하위 가방 동기화 중...★")
    opened_any = False
    container_ids = [0x0E75, 0x0E76, 0x0E79, 0x0E7D, 0x0E80, 0x09B0, 0x0E7A]
    for item in Player.Backpack.Contains:
        if getattr(item, 'IsContainer', False) or item.ItemID in container_ids:
            Items.UseItem(item)
            opened_any = True
            Misc.Pause(600)
    if opened_any:
        Misc.Pause(1000)


# =============================================================================
# [부활 처리]
# =============================================================================
_UNDERTAKER_STAFF_ID = 0x13F8


def make_revival_state():
    """부활/시체 추적 상태 초기화. 각 봇 시작 시 1회 호출."""
    return {
        'was_ghost':            False,
        'my_corpse':            None,
        'corpse_x':             0,
        'corpse_y':             0,
        'last_party_msg_time':  0.0,
        'last_corpse_msg_time': 0.0,
        'just_revived':         False,
    }


def handle_revival(state, dress_name, enable_loot=True, enable_gump=True, use_undertaker=True):
    """
    메인 루프에서 매 사이클 호출.
    반환값: True이면 호출 측에서 continue (유령 상태)
    state['just_revived']: 이번 사이클에 부활 처리가 완료되었으면 True
    enable_loot: False이면 시체 위치 표시만 (루팅 이동 없음, 리더컨트롤용)
    enable_gump: True이면 부활 검프(0xb04c9a31) 자동 수락
    use_undertaker: True이면 부활 후 장의사 지팡이(0x13F8) 사용
    """
    state['just_revived'] = False

    if Player.IsGhost:
        if enable_gump:
            if Gumps.GetGumpData(0xb04c9a31):
                Misc.Pause(500)
                Gumps.SendAction(0xb04c9a31, 1)
                Gumps.CloseGump(0xb04c9a31)

        if not state['was_ghost']:
            state['was_ghost'] = True
            if state['my_corpse'] is None:
                corpses = Items.FindAllByID(0x2006, -1, -1, 2)
                own = next(
                    (c for c in corpses if Player.Name.lower() in (c.Name or "").lower()),
                    None
                )
                if own:
                    state['my_corpse'] = own.Serial
                    state['corpse_x']  = own.Position.X
                    state['corpse_y']  = own.Position.Y
            Player.ChatSay(33, "[보고] 사망. 시체 위치: ({}, {})".format(
                state['corpse_x'], state['corpse_y']))
        return True

    # ── 부활 감지 ──
    if state['was_ghost']:
        Misc.Pause(3000)
        Dress.ChangeList(dress_name)
        Dress.DressFStart()
        Misc.Pause(2000)
        Player.ChatSay(68, "★부활 정비 완료★")
        state['was_ghost']    = False
        state['just_revived'] = True

        if use_undertaker and state['my_corpse'] is not None:
            staff = Items.FindByID(_UNDERTAKER_STAFF_ID, -1, Player.Backpack.Serial)
            if staff:
                px, py = Player.Position.X, Player.Position.Y
                Items.UseItem(staff)
                Player.ChatSay(68, "★장의사 지팡이 사용★")
                summoned = []
                for _ in range(16):
                    Misc.Pause(500)
                    nearby   = Items.FindAllByID(0x2006, -1, -1, 2)
                    summoned = [c for c in nearby if c.Position.X == px and c.Position.Y == py]
                    if summoned:
                        break
                if summoned:
                    for c in summoned:
                        Items.UseItem(c)
                        Misc.Pause(500)
                        Items.UseItem(c)
                        Misc.Pause(500)
                    Player.ChatSay(68, "★장의사 지팡이 루팅 완료: {}개 시체★".format(len(summoned)))
                    state['my_corpse'] = None
                    state['corpse_x']  = 0
                    state['corpse_y']  = 0
                else:
                    Player.ChatSay(33, "★장의사 지팡이: 시체 미소환, 일반 추적으로 전환★")
            else:
                Player.ChatSay(33, "★장의사 지팡이 없음, 일반 추적★")

    # ── 시체 추적 ──
    if state['my_corpse']:
        c = Items.FindBySerial(state['my_corpse'])
        if not c or c.ItemID != 0x2006:
            state['my_corpse'] = None
            state['corpse_x']  = 0
            state['corpse_y']  = 0
            Journal.Clear()
            Player.ChatSay(68, "[시스템] 시체 해골 변환: 추적 해제")
        elif enable_loot:
            dx       = state['corpse_x'] - Player.Position.X
            dy       = state['corpse_y'] - Player.Position.Y
            abs_dist = max(abs(dx), abs(dy))
            now      = time.time()

            if abs_dist > 7 and now - state['last_party_msg_time'] > 5.0:
                dir_str = '알수없음'
                if   dx == 0 and dy < 0: dir_str = '▲ 북쪽'
                elif dx == 0 and dy > 0: dir_str = '▼ 남쪽'
                elif dx < 0 and dy == 0: dir_str = '◀ 서쪽'
                elif dx > 0 and dy == 0: dir_str = '▶ 동쪽'
                elif dx < 0 and dy < 0:  dir_str = '↖ 북서'
                elif dx > 0 and dy < 0:  dir_str = '↗ 북동'
                elif dx < 0 and dy > 0:  dir_str = '↙ 남서'
                elif dx > 0 and dy > 0:  dir_str = '↘ 남동'
                Player.ChatSay(68, '[시스템] 시체 방향 {} / 거리: {}'.format(dir_str, int(abs_dist)))
                state['last_party_msg_time'] = now

            if abs_dist <= 14 and now - state['last_corpse_msg_time'] > 1.0:
                Items.Message(c, 68, "▼ [내 시체] ▼")
                state['last_corpse_msg_time'] = now

            if abs_dist <= 5:
                if abs_dist > 2:
                    Player.PathFindTo(c.Position.X, c.Position.Y, c.Position.Z)
                    Misc.Pause(1000)
                else:
                    Items.UseItem(c); Misc.Pause(500)
                    Items.UseItem(c); Misc.Pause(500)
                    if (Journal.Search("loot this corpse") or Journal.Search("Loot this corpse")
                            or Journal.Search("you may not") or Journal.Search("You may not")):
                        state['my_corpse'] = None
                        state['corpse_x']  = 0
                        state['corpse_y']  = 0
                        Journal.Clear()
                        Player.ChatSay(68, "[시스템] 시체 루팅 완료")
        else:
            now = time.time()
            if now - state['last_corpse_msg_time'] >= 1.0:
                Items.Message(c, 68, "▼ {} 시체 ▼".format(Player.Name))
                state['last_corpse_msg_time'] = now

    return False
