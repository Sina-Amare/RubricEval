#!/usr/bin/env python3
"""
Test script to verify Telegram bot connection.

Run this to check if the bot token is valid and bot can connect.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from telegram import Bot
from config import BOT_TOKEN


async def test_connection():
    """Test bot connection."""
    print("🔄 Testing bot connection...")
    print(f"Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    
    try:
        # Create bot instance
        bot = Bot(token=BOT_TOKEN)
        
        # Get bot info
        bot_info = await bot.get_me()
        
        print("✅ Bot connection successful!")
        print(f"Bot Name: {bot_info.first_name}")
        print(f"Bot Username: @{bot_info.username}")
        print(f"Bot ID: {bot_info.id}")
        
        # Get updates to check if bot is receiving messages
        updates = await bot.get_updates(limit=1)
        if updates:
            print(f"\n📨 Bot has {len(updates)} pending update(s)")
        else:
            print("\n📨 No pending updates")
        
        print("\n✅ Bot is ready to use!")
        print("You can now run: python src/bot.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nPlease check:")
        print("1. Is the BOT_TOKEN correct in .env?")
        print("2. Did you create the bot with BotFather?")
        print("3. Is your internet connection working?")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)