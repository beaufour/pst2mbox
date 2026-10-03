from pst2mbox.cli_imap import progress_description


def test_progress_description_shows_folder_and_counts():
    assert progress_description("Inbox/Work", 5, 2, 1) == (
        "Folder: Inbox/Work | uploaded: 5 | skipped: 2 | failed: 1"
    )
