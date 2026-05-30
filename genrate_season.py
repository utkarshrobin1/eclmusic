"""
Run this script once to generate your Pyrogram STRING SESSION.
After generating, set SESSION_STRING as an environment variable (or in .env).
"""

import asyncio
import os

try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client

API_ID   = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")

if not API_ID or not API_HASH:
    raise SystemExit("Set API_ID and API_HASH as environment variables before running.")


async def main():
    print("Starting Session Generator...")
    print("Enter your phone number with country code (e.g. +91...) when prompted.\n")

    app = Client("my_account", api_id=int(API_ID), api_hash=API_HASH, in_memory=True)

    await app.start()
    string_session = await app.export_session_string()

    print("\n" + "=" * 60)
    print(">> YOUR STRING SESSION <<")
    print("=" * 60 + "\n")
    print(string_session)
    print("\n" + "=" * 60)
    print("Copy the session above and set it as SESSION_STRING in your .env file.")

    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
