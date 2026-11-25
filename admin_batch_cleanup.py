"""管理群批量清理脚本（默认执行，--dry-run 为演练模式）。

流程：实时检测“我是管理员/群主”的群 -> 导出 admin_chat_ids.json ->
加载待删除名单 -> 对命中成员执行批量剔除（默认）或仅预览（--dry-run）。

用法：
    python admin_batch_cleanup.py                    # 默认执行：真实剔除命中成员（不限人数）
    python admin_batch_cleanup.py --dry-run          # 演练：只预览命中名单，不执行删除
    python admin_batch_cleanup.py --max-kicks 50     # 限制单次最多剔除 50 人
    python admin_batch_cleanup.py --members 名单.json --admins-out 管理群.json
"""
import argparse
import asyncio
import sys

# Windows GBK 控制台下保证中文/emoji 正常输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from tg_member_cleaner import (
    ADMIN_CHATS_FILE,
    MEMBERS_FILE,
    build_client,
    clean_chats,
    export_admin_chats,
    load_delete_members,
    load_target_chats,
)


async def main():
    parser = argparse.ArgumentParser(description="管理群批量清理（默认执行，--dry-run 演练）")
    parser.add_argument("--dry-run", action="store_true", help="演练模式：只预览命中名单，不执行删除")
    parser.add_argument("--members", default=MEMBERS_FILE, help=f"待删除名单 JSON（默认 {MEMBERS_FILE}）")
    parser.add_argument("--admins-out", default=ADMIN_CHATS_FILE, help=f"管理群清单输出路径（默认 {ADMIN_CHATS_FILE}）")
    parser.add_argument("--max-kicks", type=int, default=0, help="单次剔除上限，0=不限制（默认），正数=设上限")
    args = parser.parse_args()

    if args.max_kicks < 0:
        parser.error("--max-kicks 不能为负数（0 表示不限制）")

    execute = not args.dry_run
    mode = "执行模式" if execute else "演练模式 (dry-run)"
    members = load_delete_members(args.members)
    print(f"📋 {mode} | 已加载待删除名单：{len(members)} 人（去重后）")

    app = build_client()
    async with app:
        # 1) 实时检测并导出管理群清单
        admin_chats = await export_admin_chats(app, out_path=args.admins_out)
        if not admin_chats:
            print("ℹ️ 未检测到任何管理群，流程结束。")
            return

        # 2) 复用清理脚本：从导出的 JSON 加载群 ID，执行批量剔除或演练预览
        chat_ids = load_target_chats(args.admins_out)
        await clean_chats(app, chat_ids, members, execute=execute, max_kicks=args.max_kicks)


if __name__ == "__main__":
    asyncio.run(main())
