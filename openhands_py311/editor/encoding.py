"""
Encoding management for file operations.

This module provides encoding detection and management for the editor module 
compatible with Python 3.11.11.
"""

import functools
import os
from pathlib import Path
from typing import Dict, Tuple, Optional, Callable, Any

try:
    import charset_normalizer
    HAVE_CHARSET_NORMALIZER = True
except ImportError:
    HAVE_CHARSET_NORMALIZER = False


class EncodingManager:
    """Manages file encodings across multiple operations to ensure consistency."""

    # Default maximum number of entries in the cache
    DEFAULT_MAX_CACHE_SIZE = 1000

    def __init__(self, max_cache_size: Optional[int] = None):
        """Initialize the encoding manager.
        
        Args:
            max_cache_size: Maximum number of entries in the cache. If None,
                            uses DEFAULT_MAX_CACHE_SIZE.
        """
        # Cache detected encodings to avoid repeated detection on the same file
        # Format: {path_str: (encoding, mtime)}
        self._encoding_cache: Dict[str, Tuple[str, float]] = {}
        self._max_cache_size = max_cache_size or self.DEFAULT_MAX_CACHE_SIZE
        # Default fallback encoding
        self.default_encoding = 'utf-8'
        # Confidence threshold for encoding detection
        self.confidence_threshold = 0.9

    def detect_encoding(self, path: Path) -> str:
        """Detect the encoding of a file without handling caching logic.
        
        Args:
            path: Path to the file
            
        Returns:
            The detected encoding or default encoding if detection fails
        """
        # Handle non-existent files
        if not path.exists():
            return self.default_encoding

        # Read a sample of the file to detect encoding
        sample_size = min(os.path.getsize(path), 1024 * 1024)  # Max 1MB sample
        with open(path, 'rb') as f:
            raw_data = f.read(sample_size)

        # Use charset_normalizer if available
        if HAVE_CHARSET_NORMALIZER:
            results = charset_normalizer.detect(raw_data)
            # Get the best match if any exists
            if results and results['confidence'] > self.confidence_threshold:
                encoding = results['encoding']
            else:
                encoding = self.default_encoding
        else:
            # Fallback detection method using Python's standard library
            import codecs
            encodings_to_try = ['utf-8', 'latin-1', 'ascii', 'utf-16', 'utf-32']
            for enc in encodings_to_try:
                try:
                    codecs.decode(raw_data, enc)
                    encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            else:
                encoding = self.default_encoding

        return encoding

    def get_encoding(self, path: Path) -> str:
        """Get encoding for a file, using cache or detecting if necessary.
        
        Args:
            path: Path to the file
            
        Returns:
            The encoding for the file
        """
        path_str = str(path)
        # If file doesn't exist, return default encoding
        if not path.exists():
            return self.default_encoding

        # Get current modification time
        current_mtime = os.path.getmtime(path)

        # Check cache for valid entry
        if path_str in self._encoding_cache:
            cached_encoding, cached_mtime = self._encoding_cache[path_str]
            if cached_mtime == current_mtime:
                return cached_encoding

        # No valid cache entry, detect encoding
        encoding = self.detect_encoding(path)

        # Cache the result with current modification time
        self._encoding_cache[path_str] = (encoding, current_mtime)
        
        # If cache is too large, remove oldest entries
        if len(self._encoding_cache) > self._max_cache_size:
            # Convert to list for Python 3.7+ compatibility
            items = list(self._encoding_cache.items())
            # Sort by mtime (second element of the tuple)
            items.sort(key=lambda x: x[1][1])
            # Remove oldest 10% of entries
            num_to_remove = max(1, int(len(items) * 0.1))
            for i in range(num_to_remove):
                del self._encoding_cache[items[i][0]]
                
        return encoding


def with_encoding(method: Callable) -> Callable:
    """Decorator to handle file encoding for file operations.
    
    This decorator automatically detects and applies the correct encoding
    for file operations, ensuring consistency between read and write operations.
    
    Args:
        method: The method to decorate
        
    Returns:
        The decorated method
    """
    @functools.wraps(method)
    def wrapper(self, path: Path, *args, **kwargs) -> Any:
        # Skip encoding handling for directories
        if path.is_dir():
            return method(self, path, *args, **kwargs)

        # For files that don't exist yet (like in 'create' command),
        # use the default encoding
        if not path.exists():
            if 'encoding' not in kwargs:
                kwargs['encoding'] = self._encoding_manager.default_encoding
        else:
            # Get encoding from the encoding manager for existing files
            encoding = self._encoding_manager.get_encoding(path)
            # Add encoding to kwargs if the method accepts it
            if 'encoding' not in kwargs:
                kwargs['encoding'] = encoding

        return method(self, path, *args, **kwargs)

    return wrapper
