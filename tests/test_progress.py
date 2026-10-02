from pst2mbox.progress import ImportProgress


def test_progress_requires_same_imap_destination(tmp_path):
    pst_file = tmp_path / "mail.pst"
    pst_file.write_bytes(b"pst")
    progress = ImportProgress(pst_file, "imap.example.com:993:user@example.com")

    assert progress.is_compatible(pst_file, "imap.example.com:993:user@example.com")
    assert not progress.is_compatible(pst_file, "other.example.com:993:user@example.com")
    assert not progress.is_compatible(pst_file, "imap.example.com:993:other@example.com")
