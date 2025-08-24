#!/bin/bash
# Start the CV Review Bot

echo "🚀 Starting CV Review Bot..."
echo "📱 Bot: @TaskEvaluator_bot"
echo "================================"
echo ""
echo "Commands:"
echo "  /start   - Welcome message"
echo "  /analyze - Start analysis"
echo "  /recent  - View recent analyses"
echo "  /stats   - View statistics"
echo "  /help    - Show help"
echo ""
echo "Press Ctrl+C to stop the bot"
echo "================================"
echo ""

# Activate virtual environment
source venv/bin/activate

# Run the bot
python src/bot.py