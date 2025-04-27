import os
import warnings
import json
from typing import Any, Dict, List, Optional

import httpx
from pydantic import SecretStr

from openhands.core.config import LLMConfig
from openhands.core.exceptions import LLMNoResponseError
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import Message
from openhands.llm.debug_mixin import DebugMixin
from openhands.llm.metrics import Metrics
from openhands.llm.retry_mixin import RetryMixin

# Default model when none is specified
DEFAULT_MODEL = "meta-llama/CodeLlama-13b-Instruct-hf"
HF_TOKEN_ENV = "HF_TOKEN"
HUGGING_FACE_HUB_TOKEN = "HUGGING_FACE_HUB_TOKEN"

class VLLMStarCoder(RetryMixin, DebugMixin):
    """
    A class that integrates with Hugging Face models.
    """

    def __init__(
        self,
        config: LLMConfig,
        metrics: Metrics | None = None,
        retry_listener: Any = None,
    ):
        """Initialize the model instance.

        Args:
            config: The LLM configuration.
            metrics: The metrics to use.
            retry_listener: Optional callback for retry events.
        """
        # Use the model from config, or default to CodeLlama if not specified
        model_name = config.model
        if model_name.startswith("huggingface/"):
            model_name = model_name[len("huggingface/"):]
        
        self.metrics = metrics if metrics is not None else Metrics(model_name=model_name)
        self.config = config
        self.retry_listener = retry_listener
        
        # Use provided model or default
        if not self.config.model or self.config.model == "huggingface":
            self.config.model = DEFAULT_MODEL
            
        # Get or create base_url for Hugging Face
        if not self.config.base_url:
            if self.config.model.startswith("huggingface/"):
                model = self.config.model[len("huggingface/"):]
                self.config.base_url = f"https://api-inference.huggingface.co/models/{model}"
            else:
                self.config.base_url = f"https://api-inference.huggingface.co/models/{self.config.model}"
        
        # Check for API key
        self.hf_token = self.config.api_key.get_secret_value() if self.config.api_key else None
        
        # If no API key in config, try environment variables
        if not self.hf_token:
            self.hf_token = os.environ.get(HF_TOKEN_ENV) or os.environ.get(HUGGING_FACE_HUB_TOKEN)
            if not self.hf_token:
                logger.warning(f"No Hugging Face API token found in config or environment ({HF_TOKEN_ENV} or {HUGGING_FACE_HUB_TOKEN})")
        
        logger.info(f"Initialized model client with base URL: {self.config.base_url}")

    async def generate(
        self, 
        messages: List[Message] | Message,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a response from the Hugging Face model.

        Args:
            messages: The messages to generate a response for.
            temperature: The temperature to use for generation.
            max_tokens: The maximum number of tokens to generate.
            **kwargs: Additional arguments to pass to the API.

        Returns:
            A dictionary containing the generated response.
        """
        if isinstance(messages, Message):
            messages = [messages]
            
        # Format messages for the model
        formatted_messages = self.format_messages_for_llm(messages)
        prompt = self._convert_messages_to_prompt(formatted_messages)
        
        # Log the prompt
        self.log_prompt(formatted_messages)
        
        # Prepare the request payload for Hugging Face API
        request_data = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            }
        }
        
        # Add any additional parameters to the parameters field
        for key, value in kwargs.items():
            if key not in ["inputs", "parameters"]:
                request_data["parameters"][key] = value
        
        # Make the request to Hugging Face API
        try:
            headers = {
                "Content-Type": "application/json",
            }
            
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
                
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.base_url,
                    json=request_data,
                    headers=headers,
                    timeout=self.config.timeout or 120,  # Longer timeout for large models
                )
                
            if response.status_code != 200:
                error_msg = f"Hugging Face API returned status code {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise LLMNoResponseError(error_msg)
                
            response_data = response.json()
            
            # Hugging Face returns a list of generated texts
            generated_text = ""
            if isinstance(response_data, list) and len(response_data) > 0:
                generated_text = response_data[0].get("generated_text", "")
            
            # Format the response to match the expected structure
            result = {
                "id": f"hf-{self.config.model}-{id(self)}",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": generated_text,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(prompt) // 4,  # Rough estimate
                    "completion_tokens": len(generated_text) // 4,  # Rough estimate
                    "total_tokens": (len(prompt) + len(generated_text)) // 4,  # Rough estimate
                },
            }
            
            # Log the response
            self.log_response(generated_text)
            
            return result
            
        except httpx.TimeoutException:
            error_msg = "Request to Hugging Face API timed out"
            logger.error(error_msg)
            raise LLMNoResponseError(error_msg)
        except Exception as e:
            error_msg = f"Error calling Hugging Face API: {str(e)}"
            logger.error(error_msg)
            raise LLMNoResponseError(error_msg)

    def _convert_messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Convert a list of messages to a prompt string for the model.

        Args:
            messages: A list of message dictionaries.

        Returns:
            A prompt string formatted for the model.
        """
        prompt = ""
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")
            
            # Handle content that might be a list (multi-modal)
            if isinstance(content, list):
                content_str = ""
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        content_str += item["text"] + "\n"
                content = content_str
            
            # Format based on role
            if role == "system":
                prompt += f"<system>\n{content}\n</system>\n\n"
            elif role == "user":
                prompt += f"<human>\n{content}\n</human>\n\n"
            elif role == "assistant":
                prompt += f"<assistant>\n{content}\n</assistant>\n\n"
            else:
                # For any other role, just add the content
                prompt += f"{content}\n\n"
                
        # Add the final assistant prompt
        prompt += "<assistant>\n"
        
        return prompt

    def format_messages_for_llm(self, messages: Message | List[Message]) -> List[Dict[str, Any]]:
        """Format messages for the LLM.

        Args:
            messages: A message or list of messages.

        Returns:
            A list of message dictionaries.
        """
        if isinstance(messages, Message):
            messages = [messages]
            
        # Convert Message objects to dictionaries
        formatted_messages = []
        for message in messages:
            if hasattr(message, "model_dump"):
                formatted_messages.append(message.model_dump())
            else:
                # Fallback if model_dump is not available
                formatted_messages.append({
                    "role": getattr(message, "role", "user"),
                    "content": getattr(message, "content", "")
                })
                
        return formatted_messages

    def get_token_count(self, messages: List[Dict] | List[Message]) -> int:
        """Get the number of tokens in a list of messages.

        Args:
            messages: A list of messages.

        Returns:
            The number of tokens.
        """
        # For simplicity, we'll estimate token count based on characters
        # A more accurate implementation would use a proper tokenizer
        if isinstance(messages, list) and len(messages) > 0:
            if isinstance(messages[0], Message):
                messages = self.format_messages_for_llm(messages)  # type: ignore
                
        total_chars = 0
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                    
        # Rough estimate: 4 characters per token
        return total_chars // 4

    def reset(self) -> None:
        """Reset the metrics."""
        self.metrics.reset()

    def __str__(self) -> str:
        return f"HuggingFaceModel(model={self.config.model}, base_url={self.config.base_url})"

    def __repr__(self) -> str:
        return str(self)
        
    # Add compatibility methods for synchronous use
    def completion(self, messages, **kwargs):
        """Synchronous completion method for compatibility with the LLM class."""
        import asyncio
        
        # Run the async generate method in a synchronous context
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.generate(messages, **kwargs))
            return result
        finally:
            loop.close()
