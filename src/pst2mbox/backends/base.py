"""Base backend interface for PST file readers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from pst2mbox.models import Folder, Message


class PSTBackend(ABC):
    """Abstract base class for PST file reading backends."""

    def __init__(self, pst_path: Path) -> None:
        """Initialize the backend with a PST file path.

        Args:
            pst_path: Path to the PST file to read.
        """
        self.pst_path = pst_path
        self._is_open = False

    @abstractmethod
    def open(self) -> None:
        """Open the PST file for reading.

        Raises:
            FileNotFoundError: If the PST file doesn't exist.
            ValueError: If the file is not a valid PST file.
            PermissionError: If the file cannot be read.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the PST file and release resources."""
        pass

    @abstractmethod
    def get_folders(self) -> list[Folder]:
        """Get all folders in the PST file.

        Returns:
            List of folders in the PST file.

        Raises:
            RuntimeError: If the PST file is not open.
        """
        pass

    @abstractmethod
    def iter_messages(
        self, folder: Folder | None = None
    ) -> Iterator[Message]:
        """Iterate over messages in the PST file.

        Args:
            folder: Optional folder to filter messages. If None, iterates
                   over all messages in all folders.

        Yields:
            Messages from the PST file.

        Raises:
            RuntimeError: If the PST file is not open.
        """
        pass

    @abstractmethod
    def get_message_count(self, folder: Folder | None = None) -> int:
        """Get the total number of messages.

        Args:
            folder: Optional folder to count messages in. If None, counts
                   all messages in all folders.

        Returns:
            Total number of messages.

        Raises:
            RuntimeError: If the PST file is not open.
        """
        pass

    def __enter__(self) -> "PSTBackend":
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.close()
