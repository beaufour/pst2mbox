"""readpst-based backend for reading PST files."""

from email import utils
import mailbox
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

from pst2mbox.backends.base import PSTBackend
from pst2mbox.models import Attachment, Folder, Message
from datetime import datetime


class ReadPSTBackend(PSTBackend):
    """Backend that uses the readpst command-line tool."""

    def __init__(self, pst_path: Path) -> None:
        """Initialize the readpst backend.

        Args:
            pst_path: Path to the PST file to read.
        """
        super().__init__(pst_path)
        self._temp_dir: Path | None = None
        self._mbox_files: list[Path] = []
        self._folders: list[Folder] = []
        self._conversion_errors: list[tuple[str, str, str]] = []  # (message_id, subject, error)

    def _check_readpst_available(self) -> bool:
        """Check if readpst is installed and available.

        Returns:
            True if readpst is available, False otherwise.
        """
        return shutil.which("readpst") is not None

    def open(self) -> None:
        """Open the PST file by running readpst to extract to mbox format.

        Raises:
            FileNotFoundError: If the PST file doesn't exist or readpst is not installed.
            ValueError: If the file is not a valid PST file.
            RuntimeError: If readpst fails to extract the PST file.
        """
        if not self.pst_path.exists():
            raise FileNotFoundError(f"PST file not found: {self.pst_path}")

        if not self._check_readpst_available():
            raise FileNotFoundError(
                "readpst command not found. Please install libpst/pst-utils:\n"
                "  macOS: brew install libpst\n"
                "  Ubuntu/Debian: sudo apt-get install pst-utils\n"
                "  Fedora: sudo dnf install libpst"
            )

        # Create temporary directory for extraction
        self._temp_dir = Path(tempfile.mkdtemp(prefix="pst2mbox_"))

        # Run readpst to extract PST to mbox format
        # -r: recursive (include subfolders)
        # -D: include deleted items
        # -o: output directory
        # Note: Default output format (without -M or -S) is mbox
        # Run readpst - it may return non-zero exit code even on successful extraction
        # (e.g., when encountering calendar items), so we don't check the return code
        result = subprocess.run(
            [
                "readpst",
                "-r",  # recursive
                "-D",  # include deleted
                "-o",
                str(self._temp_dir),
                str(self.pst_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # Check if extraction produced any output files
        if not any(self._temp_dir.iterdir()):
            raise RuntimeError(
                f"readpst failed to extract PST file. Error: {result.stderr}"
            )

        # Find all mbox files created by readpst
        # readpst default format creates files named "mbox" in each folder directory
        self._mbox_files = list(self._temp_dir.rglob("mbox"))
        # Also check for .mbox extension as a fallback
        self._mbox_files.extend(self._temp_dir.rglob("*.mbox"))

        # Clear any previous conversion errors
        self._conversion_errors = []

        # Build folder structure from mbox files
        self._build_folder_structure()
        self._is_open = True

    def _build_folder_structure(self) -> None:
        """Build folder structure from extracted mbox files."""
        assert self._temp_dir is not None
        folders_dict: dict[str, Folder] = {}

        for mbox_file in self._mbox_files:
            # Get relative path from temp dir
            # For file "Outlook/Inbox/mbox", we want folder path "Outlook/Inbox"
            rel_path = mbox_file.relative_to(self._temp_dir)

            # The folder path is the parent directory of the mbox file
            if rel_path.parent == Path("."):
                # mbox file at root
                folder_name = mbox_file.stem
                full_path = folder_name
            else:
                # mbox file in subdirectory - use parent dir as folder path
                full_path = str(rel_path.parent)
                folder_name = rel_path.parent.name

            # Count messages in this mbox
            try:
                mbox = mailbox.mbox(str(mbox_file))
                message_count = len(mbox)
            except Exception:
                message_count = 0

            folder = Folder(
                name=folder_name,
                path=full_path,
                message_count=message_count,
            )
            folders_dict[full_path] = folder
            self._folders.append(folder)

    def close(self) -> None:
        """Close the backend and clean up temporary files."""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)
        self._temp_dir = None
        self._mbox_files = []
        self._folders = []
        self._is_open = False

    def get_folders(self) -> list[Folder]:
        """Get all folders in the PST file.

        Returns:
            List of folders.

        Raises:
            RuntimeError: If the PST file is not open.
        """
        if not self._is_open:
            raise RuntimeError("PST file is not open. Call open() first.")
        assert self._temp_dir is not None
        return self._folders.copy()

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
        if not self._is_open:
            raise RuntimeError("PST file is not open. Call open() first.")
        assert self._temp_dir is not None

        # Determine which mbox files to process
        mbox_files_to_process = []
        if folder:
            # Find mbox file for this folder using same logic as _build_folder_structure
            for mbox_file in self._mbox_files:
                rel_path = mbox_file.relative_to(self._temp_dir)

                # Calculate folder path same way as in _build_folder_structure
                if rel_path.parent == Path("."):
                    full_path = mbox_file.stem
                else:
                    full_path = str(rel_path.parent)

                if full_path == folder.path:
                    mbox_files_to_process.append(mbox_file)
                    break
        else:
            mbox_files_to_process = self._mbox_files

        # Iterate through mbox files and convert messages
        for mbox_file in mbox_files_to_process:
            rel_path = mbox_file.relative_to(self._temp_dir)

            # Calculate folder path same way as in _build_folder_structure
            if rel_path.parent == Path("."):
                full_folder_path = mbox_file.stem
            else:
                full_folder_path = str(rel_path.parent)

            try:
                mbox = mailbox.mbox(str(mbox_file))
            except Exception as e:
                print(f"Warning: Failed to open mbox file {mbox_file}: {e}")
                continue

            for mbox_message in mbox:
                try:
                    yield self._convert_mbox_message(mbox_message, full_folder_path)
                except Exception as e:
                    # Track error and continue processing other messages
                    message_id = self._header_to_str(mbox_message.get("Message-ID", ""))
                    subject = str(mbox_message.get("Subject", "(unknown)"))
                    self._conversion_errors.append((message_id, subject, str(e)))
                    continue

    def _header_to_str(self, value) -> str:
        """Convert a header value to string.

        Args:
            value: Header value (can be str, Header object, or None).

        Returns:
            String representation of the header value.
        """
        if value is None:
            return ""
        return str(value)

    def _convert_mbox_message(
        self, mbox_message: mailbox.mboxMessage, folder_path: str
    ) -> Message:
        """Convert an mbox message to our internal Message format.

        Args:
            mbox_message: The mbox message to convert.
            folder_path: Path of the folder containing this message.

        Returns:
            Converted Message object.
        """
        # Extract basic headers (convert Header objects to strings)
        subject = self._header_to_str(mbox_message.get("Subject", "(No Subject)"))
        sender = self._header_to_str(mbox_message.get("From", ""))
        message_id = self._header_to_str(mbox_message.get("Message-ID", ""))
        in_reply_to = self._header_to_str(mbox_message.get("In-Reply-To"))

        # Parse date
        date_str = self._header_to_str(mbox_message.get("Date", ""))
        try:
            date = utils.parsedate_to_datetime(date_str)
        except Exception:
            date = datetime.now()

        # Parse recipients (convert Header objects to strings first)
        recipients = self._parse_addresses(self._header_to_str(mbox_message.get("To", "")))
        cc = self._parse_addresses(self._header_to_str(mbox_message.get("Cc", "")))
        bcc = self._parse_addresses(self._header_to_str(mbox_message.get("Bcc", "")))

        # Extract body and attachments
        body = ""
        html_body = None
        attachments: list[Attachment] = []

        if mbox_message.is_multipart():
            for part in mbox_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    # This is an attachment
                    filename = part.get_filename() or "unknown"
                    content = part.get_payload(decode=True)
                    if not isinstance(content, bytes):
                        content = b""
                    attachments.append(
                        Attachment(
                            filename=filename,
                            content=content,
                            content_type=content_type,
                        )
                    )
                elif content_type == "text/plain" and not body:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="ignore")
                elif content_type == "text/html" and not html_body:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        html_body = payload.decode("utf-8", errors="ignore")
        else:
            # Single part message
            payload = mbox_message.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode("utf-8", errors="ignore")

        # Extract all headers (convert Header objects to strings)
        headers = {k: self._header_to_str(v) for k, v in mbox_message.items()}

        return Message(
            subject=subject,
            sender=sender,
            recipients=recipients,
            date=date,
            body=body,
            message_id=message_id,
            folder_path=folder_path,
            html_body=html_body,
            attachments=attachments,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
            headers=headers,
        )

    def _parse_addresses(self, address_string: str) -> list[str]:
        """Parse email addresses from a header string.

        Args:
            address_string: String containing email addresses.

        Returns:
            List of email addresses.
        """
        if not address_string:
            return []

        addresses = utils.getaddresses([address_string])
        return [addr[1] for addr in addresses if addr[1]]

    def get_message_count(self, folder: Folder | None = None) -> int:
        """Get the total number of messages.

        Args:
            folder: Optional folder to count messages in.

        Returns:
            Total number of messages.

        Raises:
            RuntimeError: If the PST file is not open.
        """
        if not self._is_open:
            raise RuntimeError("PST file is not open. Call open() first.")

        if folder:
            return folder.message_count

        return sum(f.message_count for f in self._folders)

    def get_conversion_errors(self) -> list[tuple[str, str, str]]:
        """Get messages that failed to convert during iteration.

        Returns:
            List of (message_id, subject, error_message) tuples for failed conversions.
        """
        return self._conversion_errors.copy()
