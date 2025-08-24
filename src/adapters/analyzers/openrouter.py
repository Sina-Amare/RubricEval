"""
OpenRouter analyzer adapter for LLM-based code analysis.

This module provides a robust, modular implementation for code analysis
using LLM models through the OpenRouter API. It handles multi-model
fallback, retry logic, token management, and structured response parsing.
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from interfaces.analyzer import AnalyzerAdapter
from core.models import (
    AnalysisRequest, AnalysisResult, RecommendationLevel,
    RepositoryContent, Role
)
from core.exceptions import (
    AnalysisError, RateLimitError, TokenLimitError,
    ConfigurationError
)
from utils.logger import setup_logger, log_performance
from utils.token_counter import TokenCounter
from utils.validators import validate_analysis_result
from config import (
    OPENROUTER_KEY, PRIMARY_MODEL, FALLBACK_MODEL,
    TEMPERATURE, ANALYSIS_TIMEOUT, MAX_TOKENS
)

# Initialize logger for this module
logger = setup_logger(__name__)


class OpenRouterAdapter(AnalyzerAdapter):
    """
    OpenRouter adapter for LLM-based code analysis.
    
    This adapter provides:
    - Multi-model fallback chain for reliability
    - Automatic token management and content truncation
    - Retry logic with exponential backoff
    - Structured prompt engineering
    - Response validation and parsing
    - Comprehensive error handling
    
    The adapter implements a fallback strategy where it tries multiple
    models in order of preference, falling back to smaller models if
    the primary models fail or if content exceeds their context windows.
    """
    
    def __init__(self):
        """
        Initialize the OpenRouter adapter.
        
        Raises:
            ConfigurationError: If required configuration is missing
        """
        if not OPENROUTER_KEY:
            raise ConfigurationError("OPENROUTER_KEY is required")
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/cv-review-bot",
            "X-Title": "CV Review Bot"
        }
        
        # Model configuration with context limits and capabilities
        self.models = [
            {
                "name": PRIMARY_MODEL,
                "context_window": 1000000,  # 1M tokens for Gemini Flash
                "family": "gemini",
                "description": "Primary model - fast and efficient",
                "capabilities": ["code_analysis", "json_output"]
            },
            {
                "name": FALLBACK_MODEL,
                "context_window": 128000,  # 128K tokens for GPT-4
                "family": "gpt",
                "description": "Fallback model - high quality",
                "capabilities": ["code_analysis", "json_output"]
            },
            {
                "name": "openai/gpt-3.5-turbo-16k",
                "context_window": 16000,  # 16K tokens for GPT-3.5
                "family": "gpt",
                "description": "Emergency fallback - basic analysis",
                "capabilities": ["code_analysis"]
            }
        ]
        
        logger.info(f"OpenRouter adapter initialized with {len(self.models)} models")
        logger.info(f"Primary model: {PRIMARY_MODEL}")
    
    @log_performance("openrouter_analysis")
    async def analyze_code(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Analyze code using OpenRouter LLM models with fallback chain.
        
        This method implements a robust analysis pipeline:
        1. Validates the analysis request
        2. Attempts analysis with each model in the fallback chain
        3. Handles token limits by truncating content if necessary
        4. Retries on transient failures with exponential backoff
        5. Validates and structures the final response
        
        Args:
            request: Analysis request containing repository content and requirements
            
        Returns:
            Structured analysis result
            
        Raises:
            AnalysisError: If all analysis attempts fail
            TokenLimitError: If repository is too large for any model
        """
        logger.info(
            f"Starting code analysis for {request.role.value} submission "
            f"(repo: {request.repository_content.url})"
        )
        
        # Validate request
        self._validate_request(request)
        
        # Try each model in the fallback chain
        last_error = None
        for i, model_config in enumerate(self.models):
            try:
                logger.info(
                    f"Attempt {i+1}/{len(self.models)}: {model_config['name']} "
                    f"(context: {model_config['context_window']} tokens)"
                )
                
                # Check if content fits within model's context window
                content = self._prepare_content_for_model(
                    request.repository_content, model_config
                )
                
                # Perform analysis with this model
                result = await self._analyze_with_model(
                    request, model_config, content
                )
                
                if result:
                    logger.info(
                        f"Analysis successful with {model_config['name']}"
                    )
                    return result
                    
            except TokenLimitError as e:
                logger.warning(
                    f"Token limit exceeded for {model_config['name']}: {e}"
                )
                last_error = e
                continue
                
            except RateLimitError as e:
                logger.warning(
                    f"Rate limit hit for {model_config['name']}: {e}"
                )
                if e.retry_after:
                    logger.info(f"Waiting {e.retry_after} seconds before retry...")
                    await asyncio.sleep(e.retry_after)
                last_error = e
                continue
                
            except Exception as e:
                logger.warning(
                    f"Model {model_config['name']} failed: {type(e).__name__}: {e}"
                )
                last_error = e
                continue
        
        # All models failed
        error_msg = f"All {len(self.models)} models failed to analyze code"
        logger.error(error_msg)
        
        if isinstance(last_error, (TokenLimitError, RateLimitError)):
            raise last_error
        else:
            raise AnalysisError(
                error_msg,
                details={"last_error": str(last_error) if last_error else None}
            )
    
    async def test_connection(self) -> bool:
        """
        Test connection to OpenRouter API.
        
        Sends a minimal test request to verify API connectivity
        and authentication.
        
        Returns:
            True if connection test succeeds, False otherwise
        """
        try:
            logger.info("Testing OpenRouter API connection...")
            
            payload = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "Respond with 'OK' if you can read this."}
                ],
                "max_tokens": 10,
                "temperature": 0
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.info(f"Connection test successful: {content.strip()}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Connection test failed ({response.status}): {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Connection test error: {type(e).__name__}: {e}")
            return False
    
    def get_supported_models(self) -> List[Dict[str, Any]]:
        """
        Get list of supported models with their capabilities.
        
        Returns:
            List of model information dictionaries
        """
        return [
            {
                "name": model["name"],
                "context_window": model["context_window"],
                "family": model["family"],
                "description": model["description"],
                "capabilities": model["capabilities"],
                "cost_per_token": None  # Would need to be fetched from OpenRouter API
            }
            for model in self.models
        ]
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.
        
        Uses the primary model's tokenization approach for estimation.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        primary_model = self.models[0]
        return TokenCounter.estimate_tokens(text, primary_model["family"])
    
    async def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate that LLM response has expected structure.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            True if response is valid, False otherwise
        """
        try:
            is_valid, error = validate_analysis_result(response)
            if not is_valid:
                logger.warning(f"Response validation failed: {error}")
            return is_valid
        except Exception as e:
            logger.error(f"Response validation error: {e}")
            return False
    
    # Private helper methods
    
    def _validate_request(self, request: AnalysisRequest) -> None:
        """
        Validate analysis request structure and content.
        
        Args:
            request: Analysis request to validate
            
        Raises:
            AnalysisError: If request is invalid
        """
        if not request.repository_content:
            raise AnalysisError("Repository content is required")
        
        if not request.task_requirements:
            raise AnalysisError("Task requirements are required")
        
        if not request.role:
            raise AnalysisError("Role is required")
        
        if request.repository_content.total_tokens <= 0:
            raise AnalysisError("Repository appears to be empty")
        
        logger.debug("Request validation passed")
    
    def _prepare_content_for_model(self, repo_content: RepositoryContent, 
                                  model_config: Dict[str, Any]) -> str:
        """
        Prepare repository content for a specific model's context window.
        
        Args:
            repo_content: Repository content to prepare
            model_config: Model configuration including context window
            
        Returns:
            Formatted content string ready for analysis
            
        Raises:
            TokenLimitError: If content is too large even after truncation
        """
        # Format repository content as structured text
        content_parts = []
        content_parts.append(f"# Repository: {repo_content.url}")
        content_parts.append(f"\n# Repository Structure:\n{repo_content.structure}")
        content_parts.append("\n# Repository Files:")
        
        # Add file contents with priority-based selection
        for file_info in repo_content.files:
            content_parts.append(f"\n## File: {file_info.path}")
            content_parts.append(f"Language: {file_info.language or 'Unknown'}")
            content_parts.append(f"Priority: {file_info.priority}")
            content_parts.append(f"\n```\n{file_info.content}\n```\n")
        
        full_content = "\n".join(content_parts)
        
        # Check if content fits in model's context window
        # Reserve space for prompt and response (estimate 30% of context)
        usable_context = int(model_config["context_window"] * 0.7)
        
        if TokenCounter.can_fit_context(full_content, usable_context, model_config["family"]):
            return full_content
        
        # Content is too large, try to truncate intelligently
        logger.warning(
            f"Content too large for {model_config['name']}, truncating..."
        )
        
        truncated_content = TokenCounter.truncate_to_fit(
            full_content, usable_context, model_config["family"]
        )
        
        # Final check - if still too large, this model can't handle it
        if not TokenCounter.can_fit_context(
            truncated_content, usable_context, model_config["family"]
        ):
            estimated_tokens = TokenCounter.estimate_tokens(
                truncated_content, model_config["family"]
            )
            raise TokenLimitError(
                f"Repository too large for {model_config['name']} model",
                token_count=estimated_tokens,
                limit=usable_context
            )
        
        return truncated_content
    
    async def _analyze_with_model(self, request: AnalysisRequest, 
                                 model_config: Dict[str, Any], 
                                 content: str) -> Optional[AnalysisResult]:
        """
        Perform analysis using a specific model.
        
        Args:
            request: Analysis request
            model_config: Configuration for the model to use
            content: Prepared repository content
            
        Returns:
            Analysis result if successful, None if failed
            
        Raises:
            AnalysisError: If analysis fails
            RateLimitError: If rate limits are exceeded
        """
        # Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(request, content)
        
        # Prepare API payload
        payload = {
            "model": model_config["name"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": TEMPERATURE,
            "max_tokens": 4000,  # Limit response size
        }
        
        # Add JSON format instruction for compatible models
        if "json_output" in model_config.get("capabilities", []):
            if "gpt" in model_config["family"]:
                payload["response_format"] = {"type": "json_object"}
        
        # Make API call with retry logic
        retry_policy = self.get_retry_policy()
        
        for attempt in range(retry_policy["max_retries"]):
            try:
                logger.debug(
                    f"API call attempt {attempt + 1}/{retry_policy['max_retries']} "
                    f"to {model_config['name']}"
                )
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url,
                        headers=self.headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=ANALYSIS_TIMEOUT)
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            # Extract response content
                            response_content = data['choices'][0]['message']['content']
                            
                            # Parse and validate response
                            parsed_result = self._parse_llm_response(response_content)
                            
                            if await self.validate_response(parsed_result):
                                return self._convert_to_analysis_result(parsed_result)
                            else:
                                logger.warning("Response validation failed")
                                return None
                                
                        elif response.status == 429:  # Rate limit
                            retry_after = int(response.headers.get('retry-after', 60))
                            raise RateLimitError(
                                f"Rate limit exceeded for {model_config['name']}",
                                retry_after=retry_after
                            )
                            
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"API error {response.status}: {error_text}"
                            )
                            
                            if attempt < retry_policy["max_retries"] - 1:
                                # Calculate exponential backoff delay
                                delay = min(
                                    retry_policy["initial_delay"] * 
                                    (retry_policy["exponential_base"] ** attempt),
                                    retry_policy["max_delay"]
                                )
                                logger.info(f"Retrying in {delay} seconds...")
                                await asyncio.sleep(delay)
                                continue
                            
                            raise AnalysisError(
                                f"API call failed: {response.status} {error_text}"
                            )
                            
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt < retry_policy["max_retries"] - 1:
                    delay = min(
                        retry_policy["initial_delay"] * 
                        (retry_policy["exponential_base"] ** attempt),
                        retry_policy["max_delay"]
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise AnalysisError("Analysis request timed out")
                    
            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error: {e}")
                if attempt < retry_policy["max_retries"] - 1:
                    delay = min(
                        retry_policy["initial_delay"] * 
                        (retry_policy["exponential_base"] ** attempt),
                        retry_policy["max_delay"]
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise AnalysisError(f"HTTP client error: {e}")
        
        return None
    
    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for LLM analysis.
        
        Returns:
            System prompt string that defines the AI's role and objectives
        """
        return """You are an expert code reviewer evaluating candidates for technical positions.
Your task is to analyze submitted code repositories against specific job requirements and provide thorough, objective evaluations.

Core Evaluation Principles:
1. **Accuracy**: Base your assessment on what's actually implemented, not what could be
2. **Fairness**: Consider this is a technical assessment, not production code
3. **Thoroughness**: Evaluate all aspects - functionality, code quality, architecture, testing
4. **Constructiveness**: Provide specific, actionable feedback
5. **Consistency**: Apply the same standards across all submissions

Focus Areas:
- **Requirements Compliance**: Does the code meet all specified requirements?
- **Code Quality**: Is the code well-structured, readable, and maintainable?
- **Architecture**: Are appropriate design patterns and architectural decisions used?
- **Testing**: Is there adequate test coverage and quality?
- **Security**: Are there any security vulnerabilities or bad practices?
- **Best Practices**: Does the code follow language/framework conventions?

Provide your analysis in the specified JSON format with detailed, specific feedback."""
    
    def _build_user_prompt(self, request: AnalysisRequest, content: str) -> str:
        """
        Build the user prompt for analysis.
        
        Args:
            request: Analysis request with requirements and role
            content: Prepared repository content
            
        Returns:
            Complete user prompt for analysis
        """
        return f"""Analyze this {request.role.value} developer code submission against the provided requirements.

# Job Requirements
{request.task_requirements}

# Submitted Repository
{content}

# Analysis Instructions
Evaluate the submission thoroughly and provide your analysis in this exact JSON format:

{{
    "requirements_met": {{
        "requirement_1": true/false,
        "requirement_2": true/false
        // List each requirement and whether it's satisfied
    }},
    "scores": {{
        "completeness": 0-100,  // How complete is the implementation?
        "quality": 0-100,       // Code quality and best practices
        "architecture": 0-100,  // Design and structure quality
        "testing": 0-100        // Test coverage and quality
    }},
    "strengths": [
        "List specific strong points in the implementation"
    ],
    "weaknesses": [
        "List specific areas needing improvement"
    ],
    "critical_issues": [
        "Any blocking problems that prevent the solution from working"
    ],
    "security_concerns": [
        "Any security vulnerabilities or risky patterns found"
    ],
    "recommendation": "ACCEPT" or "REJECT",
    "confidence": 0-100,  // How confident are you in this assessment?
    "detailed_feedback": "Comprehensive explanation of your decision with specific examples and suggestions for improvement"
}}

Be thorough but fair. Focus on demonstrating technical competency for the {request.role.value} role."""
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured data.
        
        Handles various response formats including plain JSON,
        markdown code blocks, and mixed text with JSON.
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Parsed dictionary
            
        Raises:
            AnalysisError: If response cannot be parsed
        """
        if not response_text or not response_text.strip():
            raise AnalysisError("Empty response from LLM")
        
        try:
            # Try direct JSON parsing first
            if response_text.strip().startswith('{'):
                return json.loads(response_text.strip())
            
            # Look for JSON in markdown code blocks
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    json_text = response_text[json_start:json_end].strip()
                    return json.loads(json_text)
            
            # Look for JSON in regular code blocks
            if '```' in response_text:
                # Find first code block that might be JSON
                parts = response_text.split('```')
                for i in range(1, len(parts), 2):  # Odd indices are code blocks
                    code_block = parts[i].strip()
                    # Remove language identifier if present
                    lines = code_block.split('\n')
                    if lines[0] and not lines[0].startswith('{'):
                        code_block = '\n'.join(lines[1:])
                    
                    if code_block.strip().startswith('{'):
                        try:
                            return json.loads(code_block)
                        except json.JSONDecodeError:
                            continue
            
            # Look for JSON object anywhere in the text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                return json.loads(json_text)
            
            # If all else fails, return a structured error
            logger.error("Could not extract JSON from LLM response")
            return self._create_error_result("Failed to parse analysis response")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Response text: {response_text[:500]}...")
            return self._create_error_result(f"Invalid JSON in response: {str(e)}")
            
        except Exception as e:
            logger.error(f"Response parsing error: {e}")
            return self._create_error_result(f"Failed to parse response: {str(e)}")
    
    def _convert_to_analysis_result(self, parsed_response: Dict[str, Any]) -> AnalysisResult:
        """
        Convert parsed LLM response to structured AnalysisResult.
        
        Args:
            parsed_response: Parsed response dictionary from LLM
            
        Returns:
            Structured AnalysisResult object
        """
        # Map recommendation string to enum
        recommendation_str = parsed_response.get('recommendation', 'REJECT').upper()
        if recommendation_str == 'ACCEPT':
            recommendation = RecommendationLevel.ACCEPT
        elif recommendation_str == 'STRONGLY_ACCEPT':
            recommendation = RecommendationLevel.STRONGLY_ACCEPT
        elif recommendation_str == 'REVIEW_REQUIRED':
            recommendation = RecommendationLevel.REVIEW_REQUIRED
        elif recommendation_str == 'STRONGLY_REJECT':
            recommendation = RecommendationLevel.STRONGLY_REJECT
        else:
            recommendation = RecommendationLevel.REJECT
        
        # Convert confidence to 0-1 scale if it's 0-100
        confidence = parsed_response.get('confidence', 0)
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100.0
        
        # Ensure scores are floats
        scores = parsed_response.get('scores', {})
        normalized_scores = {}
        for key, value in scores.items():
            if isinstance(value, (int, float)):
                normalized_scores[key] = float(value)
            else:
                normalized_scores[key] = 0.0
        
        return AnalysisResult(
            requirements_met=parsed_response.get('requirements_met', {}),
            scores=normalized_scores,
            recommendation=recommendation,
            confidence=float(confidence),
            strengths=parsed_response.get('strengths', []),
            weaknesses=parsed_response.get('weaknesses', []),
            detailed_feedback=parsed_response.get('detailed_feedback', ''),
            suggestions=parsed_response.get('suggestions', [])
        )
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """
        Create a structured error result when analysis fails.
        
        Args:
            error_message: Description of the error
            
        Returns:
            Dictionary representing a failed analysis
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
