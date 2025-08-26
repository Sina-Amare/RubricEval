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
                    # Set the model that was actually used
                    result.model_used = model_config['name']
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
            
            # Debug log for critical files
            if 'cookie' in file_info.path.lower() or 'auth' in file_info.path.lower() or 'login' in file_info.path.lower():
                logger.info(f"Including critical file for frontend: {file_info.path}")
                
                # Check for cookie usage patterns in the content
                if any(pattern in file_info.content for pattern in ['js-cookie', 'setCookie', 'getCookie', 'Cookies.set', 'Cookies.get']):
                    logger.warning(f"⚠️ DETECTED COOKIE USAGE in {file_info.path}")
        
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
                            
                            # CRITICAL: Convert requirements BEFORE penalty validation
                            # This ensures penalty validation has access to properly extracted requirements
                            self._normalize_requirements(parsed_result)
                            
                            # Ensure penalty_breakdown exists
                            self._ensure_penalty_breakdown(parsed_result)
                            
                            if await self.validate_response(parsed_result):
                                return self._convert_to_analysis_result(parsed_result, request.role.value, content)
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
            
            # Extract repository structure separately for clearer prompt formatting
            repository_structure = request.repository_content.structure if hasattr(request.repository_content, 'structure') else "Structure not available"
            
            prompt = load_prompt(
                prompt_file,
                role=request.role.value,
                task_requirements=request.task_requirements,
                github_url=request.github_url,
                file_count=file_count,
                total_tokens=total_tokens,
                repository_structure=repository_structure,
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
                
                # CRITICAL: Log storage method check first
                if 'storage_method_check' in recovered_json:
                    storage_check = recovered_json['storage_method_check']
                    logger.warning(f"🔍 STORAGE METHOD CHECK: {storage_check}")
                    
                    # Log evidence specifically
                    if 'evidence' in storage_check:
                        logger.warning(f"📝 EVIDENCE: {storage_check['evidence']}")
                    
                    # Override localstorage_implementation based on what was actually found
                    if storage_check.get('found_cookies') and not storage_check.get('found_localStorage'):
                        logger.warning("⚠️ Found cookies but no localStorage - forcing localstorage_implementation to FALSE")
                        if 'requirements_met' not in recovered_json:
                            recovered_json['requirements_met'] = {}
                        recovered_json['requirements_met']['localstorage_implementation'] = False
                
                # Log what requirements_met the LLM actually returned
                if 'requirements_met' in recovered_json:
                    logger.info(f"LLM requirements_met: {recovered_json['requirements_met']}")
                    # Specifically log localStorage implementation
                    if 'localstorage_implementation' in recovered_json.get('requirements_met', {}):
                        logger.warning(f"⚠️ LLM marked localstorage_implementation as: {recovered_json['requirements_met']['localstorage_implementation']}")
                elif 'requirements_implementation' in recovered_json:
                    logger.info(f"LLM requirements_implementation found with {len(recovered_json['requirements_implementation'])} items")
                    # Log a sample of the implementation data
                    sample = list(recovered_json['requirements_implementation'].items())[:3]
                    logger.debug(f"Sample requirements_implementation: {sample}")
                else:
                    logger.warning("No requirements_met or requirements_implementation found in LLM response")
                    logger.info(f"Available keys in response: {list(recovered_json.keys())}")
                
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
    
    def _normalize_requirements(self, parsed_response: Dict[str, Any]) -> None:
        """
        Normalize requirements from various formats to standard requirements_met.
        This MUST be called before penalty validation to ensure correct penalty skipping.
        
        Args:
            parsed_response: Response dictionary (modified in place)
        """
        requirements_met = {}
        
        # Try multiple locations where requirements might be stored
        if 'requirements_implementation' in parsed_response:
            # Convert new format to old format for compatibility
            logger.info("Converting requirements_implementation to requirements_met")
            for req_name, req_data in parsed_response.get('requirements_implementation', {}).items():
                if isinstance(req_data, dict):
                    requirements_met[req_name] = req_data.get('implemented', False)
                else:
                    requirements_met[req_name] = bool(req_data)
        elif 'requirements_met' in parsed_response:
            # Old format - ensure all values are booleans
            raw_requirements = parsed_response.get('requirements_met', {})
            for key, value in raw_requirements.items():
                # Handle different representations of boolean values
                if isinstance(value, bool):
                    requirements_met[key] = value
                elif isinstance(value, str):
                    requirements_met[key] = value.lower() in ['true', 'yes', '✓', 'pass', 'implemented']
                elif isinstance(value, dict):
                    requirements_met[key] = value.get('implemented', False) or value.get('met', False)
                else:
                    requirements_met[key] = bool(value)
        
        # FALLBACK: If requirements_met is empty or all False, try to infer from feedback
        if not requirements_met or all(not v for v in requirements_met.values()):
            logger.warning("Requirements all False or missing - attempting inference from feedback")
            feedback = parsed_response.get('detailed_feedback', '').lower()
            strengths_text = ' '.join(parsed_response.get('strengths', [])).lower()
            combined_text = feedback + ' ' + strengths_text
            
            # Infer based on positive mentions in feedback
            if ('repository pattern' in combined_text or 'dependency inversion' in combined_text) and ('implement' in combined_text or 'effective use' in combined_text or 'use of interfaces' in combined_text):
                requirements_met['repository_pattern'] = True
                logger.info("Inferred repository_pattern=True from feedback")
            
            if 'service layer' in combined_text and ('implement' in combined_text or 'proper' in combined_text):
                requirements_met['service_layer'] = True
                logger.info("Inferred service_layer=True from feedback")
            
            if 'redis' in combined_text and ('implement' in combined_text or 'uses redis' in combined_text or 'redis integration' in combined_text):
                requirements_met['redis_implementation'] = True
                logger.info("Inferred redis_implementation=True from feedback")
            
            if any(arch in combined_text for arch in ['layered architecture', 'clean architecture', 'hexagonal', 'mvc']):
                requirements_met['architectural_pattern'] = True
                logger.info("Inferred architectural_pattern=True from feedback")
            
            if 'docker' in combined_text and ('dockerfile' in combined_text or 'docker-compose' in combined_text or 'dockerization' in combined_text):
                requirements_met['dockerization'] = True
                logger.info("Inferred dockerization=True from feedback")
        
        # Store the normalized requirements back
        parsed_response['requirements_met'] = requirements_met
        logger.info(f"Normalized requirements_met: {requirements_met}")
    
    def _ensure_penalty_breakdown(self, data: Dict[str, Any]) -> None:
        """
        Ensure penalty_breakdown exists and is properly populated.
        
        Args:
            data: Response dictionary (modified in place)
        """
        # CRITICAL: First validate and adjust penalties
        self._validate_and_adjust_penalty(data)
        
        if 'penalty_breakdown' not in data or not data.get('penalty_breakdown'):
            logger.warning("Creating missing penalty_breakdown structure")
            data['penalty_breakdown'] = {
                'issues_found': [],
                'total_penalty': 0
            }
        
        # If we have a critical_issues_penalty but empty breakdown, create a generic entry
        penalty_score = data.get('scores', {}).get('critical_issues_penalty', 0)
        breakdown = data.get('penalty_breakdown', {})
        
        if penalty_score > 0 and not breakdown.get('issues_found'):
            logger.warning(f"Penalty score {penalty_score} but no breakdown - creating generic entry")
            # Try to infer severity from score
            if penalty_score >= 45:
                severity = 'critical'
                desc = 'Critical security/requirement issues detected'
            elif penalty_score >= 30:
                severity = 'major'
                desc = 'Major requirement violations detected'
            elif penalty_score >= 20:
                severity = 'moderate'
                desc = 'Moderate issues detected'
            else:
                severity = 'minor'
                desc = 'Minor issues detected'
            
            breakdown['issues_found'] = [{
                'issue': f"[INFERRED] {desc}",
                'severity': severity,
                'penalty': penalty_score
            }]
            breakdown['total_penalty'] = penalty_score
    
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
    
    def _validate_and_adjust_penalty(self, parsed_response: Dict[str, Any]) -> None:
        """
        Simple penalty validation - just ensure the structure exists.
        Trust the LLM's evaluation based on our clear prompt.
        
        Args:
            parsed_response: Parsed response dictionary from LLM (modified in place)
        """
        # Just ensure penalty_breakdown exists and trust the LLM
        if 'penalty_breakdown' not in parsed_response:
            parsed_response['penalty_breakdown'] = {
                'issues_found': [],
                'total_penalty': 0
            }
        
        # Cap security penalties if they're too high
        issues = parsed_response.get('penalty_breakdown', {}).get('issues_found', [])
        for issue in issues:
            if isinstance(issue, dict):
                issue_text = issue.get('issue', '').lower()
                # Cap math/rand penalty at 20
                if 'math/rand' in issue_text and issue.get('penalty', 0) > 20:
                    logger.info(f"Capping math/rand penalty to 20")
                    issue['penalty'] = 20
                # Cap JWT issues at 15  
                elif 'jwt' in issue_text and 'hardcoded' in issue_text and issue.get('penalty', 0) > 15:
                    logger.info(f"Capping JWT penalty to 15")
                    issue['penalty'] = 15
        
        # Recalculate total
        total = sum(i.get('penalty', 0) for i in issues if isinstance(i, dict))
        parsed_response['penalty_breakdown']['total_penalty'] = total
        
        # Ensure scores match
        if 'scores' not in parsed_response:
            parsed_response['scores'] = {}
        parsed_response['scores']['critical_issues_penalty'] = total
    
    def _convert_to_analysis_result(self, parsed_response: Dict[str, Any], role: str = "backend", content: str = None) -> AnalysisResult:
        """
        Convert parsed LLM response to structured AnalysisResult.
        
        Args:
            parsed_response: Parsed response dictionary from LLM
            
        Returns:
            Structured AnalysisResult object
        """
        # NOTE: Penalty validation already done in _ensure_penalty_breakdown
        # Do NOT call _validate_and_adjust_penalty again here!
        
        # Map LLM recommendation string to enum
        # Both backend and frontend use 'recommendation' field with yes/no format
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
                # Force a decision based on positive metrics average and critical issues
                scores = parsed_response.get('scores', {})
                
                # Calculate average of positive metrics only (exclude penalty)
                penalty_keywords = ['penalty', 'critical_issues', 'violations']
                positive_scores = []
                penalty = 0
                
                for key, value in scores.items():
                    if any(keyword in key.lower() for keyword in penalty_keywords):
                        penalty = max(penalty, value)  # Use highest penalty value found
                    else:
                        positive_scores.append(value)
                
                avg_score = sum(positive_scores) / len(positive_scores) if positive_scores else 0
                
                if penalty >= 50:
                    logger.info(f"Critical issues detected (penalty: {penalty}), forcing REJECT")
                    recommendation = RecommendationLevel.REJECT
                elif avg_score >= 70:
                    logger.info(f"Converting 'maybe' to ACCEPT (score: {avg_score:.1f}%, penalty: {penalty})")
                    recommendation = RecommendationLevel.ACCEPT
                else:
                    logger.info(f"Converting 'maybe' to REJECT (score: {avg_score:.1f}%, penalty: {penalty})")
                    recommendation = RecommendationLevel.REJECT
        else:
            # Fallback - make decision based on scores
            scores = parsed_response.get('scores', {})
            
            # Calculate average of positive metrics only (exclude penalty)
            penalty_keywords = ['penalty', 'critical_issues', 'violations']
            positive_scores = []
            penalty = 0
            
            for key, value in scores.items():
                if any(keyword in key.lower() for keyword in penalty_keywords):
                    penalty = max(penalty, value)  # Use highest penalty value found
                else:
                    positive_scores.append(value)
            
            avg_score = sum(positive_scores) / len(positive_scores) if positive_scores else 0
            
            if penalty >= 50:
                logger.warning(f"Unknown recommendation '{recommendation_str}', defaulting to REJECT due to critical issues (penalty: {penalty})")
                recommendation = RecommendationLevel.REJECT
            elif avg_score >= 70:
                logger.warning(f"Unknown recommendation '{recommendation_str}', defaulting to ACCEPT (score: {avg_score:.1f}%, penalty: {penalty})")
                recommendation = RecommendationLevel.ACCEPT
            else:
                logger.warning(f"Unknown recommendation '{recommendation_str}', defaulting to REJECT (score: {avg_score:.1f}%, penalty: {penalty})")
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
        
        # Calculate average score from POSITIVE metrics only (exclude penalties)
        positive_scores = []
        for key, value in normalized_scores.items():
            # Skip penalty scores
            if 'penalty' not in key.lower() and 'critical' not in key.lower():
                positive_scores.append(value)
        
        avg_score = sum(positive_scores) / len(positive_scores) if positive_scores else 0
        logger.info(f"Average of positive scores: {avg_score:.1f}% (from {positive_scores})")
        
        # Handle both old and new prompt formats robustly
        # New format has 'requirements_implementation', old has 'requirements_met'
        requirements_met = {}
        
        # Try multiple locations where requirements might be stored
        if 'requirements_implementation' in parsed_response:
            # Convert new format to old format for compatibility
            for req_name, req_data in parsed_response.get('requirements_implementation', {}).items():
                if isinstance(req_data, dict):
                    requirements_met[req_name] = req_data.get('implemented', False)
                else:
                    requirements_met[req_name] = bool(req_data)
        elif 'requirements_met' in parsed_response:
            # Old format - ensure all values are booleans
            raw_requirements = parsed_response.get('requirements_met', {})
            for key, value in raw_requirements.items():
                # Handle different representations of boolean values
                if isinstance(value, bool):
                    requirements_met[key] = value
                elif isinstance(value, str):
                    requirements_met[key] = value.lower() in ['true', 'yes', '✓', 'pass', 'implemented']
                elif isinstance(value, dict):
                    requirements_met[key] = value.get('implemented', False) or value.get('met', False)
                else:
                    requirements_met[key] = bool(value)
        else:
            # No requirements found - try to extract from other fields
            logger.warning("No requirements_met or requirements_implementation in response")
            
            # Try to infer from scores or other fields
            if 'task_requirements' in parsed_response:
                for req, status in parsed_response['task_requirements'].items():
                    requirements_met[req] = bool(status)
            elif 'architecture_check' in parsed_response:
                # Map architecture check results
                arch_check = parsed_response['architecture_check']
                requirements_met['architectural_pattern'] = arch_check.get('pattern', False)
                requirements_met['repository_pattern'] = arch_check.get('repository', False)
                requirements_met['service_layer'] = arch_check.get('service', False)
                requirements_met['redis_implementation'] = arch_check.get('redis', False)
                requirements_met['database_implementation'] = arch_check.get('database', False)
        
        # Log what we extracted
        logger.info(f"Extracted requirements_met: {requirements_met}")
        
        # FALLBACK: If requirements_met is empty or all False, try to infer from feedback
        if not requirements_met or all(not v for v in requirements_met.values()):
            logger.warning("Requirements all False or missing - attempting inference from feedback")
            feedback = parsed_response.get('detailed_feedback', '').lower()
            strengths_text = ' '.join(parsed_response.get('strengths', [])).lower()
            combined_text = feedback + ' ' + strengths_text
            
            # Infer based on positive mentions in feedback
            if 'repository pattern' in combined_text and 'implement' in combined_text:
                requirements_met['repository_pattern'] = True
                logger.info("Inferred repository_pattern=True from feedback")
            
            if 'service layer' in combined_text and ('implement' in combined_text or 'proper' in combined_text):
                requirements_met['service_layer'] = True
                logger.info("Inferred service_layer=True from feedback")
            
            if 'redis' in combined_text and ('implement' in combined_text or 'uses redis' in combined_text):
                requirements_met['redis_implementation'] = True
                logger.info("Inferred redis_implementation=True from feedback")
            
            if any(arch in combined_text for arch in ['layered architecture', 'clean architecture', 'hexagonal', 'mvc']):
                requirements_met['architectural_pattern'] = True
                logger.info("Inferred architectural_pattern=True from feedback")
            
            if 'docker' in combined_text and ('dockerfile' in combined_text or 'docker-compose' in combined_text):
                requirements_met['dockerization'] = True
                logger.info("Inferred dockerization=True from feedback")
        
        # For frontend, double-check cookie usage in actual content
        if role == "frontend" and content:
            cookie_patterns = ['js-cookie', 'setCookie', 'getCookie', 'Cookies.set', 'Cookies.get', 'removeCookie']
            localStorage_patterns = ['localStorage.setItem', 'localStorage.getItem', 'localStorage.removeItem', 'localStorage.clear']
            
            has_cookies = any(pattern in content for pattern in cookie_patterns)
            has_localStorage = any(pattern in content for pattern in localStorage_patterns)
            
            if has_cookies and not has_localStorage:
                logger.warning("⚠️ Detected cookie usage instead of localStorage - applying penalty but keeping requirement as met")
                # NOTE: Don't mark requirement as False - it's technically implemented, just with a different method
                # requirements_met['localstorage_implementation'] stays True, but we add penalty
                
                # Add a 20-point penalty for not following the exact requirement
                if 'penalty_breakdown' not in parsed_response:
                    parsed_response['penalty_breakdown'] = {'issues_found': [], 'total_penalty': 0}
                
                # Check if penalty already exists to avoid duplication
                existing_issues = parsed_response['penalty_breakdown'].get('issues_found', [])
                has_storage_penalty = any('localStorage' in str(issue.get('issue', '')) for issue in existing_issues)
                
                if not has_storage_penalty:
                    storage_penalty = {
                        'category': 'requirements',
                        'issue': 'Used cookies instead of localStorage (task explicitly required localStorage)',
                        'severity': 'medium',
                        'penalty': 20,
                        'evidence': 'Found js-cookie or setCookie functions instead of localStorage API'
                    }
                    parsed_response['penalty_breakdown']['issues_found'].append(storage_penalty)
                    parsed_response['penalty_breakdown']['total_penalty'] = parsed_response['penalty_breakdown'].get('total_penalty', 0) + 20
                    
                    # Update scores if they exist
                    if 'scores' in parsed_response:
                        parsed_response['scores']['critical_issues_penalty'] = parsed_response['penalty_breakdown']['total_penalty']
                    
                    logger.warning("📝 Added 20-point penalty for using cookies instead of localStorage")
        
        # Extract strengths and weaknesses from different possible locations
        strengths = parsed_response.get('strengths', [])
        weaknesses = parsed_response.get('weaknesses', [])
        
        # Try to extract from seniority_assessment if not found
        if not strengths and 'seniority_assessment' in parsed_response:
            seniority = parsed_response['seniority_assessment']
            # Handle case where seniority_assessment might be a list instead of dict
            if isinstance(seniority, dict):
                strengths = seniority.get('strengths', [])
                weaknesses = seniority.get('growth_areas', weaknesses)
            else:
                logger.warning(f"seniority_assessment is not a dict, got: {type(seniority)}")
        
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
            seniority_for_suggestions = parsed_response['seniority_assessment']
            if isinstance(seniority_for_suggestions, dict):
                growth_areas = seniority_for_suggestions.get('growth_areas', [])
                if growth_areas:
                    suggestions = [f"Consider improving: {area}" for area in growth_areas[:3]]
        
        # Extract hiring decision if present
        hiring_decision = parsed_response.get('hiring_decision', {})
        
        # TWO-PHASE DECISION LOGIC
        penalty = normalized_scores.get('critical_issues_penalty', 0)
        avg_positive = avg_score  # Already calculated above
        
        # Define the mandatory requirements based on role
        if role == "frontend":
            mandatory_requirements = [
                'login_page_implementation',
                'phone_validation',
                'api_integration',
                'localstorage_implementation',
                'dashboard_page',
                'logout_functionality',
                'nextjs_app_router',
                'typescript_strict',
                'tailwind_only',
                'responsive_design',
                'folder_structure'
            ]
        else:  # backend
            mandatory_requirements = [
                'otp_login_registration',
                'rate_limiting', 
                'user_management',
                'api_documentation',
                'architectural_pattern',
                'repository_pattern',
                'service_layer',
                'redis_implementation',
                'database_implementation',
                'dockerization'
            ]
        
        # Phase 1: Check if ALL mandatory requirements are met
        missing_requirements = []
        for req in mandatory_requirements:
            if not requirements_met.get(req, False):
                missing_requirements.append(req)
        
        # Make the decision
        if missing_requirements:
            # Phase 1 failure - missing mandatory requirements
            hiring_decision['decision'] = 'NO_HIRE'
            hiring_decision['primary_reason'] = f"Missing mandatory requirements: {', '.join(missing_requirements)}"
            hiring_decision['phase_1_pass'] = False
        elif penalty > 50:
            # Phase 2 failure - too many issues
            hiring_decision['decision'] = 'NO_HIRE'
            hiring_decision['primary_reason'] = f"Critical issues penalty too high: {penalty} points"
            hiring_decision['phase_1_pass'] = True
        elif avg_positive >= 70:
            # All requirements met + good quality = HIRE
            hiring_decision['decision'] = 'HIRE'
            hiring_decision['primary_reason'] = f"All requirements met with {avg_positive:.1f}% quality"
            hiring_decision['phase_1_pass'] = True
        else:
            # All requirements met but quality below threshold
            hiring_decision['decision'] = 'REVIEW'
            hiring_decision['primary_reason'] = f"All requirements met but quality at {avg_positive:.1f}% (below 70%)"
            hiring_decision['phase_1_pass'] = True
        
        # Extract architecture analysis for frontend (required field)
        architecture_analysis = parsed_response.get('architecture_analysis', None)
        if role == "frontend" and not architecture_analysis:
            # Log error but don't generate fake data
            logger.error("Frontend analysis missing required architecture_analysis field")
            # Add a marker that it was missing
            parsed_response['missing_architecture_analysis'] = True
        
        # Validate response quality for frontend
        if role == "frontend":
            detailed_feedback = parsed_response.get('detailed_feedback', '')
            
            # Check for banned vague phrases
            vague_phrases = [
                'could benefit from', 'might improve', 'consider adding',
                'somewhat lacking', 'generally good', 'mostly works',
                'may need', 'should consider', 'would be better'
            ]
            
            has_vague_language = any(phrase in detailed_feedback.lower() for phrase in vague_phrases)
            if has_vague_language:
                logger.warning("Frontend analysis contains vague language - may need re-analysis")
            
            # Check for specific evidence (file:line format)
            has_specific_evidence = bool(re.search(r'\w+\.\w+:\d+', detailed_feedback))
            if not has_specific_evidence:
                logger.warning("Frontend analysis lacks specific file:line evidence")
            
            # Validate localStorage detection evidence
            storage_check = parsed_response.get('storage_method_check', {})
            if not storage_check.get('evidence') or storage_check.get('evidence') == 'No evidence found':
                logger.warning("Frontend analysis missing localStorage detection evidence")

        return AnalysisResult(
            requirements_met=requirements_met,
            scores=normalized_scores,
            recommendation=recommendation,
            confidence=float(confidence),
            strengths=strengths,
            weaknesses=weaknesses,
            detailed_feedback=parsed_response.get('detailed_feedback', ''),
            suggestions=suggestions,
            hiring_decision=hiring_decision,
            penalty_breakdown=parsed_response.get('penalty_breakdown', None),
            architecture_analysis=architecture_analysis
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
