"""Utility functions for converting messages to RFC822 email format."""

import email.encoders
import email.utils
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pst2mbox.models import Attachment, Message


def sanitize_header(value) -> str:
    """Sanitize a header value by removing newline characters.

    Args:
        value: Header value to sanitize (can be str or Header object).

    Returns:
        Sanitized header value with newlines replaced by spaces.
    """
    if not value:
        return ""
    # Convert Header objects to string
    value = str(value)
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def message_to_rfc822(message: Message) -> MIMEMultipart:
    """Convert internal Message to RFC822 EmailMessage.

    Args:
        message: Message to convert.

    Returns:
        MIMEMultipart email message object.
    """
    # Always use MIMEMultipart for consistency
    email_msg = MIMEMultipart()

    # Set headers (sanitize to remove newlines)
    email_msg["Subject"] = sanitize_header(message.subject)
    email_msg["From"] = sanitize_header(message.sender)
    email_msg["To"] = sanitize_header(", ".join(message.recipients))
    email_msg["Date"] = email.utils.format_datetime(message.date)
    email_msg["Message-ID"] = sanitize_header(message.message_id)

    if message.cc:
        email_msg["Cc"] = sanitize_header(", ".join(message.cc))
    if message.bcc:
        email_msg["Bcc"] = sanitize_header(", ".join(message.bcc))
    if message.in_reply_to:
        email_msg["In-Reply-To"] = sanitize_header(message.in_reply_to)
    if message.references:
        email_msg["References"] = sanitize_header(" ".join(message.references))

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
                email_msg[key] = sanitize_header(value)
            except Exception:
                # Skip headers that can't be set
                pass

    # Add body
    text_part = MIMEText(message.body, "plain", "utf-8")
    email_msg.attach(text_part)

    # Add HTML part if present
    if message.html_body:
        html_part = MIMEText(message.html_body, "html", "utf-8")
        email_msg.attach(html_part)

    # Add attachments
    for attachment in message.attachments:
        _add_attachment(email_msg, attachment)

    return email_msg


def message_to_rfc822_stripped(message: Message) -> MIMEMultipart:
    """Convert internal Message to RFC822 EmailMessage without attachments.

    Adds a note to the body listing the stripped attachments.

    Args:
        message: Message to convert.

    Returns:
        MIMEMultipart email message object without attachments.
    """
    # Always use MIMEMultipart for consistency
    email_msg = MIMEMultipart()

    # Set headers (sanitize to remove newlines)
    email_msg["Subject"] = sanitize_header(message.subject)
    email_msg["From"] = sanitize_header(message.sender)
    email_msg["To"] = sanitize_header(", ".join(message.recipients))
    email_msg["Date"] = email.utils.format_datetime(message.date)
    email_msg["Message-ID"] = sanitize_header(message.message_id)

    if message.cc:
        email_msg["Cc"] = sanitize_header(", ".join(message.cc))
    if message.bcc:
        email_msg["Bcc"] = sanitize_header(", ".join(message.bcc))
    if message.in_reply_to:
        email_msg["In-Reply-To"] = sanitize_header(message.in_reply_to)
    if message.references:
        email_msg["References"] = sanitize_header(" ".join(message.references))

    # Add custom headers
    for key, value in message.headers.items():
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
                email_msg[key] = sanitize_header(value)
            except Exception:
                pass

    # Build body with attachment notice
    body = message.body
    if message.attachments:
        attachment_list = "\n".join(
            f"  - {att.filename} ({att.size:,} bytes)"
            for att in message.attachments
        )
        total_size = sum(att.size for att in message.attachments)
        body += (
            f"\n\n---\n"
            f"[{len(message.attachments)} attachment(s) removed due to size limit "
            f"({total_size:,} bytes total):\n{attachment_list}]"
        )

    text_part = MIMEText(body, "plain", "utf-8")
    email_msg.attach(text_part)

    # Add HTML part if present (with attachment notice)
    if message.html_body:
        html_body = message.html_body
        if message.attachments:
            total_size_html = sum(att.size for att in message.attachments)
            html_body += (
                f"<hr><p><em>[{len(message.attachments)} attachment(s) removed "
                f"due to size limit ({total_size_html:,} bytes total)]</em></p>"
            )
        html_part = MIMEText(html_body, "html", "utf-8")
        email_msg.attach(html_part)

    # No attachments added
    return email_msg


def _add_attachment(email_msg: MIMEMultipart, attachment: Attachment) -> None:
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
