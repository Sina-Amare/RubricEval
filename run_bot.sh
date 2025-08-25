#!/bin/bash

# CV Review Bot - Production Startup Script
# This script ensures only one instance runs and handles all cleanup

echo "========================================"
echo "CV Review Bot - Starting..."
echo "========================================"

# Configuration
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Check if running in Docker container
if [ -f /.dockerenv ]; then
    # Running in Docker - use container's tmp
    PID_FILE="/tmp/cv_review_bot.pid"
    echo "Running in Docker container"
else
    # Running on host - use local tmp
    PID_FILE="/tmp/cv_review_bot.pid"
    echo "Running on host system"
fi
LOG_FILE="$BOT_DIR/logs/bot.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if process is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Check for existing instance
if is_running; then
    OLD_PID=$(cat "$PID_FILE")
    echo -e "${YELLOW}Found existing bot instance (PID: $OLD_PID)${NC}"
    echo "Stopping it gracefully..."
    
    # Try graceful shutdown first
    kill -TERM "$OLD_PID" 2>/dev/null
    
    # Wait up to 5 seconds for graceful shutdown
    for i in {1..5}; do
        if ! is_running; then
            echo -e "${GREEN}Previous instance stopped successfully${NC}"
            break
        fi
        sleep 1
    done
    
    # Force kill if still running
    if is_running; then
        echo -e "${YELLOW}Force stopping stubborn instance...${NC}"
        kill -9 "$OLD_PID" 2>/dev/null
        rm -f "$PID_FILE"
    fi
fi

# Clean up any orphaned PID file
rm -f "$PID_FILE"

# Activate virtual environment
if [ -d "$BOT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$BOT_DIR/venv/bin/activate"
else
    echo -e "${RED}Virtual environment not found! Please run: python3 -m venv venv${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f "$BOT_DIR/.env" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$BOT_DIR/logs"

# Clear old webhook connections (using Python directly)
echo "Clearing any stale Telegram connections..."
python3 -c "
import os
import sys
sys.path.insert(0, '$BOT_DIR/src')
from config import BOT_TOKEN
import asyncio
from telegram import Bot

async def clear_webhook():
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        print('✓ Telegram webhooks cleared')
    except Exception as e:
        print(f'Warning: Could not clear webhooks: {e}')

asyncio.run(clear_webhook())
" 2>/dev/null

# Start the bot
echo -e "${GREEN}Starting CV Review Bot...${NC}"
echo "Logs will be written to: $LOG_FILE"
echo "========================================"

# Run the bot - it has its own restart logic in Python
# We don't need shell-level restart since bot.py handles it
python3 "$BOT_DIR/src/bot.py" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Bot stopped normally${NC}"
else
    echo -e "${YELLOW}Bot exited with code $EXIT_CODE${NC}"
    echo "Note: The bot has internal recovery mechanisms and should have restarted automatically"
fi

echo "========================================"
echo "Bot shutdown complete"
echo "========================================"