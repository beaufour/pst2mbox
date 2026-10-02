"""Generic IMAP uploader for restoring PST messages."""

import base64
import email
import hashlib
import imaplib
import logging
import re
import time
from typing import Optional

from pst2mbox.models import Message
from pst2mbox.utils import message_to_rfc822

logger = logging.getLogger(__name__)
RESTORE_ID_HEADER = "X-PST2MBOX-ID"


def encode_modified_utf7(value: str) -> str:
    """Encode an IMAP mailbox name using modified UTF-7 (RFC 3501)."""
    result: list[str] = []
    non_ascii: list[str] = []

    def flush_non_ascii() -> None:
        if non_ascii:
            encoded = base64.b64encode("".join(non_ascii).encode("utf-16-be"))
            result.append("&" + encoded.decode("ascii").rstrip("=").replace("/", ",") + "-")
            non_ascii.clear()

    for character in value:
        if " " <= character <= "~":
            flush_non_ascii()
            result.append("&-" if character == "&" else character)
        else:
            non_ascii.append(character)
    flush_non_ascii()
    return "".join(result)


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
        encoded = encode_modified_utf7(mailbox)
        return '"' + encoded.replace("\\", "\\\\").replace('"', '\\"') + '"'

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

    @staticmethod
    def _quote_search_value(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    @staticmethod
    def _restore_id(message: Message) -> str:
        """Return a stable identifier for this source message and folder."""
        digest = hashlib.sha256()
        values = [
            message.folder_path,
            message.message_id,
            message.subject,
            message.sender,
            ",".join(message.recipients),
            message.date.isoformat(),
            message.body,
            message.html_body or "",
        ]
        for value in values:
            digest.update(value.encode("utf-8", errors="surrogatepass"))
            digest.update(b"\0")
        for attachment in message.attachments:
            digest.update(attachment.filename.encode("utf-8", errors="surrogatepass"))
            digest.update(b"\0")
            digest.update(attachment.content)
            digest.update(b"\0")
        return digest.hexdigest()

    def _search_header(self, header: str, value: str) -> list[str]:
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")
        status, response = self._imap.search(
            None, "HEADER", header, self._quote_search_value(value)
        )
        if status != "OK" or not response or not isinstance(response[0], bytes):
            return []
        return response[0].decode("ascii").split()

    def _fetch_headers(self, sequence_number: str, fields: str) -> list[email.message.Message]:
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")
        status, data = self._imap.fetch(
            sequence_number, f"(BODY.PEEK[HEADER.FIELDS ({fields})])"
        )
        if status != "OK":
            return []
        return [
            email.message_from_bytes(item[1])
            for item in data or []
            if isinstance(item, tuple)
        ]

    def _is_duplicate(self, message: Message, mailbox: str, restore_id: str) -> bool:
        if not self._imap:
            raise IMAPConnectionError("Not connected to IMAP")
        status, _ = self._imap.select(self._quote_mailbox(mailbox), readonly=True)
        if status != "OK":
            raise IMAPUploadError(f"Failed to select mailbox {mailbox}")

        for sequence_number in self._search_header(RESTORE_ID_HEADER, restore_id):
            for headers in self._fetch_headers(sequence_number, RESTORE_ID_HEADER):
                if self._normalized_header(headers.get(RESTORE_ID_HEADER)) == restore_id:
                    return True

        message_id = self._normalized_header(message.message_id)
        if not message_id:
            # ponytail: legacy headerless messages have no safe remote key; the restore ID covers future runs.
            return False
        received = self._normalized_header(message.headers.get("Received"))
        legacy_headers = {
            "Date": self._normalized_header(email.utils.format_datetime(message.date)),
            "From": self._normalized_header(message.sender),
            "To": self._normalized_header(", ".join(message.recipients)),
        }
        for sequence_number in self._search_header("Message-ID", message_id):
            for headers in self._fetch_headers(sequence_number, "MESSAGE-ID RECEIVED DATE FROM TO"):
                if self._normalized_header(headers.get("Message-ID")) != message_id:
                    continue
                if received and any(
                    self._normalized_header(value) == received
                    for value in headers.get_all("Received", [])
                ):
                    return True
                if all(
                    self._normalized_header(headers.get(name)) == value
                    for name, value in legacy_headers.items()
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
            restore_id = self._restore_id(message)
            if self._is_duplicate(message, mailbox, restore_id):
                return "duplicate"
            email_message = message_to_rfc822(message)
            email_message[RESTORE_ID_HEADER] = restore_id
            append_result = self._imap.append(
                self._quote_mailbox(mailbox),
                "",
                imaplib.Time2Internaldate(message.date.timestamp()),
                email_message.as_bytes(),
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
