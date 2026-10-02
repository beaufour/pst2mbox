# Quick Start Guide

Get up and running with pst2mbox in 5 minutes!

## 1. Install Prerequisites

First, install `readpst` (the PST extraction tool):

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

Verify installation:
```bash
readpst -V
```

## 2. Install pst2mbox

**For users:**
```bash
pip install pst2mbox
```

**For development:**
```bash
git clone <your-repo-url>
cd pst2mbox
uv sync
```

## 3. Choose Your Command

This package provides two commands:

| Command | Purpose | Best For |
|---------|---------|----------|
| `pst2mbox` | Convert PST to mbox format | Thunderbird, Apple Mail, archiving |
| `pst2imap` | Restore PST directly to IMAP | IMAP users |

---

## Option A: Convert to mbox (`pst2mbox`)

### Basic Conversion

```bash
pst2mbox your-archive.pst -o output.mbox
```

That's it! Your PST file is now converted to mbox format.

### Common Use Cases

**Preview before converting:**
```bash
pst2mbox archive.pst -o output.mbox --dry-run --verbose
```

**Convert only Inbox:**
```bash
pst2mbox archive.pst -o inbox.mbox --folder Inbox
```

**Split by folders:**
```bash
pst2mbox archive.pst -o output_dir/ --strategy folder
```

### Import mbox into Email Client

**Thunderbird:**
1. Install ImportExportTools NG add-on
2. File → ImportExportTools NG → Import mbox file
3. Select your .mbox file

**Apple Mail:**
1. File → Import Mailboxes
2. Select "Files in mbox format"
3. Choose your .mbox file

---

## Option B: Restore to IMAP (`pst2imap`)

### Basic Import

```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com
```

Enter the account password when prompted. Messages restore into their original PST folder paths.

### Common Use Cases

**Preview before importing:**
```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com --dry-run
```

**Import only Inbox:**
```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com --folder Inbox
```

**Resume interrupted import:**
```bash
pst2imap archive.pst --imap-host imap.example.com --username user@example.com --resume
```

---

## Troubleshooting

**"readpst command not found"**
→ Install libpst (see step 1)

**"PST file is corrupted"**
→ Use scanpst.exe (Windows) to repair first

**"Permission denied"**
→ Check file permissions: `chmod +r your-file.pst`

**IMAP login errors**
→ Check the host, port, username, and password or app password

## Next Steps

- Read the full [README.md](README.md) for all features
- Report issues on GitHub

## Need Help?

Open an issue on GitHub with:
- Your OS and Python version
- The command you ran
- Error message (use `--verbose` for details)
