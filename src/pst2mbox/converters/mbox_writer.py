"""Writer for converting messages to mbox format."""

import email.encoders
import email.utils
import mailbox
from email.message import EmailMessage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Iterator

from pst2mbox.models import Attachment, Message


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

        # Convert message to email format
        email_message = self._convert_to_email(message)

        # Add folder header for FLAT_WITH_HEADER strategy
        if self.strategy == OutputStrategy.FLAT_WITH_HEADER and message.folder_path:
            email_message["X-Folder"] = message.folder_path

        # Add to mbox
        mbox = self._mbox_files[mbox_key]
        mbox.add(email_message)

    def _convert_to_email(self, message: Message) -> EmailMessage:
        """Convert internal Message to EmailMessage.

        Args:
            message: Message to convert.

        Returns:
            EmailMessage object.
        """
        # Create base email message
        if message.has_attachments() or message.html_body:
            # Use multipart for messages with attachments or HTML
            email_msg = MIMEMultipart()
        else:
            # Simple text message
            email_msg = EmailMessage()

        # Set headers
        email_msg["Subject"] = message.subject
        email_msg["From"] = message.sender
        email_msg["To"] = ", ".join(message.recipients)
        email_msg["Date"] = email.utils.format_datetime(message.date)
        email_msg["Message-ID"] = message.message_id

        if message.cc:
            email_msg["Cc"] = ", ".join(message.cc)
        if message.bcc:
            email_msg["Bcc"] = ", ".join(message.bcc)
        if message.in_reply_to:
            email_msg["In-Reply-To"] = message.in_reply_to
        if message.references:
            email_msg["References"] = " ".join(message.references)

        # Add custom headers
        for key, value in message.headers.items():
            # Skip headers we already set
            if key.lower() not in [
                "subject",
                "from",
                "to",
                "date",
                "message-id",
                "cc",
                "bcc",
                "in-reply-to",
                "references",
            ]:
                try:
                    email_msg[key] = value
                except Exception:
                    # Skip headers that can't be set
                    pass

        # Add body
        if isinstance(email_msg, MIMEMultipart):
            # Add text part
            text_part = MIMEText(message.body, "plain", "utf-8")
            email_msg.attach(text_part)

            # Add HTML part if present
            if message.html_body:
                html_part = MIMEText(message.html_body, "html", "utf-8")
                email_msg.attach(html_part)

            # Add attachments
            for attachment in message.attachments:
                self._add_attachment(email_msg, attachment)
        else:
            email_msg.set_content(message.body)

        return email_msg

    def _add_attachment(
        self, email_msg: MIMEMultipart, attachment: Attachment
    ) -> None:
        """Add an attachment to the email message.

        Args:
            email_msg: Email message to add attachment to.
            attachment: Attachment to add.
        """
        # Parse content type
        maintype, _, subtype = attachment.content_type.partition("/")
        if not subtype:
            maintype = "application"
            subtype = "octet-stream"

        # Create attachment part
        part = MIMEBase(maintype, subtype)
        part.set_payload(attachment.content)

        # Encode attachment
        email.encoders.encode_base64(part)

        # Add header with filename
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment.filename,
        )

        email_msg.attach(part)

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
