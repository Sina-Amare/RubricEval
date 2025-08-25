"""
OpenRouter analyzer adapter for LLM-based code analysis.

This module provides a robust, modular implementation for code analysis
using LLM models through the OpenRouter API. It handles multi-model
fallback, retry logic, token management, and structured response parsing.
"""

import json
import re
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
from utils.prompts import load_prompt
from utils.json_recovery import JSONRecovery
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
    
    async def call_llm_for_selection(self, prompt: str, model_name: str = None) -> str:
        """
        Call LLM for file selection or other auxiliary tasks.
        
        Args:
            prompt: The prompt to send to the LLM
            model_name: Optional specific model to use
            
        Returns:
            Raw LLM response text
            
        Raises:
            AnalysisError: If LLM call fails
        """
        if not model_name:
            model_name = self.models[0]["name"]  # Use primary model
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a code analysis assistant. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        raise AnalysisError(f"LLM call failed: {response.status} {error_text}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error in LLM call: {e}")
            raise AnalysisError(f"Network error calling LLM: {str(e)}")
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            raise AnalysisError(f"Failed to call LLM: {str(e)}")
    
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
        
        # Log the actual content being sent (first 1000 chars for debugging)
        logger.debug(f"Content preview being sent to LLM: {content[:1000]}...")
        logger.info(f"Total content size: {len(content)} characters, {len(request.repository_content.files)} files")
        
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
                            
                            # Log the response for debugging
                            logger.debug(f"LLM Response preview: {response_content[:500]}...")
                            logger.info(f"LLM Response length: {len(response_content)} characters")
                            
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
        Build the user prompt for analysis using external prompt template.
        
        Args:
            request: Analysis request with requirements and role
            content: Prepared repository content
            
        Returns:
            Complete user prompt for analysis
        """
        # Count files and tokens
        file_count = content.count('\n---\n')  # Rough count based on separators
        total_tokens = TokenCounter.estimate_tokens(content, "openai")
        
        # Load and format the prompt from external file
        # Use role-specific senior-level prompts for more rigorous evaluation
        try:
            # Determine which prompt file to use based on role
            if request.role.value == "frontend":
                prompt_file = "analysis/senior_frontend_analysis.md"
            elif request.role.value == "backend":
                prompt_file = "analysis/senior_backend_analysis.md"
            else:
                # Fallback to generic prompt for other roles
                prompt_file = "analysis/code_review.md"
            
            logger.info(f"Using prompt: {prompt_file} for {request.role.value} analysis")
            prompt = load_prompt(
                prompt_file,
                role=request.role.value,
                task_requirements=request.task_requirements,
                github_url=request.github_url,
                file_count=file_count,
                total_tokens=total_tokens,
                code_content=content
            )
            return prompt
        except Exception as e:
            logger.warning(f"Failed to load external prompt, using fallback: {e}")
            # Fallback to inline prompt if loading fails
            return f"""Analyze this {request.role.value} developer code submission against the provided requirements.

# Job Requirements
{request.task_requirements}

# Submitted Repository
{content}

# Analysis Instructions
Evaluate the submission thoroughly and provide your analysis in JSON format with these fields:
- requirements_met: Object mapping each requirement to true/false
- scores: Object with completeness, quality, architecture, testing (0-100)
- strengths: Array of strong points (REQUIRED: minimum 3 items, be specific)
- weaknesses: Array of areas needing improvement (REQUIRED: minimum 3 items, be constructive)
- recommendation: "strong_yes", "yes", "no", or "strong_no" (avoid "maybe")
- confidence: 0.0-1.0
- detailed_feedback: Comprehensive explanation

IMPORTANT: You MUST provide at least 3 strengths and 3 weaknesses. Even excellent code has areas for improvement, and even poor code has some positive aspects.

Be thorough but fair. Focus on demonstrating technical competency for the {request.role.value} role."""
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured data using robust recovery.
        
        Uses multiple strategies to extract JSON even from malformed responses,
        ensuring expensive LLM calls are not wasted due to minor formatting issues.
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Parsed dictionary (may include partial recovery)
            
        Raises:
            AnalysisError: Only if response is completely unparseable
        """
        if not response_text or not response_text.strip():
            raise AnalysisError("Empty response from LLM")
        
        # Use robust JSON recovery system
        recovered_json, raw_json = JSONRecovery.extract_json(response_text)
        
        if recovered_json:
            # Validate minimum structure
            if JSONRecovery.validate_recovered_json(recovered_json):
                logger.info("Successfully recovered JSON from LLM response")
                
                # Add metadata about recovery if partial
                if recovered_json.get('partial_recovery'):
                    logger.warning("Response was partially recovered - some data may be incomplete")
                    # Ensure we have all required fields with defaults
                    recovered_json = self._ensure_complete_structure(recovered_json)
                
                return recovered_json
            else:
                logger.warning("Recovered JSON lacks minimum required fields")
                # Try to augment with defaults
                return self._augment_incomplete_json(recovered_json)
        
        # If recovery completely failed, log the issue
        logger.error(f"JSON recovery failed: {raw_json}")
        logger.debug(f"Original response (first 1000 chars): {response_text[:1000]}...")
        
        # Create structured error result as last resort
        # But include any text we can extract as feedback
        error_result = self._create_error_result("Failed to parse analysis response")
        error_result['detailed_feedback'] = self._extract_text_feedback(response_text)
        error_result['parse_failure'] = True
        
        return error_result
    
    def _ensure_complete_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure partially recovered JSON has all required fields."""
        # Default structure
        defaults = {
            "requirements_met": {},
            "scores": {
                "completeness": 0,
                "quality": 0,
                "architecture": 0,
                "testing": 0
            },
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "recommendation": "review_required",
            "confidence": 50,
            "detailed_feedback": "Analysis partially recovered from malformed response"
        }
        
        # Merge with defaults (data overwrites defaults)
        for key, default_value in defaults.items():
            if key not in data:
                data[key] = default_value
            elif key == 'scores' and isinstance(data[key], dict):
                # Ensure all score fields exist
                for score_key, score_default in defaults['scores'].items():
                    if score_key not in data['scores']:
                        data['scores'][score_key] = score_default
        
        return data
    
    def _augment_incomplete_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Augment incomplete JSON with required fields."""
        # Start with error result structure
        result = self._create_error_result("Incomplete analysis response")
        
        # Override with any data we recovered
        if data:
            for key, value in data.items():
                if value is not None and value != "":
                    result[key] = value
        
        result['partial_recovery'] = True
        return result
    
    def _extract_text_feedback(self, response_text: str) -> str:
        """Extract any meaningful text feedback from failed response."""
        # Remove JSON artifacts and code blocks
        text = re.sub(r'```[^`]*```', '', response_text)
        text = re.sub(r'[{}\[\]]', '', text)
        text = re.sub(r'"[^"]*":', '', text)
        
        # Get first meaningful paragraph
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        feedback = ' '.join(lines[:5]) if lines else "Unable to extract feedback"
        
        return feedback[:500]  # Limit length
    
    def _convert_to_analysis_result(self, parsed_response: Dict[str, Any]) -> AnalysisResult:
        """
        Convert parsed LLM response to structured AnalysisResult.
        
        Args:
            parsed_response: Parsed response dictionary from LLM
            
        Returns:
            Structured AnalysisResult object
        """
        # Map LLM recommendation string to enum
        # LLM should return: strong_yes, yes, maybe, no, strong_no
        # But sometimes returns: strongly_accept, accept, review_required, reject, strongly_reject
        # Default to 'maybe' to give candidates benefit of doubt
        recommendation_str = parsed_response.get('recommendation', 'maybe').lower().strip()
        
        # Handle both formats - NO MAYBE unless exceptional case
        if recommendation_str in ['strong_yes', 'strongly_accept']:
            recommendation = RecommendationLevel.STRONGLY_ACCEPT
        elif recommendation_str in ['yes', 'accept']:
            recommendation = RecommendationLevel.ACCEPT
        elif recommendation_str in ['no', 'reject']:
            recommendation = RecommendationLevel.REJECT
        elif recommendation_str in ['strong_no', 'strongly_reject']:
            recommendation = RecommendationLevel.STRONGLY_REJECT
        elif recommendation_str in ['maybe', 'review_required', 'review']:
            # Check if this is a legitimate exception case
            exception_case = parsed_response.get('hiring_recommendation', {}).get('exception_case', {})
            if exception_case.get('is_exception') and exception_case.get('exception_reason'):
                logger.warning(f"Review required (exception): {exception_case.get('exception_reason')}")
                recommendation = RecommendationLevel.REVIEW_REQUIRED
            else:
                # Force a decision - if avg score >= 60%, accept, otherwise reject
                scores = parsed_response.get('scores', {})
                avg_score = sum(scores.values()) / len(scores) if scores else 0
                if avg_score >= 60:
                    logger.info(f"Converting 'maybe' to ACCEPT (score: {avg_score:.1f}%)")
                    recommendation = RecommendationLevel.ACCEPT
                else:
                    logger.info(f"Converting 'maybe' to REJECT (score: {avg_score:.1f}%)")
                    recommendation = RecommendationLevel.REJECT
        else:
            # Fallback - make decision based on scores
            scores = parsed_response.get('scores', {})
            avg_score = sum(scores.values()) / len(scores) if scores else 0
            if avg_score >= 60:
                logger.warning(f"Unknown recommendation '{recommendation_str}', defaulting to ACCEPT (score: {avg_score:.1f}%)")
                recommendation = RecommendationLevel.ACCEPT
            else:
                logger.warning(f"Unknown recommendation '{recommendation_str}', defaulting to REJECT (score: {avg_score:.1f}%)")
                recommendation = RecommendationLevel.REJECT
        
        # Convert confidence to 0-1 scale if it's 0-100
        # Default to moderate confidence (0.6) if not provided
        confidence = parsed_response.get('confidence', 0.6)
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
        
        # Calculate average score for default generation
        avg_score = sum(normalized_scores.values()) / len(normalized_scores) if normalized_scores else 0
        
        # Handle both old and new prompt formats
        # New format has 'requirements_implementation', old has 'requirements_met'
        requirements_met = {}
        
        if 'requirements_implementation' in parsed_response:
            # Convert new format to old format for compatibility
            for req_name, req_data in parsed_response.get('requirements_implementation', {}).items():
                if isinstance(req_data, dict):
                    requirements_met[req_name] = req_data.get('implemented', False)
                else:
                    requirements_met[req_name] = bool(req_data)
        else:
            # Old format
            requirements_met = parsed_response.get('requirements_met', {})
        
        # Extract strengths and weaknesses from different possible locations
        strengths = parsed_response.get('strengths', [])
        weaknesses = parsed_response.get('weaknesses', [])
        
        # Try to extract from seniority_assessment if not found
        if not strengths and 'seniority_assessment' in parsed_response:
            seniority = parsed_response['seniority_assessment']
            strengths = seniority.get('strengths', [])
            weaknesses = seniority.get('growth_areas', weaknesses)
        
        # Add default values if empty
        if not strengths:
            if avg_score >= 80:
                strengths = [
                    "Code meets the specified requirements",
                    "Implementation shows understanding of the technology stack",
                    "Solution addresses the core problem effectively"
                ]
            elif avg_score >= 60:
                strengths = [
                    "Basic requirements are addressed",
                    "Code shows effort and understanding",
                    "Some good practices are followed"
                ]
            else:
                strengths = [
                    "Submission shows effort",
                    "Some requirements are attempted",
                    "Basic code structure is present"
                ]
        
        if not weaknesses:
            if avg_score >= 80:
                weaknesses = [
                    "Could benefit from more comprehensive testing",
                    "Documentation could be more detailed",
                    "Some edge cases might need additional handling"
                ]
            elif avg_score >= 60:
                weaknesses = [
                    "Code organization could be improved",
                    "Error handling needs enhancement",
                    "Some best practices are not followed consistently"
                ]
            else:
                weaknesses = [
                    "Several requirements are not fully implemented",
                    "Code quality needs significant improvement",
                    "Architecture and design patterns need work"
                ]
        
        # Extract suggestions from various possible locations
        suggestions = parsed_response.get('suggestions', [])
        if not suggestions and 'seniority_assessment' in parsed_response:
            # Try to use growth areas as suggestions
            growth_areas = parsed_response['seniority_assessment'].get('growth_areas', [])
            if growth_areas:
                suggestions = [f"Consider improving: {area}" for area in growth_areas[:3]]
        
        # Extract hiring decision if present (new format)
        hiring_decision = parsed_response.get('hiring_decision', None)
        
        return AnalysisResult(
            requirements_met=requirements_met,
            scores=normalized_scores,
            recommendation=recommendation,
            confidence=float(confidence),
            strengths=strengths,
            weaknesses=weaknesses,
            detailed_feedback=parsed_response.get('detailed_feedback', ''),
            suggestions=suggestions,
            hiring_decision=hiring_decision
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
