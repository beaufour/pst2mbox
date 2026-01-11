"""Gmail IMAP uploader for importing messages to Gmail."""

import imaplib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pst2mbox.auth import GoogleOAuth2
from pst2mbox.models import Message
from pst2mbox.utils import message_to_rfc822

logger = logging.getLogger(__name__)


class GmailConnectionError(Exception):
    """Base exception for Gmail connection issues."""

    pass


class GmailAuthenticationError(GmailConnectionError):
    """OAuth2 or IMAP authentication failed."""

    pass


class GmailUploadError(Exception):
    """Failed to upload a specific message."""

    pass


class GmailUploader:
    """Uploads messages to Gmail via IMAP."""

    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2  # Exponential backoff base in seconds
    UPLOAD_DELAY = 0.1  # 100ms delay between uploads to avoid rate limits

    def __init__(
        self,
        email: str,
        credentials_path: Path,
        token_path: Path,
        label_prefix: Optional[str] = None,
    ) -> None:
        """Initialize Gmail uploader.

        Args:
            email: Gmail address to upload to.
            credentials_path: Path to OAuth client credentials JSON.
            token_path: Path to store/load refresh token.
            label_prefix: Prefix for all created labels (default: auto-generated).
        """
        self.email = email
        self.oauth = GoogleOAuth2(credentials_path, token_path)
        self.label_prefix = label_prefix or f"PST-Import-{datetime.now().strftime('%Y-%m-%d')}"
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self._created_labels: set[str] = set()

    def connect(self) -> None:
        """Connect and authenticate to Gmail IMAP server.

        Raises:
            GmailAuthenticationError: If authentication fails.
            GmailConnectionError: If connection fails.
        """
        try:
            # Get OAuth2 credentials
            credentials = self.oauth.get_credentials()

            # Connect to Gmail IMAP
            self._imap = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT)

            # Authenticate using XOAUTH2
            auth_string = self._build_xoauth2_string(self.email, credentials.token)
            self._imap.authenticate("XOAUTH2", lambda x: auth_string)

            logger.info(f"Connected to Gmail as {self.email}")

        except imaplib.IMAP4.error as e:
            # Token may appear valid locally but be invalidated server-side.
            # Try forcing a refresh and retry once.
            if "AUTHENTICATIONFAILED" in str(e):
                logger.warning("Authentication failed, forcing token refresh and retrying...")
                try:
                    credentials = self.oauth.force_refresh()
                    self._imap = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT)
                    auth_string = self._build_xoauth2_string(self.email, credentials.token)
                    self._imap.authenticate("XOAUTH2", lambda x: auth_string)
                    logger.info(f"Connected to Gmail as {self.email} (after token refresh)")
                    return
                except Exception as retry_error:
                    raise GmailAuthenticationError(
                        f"IMAP authentication failed after token refresh: {retry_error}"
                    )
            raise GmailAuthenticationError(f"IMAP authentication failed: {e}")
        except Exception as e:
            raise GmailConnectionError(f"Failed to connect to Gmail: {e}")

    def disconnect(self) -> None:
        """Disconnect from Gmail IMAP server."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def _build_xoauth2_string(self, email: str, access_token: str) -> bytes:
        """Build XOAUTH2 SASL authentication string.

        Args:
            email: User's email address.
            access_token: OAuth2 access token.

        Returns:
            Raw authentication string as bytes (imaplib handles base64 encoding).
        """
        auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
        return auth_string.encode("utf-8")

    def _quote_mailbox(self, mailbox: str) -> str:
        """Quote mailbox name for IMAP commands.

        IMAP mailbox names containing spaces or special characters must be
        quoted. imaplib doesn't do this automatically, so we handle it here.

        Args:
            mailbox: The mailbox/label name.

        Returns:
            Properly quoted mailbox name for IMAP.
        """
        # Escape backslashes and double quotes, then wrap in quotes
        escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def ensure_label_exists(self, label: str) -> None:
        """Create a Gmail label if it doesn't exist.

        Gmail requires parent labels to exist before creating children.
        For "Parent/Child/Grandchild", we create each level in order.

        Args:
            label: Label name (can be nested like "Parent/Child").
        """
        if label in self._created_labels:
            return

        if not self._imap:
            raise GmailConnectionError("Not connected to Gmail")

        # Gmail requires creating parent labels first for nested hierarchy
        # For "A/B/C", create "A", then "A/B", then "A/B/C"
        parts = label.split("/")
        for i in range(1, len(parts) + 1):
            partial_label = "/".join(parts[:i])
            if partial_label in self._created_labels:
                continue

            self._create_single_label(partial_label)

    def _create_single_label(self, label: str) -> None:
        """Create a single Gmail label (no hierarchy handling).

        Args:
            label: Label name to create.
        """
        try:
            # Quote mailbox name for IMAP (imaplib doesn't auto-quote spaces)
            quoted_label = self._quote_mailbox(label)
            status, response = self._imap.create(quoted_label)

            # ALREADYEXISTS is not an error
            if status == "OK" or b"ALREADYEXISTS" in (response[0] or b""):
                self._created_labels.add(label)
                logger.debug(f"Label created or exists: {label}")
            else:
                logger.warning(f"Failed to create label {label}: {response}")

        except imaplib.IMAP4.error as e:
            # Label may already exist
            if "ALREADYEXISTS" not in str(e):
                logger.warning(f"Error creating label {label}: {e}")
            self._created_labels.add(label)

    def build_label_path(self, folder_path: str) -> str:
        """Build Gmail label path from PST folder path.

        Args:
            folder_path: Original PST folder path (e.g., "Inbox/Work").

        Returns:
            Gmail label path with prefix (e.g., "PST-Import-2024-01-11/Inbox/Work").
        """
        if folder_path:
            return f"{self.label_prefix}/{folder_path}"
        return self.label_prefix

    def upload_message(
        self,
        message: Message,
        retry_count: int = 0,
    ) -> Optional[str]:
        """Upload a message to Gmail.

        Args:
            message: Message to upload.
            retry_count: Current retry attempt (for internal use).

        Returns:
            Gmail message UID if successful, None if failed.

        Raises:
            GmailConnectionError: If not connected.
            GmailUploadError: If upload fails after retries.
        """
        if not self._imap:
            raise GmailConnectionError("Not connected to Gmail")

        try:
            # Build label path
            label = self.build_label_path(message.folder_path)

            # Ensure label exists
            self.ensure_label_exists(label)

            # Convert message to RFC822 format
            email_message = message_to_rfc822(message)
            message_bytes = email_message.as_bytes()

            # Check message size (Gmail limit is 25MB)
            if len(message_bytes) > 25 * 1024 * 1024:
                logger.warning(
                    f"Message too large ({len(message_bytes)} bytes), skipping: "
                    f"{message.subject[:50]}"
                )
                return None

            # Format date for IMAP APPEND
            date_str = imaplib.Time2Internaldate(message.date.timestamp())

            # Upload message using APPEND
            # Quote mailbox name for IMAP (imaplib doesn't auto-quote spaces)
            quoted_label = self._quote_mailbox(label)
            result = self._imap.append(
                quoted_label,
                "",  # No flags
                date_str,
                message_bytes,
            )
            status: str = result[0]
            response = result[1]

            if status != "OK":
                raise GmailUploadError(f"APPEND failed: {response}")

            # Log if response looks unusual (should contain APPENDUID)
            response_str = str(response)
            if response and b"APPENDUID" not in response[0]:
                logger.warning(
                    f"IMAP APPEND response missing APPENDUID: {response_str}"
                )

            # Add small delay to avoid rate limits
            time.sleep(self.UPLOAD_DELAY)

            logger.debug(f"Uploaded message: {message.subject[:50]}")
            return response_str

        except (imaplib.IMAP4.abort, ConnectionError, BrokenPipeError) as e:
            # Connection was lost, try to reconnect
            if retry_count < self.MAX_RETRIES:
                delay = self.RETRY_DELAY_BASE ** (retry_count + 1)
                logger.warning(
                    f"Connection lost, retrying in {delay}s (attempt {retry_count + 1}): {e}"
                )
                time.sleep(delay)

                # Reconnect
                self.disconnect()
                self.connect()

                # Retry upload
                return self.upload_message(message, retry_count + 1)
            else:
                raise GmailUploadError(
                    f"Failed to upload after {self.MAX_RETRIES} retries: {e}"
                )

        except imaplib.IMAP4.error as e:
            raise GmailUploadError(f"IMAP error uploading message: {e}")

    def __enter__(self) -> "GmailUploader":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.disconnect()
