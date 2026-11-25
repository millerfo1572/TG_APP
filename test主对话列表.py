import asyncio
import os
import sys
from dotenv import load_dotenv

# 强制 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台打印 emoji/中文时报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from pyrogram import Client, utils
from pyrogram.raw.functions.messages import GetDialogs, GetDialogFilters
from pyrogram.raw.functions.users import GetUsers
from pyrogram.raw.functions.channels import GetChannels
from pyrogram.raw.types import DialogFilter, DialogFilterDefault
from pyrogram.raw.types import (
    InputPeerEmpty,
    PeerUser, PeerChat, PeerChannel,
    InputPeerUser, InputPeerChat, InputPeerChannel,
)
from rich.console import Console

console = Console()

# 缓存每个会话中"我"的管理员身份：chat_id -> "群主" / "管理员" / "否" / "未知"
ADMIN_MAP = {}

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")

proxy_scheme = os.getenv("PROXY_SCHEME")
proxy_host = os.getenv("PROXY_HOST")
proxy_port = os.getenv("PROXY_PORT")

proxy_dict = None
if proxy_scheme and proxy_host and proxy_port:
    proxy_dict = {
        "scheme": proxy_scheme,
        "hostname": proxy_host,
        "port": int(proxy_port)
    }

def print_dialog(chat_id, chat_type, title, archived=False):
    color = "yellow" if archived else "cyan"
    admin = ADMIN_MAP.get(chat_id)
    if admin == "群主":
        admin_text = "[bold red]群主[/bold red]"
    elif admin == "管理员":
        admin_text = "[bold green]管理员[/bold green]"
    elif admin == "否":
        admin_text = "[dim]否[/dim]"
    else:
        admin_text = "[dim]-[/dim]"
    console.print(
        f"[{color}]{chat_id:>16}[/{color}] | "
        f"[magenta]{chat_type:<15}[/magenta] | "
        f"{admin_text:<10} | "
        f"[bold white]{title}[/bold white]"
    )

async def load_admin_status(app, chat_id):
    """查询我在该会话里的身份：群主/管理员/否，并写入 ADMIN_MAP 缓存"""
    if chat_id in ADMIN_MAP:
        return ADMIN_MAP[chat_id]
    label = "未知"
    try:
        member = await app.get_chat_member(chat_id, "me")
        status = member.status.name if member.status is not None else ""
        if status == "OWNER":
            label = "群主"
        elif status == "ADMINISTRATOR":
            label = "管理员"
        else:
            label = "否"
    except Exception:
        label = "未知"
    ADMIN_MAP[chat_id] = label
    return label

def build_input_peer(peer, users_by_id, chats_by_id):
    """把 raw Peer 转成 raw InputPeer（从本次响应的 users/chats 取 access_hash）"""
    if isinstance(peer, PeerUser):
        u = users_by_id[peer.user_id]
        return InputPeerUser(user_id=u.id, access_hash=u.access_hash)
    if isinstance(peer, PeerChat):
        return InputPeerChat(chat_id=peer.chat_id)
    if isinstance(peer, PeerChannel):
        ch = chats_by_id[peer.channel_id]
        return InputPeerChannel(channel_id=ch.id, access_hash=ch.access_hash)
    raise ValueError(f"无法转换 peer: {peer}")

def input_peer_id(peer):
    """从 raw InputPeer 取出整型 id 与类型"""
    if isinstance(peer, InputPeerUser):
        return peer.user_id, "user"
    if isinstance(peer, InputPeerChat):
        return peer.chat_id, "chat"
    if isinstance(peer, InputPeerChannel):
        return peer.channel_id, "channel"
    return None, None

async def resolve_input_peer(app, peer):
    """把 DialogFilter.include_peers 里的 InputPeer 解析成 (id, type, title)"""
    pid, kind = input_peer_id(peer)
    if pid is None:
        return None, "?", "?"
    if kind == "user":
        u = (await app.invoke(GetUsers(id=[peer])))[0]
        name = u.first_name or u.last_name or u.username or ""
        return pid, "PRIVATE" if not u.username else "USER", name
    if kind == "channel":
        ch = (await app.invoke(GetChannels(id=[peer]))).chats[0]
        return pid, "SUPERGROUP" if getattr(ch, "megagroup", False) else "CHANNEL", ch.title or ""
    # 旧式基础群组
    c = await app.get_chat(-pid)
    return -pid, "GROUP", c.title or ""

async def fetch_folder(app, folder_id, color):
    """按 folder_id 分页拉取某个文件夹(或归档)里的所有对话，返回 (count, [(chat_id, type, title), ...])"""
    dialogs_info = []
    offset_date = 0
    offset_id = 0
    offset_peer = InputPeerEmpty()
    limit = 100

    while True:
        r = await app.invoke(
            GetDialogs(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=limit,
                folder_id=folder_id,
                hash=0
            )
        )
        if not r.dialogs:
            break
        messages_map = {m.id: m for m in r.messages}
        users_by_id = {u.id: u for u in r.users}
        chats_by_id = {c.id: c for c in r.chats}
        for dialog in r.dialogs:
            try:
                chat_id = utils.get_peer_id(dialog.peer)
                c = await app.get_chat(chat_id)
                dialogs_info.append((c.id, c.type.name, c.title or ""))
            except Exception as e:
                console.print(f"[red]⚠️ 跳过异常对话: {e}[/red]")
        last_d = r.dialogs[-1]
        offset_id = last_d.top_message
        msg = messages_map.get(last_d.top_message)
        offset_date = msg.date if msg else 0
        offset_peer = build_input_peer(last_d.peer, users_by_id, chats_by_id)
    return dialogs_info

async def main():
    async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, proxy=proxy_dict) as app:
        console.rule("[bold green]主对话列表")
        cnt_main = 0
        seen = set()      # 去重（pyrogram get_dialogs 偶发重复条目）
        async for d in app.get_dialogs():
            try:
                c = d.chat
                if c.id in seen:
                    continue
                seen.add(c.id)
                cnt_main += 1
                # 只对群组/超级群查询管理员身份（私聊/频道/机器人无意义）
                if c.type.name in ("GROUP", "SUPERGROUP"):
                    await load_admin_status(app, c.id)
                print_dialog(c.id, c.type.name, c.title)
            except Exception as e:
                console.print(f"[red]⚠️ 跳过异常对话: {e}[/red]")
        console.print(f"\n[bold green]主列表总数：{cnt_main}[/bold green]")

        # 统计群组中的管理员情况
        admin_cnt = sum(1 for cid in seen if ADMIN_MAP.get(cid) == "管理员")
        owner_cnt = sum(1 for cid in seen if ADMIN_MAP.get(cid) == "群主")
        no_admin_cnt = sum(1 for cid in seen if ADMIN_MAP.get(cid) == "否")
        console.print(
            f"[bold green]其中群组管理员统计：管理员 {admin_cnt} 个 | 群主 {owner_cnt} 个 | "
            f"非管理员 {no_admin_cnt} 个[/bold green]"
        )

        # folder_id 映射(本账号服务端实测): 0=主列表, 1=置顶(Pinned), 自定义文件夹 id 来自 GetDialogFilters(≥2)
        # 注意: 该服务端用 folder_id=2 查归档会报 FOLDER_ID_INVALID，
        #       即没有可通过 getDialogs 查询的独立归档夹，故不再单列"归档"段。

        # -------- 置顶对话 (folder_id=1，本服务端实测=folder_id=1) --------
        console.rule("[bold yellow]置顶对话列表 (folder_id=1)")
        pinned = await fetch_folder(app, 1, "yellow")
        if not pinned:
            console.print("[dim]（没有置顶对话）[/dim]")
        for chat_id, chat_type, title in pinned:
            print_dialog(chat_id, chat_type, title, archived=True)
        console.print(f"\n[bold yellow]置顶列表总数：{len(pinned)}[/bold yellow]")

        # -------- 自定义聊天文件夹 (DialogFilter, id 通常 ≥2) --------
        console.rule("[bold magenta]自定义聊天文件夹")
        try:
            filters = await app.invoke(GetDialogFilters())
        except Exception as e:
            console.print(f"[red]获取文件夹失败: {e}[/red]")
            filters = []

        # 过滤掉 DialogFilterDefault（"全部聊天"默认夹，没有 .id 属性）
        filters = [f for f in filters if isinstance(f, DialogFilter)]

        if not filters:
            console.print("[dim]（没有自定义聊天文件夹）[/dim]")
        for f in filters:
            # 本服务端 getDialogs 仅支持 folder_id=0/1，自定义文件夹不能用 folder_id 查询；
            # 改为解析 DialogFilter 的定义：规则标志 + 显式包含的 peer。
            rules = []
            if getattr(f, "contacts", False): rules.append("联系人")
            if getattr(f, "non_contacts", False): rules.append("非联系人")
            if getattr(f, "groups", False): rules.append("群组")
            if getattr(f, "broadcasts", False): rules.append("频道")
            if getattr(f, "bots", False): rules.append("机器人")
            if getattr(f, "exclude_muted", False): rules.append("排除静音")
            if getattr(f, "exclude_read", False): rules.append("排除已读")
            if getattr(f, "exclude_archived", False): rules.append("排除归档")
            console.print(
                f"\n[bold magenta]📁 {f.title}[/bold magenta] "
                f"[dim](id={f.id}, 规则: {', '.join(rules) or '仅显式包含'})[/dim]"
            )
            console.print(
                f"[dim]显式包含 {len(f.include_peers)} 个 | 排除 {len(f.exclude_peers)} 个 | 置顶 {len(f.pinned_peers)} 个[/dim]"
            )
            for peer in f.include_peers:
                try:
                    chat_id, chat_type, title = await resolve_input_peer(app, peer)
                    print_dialog(chat_id, chat_type, title, archived=True)
                except Exception as e:
                    console.print(f"[red]⚠️ 跳过: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(main())
