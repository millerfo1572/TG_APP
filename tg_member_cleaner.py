"""Telegram 群成员清理核心模块（可被其他脚本 import）。

提供：
- build_client()                 构造 pyrogram Client（复用 .env 与代理配置，含 flood 容错）
- load_delete_members(path)      读取待删除名单，按用户 ID 去重并合并用户名
- load_target_chats(path)        读取目标群 ID 列表
- export_admin_chats(...)        实时检测“管理员/群主”身份的群并导出 JSON 清单
- find_members_in_chat(...)      检测群内命中的名单成员（排除群主/管理员）
- kick_member(...)               踢出成员（超级群 ban+unban；普通群仅 ban）
- clean_chats(...)               遍历所有群，dry-run 预览或带限速执行移除，逐条打印并汇总
"""
import asyncio
import json
import os
import random
import time
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from pyrogram import Client, enums


MEMBERS_FILE = "delete_members.json"
CHATS_FILE = "target_chat_ids.json"

# 不允许被踢的身份
PROTECTED_STATUSES = {"OWNER", "ADMINISTRATOR"}


def build_client(sleep_threshold: int = 60) -> Client:
    """按项目统一的 .env + 代理配置构造 Client。

    sleep_threshold 默认 60 秒，避免日志中 17~21 秒 FLOOD_WAIT 超过默认 15 秒而抛错。
    """
    load_dotenv()
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    session_name = os.getenv("SESSION_NAME")

    proxy_dict = None
    scheme = os.getenv("PROXY_SCHEME")
    host = os.getenv("PROXY_HOST")
    port = os.getenv("PROXY_PORT")
    if scheme and host and port:
        proxy_dict = {"scheme": scheme, "hostname": host, "port": int(port)}

    return Client(
        session_name, api_id=api_id, api_hash=api_hash,
        proxy=proxy_dict, sleep_threshold=sleep_threshold
    )


def load_delete_members(path: str = MEMBERS_FILE) -> Dict[int, str]:
    """读取名单 JSON（{用户名: 用户ID}），按用户 ID 去重，多个用户名用 / 拼接。

    返回 {用户ID(int): 用户名标注(str)}
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    members: Dict[int, str] = {}
    for username, uid in raw.items():
        try:
            user_id = int(uid)
        except (TypeError, ValueError):
            print(f"⚠️ 跳过无效用户 ID: {username} -> {uid}")
            continue
        label = username if username.startswith("@") else f"@{username}"
        if user_id in members:
            members[user_id] = f"{members[user_id]}/{label}"
        else:
            members[user_id] = label
    return members


def load_target_chats(path: str = CHATS_FILE) -> List[int]:
    """读取目标群 ID 列表（JSON 数组）。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [int(cid) for cid in raw]


ADMIN_CHATS_FILE = "admin_chat_ids.json"

async def export_admin_chats(
    app: Client,
    out_path: str = ADMIN_CHATS_FILE,
    min_delay: float = 0.0,
    max_delay: float = 0.0,
) -> List[int]:
    """实时检测“我是管理员/群主”的群，导出群 ID JSON 数组并返回。

    只处理 GROUP / SUPERGROUP。先用 is_creator 直接识别群主（零额外请求），
    其余群用 get_chat_member(chat_id, "me") 判断是否为管理员。
    默认不额外延时（依赖 Client 的 flood wait 自动等待），避免检测过慢超时；
    如需更保守可传 min_delay/max_delay。单条异常捕获，不中断整体。
    """
    admin_chats: List[int] = []
    scanned = 0
    groups = 0

    print("🔍 开始实时检测管理群...")
    async for dialog in app.get_dialogs():
        chat = dialog.chat
        if chat is None or chat.type is None:
            continue
        if chat.type.name not in ("GROUP", "SUPERGROUP"):
            continue
        groups += 1
        scanned += 1
        status = ""
        try:
            if getattr(chat, "is_creator", False):
                status = "OWNER"
            else:
                member = await app.get_chat_member(chat.id, "me")
                status = member.status.name if member.status else ""
            if status in ("ADMINISTRATOR", "OWNER"):
                admin_chats.append(chat.id)
                print(f"   ✅ [{status}] {chat.id} | {chat.title or ''}")
        except Exception as e:
            print(f"   ⚠️ 群 {chat.id} 身份检测失败: {e}")
        # 可选延时（默认关闭，依赖 flood wait 自动等待）
        if min_delay > 0:
            await asyncio.sleep(random.uniform(min_delay, max_delay))
        if scanned % 25 == 0:
            print(f"   ...已扫描 {scanned} 个群，命中管理群 {len(admin_chats)} 个")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(admin_chats, f, ensure_ascii=False, indent=2)

    print(
        f"\n📋 检测完成：共扫描 {groups} 个群，"
        f"其中我是管理员或群主的群 {len(admin_chats)} 个"
    )
    print(f"📄 管理群清单已导出：{out_path}")
    return admin_chats


async def find_members_in_chat(app: Client, chat_id: int, member_ids: set[int]) -> List[Tuple[int, str]]:
    """批量拉取群成员，返回命中且可踢的 (用户ID, 身份状态名) 列表。

    群主/管理员会被排除（打印跳过原因）。用户不在群里不会出现在结果中。
    """
    hits = []
    try:
        async for member in app.get_chat_members(chat_id, filter=enums.ChatMembersFilter.RECENT):
            uid = member.user.id if member.user else None
            if uid is None or uid not in member_ids:
                continue
            status = member.status.name if member.status else ""
            if status in PROTECTED_STATUSES:
                print(f"   ⏭️  跳过（身份：{status}）：{uid}")
                continue
            hits.append((uid, status))
    except Exception as e:
        print(f"   ⚠️ 拉取群 {chat_id} 成员失败: {e}")
    return hits


async def kick_member(app: Client, chat_id: int, user_id: int) -> Tuple[bool, str]:
    """单纯把成员剔除群组（不做永久封禁）。

    - 超级群（ID 形如 -100xxxxxxxxxx）：ban 后必须 unban 才是“踢出且可再次加入”。
    - 普通群（ID 形如 -xxxxxxxxx）：ban 本身就是剔除成员，且不支持 unban
      （对普通群调 unban 会报 CHANNEL_INVALID），因此跳过解封。
    返回 (是否成功, 说明)，成功说明统一为“已剔除群组”。
    """
    is_supergroup = isinstance(chat_id, int) and chat_id < -1000000000000

    try:
        await app.ban_chat_member(chat_id, user_id)
    except Exception as e:
        return False, f"剔除失败：{e}"

    if is_supergroup:
        try:
            await app.unban_chat_member(chat_id, user_id)
        except Exception as e:
            return False, f"解除封禁失败：{e}"

    return True, "已剔除群组"


async def clean_chats(
    app: Client,
    chat_ids: List[int],
    member_ids: Dict[int, str],
    execute: bool = False,
    min_delay: float = 3,
    max_delay: float = 5,
    pause_every: int = 20,
    pause_seconds: float = 30,
    max_kicks: int = 0,
) -> dict:
    """遍历所有目标群：预览或执行清理，逐条打印并汇总统计。

    execute=False 时仅打印命中名单，不改动成员，也不等待。
    execute=True 时按风控限速：每次剔除间隔 min_delay~max_delay 秒随机，
    每累计 pause_every 次剔除暂停 pause_seconds 秒。
    max_kicks=0 表示不限制（一次跑完所有命中），正数表示单次上限。
    返回统计字典：chats / hits / kicked / failed / skipped / groups_cleared / limit_reached。
    """
    stats = {
        "chats": len(chat_ids), "hits": 0, "kicked": 0,
        "failed": 0, "skipped": 0, "groups_cleared": 0, "limit_reached": False,
    }
    id_set = set(member_ids)
    attempts = 0  # 已尝试剔除的次数（含成功与失败），用于限速与上限

    if execute:
        limit_text = "不限制" if max_kicks <= 0 else f"{max_kicks} 人"
        print(
            f"🛡️ 风控限速已启用：每次间隔 {min_delay}~{max_delay}s，"
            f"每 {pause_every} 次暂停 {pause_seconds}s，单次上限 {limit_text}"
        )

    for chat_id in chat_ids:
        print(f"\n📍 目标群：{chat_id}")
        hits = await find_members_in_chat(app, chat_id, id_set)
        if not hits:
            print("   ✅ 名单中无该群成员或均不可踢")
            continue

        if not execute:
            stats["hits"] += len(hits)
            stats["skipped"] += len(hits)
            print(f"   🎯 命中待剔除 {len(hits)} 人（预览，未执行）")
            for uid, _ in hits:
                print(f"      - {member_ids.get(uid, '?')} (ID: {uid})")
            continue

        group_cleared = False  # 本群是否至少有 1 人成功剔除
        for index, (uid, _) in enumerate(hits):
            if max_kicks > 0 and attempts >= max_kicks:
                stats["limit_reached"] = True
                remaining = len(hits) - index
                print(
                    f"   ⚠️ 已达单次上限 {max_kicks} 人，当前群剩余 {remaining} 人未处理"
                    if remaining > 0 else f"   ⚠️ 已达单次上限 {max_kicks} 人"
                )
                break

            names = member_ids.get(uid, "?")
            ok, msg = await kick_member(app, chat_id, uid)
            attempts += 1
            stats["hits"] += 1
            if ok:
                stats["kicked"] += 1
                group_cleared = True
                print(f"   ✅ {names} (ID: {uid}) 已剔除群组")
            else:
                stats["failed"] += 1
                print(f"   ❌ {names} (ID: {uid}) {msg}")

            # 限速：每次剔除后随机等待；每累计 pause_every 次额外长暂停
            if max_kicks <= 0 or attempts < max_kicks:
                delay = random.uniform(min_delay, max_delay)
                print(f"   ⏳ 限速等待 {delay:.1f}s ...")
                await asyncio.sleep(delay)
                if attempts % pause_every == 0:
                    print(f"   ⏸️ 已剔除 {attempts} 次，长暂停 {pause_seconds}s（防风控）...")
                    await asyncio.sleep(pause_seconds)

        if group_cleared:
            stats["groups_cleared"] += 1

        if stats["limit_reached"]:
            break

    print(
        f"\n📊 汇总：检测群数 {stats['chats']} | 命中 {stats['hits']} | "
        f"成功剔除 {stats['kicked']} | 失败 {stats['failed']} | 预览跳过 {stats['skipped']} | "
        f"已从 {stats['groups_cleared']} 个群组中剔除目标"
        + (f" | ⚠️ 达上限 {max_kicks} 提前停止" if stats["limit_reached"] else "")
    )
    return stats
