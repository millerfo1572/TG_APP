import asyncio
import os
import sys
import time
from dotenv import load_dotenv
from pyrogram import Client
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

# 强制 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台打印 emoji/中文时报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 加载 .env
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "my_tg_account")

# 代理（与 test主对话列表.py 保持一致，从 .env 读取）
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

# 只保留的会话类型
TARGET_TYPES = ("GROUP", "SUPERGROUP")

async def main():
    start = time.time()
    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy_dict
        # 如果需要代理，在这里追加 proxy 参数
    )
    async with app:
        total = 0
        groups = []
        async for dialog in app.get_dialogs():
            total += 1
            chat = dialog.chat
            chat_type = chat.type.name if chat.type is not None else ""
            if chat_type in TARGET_TYPES:
                groups.append({
                    "chat_id": chat.id,
                    "type": chat_type,        # 群属性：GROUP(普通群) / SUPERGROUP(超级群)
                    "title": chat.title or ""
                })

        elapsed = time.time() - start
        print(f"✅ 扫描到总对话数：{total}（其中 群组/超级群：{len(groups)}）")
        print(f"⏱️ 本次执行耗时：{elapsed:.2f} 秒")

        # -------- 导出 Excel (.xlsx) --------
        wb = Workbook()
        ws = wb.active
        ws.title = "TG群组"

        # 表头（带样式）
        headers = ["群ID", "群属性", "群名称"]
        header_fill = PatternFill("solid", fgColor="4472C4")
        header_font = Font(bold=True, color="FFFFFF")
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # 数据行
        for r, g in enumerate(groups, start=2):
            ws.cell(row=r, column=1, value=g["chat_id"])
            ws.cell(row=r, column=2, value=g["type"])
            ws.cell(row=r, column=3, value=g["title"])

        # 列宽自适应（简单设定）
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 60

        # 冻结首行
        ws.freeze_panes = "A2"

        out_path = "my_tg_groups.xlsx"
        wb.save(out_path)
        print(f"📄 文件已输出：{out_path}")

if __name__ == "__main__":
    asyncio.run(main())
