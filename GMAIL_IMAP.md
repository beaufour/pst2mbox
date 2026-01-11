# Gmail IMAP Notes

Technical notes about Gmail's IMAP implementation, discovered while building the pst2gmail importer.

## Label Hierarchy

Gmail uses `/` as the hierarchy delimiter for nested labels. For example:
- `Work/Projects/Alpha` appears as a nested structure in the Gmail UI

### Creating Nested Labels

**Important:** Gmail requires parent labels to exist before creating children.

To create `Parent/Child/Grandchild`, you must:
1. Create `Parent`
2. Create `Parent/Child`
3. Create `Parent/Child/Grandchild`

Creating `Parent/Child/Grandchild` directly will create a flat label with slashes in the name, not a nested hierarchy.

## Python imaplib Quirks

### Mailbox Name Quoting

Python's `imaplib` does **not** automatically quote mailbox names containing spaces. This causes IMAP commands to fail:

```python
# This fails - spaces not quoted
imap.create("Parent/Folder With Spaces")
# Sends: CREATE Parent/Folder With Spaces
# Gmail returns: BAD Could not parse command

# This works - properly quoted
imap.create('"Parent/Folder With Spaces"')
# Sends: CREATE "Parent/Folder With Spaces"
# Gmail returns: OK Success
```

When using `imaplib.IMAP4.create()` or `imaplib.IMAP4.append()`, you must manually quote mailbox names:

```python
def quote_mailbox(mailbox: str) -> str:
    """Quote mailbox name for IMAP commands."""
    escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
```

## Gmail IMAP Limits

- **Message size limit:** 25MB per message (APPENDLIMIT=35651584 bytes reported, but 25MB is practical limit)
- **Rate limiting:** Gmail may throttle requests (returns `[THROTTLED]` in responses)
- **Connection:** Use `imap.gmail.com:993` with SSL

## Authentication

Gmail requires OAuth2 for IMAP access (basic auth is disabled for most accounts).

Use XOAUTH2 SASL mechanism:
```python
auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
imap.authenticate("XOAUTH2", lambda x: auth_string.encode("utf-8"))
```

## References

- [Gmail IMAP documentation](https://developers.google.com/gmail/imap/imap-extensions)
- [RFC 3501 - IMAP4rev1](https://tools.ietf.org/html/rfc3501)
