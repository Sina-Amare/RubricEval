# CV Review Bot - Deployment Guide

## Quick Start (Development)

```bash
# Use the run script that handles everything
./run_bot.sh
```

## Production Deployment (Linux Server)

### 1. Initial Setup

```bash
# Clone repository
git clone <your-repo-url> cv_review
cd cv_review

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your BOT_TOKEN and OPENROUTER_KEY

# Create necessary directories
mkdir -p logs data/reports

# Test the bot
./run_bot.sh
```

### 2. Install as System Service (Recommended)

```bash
# Copy service file
sudo cp cv-review-bot.service /etc/systemd/system/

# Edit service file to match your paths
sudo nano /etc/systemd/system/cv-review-bot.service
# Update User= and WorkingDirectory= paths

# Reload systemd
sudo systemctl daemon-reload

# Enable bot to start on boot
sudo systemctl enable cv-review-bot

# Start the bot
sudo systemctl start cv-review-bot

# Check status
sudo systemctl status cv-review-bot

# View logs
sudo journalctl -u cv-review-bot -f
```

### 3. Service Management Commands

```bash
# Start bot
sudo systemctl start cv-review-bot

# Stop bot
sudo systemctl stop cv-review-bot

# Restart bot
sudo systemctl restart cv-review-bot

# Check status
sudo systemctl status cv-review-bot

# View logs
sudo journalctl -u cv-review-bot -f

# Disable auto-start
sudo systemctl disable cv-review-bot
```

## Docker Deployment (Alternative)

```bash
# Build image
docker build -t cv-review-bot .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Database Management

```bash
# Check database status
python scripts/check_db.py

# Clear failed submissions
python scripts/clear_db.py --failed

# Reset database (careful!)
python scripts/clear_db.py --reset
```

## Conflict Prevention Features

The bot now includes multiple layers of conflict prevention:

1. **PID File Management**: Tracks running instance in `/tmp/cv_review_bot.pid`
2. **Automatic Cleanup**: Kills previous instance if found
3. **Webhook Deletion**: Clears Telegram webhooks on startup
4. **Signal Handlers**: Graceful shutdown on SIGTERM/SIGINT
5. **Retry Logic**: Handles network issues during startup

## No More Manual Kills Needed!

The bot automatically:
- Detects and stops previous instances
- Clears Telegram webhooks
- Handles graceful shutdown
- Restarts on crashes (when using systemd)

## Troubleshooting

### Bot not responding to commands
```bash
# Check if bot is running
sudo systemctl status cv-review-bot

# Check for errors in logs
sudo journalctl -u cv-review-bot -n 100

# Restart bot
sudo systemctl restart cv-review-bot
```

### Database issues
```bash
# Check database
python scripts/check_db.py

# Clear stuck submissions
python scripts/clear_db.py --failed
```

### Telegram conflicts
The bot now handles this automatically, but if needed:
```bash
# Force clear webhooks
python3 -c "
import asyncio
from telegram import Bot
from config import BOT_TOKEN

async def clear():
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    print('Webhooks cleared')

asyncio.run(clear())
"
```

## Environment Variables

Required in `.env`:
```bash
BOT_TOKEN=your_telegram_bot_token
OPENROUTER_KEY=your_openrouter_api_key
```

Optional:
```bash
MANAGER_IDS=telegram_id1,telegram_id2
PRIMARY_MODEL=google/gemini-2.5-flash
FALLBACK_MODEL=openai/gpt-5-mini
DATABASE_PATH=./data/reviews.db
MAX_REPO_SIZE_MB=100
ANALYSIS_TIMEOUT=600
```