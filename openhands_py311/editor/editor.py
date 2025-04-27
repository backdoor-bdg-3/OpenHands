"""
Editor implementation for OpenHands Python 3.11 compatibility.

This module provides the OHEditor class for file editing functionality compatible with Python 3.11.11.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union, Any, get_args

try:
    from binaryornot.check import is_binary
    HAVE_BINARYORNOT = True
except ImportError:
    HAVE_BINARYORNOT = False

from openhands_py311.linter.linter import DefaultLinter
from openhands_py311.utils.diff import get_diff
from openhands_py311.editor.config import SNIPPET_CONTEXT_WINDOW
from openhands_py311.editor.encoding import EncodingManager, with_encoding
from openhands_py311.editor.exceptions import (
    EditorToolParameterInvalidError,
    EditorToolParameterMissingError,
    FileValidationError,
    ToolError,
)
from openhands_py311.editor.history import FileHistoryManager
from openhands_py311.editor.prompts import DIRECTORY_CONTENT_TRUNCATED_NOTICE, FILE_CONTENT_TRUNCATED_NOTICE
from openhands_py311.editor.results import CLIResult, maybe_truncate

# Define the Command literal type for Python 3.11 compatibility
Command = Literal[
    'view',
    'create',
    'str_replace',
    'insert',
    'undo_edit',
]

# Get available commands as a tuple
AVAILABLE_COMMANDS = ('view', 'create', 'str_replace', 'insert', 'undo_edit')


class OHEditor:
    """
    An filesystem editor tool that allows the agent to
    - view
    - create
    - navigate
    - edit files
    
    This implementation is compatible with Python 3.11.11.
    """

    TOOL_NAME = 'oh_editor'
    MAX_FILE_SIZE_MB = 10  # Maximum file size in MB

    def __init__(
        self,
        max_file_size_mb: Optional[int] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize the editor.

        Args:
            max_file_size_mb: Maximum file size in MB. If None, uses the default MAX_FILE_SIZE_MB.
            workspace_root: Root directory that serves as the current working directory for relative path
                           suggestions. Must be an absolute path. If None, no path suggestions will be
                           provided for relative paths.
        """
        try:
            self._linter = DefaultLinter()
        except Exception as e:
            # If linter initialization fails, create a dummy linter
            self._linter = None
            
        self._history_manager = FileHistoryManager(max_history_per_file=10)
        self._max_file_size = (
            (max_file_size_mb or self.MAX_FILE_SIZE_MB) * 1024 * 1024
        )  # Convert to bytes
        # Initialize encoding manager
        self._encoding_manager = EncodingManager()
        # Set cwd (current working directory) if workspace_root is provided
        if workspace_root is not None:
            workspace_path = Path(workspace_root)
            # Ensure workspace_root is an absolute path
            if not workspace_path.is_absolute():
                raise ValueError(
                    f'workspace_root must be an absolute path, got: {workspace_root}'
                )
            self._cwd = workspace_path
        else:
            self._cwd = None

    def __call__(
        self,
        *,
        command: str,
        path: str,
        file_text: Optional[str] = None,
        view_range: Optional[List[int]] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        insert_line: Optional[int] = None,
        enable_linting: bool = False,
        **kwargs,
    ) -> CLIResult:
        """Execute a command on the specified file.
        
        Args:
            command: The command to execute (view, create, str_replace, insert, undo_edit).
            path: Path to the file.
            file_text: Text content for create command.
            view_range: Range of lines to view [start, end].
            old_str: String to replace in str_replace command.
            new_str: Replacement string in str_replace command or text to insert in insert command.
            insert_line: Line number to insert at in insert command.
            enable_linting: Whether to run linting on the changes.
            
        Returns:
            CLIResult: Result of the operation.
            
        Raises:
            ToolError: If the command is invalid or fails.
        """
        # Validate command
        if command not in AVAILABLE_COMMANDS:
            raise ToolError(
                f'Unrecognized command {command}. The allowed commands for the {self.TOOL_NAME} tool are: {", ".join(AVAILABLE_COMMANDS)}'
            )
        
        _path = Path(path)
        self.validate_path(command, _path)
        
        if command == 'view':
            return self.view(_path, view_range)
        elif command == 'create':
            if file_text is None:
                raise EditorToolParameterMissingError(command, 'file_text')
            self.write_file(_path, file_text)
            self._history_manager.add_history(_path, file_text)
            return CLIResult(
                path=str(_path),
                new_content=file_text,
                prev_exist=False,
                output=f'File created successfully at: {_path}',
            )
        elif command == 'str_replace':
            if old_str is None:
                raise EditorToolParameterMissingError(command, 'old_str')
            if new_str == old_str:
                raise EditorToolParameterInvalidError(
                    'new_str',
                    new_str,
                    'No replacement was performed. `new_str` and `old_str` must be different.',
                )
            return self.str_replace(_path, old_str, new_str, enable_linting)
        elif command == 'insert':
            if insert_line is None:
                raise EditorToolParameterMissingError(command, 'insert_line')
            if new_str is None:
                raise EditorToolParameterMissingError(command, 'new_str')
            return self.insert(_path, insert_line, new_str, enable_linting)
        elif command == 'undo_edit':
            return self.undo_edit(_path)
        
        # This should never happen but added for completeness
        raise ToolError(f'Unhandled command: {command}')
    
    def _count_lines(self, path: Path, encoding: str = 'utf-8') -> int:
        """
        Count the number of lines in a file safely.

        Args:
            path: Path to the file
            encoding: The encoding to use when reading the file

        Returns:
            The number of lines in the file
        """
        with open(path, encoding=encoding) as f:
            return sum(1 for _ in f)

    def str_replace(
        self,
        path: Path,
        old_str: str,
        new_str: Optional[str],
        enable_linting: bool,
        encoding: str = 'utf-8',
    ) -> CLIResult:
        """
        Implement the str_replace command, which replaces old_str with new_str in the file content.

        Args:
            path: Path to the file
            old_str: String to replace
            new_str: Replacement string
            enable_linting: Whether to run linting on the changes
            encoding: The encoding to use

        Returns:
            CLIResult: Result of the operation
        """
        self.validate_file(path)
        new_str = new_str or ''

        # Read the entire file first to handle both single-line and multi-line replacements
        file_content = self.read_file(path)

        # Find all occurrences using regex
        # Escape special regex characters in old_str to match it literally
        pattern = re.escape(old_str)
        occurrences = [
            (
                file_content.count('\n', 0, match.start()) + 1,  # line number
                match.group(),  # matched text
                match.start(),  # start position
            )
            for match in re.finditer(pattern, file_content)
        ]

        if not occurrences:
            raise ToolError(
                f'No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}.'
            )
        if len(occurrences) > 1:
            line_numbers = sorted(set(line for line, _, _ in occurrences))
            raise ToolError(
                f'No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {line_numbers}. Please ensure it is unique.'
            )

        # We found exactly one occurrence
        replacement_line, matched_text, idx = occurrences[0]

        # Create new content by replacing just the matched text
        new_file_content = (
            file_content[:idx] + new_str + file_content[idx + len(matched_text) :]
        )

        # Write the new content to the file
        self.write_file(path, new_file_content)

        # Save the content to history
        self._history_manager.add_history(path, file_content)

        # Create a snippet of the edited section
        start_line = max(0, replacement_line - SNIPPET_CONTEXT_WINDOW)
        end_line = replacement_line + SNIPPET_CONTEXT_WINDOW + new_str.count('\n')

        # Read just the snippet range
        snippet = self.read_file(path, start_line=start_line + 1, end_line=end_line)

        # Prepare the success message
        success_message = f'The file {path} has been edited. '
        success_message += self._make_output(
            snippet, f'a snippet of {path}', start_line + 1
        )

        if enable_linting and self._linter:
            # Run linting on the changes
            lint_results = self._run_linting(file_content, new_file_content, path)
            success_message += '\n' + lint_results + '\n'

        success_message += 'Review the changes and make sure they are as expected. Edit the file again if necessary.'
        return CLIResult(
            output=success_message,
            prev_exist=True,
            path=str(path),
            old_content=file_content,
            new_content=new_file_content,
        )

    def view(self, path: Path, view_range: Optional[List[int]] = None) -> CLIResult:
        """
        View the contents of a file or a directory.
        
        Args:
            path: Path to the file or directory
            view_range: Range of lines to view [start, end]
            
        Returns:
            CLIResult: Result of the operation
        """
        if path.is_dir():
            if view_range:
                raise EditorToolParameterInvalidError(
                    'view_range',
                    view_range,
                    'The `view_range` parameter is not allowed when `path` points to a directory.',
                )

            # Get files/dirs up to 2 levels deep, sorted
            items = []
            hidden_count = 0
            
            # This is a simplified implementation compared to the shell command in the original
            for root, dirs, files in os.walk(path):
                # Skip files deeper than 2 levels
                rel_root = os.path.relpath(root, path)
                depth = len(rel_root.split(os.sep)) if rel_root != '.' else 0
                if depth > 1:
                    continue
                
                # Process directories
                for d in dirs[:]:
                    if d.startswith('.'):
                        hidden_count += 1
                        dirs.remove(d)  # Don't traverse into hidden dirs
                        continue
                    if depth == 1:  # At depth 1, don't go deeper
                        items.append(f"{os.path.join(root, d)}/")
                
                # Process files
                for f in files:
                    if f.startswith('.'):
                        hidden_count += 1
                    else:
                        items.append(os.path.join(root, f))
            
            items.sort()
            
            # Format the output
            msg = [
                f"Here's the files and directories up to 2 levels deep in {path}, excluding hidden items:\n"
                + '\n'.join(items)
            ]
            if hidden_count > 0:
                msg.append(
                    f"\n{hidden_count} hidden files/directories in this directory are excluded. You can use 'ls -la {path}' to see them."
                )
            stdout = '\n'.join(msg)
            
            return CLIResult(
                output=stdout,
                path=str(path),
                prev_exist=True,
            )

        # Validate file and count lines
        self.validate_file(path)
        encoding = self._encoding_manager.get_encoding(path)
        num_lines = self._count_lines(path, encoding=encoding)

        start_line = 1
        if not view_range:
            file_content = self.read_file(path)
            output = self._make_output(file_content, str(path), start_line)

            return CLIResult(
                output=output,
                path=str(path),
                prev_exist=True,
            )

        if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                'It should be a list of two integers.',
            )

        start_line, end_line = view_range
        if start_line < 1 or start_line > num_lines:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its first element `{start_line}` should be within the range of lines of the file: {[1, num_lines]}.',
            )

        if end_line > num_lines:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its second element `{end_line}` should be smaller than the number of lines in the file: `{num_lines}`.',
            )

        if end_line != -1 and end_line < start_line:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its second element `{end_line}` should be greater than or equal to the first element `{start_line}`.',
            )

        if end_line == -1:
            end_line = num_lines

        file_content = self.read_file(path, start_line=start_line, end_line=end_line)

        # Get the detected encoding
        output = self._make_output(
            '\n'.join(file_content.splitlines()), str(path), start_line
        )  # Remove extra newlines

        return CLIResult(
            path=str(path),
            output=output,
            prev_exist=True,
        )

    def write_file(self, path: Path, file_text: str, encoding: str = 'utf-8') -> None:
        """
        Write the content of a file to a given path; raise a ToolError if an error occurs.

        Args:
            path: Path to the file to write
            file_text: Content to write to the file
            encoding: The encoding to use when writing the file
            
        Raises:
            ToolError: If the write operation fails
        """
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use open with encoding instead of path.write_text
            with open(path, 'w', encoding=encoding) as f:
                f.write(file_text)
        except Exception as e:
            raise ToolError(f'Ran into {e} while trying to write to {path}') from None

    def insert(
        self,
        path: Path,
        insert_line: int,
        new_str: str,
        enable_linting: bool,
        encoding: str = 'utf-8',
    ) -> CLIResult:
        """
        Implement the insert command, which inserts new_str at the specified line in the file content.

        Args:
            path: Path to the file
            insert_line: Line number where to insert the new content
            new_str: Content to insert
            enable_linting: Whether to run linting on the changes
            encoding: The encoding to use
            
        Returns:
            CLIResult: Result of the operation
        """
        # Validate file and count lines
        self.validate_file(path)
        num_lines = self._count_lines(path, encoding=encoding)

        if insert_line < 0 or insert_line > num_lines:
            raise EditorToolParameterInvalidError(
                'insert_line',
                insert_line,
                f'It should be within the range of lines of the file: {[0, num_lines]}',
            )

        new_str_lines = new_str.split('\n')

        # Create temporary file for the new content
        with tempfile.NamedTemporaryFile(
            mode='w', encoding=encoding, delete=False
        ) as temp_file:
            # Copy lines before insert point and save them for history
            history_lines = []
            with open(path, 'r', encoding=encoding) as f:
                for i, line in enumerate(f, 1):
                    if i > insert_line:
                        break
                    temp_file.write(line)
                    history_lines.append(line)

            # Insert new content
            for line in new_str_lines:
                temp_file.write(line + '\n')

            # Copy remaining lines and save them for history
            with open(path, 'r', encoding=encoding) as f:
                for i, line in enumerate(f, 1):
                    if i <= insert_line:
                        continue
                    temp_file.write(line)
                    history_lines.append(line)

        # Move temporary file to original location
        shutil.move(temp_file.name, path)

        # Read just the snippet range
        start_line = max(0, insert_line - SNIPPET_CONTEXT_WINDOW)
        end_line = min(
            num_lines + len(new_str_lines),
            insert_line + SNIPPET_CONTEXT_WINDOW + len(new_str_lines),
        )
        snippet = self.read_file(path, start_line=start_line + 1, end_line=end_line)

        # Save history - we already have the lines in memory
        file_text = ''.join(history_lines)
        self._history_manager.add_history(path, file_text)

        # Read new content for result
        new_file_text = self.read_file(path)

        success_message = f'The file {path} has been edited. '
        success_message += self._make_output(
            snippet,
            'a snippet of the edited file',
            max(1, insert_line - SNIPPET_CONTEXT_WINDOW + 1),
        )

        if enable_linting and self._linter:
            # Run linting on the changes
            lint_results = self._run_linting(file_text, new_file_text, path)
            success_message += '\n' + lint_results + '\n'

        success_message += 'Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary.'
        return CLIResult(
            output=success_message,
            prev_exist=True,
            path=str(path),
            old_content=file_text,
            new_content=new_file_text,
        )

    def validate_path(self, command: str, path: Path) -> None:
        """
        Check that the path/command combination is valid.

        Validates:
        1. Path is absolute
        2. Path and command are compatible
        
        Args:
            command: The command to execute
            path: Path to the file
            
        Raises:
            EditorToolParameterInvalidError: If the path is invalid for the command
        """
        # Check if its an absolute path
        if not path.is_absolute():
            suggestion_message = (
                'The path should be an absolute path, starting with `/`.'
            )

            # Only suggest the absolute path if cwd is provided and the path exists
            if self._cwd is not None:
                suggested_path = self._cwd / path
                if suggested_path.exists():
                    suggestion_message += f' Maybe you meant {suggested_path}?'

            raise EditorToolParameterInvalidError(
                'path',
                path,
                suggestion_message,
            )

        # Check if path and command are compatible
        if command == 'create' and path.exists():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'File already exists at: {path}. Cannot overwrite files using command `create`.',
            )
        if command != 'create' and not path.exists():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path {path} does not exist. Please provide a valid path.',
            )
        if command != 'view' and path.is_dir():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path {path} is a directory and only the `view` command can be used on directories.',
            )

    def undo_edit(self, path: Path) -> CLIResult:
        """
        Implement the undo_edit command.
        
        Args:
            path: Path to the file
            
        Returns:
            CLIResult: Result of the operation
        """
        current_text = self.read_file(path)
        old_text = self._history_manager.pop_last_history(path)
        
        if old_text is None:
            return CLIResult(
                output=f'No history found for {path}. Cannot undo.',
                prev_exist=True,
                path=str(path),
            )
            
        self.write_file(path, old_text)
        
        # Generate a diff
        diff = get_diff(current_text, old_text)
        
        return CLIResult(
            output=f'Changes to {path} undone successfully.\n\nDiff:\n{diff}',
            prev_exist=True,
            path=str(path),
            old_content=current_text,
            new_content=old_text,
        )

    def validate_file(self, path: Path) -> None:
        """
        Validate a file for various conditions like size and type.
        
        Args:
            path: Path to the file
            
        Raises:
            FileValidationError: If the file fails validation
        """
        # Skip validation for directories and non-existent files
        if not path.exists() or path.is_dir():
            return

        # Check file size
        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            max_size_mb = self._max_file_size / (1024 * 1024)
            raise FileValidationError(
                str(path),
                f'File is too large: {file_size / (1024 * 1024):.2f} MB (max: {max_size_mb} MB)',
            )

        # Check if the file is binary (if binaryornot is available)
        if HAVE_BINARYORNOT and is_binary(str(path)):
            raise FileValidationError(
                str(path),
                'File appears to be binary. The editor only supports text files.',
            )

    def read_file(
        self, path: Path, start_line: int = None, end_line: int = None, encoding: str = 'utf-8'
    ) -> str:
        """
        Read the content of a file or a portion of it.
        
        Args:
            path: Path to the file
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (inclusive)
            encoding: Encoding to use
            
        Returns:
            Content of the file
            
        Raises:
            ToolError: If the read operation fails
        """
        try:
            if start_line is not None and end_line is not None:
                with open(path, 'r', encoding=encoding) as f:
                    lines = f.readlines()
                return ''.join(lines[start_line - 1:end_line])
            else:
                with open(path, 'r', encoding=encoding) as f:
                    return f.read()
        except Exception as e:
            raise ToolError(f'Error reading file {path}: {str(e)}')

    def _make_output(self, content: str, content_description: str, start_line: int = 1) -> str:
        """
        Format the output with line numbers and content description.
        
        Args:
            content: Content to format
            content_description: Description of the content
            start_line: Starting line number
            
        Returns:
            Formatted output
        """
        line_numbers = []
        content_lines = content.splitlines()
        for i, line in enumerate(content_lines):
            line_numbers.append(f"{start_line + i:4d} | {line}")
            
        line_numbered_content = '\n'.join(line_numbers)
        return f"Contents of {content_description}:\n\n{line_numbered_content}"

    def _run_linting(self, old_content: str, new_content: str, path: Path) -> str:
        """
        Run linting on the changes and return formatted results.
        
        Args:
            old_content: Original content
            new_content: New content
            path: Path to the file
            
        Returns:
            Formatted linting results
        """
        if not self._linter:
            return "Linting skipped: linter not available."
            
        try:
            # Create temporary files for linting
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as old_file:
                old_file.write(old_content)
                old_file_path = old_file.name
                
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as new_file:
                new_file.write(new_content)
                new_file_path = new_file.name
                
            # Run linting
            lint_results = self._linter.lint_file_diff(old_file_path, new_file_path)
                
            # Format results
            if not lint_results:
                return "Linting: No issues found in the changes."
                
            result_lines = ["Linting results:"]
            for result in lint_results:
                for error in result.errors:
                    result_lines.append(
                        f"Line {error.get('line', 'unknown')}, "
                        f"Col {error.get('column', 'unknown')}: "
                        f"{error.get('message', 'Unknown error')}"
                    )
                    
            return "\n".join(result_lines)
        except Exception as e:
            return f"Linting error: {str(e)}"
        finally:
            # Clean up temporary files
            if 'old_file_path' in locals():
                os.unlink(old_file_path)
            if 'new_file_path' in locals():
                os.unlink(new_file_path)
