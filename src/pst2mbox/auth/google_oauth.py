"""Google OAuth2 authentication handler for Gmail IMAP access."""

import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


class GoogleOAuth2:
    """Handles Google OAuth2 authentication for Gmail IMAP access."""

    SCOPES = ["https://mail.google.com/"]

    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
    ) -> None:
        """Initialize OAuth2 handler.

        Args:
            credentials_path: Path to OAuth client credentials JSON file
                (downloaded from Google Cloud Console).
            token_path: Path to store/load the refresh token.
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._credentials: Optional[Credentials] = None

    def get_credentials(self) -> Credentials:
        """Get valid OAuth2 credentials, refreshing or re-authenticating as needed.

        Returns:
            Valid Google OAuth2 credentials.

        Raises:
            FileNotFoundError: If credentials file doesn't exist.
            ValueError: If credentials file is invalid.
        """
        # Try to load existing token
        if self.token_path.exists():
            self._credentials = self._load_token()

        # Check if we have valid credentials
        if self._credentials and self._credentials.valid:
            return self._credentials

        # Try to refresh expired credentials
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_token()
                return self._credentials
            except Exception:
                # Refresh failed, need to re-authenticate
                pass

        # No valid credentials, run authorization flow
        self._credentials = self._run_auth_flow()
        self._save_token()
        return self._credentials

    def _run_auth_flow(self) -> Credentials:
        """Run OAuth2 authorization flow with local server callback.

        Returns:
            New OAuth2 credentials.

        Raises:
            FileNotFoundError: If credentials file doesn't exist.
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found: {self.credentials_path}\n"
                "Please download OAuth client credentials from Google Cloud Console:\n"
                "1. Go to https://console.cloud.google.com/\n"
                "2. Create or select a project\n"
                "3. Enable the Gmail API\n"
                "4. Create OAuth 2.0 Client ID (Desktop application)\n"
                "5. Download the credentials JSON file\n"
                f"6. Save it as: {self.credentials_path}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            self.SCOPES,
        )

        # Run local server to receive OAuth callback
        credentials = flow.run_local_server(
            port=0,  # Use any available port
            prompt="consent",
            success_message="Authentication successful! You can close this window.",
        )

        return credentials

    def _load_token(self) -> Optional[Credentials]:
        """Load saved token from file.

        Returns:
            Credentials if token file exists and is valid, None otherwise.
        """
        try:
            with open(self.token_path, "r") as f:
                token_data = json.load(f)

            return Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
            )
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None

    def _save_token(self) -> None:
        """Save credentials token to file."""
        if not self._credentials:
            return

        # Ensure parent directory exists
        self.token_path.parent.mkdir(parents=True, exist_ok=True)

        token_data = {
            "token": self._credentials.token,
            "refresh_token": self._credentials.refresh_token,
            "token_uri": self._credentials.token_uri,
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "scopes": self._credentials.scopes,
        }

        with open(self.token_path, "w") as f:
            json.dump(token_data, f, indent=2)

    @property
    def access_token(self) -> str:
        """Get the current access token.

        Returns:
            The access token string.

        Raises:
            ValueError: If no valid credentials are available.
        """
        if not self._credentials or not self._credentials.token:
            raise ValueError("No valid credentials available. Call get_credentials() first.")
        return self._credentials.token
