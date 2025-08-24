"""
Analyzer adapter interface.

This module defines the abstract interface for LLM analyzers
that evaluate code against requirements.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from core.models import AnalysisRequest, AnalysisResult


class AnalyzerAdapter(ABC):
    """
    Abstract interface for code analyzer adapters.
    
    Implementations of this interface handle code analysis using
    various LLM providers (OpenRouter, OpenAI, local models, etc.).
    """
    
    @abstractmethod
    async def analyze_code(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Analyze code and return structured results.
        
        This method should:
        1. Format the analysis prompt
        2. Send request to LLM provider
        3. Parse and validate response
        4. Return structured results
        
        Args:
            request: Analysis request with repository content and requirements
            
        Returns:
            Structured analysis result
            
        Raises:
            AnalysisError: If analysis fails
            RateLimitError: If rate limits are exceeded
            TokenLimitError: If content exceeds model limits
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test connection to the LLM service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[Dict[str, Any]]:
        """
        Get list of supported models with their capabilities.
        
        Returns:
            List of model information dictionaries containing:
            - name: Model identifier
            - context_window: Maximum token context
            - capabilities: List of capabilities
            - cost_per_token: Optional pricing information
        """
        pass
    
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        pass
    
    @abstractmethod
    async def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate that LLM response has expected structure.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            True if response is valid, False otherwise
        """
        pass
    
    # Optional methods with default implementations
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for this analyzer.
        
        Returns:
            Maximum token count
        """
        return 100000
    
    def get_retry_policy(self) -> Dict[str, Any]:
        """
        Get retry policy for failed requests.
        
        Returns:
            Dictionary with retry configuration:
            - max_retries: Maximum number of retries
            - initial_delay: Initial delay in seconds
            - max_delay: Maximum delay in seconds
            - exponential_base: Base for exponential backoff
        """
        return {
            "max_retries": 3,
            "initial_delay": 1,
            "max_delay": 60,
            "exponential_base": 2
        }
    
    async def format_prompt(self, request: AnalysisRequest) -> str:
        """
        Format the analysis prompt for the LLM.
        
        Args:
            request: Analysis request
            
        Returns:
            Formatted prompt string
        """
        # Default implementation can be overridden
        return f"""
        Analyze the following code repository for the {request.role.value} position.
        
        Requirements:
        {request.task_requirements}
        
        Repository Content:
        {request.repository_content.structure}
        
        Please evaluate against all requirements and provide structured feedback.
        """