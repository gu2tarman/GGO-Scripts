# -*- coding: utf-8 -*-
from System.IO import Directory, File
from System.Net import WebClient
from System.Text import Encoding

import json
import os
import re
import time


SCRIPT_ID = "GGO_UPDATE_MANAGER"
SCRIPT_NAME = "GGO_업데이트매니저"
CURRENT_VERSION = "1.0"
MANAGER_VERSION = CURRENT_VERSION
MANAGER_FILE = "GGO_업데이트매니저.py"
MANIFEST_URL = "https://raw.githubusercontent.com/gu2tarman/GGO-Scripts/main/%EB%B0%B0%ED%8F%AC/GGO_update_manifest.json"
ITEMS_PER_PAGE = 6
DEBUG_LOG = False
GUMP_ID = 0x47475501
NOTES_GUMP_ID = 0x47475502
BTN_UPDATE_ALL = 9001
BTN_REFRESH = 9002
BTN_CLOSE = 9003
BTN_NOTES = 9004
BTN_NOTES_CLOSE = 9005
BTN_PREV_PAGE = 9006
BTN_NEXT_PAGE = 9007
BTN_ITEM_BASE = 9100


def ggo_msg(text, hue=68):
    prefix = "[GGO Update Manager] "
    try:
        Misc.SendMessage(prefix + text, hue)
    except:
        try:
            Player.HeadMessage(hue, prefix + text)
        except:
            print(prefix + text)


def debug_msg(text, hue=68):
    if DEBUG_LOG:
        ggo_msg(text, hue)


def get_base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except:
        return os.getcwd()


def version_tuple(version_text):
    parts = []
    for part in str(version_text).split("."):
        try:
            parts.append(int(part))
        except:
            parts.append(0)
    return tuple(parts)


def download_text(url):
    wc = WebClient()
    wc.Encoding = Encoding.UTF8
    return wc.DownloadString(url)


def cache_busted_url(url):
    sep = "&" if "?" in url else "?"
    return url + sep + "t=" + str(int(time.time()))


def read_text(path):
    if not File.Exists(path):
        return ""
    return File.ReadAllText(path, Encoding.UTF8)


def get_local_version(path):
    source = read_text(path)
    match = re.search(r"CURRENT_VERSION\s*=\s*['\"]([^'\"]+)['\"]", source)
    if match:
        return match.group(1)
    return "0.0"


def load_manifest():
    return json.loads(download_text(cache_busted_url(MANIFEST_URL)))


def get_managed_scripts(manifest):
    result = []
    for entry in manifest.get("scripts", []):
        if entry.get("managed", False):
            result.append(entry)
    return result


def short_text(text, max_len):
    value = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(value) <= max_len:
        return value
    return value[:max_len - 3] + "..."


def primary_note(text):
    value = str(text or "").replace("\r", "\n").strip()
    if not value:
        return ""
    for sep in ["\n", ";", "；", " / ", " | "]:
        if sep in value:
            value = value.split(sep)[0]
            break
    return short_text(value, 44)


def get_total_pages(total_count):
    if total_count <= 0:
        return 1
    return int((total_count + ITEMS_PER_PAGE - 1) / ITEMS_PER_PAGE)


def clamp_page(current_page, total_count):
    total_pages = get_total_pages(total_count)
    if current_page < 0:
        return 0
    if current_page >= total_pages:
        return total_pages - 1
    return current_page


def add_center_label(gd, x, y, width, color_hex, text):
    html = "<center><basefont color=#{0}>{1}</basefont></center>".format(color_hex, text)
    Gumps.AddHtml(gd, x, y, width, 20, html, False, False)


def wait_gump_button(gump_id):
    while True:
        Misc.Pause(100)
        data = Gumps.GetGumpData(gump_id)
        if data and data.buttonid > 0:
            button_id = data.buttonid
            Gumps.SendAction(gump_id, 0)
            Gumps.CloseGump(gump_id)
            return button_id


def make_backup(path, base_dir):
    if not File.Exists(path):
        ggo_msg("backup skipped, file not found: {0}".format(path), 33)
        return None

    backup_dir = os.path.join(base_dir, "_ggo_update_backup")
    if not Directory.Exists(backup_dir):
        Directory.CreateDirectory(backup_dir)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = os.path.basename(path) + "." + stamp + ".bak"
    backup_path = os.path.join(backup_dir, backup_name)
    File.Copy(path, backup_path, True)
    ggo_msg("backup created: {0}".format(backup_path), 68)
    return backup_path


def apply_update(entry, base_dir):
    local_file = entry.get("local_file", "")
    remote_url = entry.get("url", "")
    latest_version = entry.get("version", "0.0")
    display_name = entry.get("name", local_file)

    if not local_file or not remote_url:
        ggo_msg("{0}: manifest data missing.".format(display_name), 33)
        return False

    local_path = os.path.join(base_dir, local_file)
    temp_path = local_path + ".tmp"

    ggo_msg("{0}: target {1}".format(display_name, local_path), 53)
    ggo_msg("{0}: downloading v{1}".format(display_name, latest_version), 68)
    new_source = download_text(remote_url)

    File.WriteAllText(temp_path, new_source, Encoding.UTF8)
    make_backup(local_path, base_dir)
    File.Copy(temp_path, local_path, True)
    File.Delete(temp_path)
    ggo_msg("{0}: updated to v{1}".format(display_name, latest_version), 90)
    return True


def is_manager_entry(entry):
    return (
        entry.get("id", "") == SCRIPT_ID
        or entry.get("local_file", "") == MANAGER_FILE
    )


def notify_manager_updated():
    message = "업데이트매니저가 업데이트되었습니다. RE 스크립트 목록을 리프레시한 뒤 다시 실행해주세요."
    ggo_msg(message, 33)
    try:
        Player.HeadMessage(33, "업데이트매니저 갱신 완료 - 리프레시 후 재실행")
    except Exception:
        pass


def collect_update_info(base_dir, scripts):
    all_items = []
    update_items = []

    for entry in scripts:
        local_file = entry.get("local_file", "")
        display_name = entry.get("name", local_file)
        local_path = os.path.join(base_dir, local_file)
        local_version = get_local_version(local_path)
        latest_version = entry.get("version", "0.0")
        needs_update = version_tuple(latest_version) > version_tuple(local_version)

        item = {
            "entry": entry,
            "name": display_name,
            "local_version": local_version,
            "latest_version": latest_version,
            "notes": entry.get("notes", ""),
            "needs_update": needs_update,
        }
        if needs_update:
            item["update_index"] = len(update_items)
            update_items.append(item)
        all_items.append(item)

        debug_msg("{0}: local v{1} / remote v{2}".format(display_name, local_version, latest_version), 68)

    all_items.sort(key=lambda item: 0 if item["needs_update"] else 1)
    return all_items, update_items


def show_update_gump(all_items, update_items, current_page):
    try:
        Gumps.CloseGump(GUMP_ID)
        gd = Gumps.CreateGump(movable=True)
        width = 560
        row_height = 54
        file_x = 25
        version_x = 318
        action_x = 420
        action_w = 120
        total_pages = get_total_pages(len(all_items))
        current_page = clamp_page(current_page, len(all_items))

        start_index = current_page * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        page_items = all_items[start_index:end_index]

        height = 150 + max(len(page_items), 1) * row_height
        if total_pages > 1:
            height += 30
        if height < 230:
            height = 230

        Gumps.AddPage(gd, 0)
        Gumps.AddBackground(gd, 0, 0, width, height, 30546)
        Gumps.AddAlphaRegion(gd, 0, 0, width, height)
        Gumps.AddLabel(gd, 15, 12, 53, "GGO Update Manager v{0}".format(MANAGER_VERSION))
        Gumps.AddImageTiled(gd, 10, 33, width - 20, 2, 9107)

        if update_items:
            Gumps.AddLabel(gd, 15, 45, 90, "업데이트 가능: {0}개".format(len(update_items)))
        else:
            Gumps.AddLabel(gd, 15, 45, 68, "모든 파일이 최신 버전입니다.")

        if total_pages > 1:
            add_center_label(gd, 420, 45, 120, "DDDDDD", "{0} / {1}".format(current_page + 1, total_pages))

        Gumps.AddLabel(gd, file_x, 70, 1152, "파일")
        add_center_label(gd, version_x - 10, 70, 90, "DDDDDD", "버전")
        add_center_label(gd, action_x, 70, action_w, "DDDDDD", "작업")
        Gumps.AddImageTiled(gd, 15, 92, width - 30, 1, 9107)

        y = 106
        for item in page_items:
            hue = 90 if item["needs_update"] else 68
            notes = primary_note(item.get("notes", ""))
            name = short_text(item["name"], 28)

            Gumps.AddLabel(gd, file_x, y, hue, name)
            if item["needs_update"]:
                button_id = BTN_ITEM_BASE + item["update_index"]
                add_center_label(gd, version_x - 10, y + 1, 90, "99DDFF", "v{0} -> v{1}".format(item["local_version"], item["latest_version"]))
                Gumps.AddButton(gd, action_x, y - 2, 40030, 40031, button_id, 1, 0)
                add_center_label(gd, action_x, y + 1, action_w, "FFFFFF", "업데이트")
            else:
                add_center_label(gd, version_x - 10, y + 1, 90, "88FF88", "v{0} 최신".format(item["local_version"]))
                add_center_label(gd, action_x, y + 1, action_w, "88FF88", "완료")
            if item["needs_update"] and notes:
                Gumps.AddLabel(gd, file_x, y + 25, 1152, "주요 변경: {0}".format(notes))
            Gumps.AddImageTiled(gd, 15, y + row_height - 8, width - 30, 1, 9107)
            y += row_height

        bottom_y = height - 35
        nav_y = bottom_y - 28
        if update_items:
            Gumps.AddButton(gd, 15, bottom_y, 40030, 40031, BTN_UPDATE_ALL, 1, 0)
            add_center_label(gd, 15, bottom_y + 2, action_w, "FFFFFF", "전체 업데이트")

            Gumps.AddButton(gd, 150, bottom_y, 40021, 40022, BTN_NOTES, 1, 0)
            add_center_label(gd, 150, bottom_y + 2, action_w, "FFFFFF", "패치노트")

        if total_pages > 1 and current_page > 0:
            Gumps.AddButton(gd, 285, nav_y, 40021, 40022, BTN_PREV_PAGE, 1, 0)
            add_center_label(gd, 285, nav_y + 2, action_w, "FFFFFF", "이전")

        if total_pages > 1 and current_page < total_pages - 1:
            Gumps.AddButton(gd, 420, nav_y, 40021, 40022, BTN_NEXT_PAGE, 1, 0)
            add_center_label(gd, 420, nav_y + 2, action_w, "FFFFFF", "다음")

        Gumps.AddButton(gd, 285, bottom_y, 40021, 40022, BTN_REFRESH, 1, 0)
        add_center_label(gd, 285, bottom_y + 2, action_w, "FFFFFF", "다시 확인")

        Gumps.AddButton(gd, 420, bottom_y, 40297, 40298, BTN_CLOSE, 1, 0)
        add_center_label(gd, 420, bottom_y + 2, action_w, "FFFFFF", "닫기")

        Gumps.SendGump(GUMP_ID, Player.Serial, 120, 120, gd.gumpDefinition, gd.gumpStrings)
        return True
    except Exception as error:
        ggo_msg("gump failed: {0}".format(error), 33)
        return False


def show_notes_gump(update_items):
    try:
        Gumps.CloseGump(NOTES_GUMP_ID)
        gd = Gumps.CreateGump(movable=True)
        width = 520
        line_count = 0
        for item in update_items:
            note = str(item.get("notes", "") or "").strip()
            if note:
                line_count += 2
        height = 85 + max(line_count, 1) * 22
        if height < 170:
            height = 170

        Gumps.AddPage(gd, 0)
        Gumps.AddBackground(gd, 0, 0, width, height, 30546)
        Gumps.AddAlphaRegion(gd, 0, 0, width, height)
        Gumps.AddLabel(gd, 15, 12, 53, "GGO Patch Notes")
        Gumps.AddImageTiled(gd, 10, 33, width - 20, 2, 9107)

        y = 48
        has_notes = False
        for item in update_items:
            note = str(item.get("notes", "") or "").strip()
            if not note:
                continue
            has_notes = True
            Gumps.AddLabel(gd, 20, y, 90, "{0}  v{1}".format(item["name"], item["latest_version"]))
            Gumps.AddLabel(gd, 35, y + 20, 1152, short_text(note, 64))
            y += 44

        if not has_notes:
            Gumps.AddLabel(gd, 20, y, 68, "표시할 패치노트가 없습니다.")

        Gumps.AddButton(gd, 390, height - 35, 40297, 40298, BTN_NOTES_CLOSE, 1, 0)
        add_center_label(gd, 390, height - 33, 120, "FFFFFF", "닫기")
        Gumps.SendGump(NOTES_GUMP_ID, Player.Serial, 160, 140, gd.gumpDefinition, gd.gumpStrings)
        wait_gump_button(NOTES_GUMP_ID)
    except Exception as error:
        ggo_msg("patch notes gump failed: {0}".format(error), 33)


def apply_selected_updates(update_items, selected_indexes, base_dir):
    updated_count = 0
    failed_count = 0
    manager_updated = False

    for selected_index in selected_indexes:
        if selected_index < 0 or selected_index >= len(update_items):
            continue
        item = update_items[selected_index]
        try:
            if apply_update(item["entry"], base_dir):
                updated_count += 1
                if is_manager_entry(item["entry"]):
                    manager_updated = True
        except Exception as error:
            failed_count += 1
            ggo_msg("{0}: update failed: {1}".format(item["name"], error), 33)

    ggo_msg("updated {0}, failed {1}".format(updated_count, failed_count), 90)
    if updated_count > 0:
        ggo_msg("RE script list may need refresh before running updated files.", 53)
    return manager_updated


def run_manager():
    base_dir = get_base_dir()
    debug_msg("manager v{0}".format(MANAGER_VERSION), 53)
    debug_msg("base dir: {0}".format(base_dir), 53)
    debug_msg("manifest check start", 68)

    try:
        manifest = load_manifest()
    except Exception as error:
        ggo_msg("manifest download failed: {0}".format(error), 33)
        return

    scripts = get_managed_scripts(manifest)
    if not scripts:
        ggo_msg("no managed scripts in manifest", 33)
        return

    all_items, update_items = collect_update_info(base_dir, scripts)
    current_page = 0
    if not show_update_gump(all_items, update_items, current_page):
        return

    while True:
        button_id = wait_gump_button(GUMP_ID)

        if button_id == BTN_CLOSE:
            ggo_msg("manager closed", 68)
            return

        if button_id == BTN_REFRESH:
            run_manager()
            return

        if button_id == BTN_NOTES:
            show_notes_gump(update_items)
            show_update_gump(all_items, update_items, current_page)
            continue

        if button_id == BTN_PREV_PAGE:
            current_page -= 1
            show_update_gump(all_items, update_items, current_page)
            continue

        if button_id == BTN_NEXT_PAGE:
            current_page += 1
            show_update_gump(all_items, update_items, current_page)
            continue

        if button_id == BTN_UPDATE_ALL:
            manager_updated = apply_selected_updates(update_items, range(len(update_items)), base_dir)
            if manager_updated:
                notify_manager_updated()
                return
            all_items, update_items = collect_update_info(base_dir, scripts)
            current_page = clamp_page(current_page, len(all_items))
            show_update_gump(all_items, update_items, current_page)
            continue

        if button_id >= BTN_ITEM_BASE:
            selected_index = button_id - BTN_ITEM_BASE
            manager_updated = apply_selected_updates(update_items, [selected_index], base_dir)
            if manager_updated:
                notify_manager_updated()
                return
            all_items, update_items = collect_update_info(base_dir, scripts)
            current_page = clamp_page(current_page, len(all_items))
            show_update_gump(all_items, update_items, current_page)
            continue

        Misc.Pause(200)


if __name__ == "__main__":
    run_manager()
