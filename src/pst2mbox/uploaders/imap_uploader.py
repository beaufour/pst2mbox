"""Generic IMAP uploader for restoring PST messages."""

import email
import imaplib
import logging
import re
import time
from typing import Optional

from pst2mbox.models import Message
from pst2mbox.utils import message_to_rfc822

logger = logging.getLogger(__name__)


class IMAPConnectionError(Exception):
    """IMAP connection or authentication failed."""


class IMAPUploadError(Exception):
    """Uploading a message failed."""


class IMAPUploader:
    """Uploads messages to a password-authenticated IMAP account."""

    IMAP_TIMEOUT = 60
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self._delimiter = "/"
        self._created_mailboxes: set[str] = set()

    def connect(self) -> None:
        """Connect with verified TLS and authenticate with IMAP LOGIN."""
        try:
            self._imap = imaplib.IMAP4_SSL(self.host, self.port, timeout=self.IMAP_TIMEOUT)
            status, response = self._imap.login(self.username, self.password)
            if status != "OK":
                raise IMAPConnectionError(f"IMAP authentication failed: {response}")
            self._delimiter = self._get_hierarchy_delimiter()
            logger.info("Connected to %s as %s", self.host, self.username)
        except imaplib.IMAP4.error as error:
            self.disconnect()
            raise IMAPConnectionError(f"IMAP authentication failed: {error}") from error
        except Exception as error:
            self.disconnect()
            raise IMAPConnectionError(f"Failed to connect to IMAP server: {error}") from error

    def disconnect(self) -> None:
        """Close the IMAP connection."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def _get_hierarchy_delimiter(self) -> str:
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")
        status, response = self._imap.list("", "")
        if status != "OK":
            return "/"
        for item in response or []:
            if not isinstance(item, bytes):
                continue
            match = re.search(rb"\([^)]*\) (?:\"([^\"]*)\"|NIL)", item)
            if match and match.group(1):
                return match.group(1).decode("ascii")
        return "/"

    @staticmethod
    def _quote_mailbox(mailbox: str) -> str:
        return '"' + mailbox.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def mailbox_for_folder(self, folder_path: str) -> str:
        return self._delimiter.join(part for part in folder_path.split("/") if part)

    def ensure_mailbox_exists(self, mailbox: str) -> None:
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")
        parts = mailbox.split(self._delimiter)
        for index in range(1, len(parts) + 1):
            partial = self._delimiter.join(parts[:index])
            if partial in self._created_mailboxes:
                continue
            status, response = self._imap.create(self._quote_mailbox(partial))
            if status != "OK" and b"ALREADYEXISTS" not in b" ".join(response or []):
                raise IMAPUploadError(f"Failed to create mailbox {partial}: {response}")
            self._created_mailboxes.add(partial)

    @staticmethod
    def _normalized_header(value: Optional[str]) -> str:
        return " ".join(value.split()) if value else ""

    def _is_duplicate(self, message: Message, mailbox: str) -> bool:
        message_id = self._normalized_header(message.message_id)
        received = self._normalized_header(message.headers.get("Received"))
        if not message_id or not received:
            return False
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")

        status, _ = self._imap.select(self._quote_mailbox(mailbox), readonly=True)
        if status != "OK":
            raise IMAPUploadError(f"Failed to select mailbox {mailbox}")
        status, response = self._imap.search(None, "HEADER", "Message-ID", message_id)
        if status != "OK" or not response:
            return False
        first_response = response[0]
        if not isinstance(first_response, bytes):
            return False
        for sequence_number in first_response.split():
            status, data = self._imap.fetch(
                sequence_number.decode("ascii"),
                "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID RECEIVED)])",
            )
            if status != "OK":
                continue
            for item in data or []:
                if not isinstance(item, tuple):
                    continue
                headers = email.message_from_bytes(item[1])
                if self._normalized_header(headers.get("Message-ID")) == message_id and any(
                    self._normalized_header(value) == received
                    for value in headers.get_all("Received", [])
                ):
                    return True
        return False

    def upload_message(self, message: Message, retry_count: int = 0) -> str:
        """Upload one message, returning ``uploaded`` or ``duplicate``."""
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")
        mailbox = self.mailbox_for_folder(message.folder_path)
        if not mailbox:
            raise IMAPUploadError("Message has no destination mailbox")
        try:
            self.ensure_mailbox_exists(mailbox)
            if self._is_duplicate(message, mailbox):
                return "duplicate"
            append_result = self._imap.append(
                self._quote_mailbox(mailbox),
                "",
                imaplib.Time2Internaldate(message.date.timestamp()),
                message_to_rfc822(message).as_bytes(),
            )
            if not isinstance(append_result, tuple):
                raise IMAPUploadError(f"APPEND failed: {append_result}")
            status, response = append_result
            if status != "OK":
                raise IMAPUploadError(f"APPEND failed: {response}")
            return "uploaded"
        except (imaplib.IMAP4.abort, ConnectionError, BrokenPipeError, TimeoutError) as error:
            if retry_count >= self.MAX_RETRIES:
                raise IMAPUploadError(
                    f"Failed to upload after {self.MAX_RETRIES} retries: {error}"
                ) from error
            time.sleep(self.RETRY_DELAY_BASE ** (retry_count + 1))
            self.disconnect()
            self.connect()
            return self.upload_message(message, retry_count + 1)
        except imaplib.IMAP4.error as error:
            raise IMAPUploadError(f"IMAP error uploading message: {error}") from error
