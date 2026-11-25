import asyncio
import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram import enums

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

async def main():
    async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, proxy=proxy_dict) as app:
        me = await app.get_me()
        print("✅ Session 有效！")
        print(f"ID: {me.id}")
        print(f"Name: {me.first_name} {me.last_name or ''}")
        print(f"Username: @{me.username if me.username else 'none'}")

if __name__ == "__main__":
    asyncio.run(main())
