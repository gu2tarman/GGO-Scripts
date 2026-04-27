# -*- coding: utf-8 -*-
# stack_organizer.py — 컨테이너 내 동일 아이템을 6만개 단위로 정리

SCRIPT_ID = "GGO_STACK_ORGANIZER"
SCRIPT_NAME = "GGO_6만스택_organizer"
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

import sys

MAX_STACK  = 60000
MOVE_DELAY = 600   # ms

STACK_SCRIPT_SETTINGS_DEFAULTS = {
    "max_stack": MAX_STACK,
    "move_delay": MOVE_DELAY
}

STACK_SCRIPT_SETTINGS_ORDER = [
    "max_stack",
    "move_delay"
]

STACK_SCRIPT_SETTINGS_GUIDE = """GGO_6만스택_organizer script_settings.json 설명

이 파일은 6만스택 정리기의 공용 설정 파일입니다.
숫자는 숫자로 입력하세요.
쉼표는 지우지 마세요.

max_stack:
  한 스택으로 합칠 최대 수량입니다.

move_delay:
  아이템 이동 후 대기시간(ms)입니다.
"""

try:
    from GGO_user_config import load_script_settings, ensure_script_settings_guide
    ensure_script_settings_guide(SCRIPT_NAME, STACK_SCRIPT_SETTINGS_GUIDE)
    _script_settings = load_script_settings(SCRIPT_NAME, STACK_SCRIPT_SETTINGS_DEFAULTS, STACK_SCRIPT_SETTINGS_ORDER)
    MAX_STACK = int(_script_settings.get("max_stack", MAX_STACK))
    MOVE_DELAY = int(_script_settings.get("move_delay", MOVE_DELAY))
except Exception:
    pass

# ------------------------------------------------------------------
# 1. 타겟 설정
# ------------------------------------------------------------------
Player.HeadMessage(53, "정리할 아이템을 타겟하세요")
sample_serial = Target.PromptTarget()
if sample_serial <= 0:
    Player.HeadMessage(33, "취소됨")
    sys.exit()

sample = Items.FindBySerial(sample_serial)
if not sample:
    Player.HeadMessage(33, "아이템을 찾을 수 없음")
    sys.exit()

item_id      = sample.ItemID
item_hue     = sample.Hue
src_con      = sample.Container   # 아이템이 원래 있던 컨테이너

Player.HeadMessage(53, "목적지 컨테이너를 타겟하세요 (ESC = 현재 컨테이너에서 정리)")
dest_serial = Target.PromptTarget()

if dest_serial <= 0:
    # ESC — 현재 컨테이너에서 그대로 정리
    con_serial  = src_con
    move_first  = False
    Player.HeadMessage(55, "현재 컨테이너에서 정리")
else:
    # 지정 컨테이너로 이동 후 정리
    con_serial  = dest_serial
    move_first  = True
    Player.HeadMessage(55, "0x{:08X} 으로 이동 후 정리".format(con_serial))

Player.HeadMessage(68, "ID=0x{:04X} Hue={} — 시작".format(item_id, item_hue))

# ------------------------------------------------------------------
# 2. 헬퍼: 컨테이너에서 해당 아이템 스택 목록 (내림차순)
# ------------------------------------------------------------------
def get_stacks(serial):
    con = Items.FindBySerial(serial)
    if not con:
        return []
    return sorted(
        [i for i in con.Contains if i.ItemID == item_id and i.Hue == item_hue],
        key=lambda x: x.Amount,
        reverse=True
    )

# ------------------------------------------------------------------
# 3. 이동 단계 (목적지 컨테이너 지정 시)
# ------------------------------------------------------------------
if move_first:
    src_stacks = get_stacks(src_con)
    if not src_stacks:
        Player.HeadMessage(33, "원본 컨테이너에서 아이템을 찾을 수 없음")
        sys.exit()

    for stack in src_stacks:
        Items.Move(stack.Serial, con_serial, stack.Amount)
        Misc.Pause(MOVE_DELAY)

    Misc.Pause(500)
    Player.HeadMessage(68, "이동 완료 — 정리 시작")

# ------------------------------------------------------------------
# 4. 정리 루프
# ------------------------------------------------------------------
moved_total = 0

while True:
    stacks   = get_stacks(con_serial)
    partials = [s for s in stacks if s.Amount < MAX_STACK]

    if len(partials) <= 1:
        break

    acc        = partials[0]
    acc_amount = acc.Amount

    progress = False
    for src in partials[1:]:
        space = MAX_STACK - acc_amount
        if space <= 0:
            break

        move = min(src.Amount, space)
        Items.Move(src.Serial, acc.Serial, move)
        Misc.Pause(MOVE_DELAY)

        acc_amount  += move
        moved_total += move
        progress = True

    if not progress:
        break

# ------------------------------------------------------------------
# 5. 결과 출력
# ------------------------------------------------------------------
final = get_stacks(con_serial)
total_amount = sum(s.Amount for s in final)
Player.HeadMessage(68, "완료: 스택 {}개 / 총 {}개".format(len(final), total_amount))
