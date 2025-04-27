"""
Results for the editor module.

This module provides result classes for the editor module compatible with Python 3.11.11.
"""

from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, List, Optional, Union

from openhands_py311.editor.config import MAX_RESPONSE_LEN_CHAR
from openhands_py311.editor.prompts import CONTENT_TRUNCATED_NOTICE


@dataclass
class ToolResult:
    """Represents the result of a tool execution."""

    output: Optional[str] = None
    error: Optional[str] = None

    def __bool__(self) -> bool:
        """Return True if any field has a non-None/non-empty value."""
        return any(getattr(self, field.name) for field in fields(self))

    def to_dict(self, extra_field: Optional[Dict] = None) -> Dict:
        """Convert the result to a dictionary.
        
        Args:
            extra_field: Additional fields to include in the dictionary.
            
        Returns:
            Dictionary representation of the result.
        """
        result = asdict(self)

        # Add extra fields if provided
        if extra_field:
            result.update(extra_field)
        return result


@dataclass
class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output.
    
    Attributes:
        output: Output message (success case).
        error: Error message (failure case).
        path: Path to the file being operated on.
        prev_exist: Whether the file existed before the operation.
        old_content: Content of the file before the operation.
        new_content: Content of the file after the operation.
    """

    # Optional fields for file editing commands
    path: Optional[str] = None
    prev_exist: bool = True
    old_content: Optional[str] = None
    new_content: Optional[str] = None


def maybe_truncate(
    content: str,
    truncate_after: Optional[int] = MAX_RESPONSE_LEN_CHAR,
    truncate_notice: str = CONTENT_TRUNCATED_NOTICE,
) -> str:
    """Truncate content and append a notice if content exceeds the specified length.
    
    Args:
        content: Content to truncate.
        truncate_after: Maximum length before truncation, or None for no truncation.
        truncate_notice: Notice to append after truncation.
        
    Returns:
        Truncated content with notice, or original content if not truncated.
    """
    return (
        content
        if not truncate_after or len(content) <= truncate_after
        else content[:truncate_after] + truncate_notice
    )
