from datetime import datetime

from pst2mbox.models import Message
from pst2mbox.uploaders.imap_uploader import IMAPUploader


class FakeIMAP:
    delimiter = b"."
    received = b"Received: from source.example\r\n"

    def __init__(self, *_args, **_kwargs):
        self.created: list[str] = []
        self.appended: list[str] = []
        self.search_result = b""

    def login(self, _username, _password):
        return "OK", [b"logged in"]

    def list(self, _directory, _pattern):
        return "OK", [b'(\\HasNoChildren) "." ""']

    def create(self, mailbox):
        self.created.append(mailbox)
        return "OK", [b"created"]

    def select(self, _mailbox, readonly=False):
        assert readonly
        return "OK", [b"1"]

    def search(self, _charset, *_criteria):
        return "OK", [self.search_result]

    def fetch(self, _sequence_number, _query):
        return "OK", [(b"1", b"Message-ID: <one@example.com>\r\n" + self.received)]

    def append(self, mailbox, _flags, _date, _message):
        self.appended.append(mailbox)
        return "OK", [b"APPENDUID 1 1"]

    def logout(self):
        return "BYE", [b"logout"]


def message(received="from source.example"):
    return Message(
        subject="test",
        sender="sender@example.com",
        recipients=["recipient@example.com"],
        date=datetime(2025, 1, 1),
        body="body",
        message_id="<one@example.com>",
        folder_path="Inbox/Work",
        headers={"Received": received},
    )


def uploader(monkeypatch):
    monkeypatch.setattr("pst2mbox.uploaders.imap_uploader.imaplib.IMAP4_SSL", FakeIMAP)
    result = IMAPUploader("imap.example.com", 993, "user", "secret")
    result.connect()
    return result


def test_creates_server_hierarchy_and_uploads(monkeypatch):
    result = uploader(monkeypatch)

    assert result.upload_message(message()) == "uploaded"
    assert result._imap.created == ['"Inbox"', '"Inbox.Work"']
    assert result._imap.appended == ['"Inbox.Work"']


def test_skips_exact_message_id_and_received_match(monkeypatch):
    result = uploader(monkeypatch)
    result._imap.search_result = b"1"

    assert result.upload_message(message()) == "duplicate"
    assert not result._imap.appended


def test_does_not_skip_partial_header_match(monkeypatch):
    result = uploader(monkeypatch)
    result._imap.search_result = b"1"
    result._imap.received = b"Received: from another.example\r\n"

    assert result.upload_message(message()) == "uploaded"
    assert result._imap.appended == ['"Inbox.Work"']
