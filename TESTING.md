# Testing Summary

## Test Results - pst2mbox v0.1.0

Date: 2026-01-08

### Test Environment
- OS: macOS (Darwin 25.2.0)
- Python: 3.13.0
- readpst: v0.6.76
- Sample PST: Outlook.pst (3.2MB, 11 messages)

### Tests Performed

#### 1. Basic Installation ✓
```bash
uv sync
uv run pst2mbox --help
```
**Result:** Successfully installed and CLI help displays correctly.

#### 2. Sample Data Acquisition ✓
- Downloaded sample PST files from Aspose GitHub repositories
- Files contain real email data structure (Inbox, Sent Items, etc.)
- Total: 11 messages across 3 folders

#### 3. Single File Conversion ✓
```bash
uv run pst2mbox test_data/outlook.pst -o test_data/outlook.mbox --verbose
```
**Result:**
- Successfully converted 11 messages
- Output: 920KB mbox file
- All messages properly formatted with From_ envelope
- Both plain text and HTML parts preserved
- MIME attachments encoded correctly

#### 4. Folder Strategy Conversion ✓
```bash
uv run pst2mbox test_data/outlook.pst -o test_data/folder_output/ --strategy folder
```
**Result:**
- Created separate mbox files per folder
- Outlook_Inbox_mbox.mbox: 6 messages (462KB)
- Outlook_Sent_Items_mbox.mbox: 5 messages (457KB)
- Total: 11 messages correctly split

#### 5. Folder Filtering ✓
```bash
uv run pst2mbox test_data/outlook.pst -o test_data/inbox_only.mbox --folder "Outlook/Inbox"
```
**Result:**
- Successfully filtered to Inbox only
- Converted exactly 6 messages as expected
- Output: 462KB mbox file

### Issues Found and Fixed

#### Issue 1: readpst Output Format Misunderstanding
- **Problem:** Initially used `-M` flag thinking it meant mbox format
- **Reality:** `-M` creates MH format (individual RFC822 files)
- **Solution:** Use default readpst output (no `-M` flag) which creates proper mbox files

#### Issue 2: mbox File Detection
- **Problem:** Looking for `*.mbox` files but readpst creates files named just "mbox"
- **Solution:** Updated to look for files specifically named "mbox"

#### Issue 3: Folder Path Calculation
- **Problem:** Inconsistent path calculation between folder building and message iteration
- **Solution:** Unified logic to use parent directory path consistently

#### Issue 4: readpst Exit Code Handling
- **Problem:** readpst returns non-zero exit code for Calendar items but still extracts emails
- **Solution:** Don't fail on non-zero exit code, check for output files instead

#### Issue 5: Console Error Output
- **Problem:** Rich Console.print() doesn't support `err=True` parameter
- **Solution:** Removed `err=True` from all console.print() calls

### Verification

#### Message Count Verification
```bash
grep -c "^From " test_data/outlook.mbox
# Output: 11 ✓
```

#### Message Integrity Check
- From_ envelope lines present
- MIME boundaries intact
- Headers preserved
- Body content (plain and HTML) present
- Attachments encoded (Base64)

### Performance

- **Small PST (3.2MB, 11 messages):** < 1 second
- **Extraction:** Near-instant with readpst backend
- **Progress bar:** Works correctly for real-time feedback

### Known Limitations

1. **readpst dependency:** Must be installed separately
2. **Calendar/Contact items:** Not converted (email-only focus)
3. **PST corruption:** Tool doesn't repair corrupt PST files

### Next Steps

1. Add pypff backend for pure Python PST reading
2. Add more comprehensive tests with larger PST files
3. Test with ANSI format PST files (pre-Outlook 2003)
4. Add Maildir output format support
5. Implement resume/checkpoint functionality

### Test Files Location

- Sample PST: `test_data/outlook.pst`
- Single output: `test_data/outlook.mbox`
- Folder output: `test_data/folder_output/`
- Filtered output: `test_data/inbox_only.mbox`

### Conclusion

✅ **All core features working correctly**
- Basic PST to mbox conversion
- Multiple output strategies
- Folder filtering
- Progress reporting
- Error handling

The tool is ready for initial release (v0.1.0) with the readpst backend.
