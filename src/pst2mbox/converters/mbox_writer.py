"""Writer for converting messages to mbox format."""

import mailbox
from enum import Enum
from pathlib import Path
from typing import Iterator

from pst2mbox.models import Message
from pst2mbox.utils import message_to_rfc822, sanitize_header


class OutputStrategy(Enum):
    """Strategy for organizing output mbox files."""

    SINGLE_FILE = "single"  # All messages in one mbox
    PER_FOLDER = "folder"  # One mbox per PST folder
    FLAT_WITH_HEADER = "flat"  # Single mbox with X-Folder headers


class MboxWriter:
    """Writer for converting messages to mbox format."""

    def __init__(
        self, output_path: Path, strategy: OutputStrategy = OutputStrategy.SINGLE_FILE
    ) -> None:
        """Initialize the mbox writer.

        Args:
            output_path: Path to output mbox file or directory (for PER_FOLDER strategy).
            strategy: Output organization strategy.
        """
        self.output_path = output_path
        self.strategy = strategy
        self._mbox_files: dict[str, mailbox.mbox] = {}

        # Create output directory if needed
        if strategy == OutputStrategy.PER_FOLDER:
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

    def write_messages(
        self, messages: Iterator[Message], show_progress: bool = False
    ) -> int:
        """Write messages to mbox file(s).

        Args:
            messages: Iterator of messages to write.
            show_progress: Whether to show progress bar.

        Returns:
            Number of messages written.
        """
        count = 0

        for message in messages:
            self._write_message(message)
            count += 1

        return count

    def _write_message(self, message: Message) -> None:
        """Write a single message to the appropriate mbox file.

        Args:
            message: Message to write.
        """
        # Determine which mbox file to use
        if self.strategy == OutputStrategy.PER_FOLDER:
            # Create separate mbox for each folder
            mbox_key = message.folder_path or "root"
            if mbox_key not in self._mbox_files:
                # Sanitize folder path for filename
                safe_name = mbox_key.replace("/", "_").replace(" ", "_")
                mbox_path = self.output_path / f"{safe_name}.mbox"
                self._mbox_files[mbox_key] = mailbox.mbox(str(mbox_path))
        else:
            # Single file strategy
            mbox_key = "default"
            if mbox_key not in self._mbox_files:
                self._mbox_files[mbox_key] = mailbox.mbox(str(self.output_path))

        # Convert message to email format using shared utility
        email_message = message_to_rfc822(message)

        # Add folder header for FLAT_WITH_HEADER strategy
        if self.strategy == OutputStrategy.FLAT_WITH_HEADER and message.folder_path:
            email_message["X-Folder"] = sanitize_header(message.folder_path)

        # Add to mbox
        mbox = self._mbox_files[mbox_key]
        mbox.add(email_message)

    def close(self) -> None:
        """Close all open mbox files and flush changes."""
        for mbox in self._mbox_files.values():
            mbox.close()
        self._mbox_files.clear()

    def __enter__(self) -> "MboxWriter":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.close()
