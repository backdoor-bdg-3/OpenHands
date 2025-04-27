"""
Exceptions for the editor module.

This module provides exception classes for the editor module compatible with Python 3.11.11.
"""

class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class EditorToolParameterMissingError(ToolError):
    """Raised when a required parameter is missing for a tool command."""

    def __init__(self, command: str, parameter: str):
        self.command = command
        self.parameter = parameter
        self.message = f'Parameter `{parameter}` is required for command: {command}.'
        super().__init__(self.message)


class EditorToolParameterInvalidError(ToolError):
    """Raised when a parameter is invalid for a tool command."""

    def __init__(self, parameter: str, value, hint: str = None):
        self.parameter = parameter
        self.value = value
        self.message = (
            f'Invalid `{parameter}` parameter: {value}. {hint}'
            if hint
            else f'Invalid `{parameter}` parameter: {value}.'
        )
        super().__init__(self.message)


class FileValidationError(ToolError):
    """Raised when a file fails validation checks (size, type, etc.)."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        self.message = f'File validation failed for {path}: {reason}'
        super().__init__(self.message)
