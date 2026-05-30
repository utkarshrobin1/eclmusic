"""
Run this script ONCE to generate your STRING_SESSION.
It will prompt for your phone number and OTP.

Usage:
    python gen_session.py

Then copy the printed string session into your .env file.
"""
from pyrogram import Client
import os

API_ID = int(input("Enter API_ID: ").strip())
API_HASH = input("Enter API_HASH: ").strip()

with Client("gen_session", api_id=API_ID, api_hash=API_HASH) as app:
    print("\n✅ Your STRING_SESSION is:")
    print(app.export_session_string())
    print("\nCopy the above string into your .env file as STRING_SESSION=<value>")
