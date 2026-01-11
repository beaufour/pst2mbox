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
| `pst2gmail` | Import PST directly to Gmail | Gmail users |

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

## Option B: Import to Gmail (`pst2gmail`)

### One-Time Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Gmail API
3. Create OAuth credentials (Desktop application)
4. Download and save as `gmail_credentials.json`

### Basic Import

```bash
pst2gmail archive.pst -e your-email@gmail.com
```

A browser opens for authorization. Messages import under `PST-Import-YYYY-MM-DD` labels.

### Common Use Cases

**Preview before importing:**
```bash
pst2gmail archive.pst -e user@gmail.com --dry-run
```

**Custom label prefix:**
```bash
pst2gmail archive.pst -e user@gmail.com --label-prefix "Old Mail"
```

**Import only Inbox:**
```bash
pst2gmail archive.pst -e user@gmail.com --folder Inbox
```

**Resume interrupted import:**
```bash
pst2gmail archive.pst -e user@gmail.com --resume
```

---

## Troubleshooting

**"readpst command not found"**
→ Install libpst (see step 1)

**"PST file is corrupted"**
→ Use scanpst.exe (Windows) to repair first

**"Permission denied"**
→ Check file permissions: `chmod +r your-file.pst`

**Gmail OAuth errors**
→ Ensure Gmail API is enabled and credentials are for "Desktop application"

## Next Steps

- Read the full [README.md](README.md) for all features
- See [GMAIL_IMAP.md](GMAIL_IMAP.md) for Gmail technical notes
- Report issues on GitHub

## Need Help?

Open an issue on GitHub with:
- Your OS and Python version
- The command you ran
- Error message (use `--verbose` for details)
