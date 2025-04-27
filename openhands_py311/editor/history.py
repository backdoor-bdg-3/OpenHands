"""
History management for file edits with disk-based storage and memory constraints.

This module provides history management for file edits compatible with Python 3.11.11.
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any

from openhands_py311.editor.file_cache import FileCache


class FileHistoryManager:
    """Manages file edit history with disk-based storage and memory constraints.
    
    This class provides a mechanism to track and retrieve previous versions of files
    for undo operations and history tracking.
    
    Attributes:
        max_history_per_file: Maximum number of history entries to keep per file.
        cache: FileCache instance for storing history entries.
    """

    def __init__(
        self, max_history_per_file: int = 5, history_dir: Optional[Path] = None
    ):
        """Initialize the history manager.

        Args:
            max_history_per_file: Maximum number of history entries to keep per file (default: 5)
            history_dir: Directory to store history files. If None, uses a temp directory

        Notes:
            - Each file's history is limited to the last N entries to conserve memory
            - The file cache is limited to prevent excessive disk usage
            - Older entries are automatically removed when limits are exceeded
        """
        self.max_history_per_file = max_history_per_file
        if history_dir is None:
            history_dir = Path(tempfile.mkdtemp(prefix='oh_editor_history_'))
        self.cache = FileCache(str(history_dir))
        self.logger = logging.getLogger(__name__)

    def _get_metadata_key(self, file_path: Path) -> str:
        """Get the metadata key for a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Metadata key string.
        """
        return f'{file_path}.metadata'

    def _get_history_key(self, file_path: Path, counter: int) -> str:
        """Get the history key for a file and counter.
        
        Args:
            file_path: Path to the file.
            counter: History entry counter.
            
        Returns:
            History key string.
        """
        return f'{file_path}.{counter}'

    def add_history(self, file_path: Path, content: str) -> None:
        """Add a new history entry for a file.
        
        Args:
            file_path: Path to the file.
            content: Content to store in history.
        """
        metadata_key = self._get_metadata_key(file_path)
        metadata = self.cache.get(metadata_key, {'entries': [], 'counter': 0})
        counter = metadata['counter']

        # Add new entry
        history_key = self._get_history_key(file_path, counter)
        self.cache.set(history_key, content)

        metadata['entries'].append(counter)
        metadata['counter'] += 1

        # Keep only last N entries
        while len(metadata['entries']) > self.max_history_per_file:
            old_counter = metadata['entries'].pop(0)
            old_history_key = self._get_history_key(file_path, old_counter)
            self.cache.delete(old_history_key)

        self.cache.set(metadata_key, metadata)

    def pop_last_history(self, file_path: Path) -> Optional[str]:
        """Pop and return the most recent history entry for a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Most recent history entry, or None if no history exists.
        """
        metadata_key = self._get_metadata_key(file_path)
        metadata = self.cache.get(metadata_key, {'entries': [], 'counter': 0})
        entries = metadata['entries']

        if not entries:
            return None

        # Pop and remove the last entry
        last_counter = entries.pop()
        history_key = self._get_history_key(file_path, last_counter)
        content = self.cache.get(history_key)

        if content is None:
            self.logger.warning(f'History entry not found for {file_path}')
        else:
            # Remove the entry from the cache
            self.cache.delete(history_key)

        # Update metadata
        metadata['entries'] = entries
        self.cache.set(metadata_key, metadata)

        return content

    def get_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get metadata for a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Metadata dictionary.
        """
        metadata_key = self._get_metadata_key(file_path)
        metadata = self.cache.get(metadata_key, {'entries': [], 'counter': 0})
        return metadata

    def clear_history(self, file_path: Path) -> None:
        """Clear history for a given file.
        
        Args:
            file_path: Path to the file.
        """
        metadata_key = self._get_metadata_key(file_path)
        metadata = self.cache.get(metadata_key, {'entries': [], 'counter': 0})

        # Delete all history entries
        for counter in metadata['entries']:
            history_key = self._get_history_key(file_path, counter)
            self.cache.delete(history_key)

        # Clear metadata
        self.cache.set(metadata_key, {'entries': [], 'counter': 0})

    def get_all_history(self, file_path: Path) -> List[str]:
        """Get all history entries for a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            List of history entries.
        """
        metadata_key = self._get_metadata_key(file_path)
        metadata = self.cache.get(metadata_key, {'entries': [], 'counter': 0})
        entries = metadata['entries']

        history = []
        for counter in entries:
            history_key = self._get_history_key(file_path, counter)
            content = self.cache.get(history_key)
            if content is not None:
                history.append(content)

        return history
