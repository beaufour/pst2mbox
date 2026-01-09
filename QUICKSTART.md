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

## 3. Basic Usage

Convert a PST file:
```bash
pst2mbox your-archive.pst -o output.mbox
```

That's it! Your PST file is now converted to mbox format.

## 4. Common Use Cases

### Preview before converting
```bash
pst2mbox archive.pst -o output.mbox --dry-run --verbose
```

### Convert only Inbox
```bash
pst2mbox archive.pst -o inbox.mbox --folder Inbox
```

### Split by folders
```bash
pst2mbox archive.pst -o output_dir/ --strategy folder
```

## 5. Import into Email Client

### Thunderbird
1. File → ImportExportTools NG → Import mbox file
2. Select your .mbox file
3. Choose destination folder

### Apple Mail
1. File → Import Mailboxes
2. Select "Files in mbox format"
3. Choose your .mbox file

### Gmail
1. Settings → Forwarding and POP/IMAP → Enable IMAP
2. Use Thunderbird or another client to upload to IMAP

## Troubleshooting

**"readpst command not found"**
→ Install libpst (see step 1)

**"PST file is corrupted"**
→ Use scanpst.exe (Windows) to repair first

**"Permission denied"**
→ Check file permissions: `chmod +r your-file.pst`

## Next Steps

- Read the full [README.md](README.md) for all features
- See [PST2MBOX_PLAN.md](PST2MBOX_PLAN.md) for technical details
- Report issues on GitHub

## Need Help?

Open an issue on GitHub with:
- Your OS and Python version
- The command you ran
- Error message (use `--verbose` for details)
