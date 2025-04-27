from typing import Any, Optional, Union

from openhands.core.config import LLMConfig
from openhands.core.logger import openhands_logger as logger
from openhands.llm.metrics import Metrics
from openhands.llm.llm import LLM
from openhands.llm.vllm_starcoder import VLLMStarCoder

def create_llm(
    config: LLMConfig,
    metrics: Optional[Metrics] = None,
    retry_listener: Any = None,
) -> Union[LLM, VLLMStarCoder]:
    """Create a new LLM instance.
    
    Factory that creates an LLM instance based on the config.
    For Hugging Face models, it uses the standard LLM implementation.
    
    Args:
        config: The LLM configuration.
        metrics: Optional metrics instance.
        retry_listener: Optional retry listener.
        
    Returns:
        An LLM or VLLMStarCoder instance depending on the config.
    """
    if config.model.startswith('huggingface'):
        logger.info(f"Creating LLM instance for Hugging Face model: {config.model}")
        return LLM(config, metrics, retry_listener)
    
    # Default to VLLMStarCoder for compatibility with existing code
    logger.info("Creating VLLMStarCoder instance for default case")
    return VLLMStarCoder(config, metrics, retry_listener)
