"""
File editor module for OpenHands Python 3.11 compatibility.

This module provides file editing functionality compatible with Python 3.11.11.
It integrates with the enhanced OHEditor class to provide a comprehensive file
editing capability.
"""

import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable, Tuple, Any

from openhands_py311.editor.editor import OHEditor, Command
from openhands_py311.editor.encoding import EncodingManager
from openhands_py311.editor.exceptions import ToolError
from openhands_py311.editor.file_cache import FileCache
from openhands_py311.editor.results import ToolResult, CLIResult
from openhands_py311.utils.diff import get_diff

# Create a global singleton instance of the editor
# Use current directory as workspace root if not specified
_GLOBAL_EDITOR = OHEditor(workspace_root=os.getcwd())

def _make_api_tool_result(tool_result: ToolResult) -> str:
    """Convert a ToolResult to a formatted output string.
    
    Args:
        tool_result: The result to format.
        
    Returns:
        Formatted output string.
    """
    if tool_result.error:
        return f'ERROR:\n{tool_result.error}'

    assert tool_result.output, 'Expected output in file_editor.'
    return tool_result.output

def _apply_edit_snippet(original_content: str, edit_snippet: str) -> str:
    """Apply an edit snippet to the original content.
    
    This function intelligently applies an edit snippet to the original content.
    It parses the edit snippet to identify unchanged sections (marked with comments)
    and applies only the changes.
    
    Args:
        original_content: The original content of the file.
        edit_snippet: The edit snippet to apply.
        
    Returns:
        The updated content after applying the edit snippet.
    """
    # If the file is empty or doesn't exist, just return the edit snippet
    if not original_content:
        return edit_snippet
    
    # If the edit snippet is empty, return the original content
    if not edit_snippet:
        return original_content
    
    # Detect the comment style based on file content or edit snippet
    comment_styles = {
        '#': r'#\s*\.\.\.\s*(.+?)\s*\.\.\.\s*',  # Python, Ruby, Shell
        '//': r'//\s*\.\.\.\s*(.+?)\s*\.\.\.\s*',  # JavaScript, TypeScript, C, C++, Swift
        '--': r'--\s*\.\.\.\s*(.+?)\s*\.\.\.\s*',  # Lua
        '/*': r'/\*\s*\.\.\.\s*(.+?)\s*\.\.\.\s*\*/',  # CSS, multiline comments
        '<!--': r'<!--\s*\.\.\.\s*(.+?)\s*\.\.\.\s*-->',  # HTML, XML
    }
    
    # Determine the comment style to use
    comment_style = None
    pattern = None
    for style, pat in comment_styles.items():
        if style in edit_snippet:
            comment_style = style
            pattern = pat
            break
    
    # If no comment style detected, default to Python
    if not comment_style:
        comment_style = '#'
        pattern = comment_styles['#']
    
    # Check if the edit snippet contains any comment markers
    contains_markers = False
    for style, pat in comment_styles.items():
        if re.search(pat, edit_snippet):
            contains_markers = True
            break
    
    # If no markers found, treat it as a full replacement
    if not contains_markers:
        return edit_snippet
    
    # Split the edit snippet into sections
    sections = []
    current_pos = 0
    
    # Find all comment markers in the edit snippet
    markers = []
    for style, pat in comment_styles.items():
        markers.extend(re.finditer(pat, edit_snippet))
    
    # Sort markers by their position in the edit snippet
    markers.sort(key=lambda m: m.start())
    
    # Process each marker
    for marker in markers:
        # Add the content before the marker
        if marker.start() > current_pos:
            sections.append({
                'type': 'content',
                'text': edit_snippet[current_pos:marker.start()]
            })
        
        # Add the marker
        sections.append({
            'type': 'marker',
            'text': marker.group(1)  # The text inside the marker
        })
        
        current_pos = marker.end()
    
    # Add any remaining content
    if current_pos < len(edit_snippet):
        sections.append({
            'type': 'content',
            'text': edit_snippet[current_pos:]
        })
    
    # Now apply the sections to the original content
    result = []
    original_lines = original_content.splitlines()
    
    # Process each section
    for section in sections:
        if section['type'] == 'marker':
            # This is a marker for unchanged content
            marker_text = section['text'].lower()
            
            # Special case for "existing imports", "imports", etc.
            if 'import' in marker_text:
                # Find import statements in the original content
                import_pattern = r'^(?:from|import)\s+.+$'
                import_lines = []
                for line in original_lines:
                    if re.match(import_pattern, line.strip()):
                        import_lines.append(line)
                
                if import_lines:
                    result.extend(import_lines)
            
            # Special case for "existing code", "rest of code", etc.
            elif any(x in marker_text for x in ['existing code', 'rest of code', 'rest of file']):
                # Include all original content
                result.extend(original_lines)
            
            # Special case for "function body", "method body", etc.
            elif any(x in marker_text for x in ['function body', 'method body']):
                # Try to find the function/method body
                # This is a simplified approach and might need enhancement for complex cases
                in_body = False
                indent = 0
                body_lines = []
                
                for line in original_lines:
                    if not in_body and re.match(r'^(\s*)def\s+', line):
                        in_body = True
                        indent = len(re.match(r'^(\s*)', line).group(1))
                    elif in_body:
                        line_indent = len(re.match(r'^(\s*)', line).group(1))
                        if line.strip() and line_indent <= indent:
                            in_body = False
                        else:
                            body_lines.append(line)
                
                if body_lines:
                    result.extend(body_lines)
            
            # Default case: try to find a section that matches the marker text
            else:
                # This is a simplified approach and might need enhancement for complex cases
                result.extend(original_lines)
        
        else:
            # This is content to be inserted
            result.extend(section['text'].splitlines())
    
    return '\n'.join(result)

def file_editor(
    command: str,
    path: str,
    file_text: Optional[str] = None,
    view_range: Optional[List[int]] = None,
    old_str: Optional[str] = None,
    new_str: Optional[str] = None,
    insert_line: Optional[int] = None,
    enable_linting: bool = False,
) -> str:
    """Edit, view, or create a file.
    
    This function provides a comprehensive interface to the file editor functionality,
    including viewing, creating, and editing files.
    
    Args:
        command: Editor command to execute (view, create, str_replace, insert, undo_edit).
        path: Path to the file.
        file_text: Text content for create command.
        view_range: Range of lines to view [start, end].
        old_str: String to replace in str_replace command.
        new_str: Replacement string in str_replace or text to insert in insert command.
        insert_line: Line number to insert at in insert command.
        enable_linting: Whether to run linting on the changes.
        
    Returns:
        Formatted result string with JSON result data.
        
    Raises:
        ToolError: If the file operation fails.
    """
    result: Optional[ToolResult] = None
    try:
        result = _GLOBAL_EDITOR(
            command=command,
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
            enable_linting=enable_linting,
        )
    except ToolError as e:
        result = ToolResult(error=e.message)

    formatted_output_and_error = _make_api_tool_result(result)
    marker_id = uuid.uuid4().hex

    # Generate JSON result with formatted output
    def json_generator() -> str:
        yield '{'
        first = True
        for key, value in result.to_dict().items():
            if not first:
                yield ','
            first = False
            yield f'"{key}": {json.dumps(value)}'
        yield f', "formatted_output_and_error": {json.dumps(formatted_output_and_error)}'
        yield '}'

    return (
        f'<oh_aci_output_{marker_id}>\n'
        + ''.join(json_generator())
        + f'\n</oh_aci_output_{marker_id}>'
    )

def edit_file_snippet(file_path: str, edit_snippet: str) -> Dict[str, Any]:
    """Edit a file using the provided edit snippet.
    
    This function provides an intelligent file editing capability that can apply
    targeted changes to specific portions of a file based on the edit snippet.
    
    This is maintained for backward compatibility with the previous API.
    
    Args:
        file_path: Path to the file to edit.
        edit_snippet: Edit snippet to apply to the file.
        
    Returns:
        Dict: Result of the operation.
        
    Raises:
        ToolError: If the file cannot be edited.
    """
    try:
        # Make sure the path is absolute
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
            
        # Check if the file exists
        if os.path.exists(file_path):
            # Read the file
            original_content = ""
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except UnicodeDecodeError:
                # Try to detect encoding
                encoding_manager = EncodingManager()
                encoding = encoding_manager.get_encoding(Path(file_path))
                with open(file_path, 'r', encoding=encoding) as f:
                    original_content = f.read()
            
            # Create a backup of the original file
            backup_path = f"{file_path}.bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Apply the edit snippet intelligently
            updated_content = _apply_edit_snippet(original_content, edit_snippet)
            
            # Generate a diff for logging/debugging
            diff = get_diff(original_content, updated_content)
            
            # Write the content using a simple write approach for compatibility
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                success = True
                message = f"File {file_path} edited successfully."
            except Exception as write_error:
                success = False
                message = f"Error writing file: {str(write_error)}"
                # Restore from backup
                with open(backup_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
            
            # Clean up the backup if everything went well
            if os.path.exists(backup_path):
                os.remove(backup_path)
                
            return {
                "success": success,
                "message": message,
                "file_path": file_path,
                "diff": diff
            }
        else:
            # Create the file with the edit snippet
            # For new files, we just use the edit snippet as is
            try:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(edit_snippet)
                
                diff = get_diff("", edit_snippet)
                return {
                    "success": True,
                    "message": f"File {file_path} created successfully.",
                    "file_path": file_path,
                    "diff": diff
                }
            except Exception as create_error:
                return {
                    "success": False,
                    "message": f"Error creating file: {str(create_error)}",
                    "file_path": file_path,
                    "diff": ""
                }
            
    except Exception as e:
        # If there was an error and we have a backup, restore it
        backup_path = f"{file_path}.bak"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                os.remove(backup_path)
            except Exception as restore_error:
                raise ToolError(f"Error editing file {file_path} and failed to restore backup: {str(e)}. Restore error: {str(restore_error)}")
        
        raise ToolError(f"Error editing file {file_path}: {str(e)}")
