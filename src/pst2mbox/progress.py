"""Import progress tracking for resume capability."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class ImportProgress:
    """Tracks import progress to enable resuming interrupted imports."""

    def __init__(
        self,
        pst_file: Optional[Path] = None,
        destination: Optional[str] = None,
    ) -> None:
        """Initialize progress tracker.

        Args:
            pst_file: Path to PST file being imported.
            destination: IMAP host, port, and username being imported to.
        """
        self.pst_file = pst_file
        self.pst_hash: Optional[str] = None
        self.destination = destination
        self.uploaded_message_ids: set[str] = set()
        self.current_folder: Optional[str] = None
        self.total_uploaded: int = 0
        self.failed_message_ids: set[str] = set()
        self.started_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

        if pst_file:
            self.pst_hash = self._compute_file_hash(pst_file)
            self.started_at = datetime.now()

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """Compute a quick hash of a file for change detection.

        Uses first and last 1MB of file for speed on large files.

        Args:
            file_path: Path to file.

        Returns:
            Hex digest of file hash.
        """
        hasher = hashlib.md5()
        file_size = file_path.stat().st_size
        chunk_size = 1024 * 1024  # 1MB

        with open(file_path, "rb") as f:
            # Hash first chunk
            hasher.update(f.read(chunk_size))

            # Hash last chunk if file is large enough
            if file_size > chunk_size * 2:
                f.seek(-chunk_size, 2)  # Seek from end
                hasher.update(f.read(chunk_size))

            # Include file size in hash
            hasher.update(str(file_size).encode())

        return hasher.hexdigest()

    def mark_uploaded(self, message_id: str) -> None:
        """Mark a message as successfully uploaded.

        Args:
            message_id: Message ID that was uploaded.
        """
        self.uploaded_message_ids.add(message_id)
        self.total_uploaded += 1
        self.updated_at = datetime.now()

    def mark_failed(self, message_id: str) -> None:
        """Mark a message as failed to upload.

        Args:
            message_id: Message ID that failed.
        """
        self.failed_message_ids.add(message_id)
        self.updated_at = datetime.now()

    def is_uploaded(self, message_id: str) -> bool:
        """Check if a message has already been uploaded.

        Args:
            message_id: Message ID to check.

        Returns:
            True if message was previously uploaded.
        """
        return message_id in self.uploaded_message_ids

    def set_current_folder(self, folder: str) -> None:
        """Set the current folder being processed.

        Args:
            folder: Folder path being processed.
        """
        self.current_folder = folder
        self.updated_at = datetime.now()

    def save(self, path: Path) -> None:
        """Save progress to file.

        Args:
            path: Path to save progress file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "pst_file": str(self.pst_file) if self.pst_file else None,
            "pst_hash": self.pst_hash,
            "destination": self.destination,
            "uploaded_message_ids": list(self.uploaded_message_ids),
            "failed_message_ids": list(self.failed_message_ids),
            "current_folder": self.current_folder,
            "total_uploaded": self.total_uploaded,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": datetime.now().isoformat(),
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> Optional["ImportProgress"]:
        """Load progress from file.

        Args:
            path: Path to progress file.

        Returns:
            ImportProgress instance if file exists and is valid, None otherwise.
        """
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)

            progress = cls()
            progress.pst_file = Path(data["pst_file"]) if data.get("pst_file") else None
            progress.pst_hash = data.get("pst_hash")
            progress.destination = data.get("destination")
            progress.uploaded_message_ids = set(data.get("uploaded_message_ids", []))
            progress.failed_message_ids = set(data.get("failed_message_ids", []))
            progress.current_folder = data.get("current_folder")
            progress.total_uploaded = data.get("total_uploaded", 0)

            if data.get("started_at"):
                progress.started_at = datetime.fromisoformat(data["started_at"])
            if data.get("updated_at"):
                progress.updated_at = datetime.fromisoformat(data["updated_at"])

            return progress

        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def is_compatible(self, pst_file: Path, destination: str) -> bool:
        """Check if this progress is compatible with the given import.

        Args:
            pst_file: PST file path.
            destination: IMAP host, port, and username.

        Returns:
            True if progress can be resumed for this import.
        """
        if self.destination != destination:
            return False

        # Check if PST file has changed
        current_hash = self._compute_file_hash(pst_file)
        if self.pst_hash != current_hash:
            return False

        return True

    def get_stats(self) -> dict:
        """Get progress statistics.

        Returns:
            Dictionary with progress stats.
        """
        return {
            "total_uploaded": self.total_uploaded,
            "failed_count": len(self.failed_message_ids),
            "current_folder": self.current_folder,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }
