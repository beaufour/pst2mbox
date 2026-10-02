# pst2mbox

Convert Microsoft Outlook PST files to mbox format or restore them directly to an IMAP account.

## Features

- **Two commands:**
  - `pst2mbox` - Convert PST to mbox format for local use or import to other clients
  - `pst2imap` - Restore PST directly to an IMAP account (TLS + password)
- Convert PST files (both ANSI and Unicode formats)
- Multiple output strategies for mbox conversion
- Filter conversion to specific folders
- Progress bars and resumable imports
- Preserve email metadata, attachments, and threading info
- Cross-platform support (macOS, Linux, Windows)

## Installation

### Prerequisites

This tool requires `readpst` (from libpst) to be installed on your system:

**macOS:**
```bash
brew install libpst
```

**Ubuntu/Debian:**
```bash
sudo apt-get install pst-utils
```

**Fedora/RHEL:**
```bash
sudo dnf install libpst
```

**Windows:**
Download from [libpst releases](https://www.five-ten-sg.com/libpst/)

### Install pst2mbox

Using uv (recommended):
```bash
uv pip install pst2mbox
```

Or with pip:
```bash
pip install pst2mbox
```

For development:
```bash
git clone https://github.com/yourusername/pst2mbox.git
cd pst2mbox
uv sync
```

## Commands

### pst2mbox - Convert to mbox

Convert PST files to standard mbox format for importing into Thunderbird, Apple Mail, or other email clients.

#### Basic Conversion

```bash
pst2mbox archive.pst -o archive.mbox
```

#### Output Strategies

**Single file (default)** - All messages in one mbox:
```bash
pst2mbox archive.pst -o archive.mbox
```

**Per folder** - Create one mbox per PST folder:
```bash
pst2mbox archive.pst -o output_dir/ --strategy folder
```

**Flat with headers** - Single mbox with X-Folder headers:
```bash
pst2mbox archive.pst -o archive.mbox --strategy flat
```

#### Filter by Folder

```bash
# Convert only Inbox
pst2mbox archive.pst -o inbox.mbox --folder Inbox

# Convert nested folder
pst2mbox archive.pst -o work.mbox --folder "Inbox/Work"
```

#### Options

```
-o, --output PATH               Output mbox file or directory [required]
--strategy [single|folder|flat] Output organization strategy
--folder TEXT                   Only convert from this folder
-v, --verbose                   Enable verbose output
--dry-run                       Preview without writing files
--version                       Show version
--help                          Show help
```

### pst2imap - Restore to IMAP

Restore PST files directly to any IMAP server over TLS. The password is requested securely and is never stored. Folder paths from the PST are recreated directly in the destination account.

#### Basic Import

```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com
```

#### Import Specific Folder

```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com --folder Inbox
```

#### Resume Interrupted Import

```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com --resume
```

#### Preview Mode

```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com --dry-run
```

#### Options

```
--imap-host TEXT       IMAP server hostname [required]
--imap-port INTEGER    IMAP TLS port (default: 993)
--username TEXT        IMAP account username [required]
--folder TEXT          Only import from this folder
--dry-run              Preview without uploading
--resume               Resume a previously interrupted import
--force                Force re-upload, ignore previous progress
--batch-size INT       Save progress after this many messages (default: 100)
-v, --verbose          Enable verbose output
--version              Show version
--help                 Show help
```

## Architecture

pst2mbox uses a modular architecture:

```
pst2mbox/
   backends/          # PST file readers (readpst)
   converters/        # Output format writers (mbox)
   uploaders/         # Generic IMAP uploader
   models/            # Internal message representation
   cli.py             # pst2mbox command
   cli_imap.py        # pst2imap command
```

### Backend System

The tool uses a pluggable backend system. Currently implemented:

- **ReadPSTBackend**: Uses the battle-tested `readpst` command-line tool

### Output Formats

- **mbox**: Standard Unix mailbox format (via `pst2mbox`)
- **IMAP**: Direct TLS upload with account credentials (via `pst2imap`)

## Development

### Setup

```bash
git clone https://github.com/yourusername/pst2mbox.git
cd pst2mbox
uv sync
```

### Run Tests

```bash
uv run pytest
```

### Type Checking

```bash
uv run mypy src/pst2mbox
```

### Linting

```bash
uv run ruff check src/pst2mbox
```

## Troubleshooting

### "readpst command not found"

Install libpst/pst-utils as described in the Prerequisites section.

### "PST file is corrupted"

Try using Microsoft's built-in PST repair tool (scanpst.exe on Windows) before conversion.

### Large files taking too long

For very large PST files (>10GB):
- Use `--folder` to convert one folder at a time
- Ensure you have sufficient disk space (2-3x the PST size)
- For mbox: use `--strategy folder` to split output
- For IMAP: use `--resume` if interrupted

### Permission errors

Ensure you have read access to the PST file and write access to the output directory.

### IMAP login errors

- Verify the server hostname, TLS port, username, and password (or app password).

## Technical Details

### PST Format Support

- **ANSI PST**: Outlook 97-2002 (max 2GB)
- **Unicode PST**: Outlook 2003+ (up to 50GB)

### Data Preservation

The tool preserves:
- Email subject, sender, recipients (To/Cc/Bcc)
- Date and time
- Message body (plain text and HTML)
- Attachments with proper MIME encoding
- Email headers (Message-ID, In-Reply-To, References)
- Folder hierarchy

### Performance

Typical conversion rates on modern hardware:
- Small PST (<100MB): 1-2 minutes
- Medium PST (1-5GB): 10-30 minutes
- Large PST (10-50GB): 1-3 hours

IMAP imports may be slower if the server applies rate limiting.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI
- Uses [Rich](https://rich.readthedocs.io/) for beautiful terminal output
- Relies on [libpst](https://www.five-ten-sg.com/libpst/) for PST parsing

## See Also

- [readpst](https://linux.die.net/man/1/readpst) - The underlying PST extraction tool
- [mbox format](https://en.wikipedia.org/wiki/Mbox) - Unix mailbox format specification
