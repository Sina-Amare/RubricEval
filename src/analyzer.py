"""
LLM analysis module for CV Review Bot (Facade).

This module provides backward compatibility for the original analyzer interface
while delegating to the new modular adapter system.

Legacy interface maintained for:
- Existing bot integration
- Backward compatibility
- Gradual migration support
"""

import asyncio
from typing import Dict, Optional, Any
from datetime import datetime

from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import (
    AnalysisRequest, RepositoryContent, FileInfo, Role
)
from core.exceptions import AnalysisError
from utils.logger import setup_logger, log_performance

# Initialize logger for this module
logger = setup_logger(__name__)


class CodeAnalyzer:
    """
    Legacy facade for code analysis using LLM through OpenRouter API.
    
    This class maintains backward compatibility with the original interface
    while delegating to the new modular adapter system.
    
    **DEPRECATED**: This interface is maintained for backward compatibility.
    New code should use the OpenRouterAdapter directly.
    """
    
    def __init__(self):
        """Initialize the legacy code analyzer facade."""
        self._adapter = OpenRouterAdapter()
        logger.info("CodeAnalyzer facade initialized (delegating to OpenRouterAdapter)")
        logger.warning(
            "CodeAnalyzer is deprecated. Use OpenRouterAdapter directly for new code."
        )
    
    @log_performance("legacy_code_analysis")
    async def analyze_code(self, repo_content: Dict, role: str, 
                          task_requirements: str) -> Dict:
        """
        Analyze code using LLM with fallback chain (Legacy Interface).
        
        This method maintains backward compatibility by converting legacy
        dictionary-based inputs to the new typed model system, delegating
        to the OpenRouterAdapter, and converting results back to the legacy format.
        
        Args:
            repo_content: Dictionary containing repository content (legacy format)
            role: The role type ('backend' or 'frontend')
            task_requirements: The task requirements document
            
        Returns:
            Dictionary containing analysis results (legacy format)
        """
        logger.info(f"Starting legacy code analysis for {role} submission")
        logger.debug("Converting legacy format to new typed models...")
        
        try:
            # Check if repository was processed successfully
            if not repo_content.get('success'):
                error_msg = repo_content.get('error', 'Repository processing failed')
                logger.error(f"Cannot analyze - repository processing failed: {error_msg}")
                return self._create_error_result(error_msg)
            
            # Convert legacy format to new typed models
            analysis_request = self._convert_legacy_to_typed(repo_content, role, task_requirements)
            
            # Delegate to the new adapter
            result = await self._adapter.analyze_code(analysis_request)
            
            # Convert back to legacy format
            legacy_result = self._convert_typed_to_legacy(result)
            
            logger.info(f"Legacy analysis completed successfully")
            return legacy_result
            
        except AnalysisError as e:
            logger.error(f"Analysis failed: {e}")
            return self._create_error_result(str(e))
            
        except Exception as e:
            logger.error(f"Unexpected error in legacy analysis: {e}")
            return self._create_error_result(f"Analysis failed: {str(e)}")
    
    async def test_connection(self) -> bool:
        """
        Test connection to the OpenRouter API (Legacy Interface).
        
        Returns:
            True if connection test succeeds, False otherwise
        """
        logger.info("Testing connection via legacy interface")
        return await self._adapter.test_connection()
    
    # Private helper methods for legacy compatibility
    
    def _convert_legacy_to_typed(self, repo_content: Dict, role: str, 
                               task_requirements: str) -> AnalysisRequest:
        """
        Convert legacy dictionary format to typed models.
        
        Args:
            repo_content: Legacy repository content dictionary
            role: Role string
            task_requirements: Task requirements string
            
        Returns:
            Typed AnalysisRequest object
        """
        # Convert role string to enum
        role_enum = Role.BACKEND if role.lower() == 'backend' else Role.FRONTEND
        
        # Extract repository information
        repo_url = repo_content.get('repo_url', 'unknown')
        content_text = repo_content.get('content', '')
        total_tokens = repo_content.get('total_tokens', 0)
        
        # Create file info objects (simplified for legacy compatibility)
        files = []
        if content_text:
            files.append(FileInfo(
                path="combined_content.txt",
                content=content_text,
                priority="critical",
                tokens=total_tokens,
                language=None
            ))
        
        # Create repository content object
        repository_content = RepositoryContent(
            url=repo_url,
            files=files,
            total_tokens=total_tokens,
            structure="Legacy format - structure not available"
        )
        
        # Create analysis request
        return AnalysisRequest(
            repository_content=repository_content,
            role=role_enum,
            task_requirements=task_requirements
        )
    
    def _convert_typed_to_legacy(self, result: 'AnalysisResult') -> Dict:
        """
        Convert typed AnalysisResult back to legacy dictionary format.
        
        Args:
            result: Typed AnalysisResult object
            
        Returns:
            Legacy dictionary format
        """
        # Convert recommendation enum back to string
        recommendation_map = {
            'strongly_reject': 'REJECT',
            'reject': 'REJECT',
            'review_required': 'REJECT',  # Conservative mapping
            'accept': 'ACCEPT',
            'strongly_accept': 'ACCEPT'
        }
        
        recommendation_str = recommendation_map.get(
            result.recommendation.value, 'REJECT'
        )
        
        # Convert confidence back to 0-100 scale if it's 0-1
        confidence = result.confidence
        if 0 <= confidence <= 1:
            confidence = confidence * 100
        
        return {
            'requirements_met': result.requirements_met,
            'scores': result.scores,
            'strengths': result.strengths,
            'weaknesses': result.weaknesses,
            'critical_issues': [],  # Not directly mapped in new model
            'security_concerns': [],  # Not directly mapped in new model
            'recommendation': recommendation_str,
            'confidence': int(confidence),
            'detailed_feedback': result.detailed_feedback,
            'suggestions': result.suggestions
        }
    
    def _create_error_result(self, error_message: str) -> Dict:
        """
        Create a legacy error result when analysis fails.
        
        Args:
            error_message: Error description
            
        Returns:
            Legacy error result dictionary
        """
        return {
            "requirements_met": {},
            "scores": {
                "completeness": 0,
                "quality": 0,
                "architecture": 0,
                "testing": 0
            },
            "strengths": [],
            "weaknesses": ["Analysis failed due to technical issues"],
            "critical_issues": [error_message],
            "security_concerns": [],
            "recommendation": "REJECT",
            "confidence": 0,
            "detailed_feedback": f"Unable to complete analysis: {error_message}",
            "error": True,
            "error_message": error_message
        }
    
# Legacy factory function for backward compatibility
def create_analyzer() -> CodeAnalyzer:
    """
    Create a CodeAnalyzer instance (Legacy Interface).
    
    **DEPRECATED**: Use OpenRouterAdapter directly for new code.
    
    Returns:
        CodeAnalyzer instance configured with OpenRouter adapter
    """
    logger.warning("create_analyzer() is deprecated. Use OpenRouterAdapter directly.")
    return CodeAnalyzer()


# Maintain backward compatibility with direct instantiation
__all__ = ['CodeAnalyzer', 'create_analyzer']