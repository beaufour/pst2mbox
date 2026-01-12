"""Command-line interface for pst2gmail - import PST to Gmail via IMAP."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

from pst2mbox.backends.base import PSTBackend
from pst2mbox.backends.readpst_backend import ReadPSTBackend
from pst2mbox.progress import ImportProgress
from pst2mbox.uploaders import GmailUploader

console = Console()

# Default paths for OAuth files
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "pst2mbox"
DEFAULT_CREDENTIALS_PATH = DEFAULT_CONFIG_DIR / "gmail_credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "gmail_token.json"
DEFAULT_PROGRESS_PATH = DEFAULT_CONFIG_DIR / "import_progress.json"

# Local credentials file (in current directory)
LOCAL_CREDENTIALS_PATH = Path("gmail_credentials.json")


def find_credentials_path() -> Path:
    """Find credentials file, checking local directory first.

    Returns:
        Path to credentials file (local if exists, otherwise default config path).
    """
    if LOCAL_CREDENTIALS_PATH.exists():
        return LOCAL_CREDENTIALS_PATH
    return DEFAULT_CREDENTIALS_PATH


@click.command()
@click.argument("pst_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-e",
    "--email",
    required=True,
    help="Gmail address to import to",
)
@click.option(
    "--credentials",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to OAuth credentials JSON (default: ./gmail_credentials.json or ~/.config/pst2mbox/gmail_credentials.json)",
)
@click.option(
    "--label-prefix",
    type=str,
    default=None,
    help="Prefix for Gmail labels (default: PST-Import-YYYY-MM-DD)",
)
@click.option(
    "--folder",
    "filter_folder",
    type=str,
    help="Only import messages from this folder (e.g., 'Inbox' or 'Inbox/Work')",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview import without uploading",
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume a previously interrupted import",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-upload, ignore previous progress",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Save progress after this many messages (default: 100)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--show-errors",
    is_flag=True,
    help="Show error details for failed messages",
)
@click.version_option(version="0.1.0", prog_name="pst2gmail")
def main(
    pst_file: Path,
    email: str,
    credentials: Optional[Path],
    label_prefix: Optional[str],
    filter_folder: Optional[str],
    dry_run: bool,
    resume: bool,
    force: bool,
    batch_size: int,
    verbose: bool,
    show_errors: bool,
) -> None:
    """Import Microsoft Outlook PST files to Gmail via IMAP.

    PST_FILE is the path to the PST file to import.

    Before using this command, you need to set up OAuth credentials:

    \b
    1. Go to https://console.cloud.google.com/
    2. Create or select a project
    3. Enable the Gmail API
    4. Create OAuth 2.0 Client ID (Desktop application)
    5. Download the credentials JSON file
    6. Save as ./gmail_credentials.json (in current dir) or
       ~/.config/pst2mbox/gmail_credentials.json

    Examples:

    \b
        # Import entire PST to Gmail
        pst2gmail archive.pst -e user@gmail.com

    \b
        # Import with custom label prefix
        pst2gmail archive.pst -e user@gmail.com --label-prefix "Old Mail/Outlook"

    \b
        # Import only Inbox folder
        pst2gmail archive.pst -e user@gmail.com --folder Inbox

    \b
        # Resume interrupted import
        pst2gmail archive.pst -e user@gmail.com --resume
    """
    # Initialize progress tracker (declared here so it's in scope for exception handlers)
    progress: Optional[ImportProgress] = None

    # Resolve credentials path (check local first if not explicitly provided)
    if credentials is None:
        credentials = find_credentials_path()

    try:
        # Display header
        console.print("\n[bold]PST to Gmail Importer[/bold]")
        console.print(f"Input PST:  {pst_file}")
        console.print(f"Gmail:      {email}")
        if label_prefix:
            console.print(f"Label:      {label_prefix}")
        if filter_folder:
            console.print(f"Folder:     {filter_folder}")
        console.print()

        if dry_run:
            console.print("[yellow]Dry run mode - no messages will be uploaded[/yellow]\n")

        # Handle progress/resume
        if resume and not force:
            progress = ImportProgress.load(DEFAULT_PROGRESS_PATH)
            if progress:
                if progress.is_compatible(pst_file, email):
                    console.print(
                        f"[green]✓[/green] Resuming previous import "
                        f"({progress.total_uploaded} messages already uploaded)"
                    )
                    # Use the same label prefix from previous run
                    if progress.label_prefix:
                        label_prefix = progress.label_prefix
                else:
                    console.print(
                        "[yellow]Previous progress not compatible with current import[/yellow]"
                    )
                    progress = None

        # Create new progress tracker if not resuming
        if not progress:
            progress = ImportProgress(
                pst_file=pst_file,
                email=email,
                label_prefix=label_prefix,
            )

        # Open PST file
        with console.status("[bold green]Opening PST file..."):
            backend: PSTBackend = ReadPSTBackend(pst_file)
            backend.open()

        # Get folder information
        folders = backend.get_folders()
        console.print(f"[green]✓[/green] Found {len(folders)} folder(s)")

        if verbose:
            console.print("\n[bold]Folders:[/bold]")
            for folder in folders:
                console.print(f"  • {folder.path} ({folder.message_count} messages)")
            console.print()

        # Filter to specific folder if requested
        target_folder = None
        if filter_folder:
            target_folder = next(
                (f for f in folders if f.path == filter_folder), None
            )
            if not target_folder:
                console.print(f"[red]✗[/red] Folder '{filter_folder}' not found")
                console.print("\nAvailable folders:")
                for folder in folders:
                    console.print(f"  • {folder.path}")
                sys.exit(1)

        # Get total message count
        total_messages = backend.get_message_count(target_folder)
        console.print(f"[green]✓[/green] Total messages to import: {total_messages}")

        if total_messages == 0:
            console.print("[yellow]No messages to import[/yellow]")
            backend.close()
            sys.exit(0)

        # Calculate how many are already done
        already_uploaded = len(progress.uploaded_message_ids) if resume else 0
        remaining = total_messages - already_uploaded

        if remaining <= 0:
            console.print("[green]✓[/green] All messages already imported!")
            backend.close()
            sys.exit(0)

        if already_uploaded > 0:
            console.print(f"[green]✓[/green] {already_uploaded} messages already imported, {remaining} remaining")

        # Dry run - validate messages without uploading
        if dry_run:
            console.print()
            seen_ids: set[str] = set()
            duplicates: list[tuple[str, str]] = []  # (subject, message_id)
            valid_count = 0

            with console.status("[bold green]Validating messages..."):
                for msg in backend.iter_messages(target_folder):
                    if msg.message_id in seen_ids:
                        duplicates.append((msg.subject[:60], msg.message_id))
                    else:
                        seen_ids.add(msg.message_id)
                        valid_count += 1

            conversion_errors = backend.get_conversion_errors()

            console.print(f"\n[yellow]Would import {valid_count} messages to Gmail[/yellow]")
            if duplicates:
                console.print(f"[yellow]⚠[/yellow] {len(duplicates)} messages would be skipped (duplicate message ID)")
                if show_errors:
                    for subject, message_id in duplicates:
                        id_str = f" [{message_id}]" if message_id else ""
                        console.print(f"  [dim]•[/dim] {subject}{id_str}")
            if conversion_errors:
                console.print(f"[yellow]⚠[/yellow] {len(conversion_errors)} messages failed to parse from PST")
                if show_errors:
                    for message_id, subject, error in conversion_errors:
                        id_str = f" [{message_id}]" if message_id else ""
                        console.print(f"  [red]•[/red] {subject[:60]}{id_str}: {error}")
            console.print(f"[yellow]Labels would be created under: {label_prefix or 'PST-Import-YYYY-MM-DD'}[/yellow]")
            backend.close()
            sys.exit(0)

        # Connect to Gmail
        console.print()
        with console.status("[bold green]Connecting to Gmail..."):
            uploader = GmailUploader(
                email=email,
                credentials_path=credentials,
                token_path=DEFAULT_TOKEN_PATH,
                label_prefix=label_prefix,
            )
            uploader.connect()

        console.print("[green]✓[/green] Connected to Gmail")

        # Import messages
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress_bar:
            task = progress_bar.add_task(
                "Importing messages...", total=remaining
            )

            messages = backend.iter_messages(target_folder)
            imported_count = 0
            failed_count = 0
            skipped_duplicates = 0
            duplicates: list[tuple[str, str]] = []  # (subject, message_id)
            batch_count = 0

            for message in messages:
                # Skip if already uploaded (either from resume or duplicate message ID)
                if progress.is_uploaded(message.message_id):
                    skipped_duplicates += 1
                    duplicates.append((message.subject[:60], message.message_id))
                    progress_bar.update(task, advance=1)
                    continue

                try:
                    # Update current folder
                    if message.folder_path != progress.current_folder:
                        progress.set_current_folder(message.folder_path)

                    # Upload message
                    result = uploader.upload_message(message)

                    if result:
                        progress.mark_uploaded(message.message_id)
                        imported_count += 1
                    else:
                        # Message was skipped (e.g., too large)
                        progress.mark_failed(message.message_id)
                        failed_count += 1

                except Exception as e:
                    if verbose or show_errors:
                        id_str = f" [{message.message_id}]" if message.message_id else ""
                        console.print(
                            f"\n[red]Failed to upload message: {message.subject[:50]}{id_str}[/red]"
                        )
                        console.print(f"[red]Error: {e}[/red]")
                    progress.mark_failed(message.message_id)
                    failed_count += 1

                progress_bar.update(task, advance=1)
                batch_count += 1

                # Save progress periodically
                if batch_count >= batch_size:
                    progress.save(DEFAULT_PROGRESS_PATH)
                    batch_count = 0

            # Save final progress
            progress.save(DEFAULT_PROGRESS_PATH)

        # Get conversion errors from backend
        conversion_errors = backend.get_conversion_errors()

        # Disconnect
        uploader.disconnect()
        backend.close()

        # Summary
        console.print(f"\n[green]✓[/green] Successfully imported {imported_count} messages")
        if failed_count > 0:
            console.print(f"[yellow]⚠[/yellow] {failed_count} messages failed or skipped during upload")
        if skipped_duplicates > 0:
            console.print(f"[yellow]⚠[/yellow] {skipped_duplicates} messages skipped (duplicate message ID)")
            if show_errors:
                for subject, message_id in duplicates:
                    id_str = f" [{message_id}]" if message_id else ""
                    console.print(f"  [dim]•[/dim] {subject}{id_str}")
        if conversion_errors:
            console.print(f"[yellow]⚠[/yellow] {len(conversion_errors)} messages failed to parse from PST")
            if show_errors:
                for message_id, subject, error in conversion_errors:
                    id_str = f" [{message_id}]" if message_id else ""
                    console.print(f"  [red]•[/red] {subject[:60]}{id_str}: {error}")
        console.print(f"[green]✓[/green] Messages are in Gmail under label: {uploader.label_prefix}")

    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Import interrupted by user[/yellow]")
        console.print("[yellow]Use --resume to continue later[/yellow]")
        # Save progress on interrupt
        if progress:
            progress.save(DEFAULT_PROGRESS_PATH)
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        if verbose:
            console.print_exception()
        # Save progress on error
        if progress:
            progress.save(DEFAULT_PROGRESS_PATH)
        sys.exit(1)


if __name__ == "__main__":
    main()
