"""
Main Telegram bot for CV Review System.

This module implements the manager-only bot for analyzing candidate repositories.
"""

import asyncio
import sys
from datetime import datetime, timezone
from typing import Optional

# Apply network fixes BEFORE importing telegram
from utils.network_fix import install_network_fixes
install_network_fixes()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

# Add imports from our modules
from config import BOT_TOKEN, MANAGER_IDS
from core.models import Submission, Role, SubmissionStatus
from core.exceptions import ValidationError, RepositoryError, AnalysisError
from adapters.storage.sqlite import SQLiteAdapter
from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from adapters.notifications.telegram import TelegramAdapter
from utils.logger import setup_logger, log_error_with_context
from utils.validators import validate_github_url

# Initialize logger
logger = setup_logger(__name__)

# Conversation states
WAITING_FOR_URL = 1
WAITING_FOR_ROLE = 2

# Initialize adapters (will be done in main)
storage_adapter = None
repo_adapter = None
analyzer_adapter = None
notification_adapter = None


# Command handlers

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    logger.info(f"Start command from user {user.username} ({user.id})")
    
    welcome_message = """
👋 Welcome to CV Review Bot!

I help you analyze candidate GitHub repositories quickly and consistently.

**How to use:**
1. Type /analyze to start
2. Send me the GitHub repository URL
3. Select the position (Backend/Frontend)
4. Get detailed analysis in 2-5 minutes

**Commands:**
/analyze - Start new analysis
/recent - View recent analyses
/stats - View statistics
/help - Show this message
/cancel - Cancel current operation
    """
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await start_command(update, context)


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the analysis conversation."""
    user = update.effective_user
    logger.info(f"Analyze command from user {user.username} ({user.id})")
    
    # Check if user is authorized (optional - remove if all users should have access)
    if MANAGER_IDS and str(user.id) not in MANAGER_IDS:
        await update.message.reply_text(
            "❌ You are not authorized to use this bot.\n"
            "Please contact the administrator."
        )
        return ConversationHandler.END
    
    prompt_message = """
📝 Please send me the GitHub repository URL for analysis.

**Example formats:**
• `https://github.com/username/repository`
• `https://github.com/username/repo.git`
    """
    
    await update.message.reply_text(
        prompt_message,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return WAITING_FOR_URL


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle URL submission."""
    user = update.effective_user
    url = update.message.text.strip()
    
    logger.info(f"Received URL from {user.username}: {url}")
    
    # Validate URL format
    is_valid, error_msg = validate_github_url(url)
    
    if not is_valid:
        # Provide helpful error message
        if "github.com" not in url.lower():
            error_response = """
❌ That doesn't appear to be a GitHub URL.

I can only analyze GitHub repositories.
Please send a GitHub URL like:
`https://github.com/username/repository`

Try again:
            """
        else:
            error_response = """
❌ The URL format seems incorrect.

Please check the URL format:
✓ `https://github.com/username/repo`
✓ `https://github.com/username/repo.git`

Try again:
            """
        
        await update.message.reply_text(
            error_response,
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_URL
    
    # Store URL in context for next step
    context.user_data['github_url'] = url
    
    # Try to validate repository accessibility
    await update.message.reply_chat_action(ChatAction.TYPING)
    
    try:
        # Quick check if repository exists and is accessible
        is_accessible = await repo_adapter.validate_url(url)
        
        if not is_accessible:
            await update.message.reply_text(
                "⚠️ I couldn't access this repository. Please check:\n"
                "• Is the repository public?\n"
                "• Is the URL correct?\n"
                "• Does the repository exist?\n\n"
                "Please send the URL again or type /cancel to stop.",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_FOR_URL
        
    except Exception as e:
        logger.warning(f"Error checking repository accessibility: {e}")
        # Continue anyway - will fail later with better error
    
    # Extract repository name for display
    repo_name = url.split('/')[-1].replace('.git', '')
    if '/' in url:
        owner_repo = '/'.join(url.split('/')[-2:]).replace('.git', '')
    else:
        owner_repo = repo_name
    
    # Ask for role selection
    message = f"""
✅ Repository found: `{owner_repo}`

Which position is this candidate applying for?
    """
    
    keyboard = [
        [
            InlineKeyboardButton("👨‍💻 Backend Developer", callback_data="role_backend"),
            InlineKeyboardButton("🎨 Frontend Developer", callback_data="role_frontend")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_ROLE


async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle role selection callback."""
    query = update.callback_query
    user = query.from_user
    
    # Acknowledge the callback
    await query.answer()
    
    # Get role from callback data
    role_str = query.data.replace("role_", "")
    role = Role.BACKEND if role_str == "backend" else Role.FRONTEND
    
    # Get stored URL
    github_url = context.user_data.get('github_url')
    
    if not github_url:
        await query.edit_message_text(
            "❌ Session expired. Please start again with /analyze"
        )
        return ConversationHandler.END
    
    logger.info(f"Starting analysis for {github_url} as {role.value}")
    
    # Update message to show processing
    await query.edit_message_text(
        f"🔄 Analyzing repository for {role.value} position...\n"
        f"This typically takes 2-5 minutes.\n\n"
        f"Repository: `{github_url.split('/')[-1]}`\n"
        f"Position: {role.value}\n"
        f"Status: Processing...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Start the analysis in background
    asyncio.create_task(
        process_analysis(
            query.message.chat_id,
            user.id,
            user.username,
            github_url,
            role,
            context
        )
    )
    
    return ConversationHandler.END


async def process_analysis(
    chat_id: int,
    user_id: int,
    username: str,
    github_url: str,
    role: Role,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Process the repository analysis.
    
    This runs as a background task to avoid blocking the bot.
    """
    try:
        # Create submission record
        submission = Submission(
            telegram_user_id=str(user_id),
            telegram_username=username or "Unknown",
            github_url=github_url,
            role=role,
            status=SubmissionStatus.PENDING
        )
        
        submission = await storage_adapter.create_submission(submission)
        logger.info(f"Created submission {submission.id}")
        
        # Update status to analyzing
        await storage_adapter.update_submission(
            submission.id,
            status=SubmissionStatus.ANALYZING
        )
        
        # Send progress update
        await context.bot.send_message(
            chat_id=chat_id,
            text="📥 Fetching repository content..."
        )
        
        # Fetch repository
        try:
            repo_content = await repo_adapter.fetch_repository(github_url, role)
            logger.info(f"Fetched repository: {len(repo_content.files)} files")
        except RepositoryError as e:
            raise Exception(f"Repository error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to fetch repository: {str(e)}")
        
        # Send another progress update
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔍 Analyzing {len(repo_content.files)} files..."
        )
        
        # Load task requirements
        task_file = f"data/task_requirements/{role.value}_task.md"
        try:
            with open(task_file, 'r') as f:
                task_requirements = f.read()
        except FileNotFoundError:
            logger.warning(f"Task file not found: {task_file}")
            task_requirements = f"Analyze this {role.value} repository for code quality and completeness."
        
        # Create analysis request
        from core.models import AnalysisRequest
        analysis_request = AnalysisRequest(
            repository_content=repo_content,
            role=role,
            task_requirements=task_requirements,
            github_url=github_url,
            submission_id=submission.id
        )
        
        # Perform analysis
        try:
            analysis_result = await analyzer_adapter.analyze_code(analysis_request)
            logger.info(f"Analysis complete for submission {submission.id}")
        except AnalysisError as e:
            raise Exception(f"Analysis error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to analyze code: {str(e)}")
        
        # Create report
        from core.models import Report
        report = Report(
            submission_id=submission.id,
            analysis_result=analysis_result,
            model_used=analyzer_adapter.models[0]['name'] if analyzer_adapter.models else "unknown",
            tokens_used=repo_content.total_tokens,
            analysis_duration=60  # TODO: Track actual duration
        )
        
        report = await storage_adapter.create_report(report)
        logger.info(f"Created report {report.id}")
        
        # Update submission status
        await storage_adapter.update_submission(
            submission.id,
            status=SubmissionStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc)
        )
        
        # Send results
        await notification_adapter.send_analysis_complete(
            str(chat_id),
            submission,
            report
        )
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Analysis failed for {github_url}: {error_msg}")
        log_error_with_context(logger, e, {'url': github_url, 'role': role.value})
        
        # Update submission as failed
        if submission and submission.id:
            await storage_adapter.update_submission(
                submission.id,
                status=SubmissionStatus.FAILED,
                error_message=error_msg[:500],  # Truncate long errors
                completed_at=datetime.now(timezone.utc)
            )
        
        # Send error message
        await notification_adapter.send_analysis_failed(
            str(chat_id),
            submission,
            error_msg
        )
    
    finally:
        # Clean up repository adapter
        await repo_adapter.cleanup()


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent analyses."""
    user = update.effective_user
    logger.info(f"Recent command from user {user.username} ({user.id})")
    
    try:
        # Get recent reports
        reports = await storage_adapter.get_recent_reports(limit=10)
        
        if not reports:
            await update.message.reply_text(
                "📋 No recent analyses found.\n\n"
                "Use /analyze to start a new analysis."
            )
            return
        
        # Format report list
        message = "📋 **Recent Analyses:**\n\n"
        
        for i, report in enumerate(reports, 1):
            # Get submission details
            submission = await storage_adapter.get_submission(report.submission_id)
            if submission:
                repo_name = submission.github_url.split('/')[-1].replace('.git', '')
                role = submission.role.value
            else:
                repo_name = "Unknown"
                role = "Unknown"
            
            score = report.analysis_result.get_overall_score()
            rec = report.analysis_result.recommendation.value.replace('_', ' ').upper()
            
            # Format time
            if report.created_at:
                time_diff = datetime.now(timezone.utc) - report.created_at
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}d ago"
                elif time_diff.seconds > 3600:
                    time_str = f"{time_diff.seconds // 3600}h ago"
                else:
                    time_str = f"{time_diff.seconds // 60}m ago"
            else:
                time_str = "Unknown"
            
            message += f"{i}. `{repo_name}` ({role})\n"
            message += f"   Score: {score:.0%} - {rec}\n"
            message += f"   _Analyzed {time_str}_\n\n"
        
        message += "_Use /analyze to start a new analysis_"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in recent command: {e}")
        await update.message.reply_text(
            "❌ Error retrieving recent analyses.\n"
            "Please try again later."
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics."""
    user = update.effective_user
    logger.info(f"Stats command from user {user.username} ({user.id})")
    
    try:
        # Get statistics
        stats = await storage_adapter.get_statistics()
        
        # Format statistics message
        message = f"""
📊 **System Statistics**
━━━━━━━━━━━━━━━━━━━━

**Overall:**
• Total Analyses: {stats.get('total_submissions', 0)}
• Completed: {stats.get('completed_submissions', 0)}
• Failed: {stats.get('failed_submissions', 0)}
• Last 24h: {stats.get('recent_submissions_24h', 0)}

**By Position:**
        """
        
        role_breakdown = stats.get('role_breakdown', {})
        for role, count in role_breakdown.items():
            message += f"• {role.title()}: {count}\n"
        
        message += "\n**Recommendations:**\n"
        rec_breakdown = stats.get('recommendation_breakdown', {})
        for rec, count in rec_breakdown.items():
            message += f"• {rec.upper()}: {count}\n"
        
        if 'average_confidence' in stats and stats['average_confidence']:
            message += f"\n**Average Confidence:** {stats['average_confidence']:.0%}"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text(
            "❌ Error retrieving statistics.\n"
            "Please try again later."
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    user = update.effective_user
    logger.info(f"Cancel command from user {user.username} ({user.id})")
    
    # Clear user data
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ Operation cancelled.\n\n"
        "Use /analyze to start a new analysis."
    )
    
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Try to notify user
    try:
        if update and hasattr(update, 'effective_chat'):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ An error occurred. Please try again or contact support."
            )
    except:
        pass


async def initialize_adapters():
    """Initialize all adapters."""
    global storage_adapter, repo_adapter, analyzer_adapter, notification_adapter
    
    logger.info("Initializing adapters...")
    
    # Initialize storage
    storage_adapter = SQLiteAdapter()
    await storage_adapter.initialize()
    logger.info("Storage adapter initialized")
    
    # Initialize repository adapter
    repo_adapter = GitHubAdapter()
    logger.info("Repository adapter initialized")
    
    # Initialize analyzer
    analyzer_adapter = OpenRouterAdapter()
    logger.info("Analyzer adapter initialized")
    
    # Initialize notification adapter
    notification_adapter = TelegramAdapter()
    await notification_adapter.initialize()
    logger.info("Notification adapter initialized")


def main() -> None:
    """Main function to run the bot."""
    logger.info("Starting CV Review Bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Set up conversation handler for analyze command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_command)],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
            WAITING_FOR_ROLE: [CallbackQueryHandler(role_callback, pattern="^role_")]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Initialize adapters before starting
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(initialize_adapters())
    
    logger.info("Bot is ready! Starting polling...")
    
    # Start the bot
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)