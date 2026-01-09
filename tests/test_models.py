"""Tests for data models."""

from datetime import datetime

from pst2mbox.models import Attachment, Folder, Message


def test_attachment_creation():
    """Test creating an attachment."""
    att = Attachment(
        filename="test.txt",
        content=b"Hello, World!",
        content_type="text/plain",
    )
    assert att.filename == "test.txt"
    assert att.content == b"Hello, World!"
    assert att.size == 13


def test_attachment_auto_size():
    """Test automatic size calculation."""
    att = Attachment(
        filename="test.txt",
        content=b"Test",
    )
    assert att.size == 4


def test_folder_creation():
    """Test creating a folder."""
    folder = Folder(
        name="Inbox",
        path="Inbox",
        message_count=10,
    )
    assert folder.name == "Inbox"
    assert folder.path == "Inbox"
    assert folder.message_count == 10


def test_folder_full_path():
    """Test folder path hierarchy."""
    parent = Folder(name="Inbox", path="Inbox")
    child = Folder(name="Work", path="Inbox/Work", parent=parent)

    assert child.full_path() == "Inbox/Work"


def test_message_creation():
    """Test creating a message."""
    msg = Message(
        subject="Test Subject",
        sender="sender@example.com",
        recipients=["recipient@example.com"],
        date=datetime.now(),
        body="Test body",
        message_id="<test@example.com>",
    )
    assert msg.subject == "Test Subject"
    assert msg.sender == "sender@example.com"
    assert len(msg.recipients) == 1
    assert msg.body == "Test body"


def test_message_with_attachments():
    """Test message with attachments."""
    att1 = Attachment(filename="file1.txt", content=b"content1")
    att2 = Attachment(filename="file2.txt", content=b"content2")

    msg = Message(
        subject="Test",
        sender="sender@example.com",
        recipients=["recipient@example.com"],
        date=datetime.now(),
        body="Test",
        message_id="<test@example.com>",
        attachments=[att1, att2],
    )

    assert msg.has_attachments()
    assert len(msg.attachments) == 2
    assert msg.total_attachment_size() == 16
