"""
OpenHands Python 3.11 compatibility module.

This module provides the same functionality as the aci module but is compatible with Python 3.11.11.
It includes a file editor, file caching, encoding management, and other utilities needed for
file operations in Python 3.11 environments.
"""

import sys

# Ensure Python version is compatible
if sys.version_info < (3, 11):
    raise ImportError(
        f"Python {sys.version_info.major}.{sys.version_info.minor} is not supported. "
        f"OpenHands_py311 requires Python 3.11 or later."
    )

from openhands_py311.editor.file_editor import file_editor, edit_file_snippet
from openhands_py311.editor.file_cache import FileCache
from openhands_py311.editor.encoding import EncodingManager, with_encoding
from openhands_py311.editor.exceptions import ToolError
from openhands_py311.editor.results import ToolResult, CLIResult

__all__ = [
    'file_editor',
    'edit_file_snippet',
    'FileCache',
    'EncodingManager',
    'with_encoding',
    'ToolError',
    'ToolResult',
    'CLIResult',
]

__version__ = "0.1.0"
