"""群成员清理入口脚本（默认执行，--dry-run 为演练模式）。

用法：
    python clean_group_members.py                    # 默认执行：真实剔除命中成员（不限人数）
    python clean_group_members.py --dry-run          # 演练：只预览命中名单，不执行删除
    python clean_group_members.py --max-kicks 50     # 限制单次最多剔除 50 人
    python clean_group_members.py --members 名单.json --chats 群配置.json
"""
import argparse
import asyncio
import sys

# Windows GBK 控制台下保证中文/emoji 正常输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from tg_member_cleaner import (
    MEMBERS_FILE,
    CHATS_FILE,
    build_client,
    clean_chats,
    load_delete_members,
    load_target_chats,
)


async def main():
    parser = argparse.ArgumentParser(description="Telegram 群成员清理工具（默认执行，--dry-run 演练）")
    parser.add_argument("--dry-run", action="store_true", help="演练模式：只预览命中名单，不执行删除")
    parser.add_argument("--members", default=MEMBERS_FILE, help=f"待删除名单 JSON（默认 {MEMBERS_FILE}）")
    parser.add_argument("--chats", default=CHATS_FILE, help=f"目标群 ID 配置 JSON（默认 {CHATS_FILE}）")
    parser.add_argument("--max-kicks", type=int, default=0, help="单次剔除上限，0=不限制（默认），正数=设上限")
    args = parser.parse_args()

    if args.max_kicks < 0:
        parser.error("--max-kicks 不能为负数（0 表示不限制）")

    execute = not args.dry_run
    members = load_delete_members(args.members)
    chat_ids = load_target_chats(args.chats)
    mode = "执行模式" if execute else "演练模式 (dry-run)"
    print(f"📋 {mode} | 名单 {len(members)} 人（去重后） | 目标群 {len(chat_ids)} 个")

    app = build_client()
    async with app:
        await clean_chats(app, chat_ids, members, execute=execute, max_kicks=args.max_kicks)


if __name__ == "__main__":
    asyncio.run(main())
