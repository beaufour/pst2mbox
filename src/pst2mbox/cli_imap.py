"""Command-line interface for restoring PST files to a generic IMAP account."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

from pst2mbox.backends.base import PSTBackend
from pst2mbox.backends.readpst_backend import ReadPSTBackend
from pst2mbox.progress import ImportProgress
from pst2mbox.uploaders import IMAPUploader

console = Console()
DEFAULT_PROGRESS_PATH = Path.home() / ".config" / "pst2mbox" / "imap_import_progress.json"


@click.command()
@click.argument("pst_file", type=click.Path(exists=True, path_type=Path))
@click.option("--imap-host", required=True, help="IMAP server hostname")
@click.option("--imap-port", type=click.IntRange(1, 65535), default=993, show_default=True)
@click.option("--username", required=True, help="IMAP account username")
@click.option("--folder", "filter_folder", help="Only import messages from this PST folder")
@click.option("--dry-run", is_flag=True, help="Preview import without uploading")
@click.option("--resume", is_flag=True, help="Resume a previously interrupted import")
@click.option("--force", is_flag=True, help="Ignore previous progress")
@click.option("--batch-size", type=click.IntRange(1), default=100, show_default=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--show-errors", is_flag=True, help="Show error details for failed messages")
@click.option("--log-file", type=click.Path(path_type=Path), help="Write summary and errors to this file")
def main(
    pst_file: Path,
    imap_host: str,
    imap_port: int,
    username: str,
    filter_folder: Optional[str],
    dry_run: bool,
    resume: bool,
    force: bool,
    batch_size: int,
    verbose: bool,
    show_errors: bool,
    log_file: Optional[Path],
) -> None:
    """Restore PST_FILE directly into an IMAP account over TLS."""
    destination = f"{imap_host}:{imap_port}:{username}"
    progress: Optional[ImportProgress] = None
    uploader: Optional[IMAPUploader] = None
    backend: Optional[PSTBackend] = None
    try:
        console.print("\n[bold]PST to IMAP Restorer[/bold]")
        console.print(f"Input PST:  {pst_file}\nDestination: {destination}\n")
        if resume and not force:
            progress = ImportProgress.load(DEFAULT_PROGRESS_PATH)
            if progress and not progress.is_compatible(pst_file, destination):
                console.print("[yellow]Previous progress is not compatible with this destination[/yellow]")
                progress = None
        if not progress:
            progress = ImportProgress(pst_file=pst_file, destination=destination)

        backend = ReadPSTBackend(pst_file)
        with console.status("[bold green]Opening PST file..."):
            backend.open()
        folders = backend.get_folders()
        target_folder = next((folder for folder in folders if folder.path == filter_folder), None) if filter_folder else None
        if filter_folder and not target_folder:
            raise click.ClickException(f"Folder '{filter_folder}' not found")
        total_messages = backend.get_message_count(target_folder)
        if not total_messages:
            console.print("[yellow]No messages to import[/yellow]")
            return

        if dry_run:
            console.print(f"[yellow]Would import {total_messages} messages to {destination}[/yellow]")
            return

        password = click.prompt("IMAP password", hide_input=True)
        uploader = IMAPUploader(imap_host, imap_port, username, password)
        with console.status("[bold green]Connecting to IMAP server..."):
            uploader.connect()

        imported_count = failed_count = skipped_count = batch_count = 0
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), TimeRemainingColumn(), console=console) as progress_bar:
            task = progress_bar.add_task("Restoring messages...", total=total_messages)
            for message in backend.iter_messages(target_folder):
                if progress.is_uploaded(message.message_id):
                    skipped_count += 1
                else:
                    try:
                        result = uploader.upload_message(message)
                        progress.mark_uploaded(message.message_id)
                        if result == "uploaded":
                            imported_count += 1
                        else:
                            skipped_count += 1
                    except Exception as error:
                        progress.mark_failed(message.message_id)
                        failed_count += 1
                        if verbose or show_errors:
                            console.print(f"[red]Failed: {message.subject[:50]}: {error}[/red]")
                progress_bar.update(task, advance=1)
                batch_count += 1
                if batch_count >= batch_size:
                    progress.save(DEFAULT_PROGRESS_PATH)
                    batch_count = 0
        progress.save(DEFAULT_PROGRESS_PATH)
        console.print(f"[green]✓[/green] Restored {imported_count} messages")
        if skipped_count:
            console.print(f"[yellow]⚠[/yellow] {skipped_count} messages skipped as already present")
        if failed_count:
            console.print(f"[yellow]⚠[/yellow] {failed_count} messages failed")
        if log_file:
            log_file.write_text(
                f"pst2imap Import Log\nDate: {datetime.now().isoformat()}\nPST File: {pst_file}\nDestination: {destination}\nRestored: {imported_count}\nSkipped: {skipped_count}\nFailed: {failed_count}\n"
            )
    except (click.ClickException, FileNotFoundError, RuntimeError) as error:
        raise click.ClickException(str(error)) from error
    except KeyboardInterrupt:
        if progress:
            progress.save(DEFAULT_PROGRESS_PATH)
        raise click.Abort()
    finally:
        if uploader:
            uploader.disconnect()
        if backend:
            backend.close()


if __name__ == "__main__":
    main()
