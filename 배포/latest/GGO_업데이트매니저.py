# -*- coding: utf-8 -*-
from System.Diagnostics import Process, ProcessStartInfo
from System.IO import Directory, File
from System.Net import WebClient
from System.Text import Encoding

import json
import os
import re
import time


SCRIPT_ID = "GGO_UPDATE_MANAGER"
SCRIPT_NAME = "GGO_업데이트매니저"
CURRENT_VERSION = "1.1"
MANAGER_VERSION = CURRENT_VERSION
MANAGER_FILE = "GGO_업데이트매니저.py"
MANIFEST_URL = "https://raw.githubusercontent.com/gu2tarman/GGO-Scripts/main/%EB%B0%B0%ED%8F%AC/GGO_update_manifest.json"
SUPPORT_DISCORD_URL = "http://uomargo.net"
SUPPORT_WEBHOOK_URL = "https://discord.gg/KQzHZsZ9eH"
SUPPORT_KAKAO_URL = "https://open.kakao.com/o/sA71kz5d"
ITEMS_PER_PAGE = 6
DEBUG_LOG = False
GUMP_ID = 0x47475501
NOTES_GUMP_ID = 0x47475502
SUPPORT_GUMP_ID = 0x47475503
BTN_UPDATE_ALL = 9001
BTN_OTHER_SCRIPTS = 9002
BTN_CLOSE = 9003
BTN_NOTES = 9004
BTN_NOTES_CLOSE = 9005
BTN_PREV_PAGE = 9006
BTN_NEXT_PAGE = 9007
BTN_SUPPORT = 9008
BTN_SUPPORT_DISCORD = 9009
BTN_SUPPORT_WEBHOOK = 9010
BTN_SUPPORT_KAKAO = 9011
BTN_SUPPORT_BACK = 9012
BTN_UPDATE_LIST = 9013
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
        Gumps.WaitForGump(gump_id, 60000)
        data = Gumps.GetGumpData(gump_id)
        if data is None:
            continue
        button_id = data.buttonid
        if button_id == 0:
            return BTN_CLOSE
        Gumps.SendAction(gump_id, 0)
        Gumps.CloseGump(gump_id)
        return button_id


def open_url(url, label):
    if not url:
        ggo_msg("{0} 링크가 아직 설정되지 않았습니다.".format(label), 33)
        return False
    try:
        psi = ProcessStartInfo()
        psi.FileName = url
        psi.UseShellExecute = True
        Process.Start(psi)
        ggo_msg("{0} 링크를 열었습니다.".format(label), 68)
        return True
    except Exception as error:
        ggo_msg("{0} 링크 열기 실패: {1}".format(label, error), 33)
        ggo_msg(url, 90)
        return False


def make_backup(path, base_dir):
    if not File.Exists(path):
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
    installed_items = []
    update_items = []
    install_items = []

    for entry in scripts:
        local_file = entry.get("local_file", "")
        display_name = entry.get("name", local_file)
        local_path = os.path.join(base_dir, local_file)
        installed = File.Exists(local_path)
        local_version = get_local_version(local_path) if installed else "0.0"
        latest_version = entry.get("version", "0.0")
        needs_update = installed and version_tuple(latest_version) > version_tuple(local_version)
        needs_install = (not installed) and entry.get("discoverable", True)

        item = {
            "entry": entry,
            "name": display_name,
            "installed": installed,
            "local_version": local_version,
            "latest_version": latest_version,
            "notes": entry.get("notes", ""),
            "needs_update": needs_update,
            "needs_install": needs_install,
        }
        if needs_update:
            update_items.append(item)
        if needs_install:
            install_items.append(item)
        if installed:
            installed_items.append(item)

        local_label = local_version if installed else "not installed"
        debug_msg("{0}: local {1} / remote v{2}".format(display_name, local_label, latest_version), 68)

    installed_items.sort(key=lambda item: 0 if item["needs_update"] else 1)
    install_items.sort(key=lambda item: item["name"])
    return installed_items, update_items, install_items


def get_action_items(display_items):
    action_items = []
    for item in display_items:
        if item.get("needs_update", False) or item.get("needs_install", False):
            item["action_index"] = len(action_items)
            action_items.append(item)
    return action_items


def show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode):
    try:
        Gumps.CloseGump(GUMP_ID)
        gd = Gumps.CreateGump(movable=True)
        width = 560
        row_height = 54
        file_x = 25
        version_x = 318
        action_x = 420
        action_w = 120
        total_pages = get_total_pages(len(display_items))
        current_page = clamp_page(current_page, len(display_items))

        start_index = current_page * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        page_items = display_items[start_index:end_index]

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

        if view_mode == "install":
            if install_items:
                Gumps.AddLabel(gd, 15, 45, 90, "다른 스크립트: {0}개".format(len(install_items)))
            else:
                Gumps.AddLabel(gd, 15, 45, 68, "설치 가능한 다른 스크립트가 없습니다.")
        else:
            if update_items:
                Gumps.AddLabel(gd, 15, 45, 90, "업데이트 가능: {0}개".format(len(update_items)))
            else:
                Gumps.AddLabel(gd, 15, 45, 68, "설치된 파일이 최신 버전입니다.")
            if install_items:
                Gumps.AddLabel(gd, 205, 45, 53, "다른 스크립트 {0}개".format(len(install_items)))

        if total_pages > 1:
            add_center_label(gd, 420, 45, 120, "DDDDDD", "{0} / {1}".format(current_page + 1, total_pages))

        Gumps.AddLabel(gd, file_x, 70, 1152, "파일")
        add_center_label(gd, version_x - 10, 70, 90, "DDDDDD", "버전")
        add_center_label(gd, action_x, 70, action_w, "DDDDDD", "작업")
        Gumps.AddImageTiled(gd, 15, 92, width - 30, 1, 9107)

        y = 106
        for item in page_items:
            hue = 90 if (item["needs_update"] or item["needs_install"]) else 68
            notes = primary_note(item.get("notes", ""))
            name = short_text(item["name"], 28)

            Gumps.AddLabel(gd, file_x, y, hue, name)
            if item["needs_update"]:
                button_id = BTN_ITEM_BASE + item["action_index"]
                add_center_label(gd, version_x - 10, y + 1, 90, "99DDFF", "v{0} -> v{1}".format(item["local_version"], item["latest_version"]))
                Gumps.AddButton(gd, action_x, y - 2, 40030, 40031, button_id, 1, 0)
                add_center_label(gd, action_x, y + 1, action_w, "FFFFFF", "업데이트")
            elif item["needs_install"]:
                button_id = BTN_ITEM_BASE + item["action_index"]
                add_center_label(gd, version_x - 10, y + 1, 90, "99DDFF", "미설치 -> v{0}".format(item["latest_version"]))
                Gumps.AddButton(gd, action_x, y - 2, 40030, 40031, button_id, 1, 0)
                add_center_label(gd, action_x, y + 1, action_w, "FFFFFF", "설치")
            else:
                add_center_label(gd, version_x - 10, y + 1, 90, "88FF88", "v{0} 최신".format(item["local_version"]))
                add_center_label(gd, action_x, y + 1, action_w, "88FF88", "완료")
            if (item["needs_update"] or item["needs_install"]) and notes:
                Gumps.AddLabel(gd, file_x, y + 25, 1152, "주요 변경: {0}".format(notes))
            Gumps.AddImageTiled(gd, 15, y + row_height - 8, width - 30, 1, 9107)
            y += row_height

        bottom_y = height - 35
        nav_y = bottom_y - 28
        Gumps.AddButton(gd, 15, bottom_y, 40030, 40031, BTN_UPDATE_ALL, 1, 0)
        if view_mode == "install":
            add_center_label(gd, 15, bottom_y + 2, action_w, "FFFFFF", "전체 설치")
        else:
            add_center_label(gd, 15, bottom_y + 2, action_w, "FFFFFF", "전체 업데이트")

        Gumps.AddButton(gd, 150, bottom_y, 40021, 40022, BTN_NOTES, 1, 0)
        add_center_label(gd, 150, bottom_y + 2, action_w, "FFFFFF", "패치노트")

        if total_pages > 1 and current_page > 0:
            Gumps.AddButton(gd, 285, nav_y, 40021, 40022, BTN_PREV_PAGE, 1, 0)
            add_center_label(gd, 285, nav_y + 2, action_w, "FFFFFF", "이전")

        if total_pages > 1 and current_page < total_pages - 1:
            Gumps.AddButton(gd, 420, nav_y, 40021, 40022, BTN_NEXT_PAGE, 1, 0)
            add_center_label(gd, 420, nav_y + 2, action_w, "FFFFFF", "다음")

        if view_mode == "install":
            Gumps.AddButton(gd, 285, bottom_y, 40021, 40022, BTN_UPDATE_LIST, 1, 0)
            add_center_label(gd, 285, bottom_y + 2, action_w, "FFFFFF", "업데이트 목록")
        else:
            Gumps.AddButton(gd, 285, bottom_y, 40021, 40022, BTN_OTHER_SCRIPTS, 1, 0)
            add_center_label(gd, 285, bottom_y + 2, action_w, "FFFFFF", "다른 스크립트")

        Gumps.AddButton(gd, 420, bottom_y, 40021, 40022, BTN_SUPPORT, 1, 0)
        add_center_label(gd, 420, bottom_y + 2, action_w, "FFFFFF", "문의&지원")

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


def show_support_gump():
    try:
        Gumps.CloseGump(SUPPORT_GUMP_ID)
        gd = Gumps.CreateGump(movable=True)
        width = 430
        height = 210
        button_x = 20
        label_x = 155

        Gumps.AddPage(gd, 0)
        Gumps.AddBackground(gd, 0, 0, width, height, 30546)
        Gumps.AddAlphaRegion(gd, 0, 0, width, height)
        Gumps.AddLabel(gd, 15, 12, 53, "GGO 문의 & 지원")
        Gumps.AddImageTiled(gd, 10, 33, width - 20, 2, 9107)

        Gumps.AddButton(gd, button_x, 52, 40021, 40022, BTN_SUPPORT_DISCORD, 1, 0)
        add_center_label(gd, button_x, 54, 120, "FFFFFF", "마고 홈피")
        Gumps.AddLabel(gd, label_x, 55, 1152, "마고 서버 홈페이지")

        Gumps.AddButton(gd, button_x, 88, 40021, 40022, BTN_SUPPORT_WEBHOOK, 1, 0)
        add_center_label(gd, button_x, 90, 120, "FFFFFF", "웹훅 발급소")
        Gumps.AddLabel(gd, label_x, 91, 1152, "알림 기능용 Discord 웹훅 생성")

        Gumps.AddButton(gd, button_x, 124, 40021, 40022, BTN_SUPPORT_KAKAO, 1, 0)
        add_center_label(gd, button_x, 126, 120, "FFFFFF", "카카오톡 1:1")
        Gumps.AddLabel(gd, label_x, 127, 1152, "각종 문의, 건의 및 제보")

        Gumps.AddButton(gd, 290, height - 35, 40297, 40298, BTN_SUPPORT_BACK, 1, 0)
        add_center_label(gd, 290, height - 33, 120, "FFFFFF", "뒤로")
        Gumps.SendGump(SUPPORT_GUMP_ID, Player.Serial, 170, 150, gd.gumpDefinition, gd.gumpStrings)

        while True:
            button_id = wait_gump_button(SUPPORT_GUMP_ID)
            if button_id == BTN_SUPPORT_DISCORD:
                open_url(SUPPORT_DISCORD_URL, "마고 홈피")
                show_support_gump()
                return
            if button_id == BTN_SUPPORT_WEBHOOK:
                open_url(SUPPORT_WEBHOOK_URL, "웹훅 발급소")
                show_support_gump()
                return
            if button_id == BTN_SUPPORT_KAKAO:
                open_url(SUPPORT_KAKAO_URL, "카카오톡 1:1")
                show_support_gump()
                return
            if button_id == BTN_SUPPORT_BACK:
                return
    except Exception as error:
        ggo_msg("support gump failed: {0}".format(error), 33)


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

    installed_items, update_items, install_items = collect_update_info(base_dir, scripts)
    view_mode = "update"
    current_page = 0
    display_items = installed_items
    action_items = get_action_items(display_items)
    if not show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode):
        return

    while True:
        button_id = wait_gump_button(GUMP_ID)

        if button_id == BTN_CLOSE:
            ggo_msg("manager closed", 68)
            return

        if button_id == BTN_NOTES:
            show_notes_gump(action_items)
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id == BTN_SUPPORT:
            show_support_gump()
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id == BTN_OTHER_SCRIPTS:
            view_mode = "install"
            current_page = 0
            display_items = install_items
            action_items = get_action_items(display_items)
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id == BTN_UPDATE_LIST:
            view_mode = "update"
            current_page = 0
            display_items = installed_items
            action_items = get_action_items(display_items)
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id == BTN_PREV_PAGE:
            current_page -= 1
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id == BTN_NEXT_PAGE:
            current_page += 1
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id == BTN_UPDATE_ALL:
            manager_updated = apply_selected_updates(action_items, range(len(action_items)), base_dir)
            if manager_updated:
                notify_manager_updated()
                return
            installed_items, update_items, install_items = collect_update_info(base_dir, scripts)
            display_items = install_items if view_mode == "install" else installed_items
            action_items = get_action_items(display_items)
            current_page = clamp_page(current_page, len(display_items))
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        if button_id >= BTN_ITEM_BASE:
            selected_index = button_id - BTN_ITEM_BASE
            manager_updated = apply_selected_updates(action_items, [selected_index], base_dir)
            if manager_updated:
                notify_manager_updated()
                return
            installed_items, update_items, install_items = collect_update_info(base_dir, scripts)
            display_items = install_items if view_mode == "install" else installed_items
            action_items = get_action_items(display_items)
            current_page = clamp_page(current_page, len(display_items))
            show_update_gump(display_items, action_items, update_items, install_items, current_page, view_mode)
            continue

        Misc.Pause(200)


if __name__ == "__main__":
    run_manager()
