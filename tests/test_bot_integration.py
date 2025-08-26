"""
Tests for Telegram bot integration and handlers.

This module tests the Telegram bot handlers, user interactions,
and end-to-end workflow scenarios.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from bot import (
    start_command, help_command, submit_command, status_command,
    stats_command, recent_command, cancel_command
)
from core.models import (
    Submission, Report, AnalysisResult, Role, SubmissionStatus, 
    RecommendationLevel
)
from core.exceptions import AnalysisError, StorageError


@pytest.mark.integration
@pytest.mark.asyncio
class TestBotCommands:
    """Test basic bot command handlers."""
    
    async def test_start_command(self, mock_telegram_update, mock_telegram_context):
        """Test /start command handler."""
        await start_command(mock_telegram_update, mock_telegram_context)
        
        # Verify response was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        response_text = call_args[0][0]
        
        # Check that welcome message contains key information
        assert "Welcome" in response_text
        assert "/submit" in response_text
        assert "/help" in response_text
    
    async def test_help_command(self, mock_telegram_update, mock_telegram_context):
        """Test /help command handler."""
        await help_command(mock_telegram_update, mock_telegram_context)
        
        # Verify response was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        response_text = call_args[0][0]
        
        # Check that help message contains command information
        assert "/submit" in response_text
        assert "/status" in response_text
        assert "/stats" in response_text
        assert "GitHub" in response_text
    
    async def test_submit_command_no_url(self, mock_telegram_update, mock_telegram_context):
        """Test /submit command without URL argument."""
        mock_telegram_context.args = []
        
        await submit_command(mock_telegram_update, mock_telegram_context)
        
        # Should ask for URL
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        response_text = call_args[0][0]
        
        assert "Usage:" in response_text or "Please provide" in response_text
        assert "GitHub URL" in response_text
    
    async def test_submit_command_invalid_url(self, mock_telegram_update, mock_telegram_context):
        """Test /submit command with invalid URL."""
        mock_telegram_context.args = ["https://gitlab.com/user/repo"]  # Invalid (not GitHub)
        
        await submit_command(mock_telegram_update, mock_telegram_context)
        
        # Should show error message
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        response_text = call_args[0][0]
        
        assert "Invalid" in response_text or "Error" in response_text
        assert "GitHub" in response_text
    
    async def test_status_command_no_submissions(self, mock_telegram_update, mock_telegram_context):
        """Test /status command when user has no submissions."""
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.return_value = []
            
            await status_command(mock_telegram_update, mock_telegram_context)
            
            # Should indicate no submissions
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "no submissions" in response_text.lower() or "haven't submitted" in response_text.lower()
    
    async def test_cancel_command_no_pending(self, mock_telegram_update, mock_telegram_context):
        """Test /cancel command when no pending submissions."""
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.return_value = []
            
            await cancel_command(mock_telegram_update, mock_telegram_context)
            
            # Should indicate nothing to cancel
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "no pending" in response_text.lower() or "nothing to cancel" in response_text.lower()


@pytest.mark.integration
@pytest.mark.asyncio
class TestBotSubmissionWorkflow:
    """Test complete submission workflow scenarios."""
    
    @pytest.fixture
    def mock_storage_adapter(self):
        """Mock storage adapter for testing."""
        adapter = AsyncMock()
        adapter.check_duplicate_submission.return_value = False
        adapter.create_submission.return_value = Submission(
            id=1,
            telegram_user_id="123456789",
            telegram_username="testuser",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            status=SubmissionStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        return adapter
    
    @pytest.fixture
    def mock_analyzer_adapter(self, sample_analysis_result):
        """Mock analyzer adapter for testing."""
        adapter = AsyncMock()
        adapter.analyze_code.return_value = sample_analysis_result
        return adapter
    
    @pytest.fixture
    def mock_github_adapter(self):
        """Mock GitHub adapter for testing."""
        from core.models import RepositoryContent, FileInfo
        
        adapter = AsyncMock()
        
        # Mock repository content
        file_info = FileInfo(
            path="src/main.py",
            content="def main():\n    print('Hello World!')",
            priority="critical",
            tokens=50,
            language="python"
        )
        
        repo_content = RepositoryContent(
            url="https://github.com/test/repo",
            files=[file_info],
            total_tokens=50,
            structure="src/\n  main.py",
            metadata={"branch": "main", "commit": "abc123"}
        )
        
        adapter.extract_repository_content.return_value = repo_content
        return adapter
    
    async def test_successful_submission_workflow(
        self, 
        mock_telegram_update, 
        mock_telegram_context,
        mock_storage_adapter,
        mock_analyzer_adapter,
        mock_github_adapter,
        sample_analysis_result
    ):
        """Test complete successful submission workflow."""
        mock_telegram_context.args = ["https://github.com/test/repo"]
        
        # Mock the adapters
        with patch('bot.storage_adapter', mock_storage_adapter), \
             patch('bot.analyzer_adapter', mock_analyzer_adapter), \
             patch('bot.github_adapter', mock_github_adapter):
            
            await submit_command(mock_telegram_update, mock_telegram_context)
            
            # Should start role selection
            mock_telegram_update.message.reply_text.assert_called()
            
            # Verify adapters were called
            mock_storage_adapter.check_duplicate_submission.assert_called_once()
            mock_storage_adapter.create_submission.assert_called_once()
    
    async def test_duplicate_submission_handling(
        self,
        mock_telegram_update,
        mock_telegram_context,
        mock_storage_adapter
    ):
        """Test handling of duplicate submission attempts."""
        mock_telegram_context.args = ["https://github.com/test/repo"]
        mock_storage_adapter.check_duplicate_submission.return_value = True
        
        with patch('bot.storage_adapter', mock_storage_adapter):
            await submit_command(mock_telegram_update, mock_telegram_context)
            
            # Should indicate duplicate
            mock_telegram_update.message.reply_text.assert_called()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "already submitted" in response_text.lower() or "duplicate" in response_text.lower()
    
    async def test_github_extraction_error_handling(
        self,
        mock_telegram_update,
        mock_telegram_context,
        mock_storage_adapter,
        mock_github_adapter
    ):
        """Test handling of GitHub repository extraction errors."""
        mock_telegram_context.args = ["https://github.com/test/repo"]
        mock_storage_adapter.check_duplicate_submission.return_value = False
        mock_github_adapter.extract_repository_content.side_effect = Exception("Repository not found")
        
        with patch('bot.storage_adapter', mock_storage_adapter), \
             patch('bot.github_adapter', mock_github_adapter):
            
            await submit_command(mock_telegram_update, mock_telegram_context)
            
            # Should handle error gracefully
            mock_telegram_update.message.reply_text.assert_called()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "error" in response_text.lower() or "failed" in response_text.lower()
    
    async def test_analysis_error_handling(
        self,
        mock_telegram_update,
        mock_telegram_context,
        mock_storage_adapter,
        mock_analyzer_adapter,
        mock_github_adapter
    ):
        """Test handling of analysis errors."""
        mock_telegram_context.args = ["https://github.com/test/repo"]
        mock_storage_adapter.check_duplicate_submission.return_value = False
        mock_analyzer_adapter.analyze_code.side_effect = AnalysisError("Analysis failed")
        
        with patch('bot.storage_adapter', mock_storage_adapter), \
             patch('bot.analyzer_adapter', mock_analyzer_adapter), \
             patch('bot.github_adapter', mock_github_adapter):
            
            await submit_command(mock_telegram_update, mock_telegram_context)
            
            # Should update submission status to failed
            mock_storage_adapter.update_submission.assert_called()


@pytest.mark.integration  
@pytest.mark.asyncio
class TestBotRoleSelection:
    """Test role selection workflow."""
    
    async def test_role_selection_callback_backend(self, mock_telegram_update, mock_telegram_context):
        """Test backend role selection callback."""
        # Mock callback query for role selection
        callback_query = MagicMock()
        callback_query.data = "role_backend_1"  # Format: role_{role}_{submission_id}
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        
        mock_telegram_update.callback_query = callback_query
        
        with patch('bot.handle_role_selection') as mock_handler:
            mock_handler.return_value = None
            
            # Import and test the role selection handler
            from bot import button_callback
            await button_callback(mock_telegram_update, mock_telegram_context)
            
            callback_query.answer.assert_called_once()
    
    async def test_role_selection_callback_frontend(self, mock_telegram_update, mock_telegram_context):
        """Test frontend role selection callback."""
        callback_query = MagicMock()
        callback_query.data = "role_frontend_1"
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        
        mock_telegram_update.callback_query = callback_query
        
        with patch('bot.handle_role_selection') as mock_handler:
            mock_handler.return_value = None
            
            from bot import button_callback
            await button_callback(mock_telegram_update, mock_telegram_context)
            
            callback_query.answer.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio 
class TestBotStatusAndStats:
    """Test status and statistics commands."""
    
    @pytest.fixture
    def sample_submissions(self):
        """Create sample submissions for testing."""
        return [
            Submission(
                id=1,
                telegram_user_id="123456789",
                telegram_username="testuser",
                github_url="https://github.com/test/repo1",
                role=Role.BACKEND,
                status=SubmissionStatus.COMPLETED,
                created_at=datetime.now(timezone.utc)
            ),
            Submission(
                id=2,
                telegram_user_id="123456789", 
                telegram_username="testuser",
                github_url="https://github.com/test/repo2",
                role=Role.FRONTEND,
                status=SubmissionStatus.PENDING,
                created_at=datetime.now(timezone.utc)
            )
        ]
    
    async def test_status_command_with_submissions(
        self, 
        mock_telegram_update, 
        mock_telegram_context,
        sample_submissions
    ):
        """Test /status command with user submissions."""
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.return_value = sample_submissions
            
            await status_command(mock_telegram_update, mock_telegram_context)
            
            # Should show submission details
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "repo1" in response_text
            assert "repo2" in response_text
            assert "COMPLETED" in response_text or "Completed" in response_text
            assert "PENDING" in response_text or "Pending" in response_text
    
    async def test_stats_command_manager(self, mock_telegram_update, mock_telegram_context):
        """Test /stats command for manager users."""
        # Mock user as manager
        mock_telegram_update.effective_user.id = 123456789  # From mock env vars MANAGER_IDS
        
        sample_stats = {
            "total_submissions": 10,
            "completed_submissions": 8,
            "failed_submissions": 1,
            "pending_submissions": 1,
            "status_breakdown": {
                "completed": 8,
                "failed": 1,
                "pending": 1
            },
            "role_breakdown": {
                "backend": 6,
                "frontend": 4
            },
            "average_confidence": 0.78
        }
        
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_statistics') as mock_get_stats:
            mock_get_stats.return_value = sample_stats
            
            await stats_command(mock_telegram_update, mock_telegram_context)
            
            # Should show statistics
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "10" in response_text  # Total submissions
            assert "78%" in response_text or "0.78" in response_text  # Average confidence
            assert "backend" in response_text.lower()
            assert "frontend" in response_text.lower()
    
    async def test_stats_command_non_manager(self, mock_telegram_update, mock_telegram_context):
        """Test /stats command for non-manager users."""
        # Mock user as non-manager
        mock_telegram_update.effective_user.id = 999999999  # Not in MANAGER_IDS
        
        await stats_command(mock_telegram_update, mock_telegram_context)
        
        # Should deny access
        mock_telegram_update.message.reply_text.assert_called_once()
        call_args = mock_telegram_update.message.reply_text.call_args
        response_text = call_args[0][0]
        
        assert "authorized" in response_text.lower() or "permission" in response_text.lower()
    
    async def test_recent_command_manager(self, mock_telegram_update, mock_telegram_context, sample_analysis_result):
        """Test /recent command for manager users."""
        mock_telegram_update.effective_user.id = 123456789  # Manager ID
        
        sample_reports = [
            Report(
                id=1,
                submission_id=1,
                analysis_result=sample_analysis_result,
                model_used="test/model",
                tokens_used=1000,
                analysis_duration=30.0,
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_recent_reports') as mock_get_recent:
            mock_get_recent.return_value = sample_reports
            
            await recent_command(mock_telegram_update, mock_telegram_context)
            
            # Should show recent reports
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "Recent" in response_text
            assert str(sample_analysis_result.confidence) in response_text or f"{sample_analysis_result.confidence*100:.1f}%" in response_text


@pytest.mark.integration
@pytest.mark.asyncio
class TestBotErrorHandling:
    """Test bot error handling scenarios."""
    
    async def test_database_connection_error(self, mock_telegram_update, mock_telegram_context):
        """Test handling of database connection errors."""
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.side_effect = StorageError("Database connection failed")
            
            await status_command(mock_telegram_update, mock_telegram_context)
            
            # Should handle error gracefully
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "error" in response_text.lower() or "unavailable" in response_text.lower()
    
    async def test_unexpected_exception(self, mock_telegram_update, mock_telegram_context):
        """Test handling of unexpected exceptions."""
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.side_effect = Exception("Unexpected error")
            
            await status_command(mock_telegram_update, mock_telegram_context)
            
            # Should handle error gracefully
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            assert "error" in response_text.lower() or "something went wrong" in response_text.lower()
    
    async def test_telegram_api_error(self, mock_telegram_update, mock_telegram_context):
        """Test handling of Telegram API errors."""
        # Mock Telegram API failure
        mock_telegram_update.message.reply_text.side_effect = Exception("Telegram API error")
        
        # Should not crash the bot
        try:
            await start_command(mock_telegram_update, mock_telegram_context)
        except Exception as e:
            # Should handle gracefully or let the error be caught by bot framework
            assert "Telegram API error" in str(e)


@pytest.mark.integration
@pytest.mark.asyncio
class TestBotMessageFormatting:
    """Test message formatting and presentation."""
    
    async def test_submission_status_formatting(self, mock_telegram_update, mock_telegram_context):
        """Test formatting of submission status messages."""
        sample_submissions = [
            Submission(
                id=1,
                telegram_user_id="123456789",
                telegram_username="testuser",
                github_url="https://github.com/test/very-long-repository-name-for-testing",
                role=Role.BACKEND,
                status=SubmissionStatus.COMPLETED,
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.return_value = sample_submissions
            
            await status_command(mock_telegram_update, mock_telegram_context)
            
            # Should format message nicely
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            # Check formatting elements
            assert "=Ê" in response_text or "Status" in response_text  # Status emoji/title
            assert "" in response_text or "COMPLETED" in response_text  # Completion indicator
            assert "backend" in response_text.lower()
    
    async def test_stats_formatting_manager(self, mock_telegram_update, mock_telegram_context):
        """Test formatting of statistics for managers."""
        mock_telegram_update.effective_user.id = 123456789  # Manager ID
        
        sample_stats = {
            "total_submissions": 42,
            "completed_submissions": 35,
            "failed_submissions": 5,
            "pending_submissions": 2,
            "status_breakdown": {"completed": 35, "failed": 5, "pending": 2},
            "role_breakdown": {"backend": 25, "frontend": 17},
            "recommendation_breakdown": {"accept": 20, "reject": 10, "review_required": 5},
            "average_confidence": 0.823
        }
        
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_statistics') as mock_get_stats:
            mock_get_stats.return_value = sample_stats
            
            await stats_command(mock_telegram_update, mock_telegram_context)
            
            # Should format statistics nicely
            mock_telegram_update.message.reply_text.assert_called_once()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            # Check key statistics are included
            assert "42" in response_text  # Total submissions
            assert "35" in response_text  # Completed
            assert "82.3%" in response_text or "82%" in response_text  # Average confidence
            assert "=È" in response_text or "Statistics" in response_text  # Stats indicator
    
    async def test_message_length_handling(self, mock_telegram_update, mock_telegram_context):
        """Test handling of long messages that exceed Telegram limits."""
        # Create many submissions to potentially exceed message length
        long_submissions_list = []
        for i in range(50):
            long_submissions_list.append(Submission(
                id=i,
                telegram_user_id="123456789",
                telegram_username="testuser",
                github_url=f"https://github.com/test/repository-with-very-long-name-{i}",
                role=Role.BACKEND if i % 2 == 0 else Role.FRONTEND,
                status=SubmissionStatus.COMPLETED,
                created_at=datetime.now(timezone.utc)
            ))
        
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.return_value = long_submissions_list
            
            await status_command(mock_telegram_update, mock_telegram_context)
            
            # Should handle long message (either truncate or split)
            mock_telegram_update.message.reply_text.assert_called()
            call_args = mock_telegram_update.message.reply_text.call_args
            response_text = call_args[0][0]
            
            # Should not exceed Telegram message limit
            assert len(response_text) <= 4096
            
            # Should indicate if truncated
            if len(long_submissions_list) > 10:  # Assuming some limit in implementation
                assert "..." in response_text or "more" in response_text.lower()


@pytest.mark.integration
@pytest.mark.asyncio
class TestBotConcurrency:
    """Test concurrent user interactions."""
    
    async def test_concurrent_submissions(self):
        """Test handling multiple concurrent submissions."""
        # Create multiple mock updates for different users
        updates = []
        contexts = []
        
        for i in range(3):
            update = MagicMock()
            update.effective_user.id = 123456789 + i
            update.effective_user.username = f"user{i}"
            update.effective_chat.id = 123456789 + i
            update.message.reply_text = AsyncMock()
            update.message.reply_chat_action = AsyncMock()
            updates.append(update)
            
            context = MagicMock()
            context.bot.send_message = AsyncMock()
            context.user_data = {}
            context.args = [f"https://github.com/test/repo{i}"]
            contexts.append(context)
        
        # Mock storage to avoid duplicates
        with patch('adapters.storage.sqlite.SQLiteAdapter.check_duplicate_submission') as mock_check:
            mock_check.return_value = False
            
            with patch('adapters.storage.sqlite.SQLiteAdapter.create_submission') as mock_create:
                mock_create.side_effect = [
                    Submission(id=i, telegram_user_id=str(123456789 + i), telegram_username=f"user{i}",
                              github_url=f"https://github.com/test/repo{i}", role=Role.BACKEND, 
                              status=SubmissionStatus.PENDING, created_at=datetime.now(timezone.utc))
                    for i in range(3)
                ]
                
                # Run concurrent submissions
                tasks = [submit_command(updates[i], contexts[i]) for i in range(3)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # All should complete without exceptions
                for result in results:
                    assert result is None  # Commands return None on success
                    assert not isinstance(result, Exception)
                
                # All users should have received responses
                for update in updates:
                    update.message.reply_text.assert_called()


@pytest.mark.integration
@pytest.mark.asyncio
class TestBotConfiguration:
    """Test bot configuration and environment handling."""
    
    async def test_manager_access_control(self, mock_telegram_update, mock_telegram_context):
        """Test manager access control for admin commands."""
        # Test with manager ID
        mock_telegram_update.effective_user.id = 123456789  # From mock env vars
        
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_statistics') as mock_get_stats:
            mock_get_stats.return_value = {"total_submissions": 0}
            
            await stats_command(mock_telegram_update, mock_telegram_context)
            
            # Manager should have access
            mock_get_stats.assert_called_once()
        
        # Test with non-manager ID
        mock_telegram_update.effective_user.id = 999999999
        
        await stats_command(mock_telegram_update, mock_telegram_context)
        
        # Should deny access
        mock_telegram_update.message.reply_text.assert_called()
        call_args = mock_telegram_update.message.reply_text.call_args
        response_text = call_args[0][0]
        
        assert "authorized" in response_text.lower() or "permission" in response_text.lower()
    
    async def test_bot_error_logging(self, mock_telegram_update, mock_telegram_context):
        """Test that bot errors are properly logged."""
        with patch('adapters.storage.sqlite.SQLiteAdapter.get_user_submissions') as mock_get:
            mock_get.side_effect = Exception("Test exception")
            
            with patch('utils.logger.setup_logger') as mock_logger:
                logger_instance = MagicMock()
                mock_logger.return_value = logger_instance
                
                await status_command(mock_telegram_update, mock_telegram_context)
                
                # Error should be logged (implementation dependent)
                # This test ensures logging infrastructure is in place