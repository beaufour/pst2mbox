"""Internal message representation for pst2mbox."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Attachment:
    """Represents an email attachment."""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    size: int = 0

    def __post_init__(self) -> None:
        """Set size based on content if not provided."""
        if self.size == 0:
            self.size = len(self.content)


@dataclass
class Folder:
    """Represents a folder in the PST file."""

    name: str
    path: str
    message_count: int = 0
    parent: Optional["Folder"] = None
    children: list["Folder"] = field(default_factory=list)

    def full_path(self) -> str:
        """Get the full hierarchical path of the folder."""
        if self.parent:
            parent_path = self.parent.full_path()
            return f"{parent_path}/{self.name}" if parent_path else self.name
        return self.name


@dataclass
class Message:
    """Represents an email message extracted from PST."""

    subject: str
    sender: str
    recipients: list[str]
    date: datetime
    body: str
    message_id: str
    folder_path: str = ""
    html_body: Optional[str] = None
    attachments: list[Attachment] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    in_reply_to: Optional[str] = None
    references: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    is_read: bool = False
    importance: str = "normal"

    def has_attachments(self) -> bool:
        """Check if message has attachments."""
        return len(self.attachments) > 0

    def total_attachment_size(self) -> int:
        """Calculate total size of all attachments."""
        return sum(att.size for att in self.attachments)
