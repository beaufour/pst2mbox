"""Command-line interface for pst2mbox."""

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
from pst2mbox.converters import MboxWriter, OutputStrategy

console = Console()


@click.command()
@click.argument("pst_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output mbox file or directory",
)
@click.option(
    "--strategy",
    type=click.Choice(["single", "folder", "flat"], case_sensitive=False),
    default="single",
    help="Output organization strategy: single (one mbox), folder (one per folder), or flat (single with X-Folder headers)",
)
@click.option(
    "--folder",
    "filter_folder",
    type=str,
    help="Only convert messages from this folder (e.g., 'Inbox' or 'Inbox/Work')",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview conversion without writing files",
)
@click.option(
    "--show-errors",
    is_flag=True,
    help="Show error details for failed messages",
)
@click.version_option(version="0.1.0", prog_name="pst2mbox")
def main(
    pst_file: Path,
    output: Path,
    strategy: str,
    filter_folder: Optional[str],
    verbose: bool,
    dry_run: bool,
    show_errors: bool,
) -> None:
    """Convert Microsoft Outlook PST files to mbox format.

    PST_FILE is the path to the PST file to convert.

    Examples:

        # Convert entire PST to single mbox file
        pst2mbox archive.pst -o archive.mbox

        # Convert with one mbox per folder
        pst2mbox archive.pst -o output_dir/ --strategy folder

        # Convert only Inbox folder
        pst2mbox archive.pst -o inbox.mbox --folder Inbox
    """
    try:
        # Map strategy string to enum
        strategy_map = {
            "single": OutputStrategy.SINGLE_FILE,
            "folder": OutputStrategy.PER_FOLDER,
            "flat": OutputStrategy.FLAT_WITH_HEADER,
        }
        output_strategy = strategy_map[strategy]

        # Display input info
        console.print("\n[bold]PST to mbox Converter[/bold]")
        console.print(f"Input PST:  {pst_file}")
        console.print(f"Output:     {output}")
        console.print(f"Strategy:   {strategy}")
        if filter_folder:
            console.print(f"Folder:     {filter_folder}")
        console.print()

        if dry_run:
            console.print("[yellow]Dry run mode - no files will be written[/yellow]\n")

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
                console.print(
                    f"[red]✗[/red] Folder '{filter_folder}' not found"
                )
                console.print("\nAvailable folders:")
                for folder in folders:
                    console.print(f"  • {folder.path}")
                sys.exit(1)

        # Get total message count
        total_messages = backend.get_message_count(target_folder)
        console.print(f"[green]✓[/green] Total messages to convert: {total_messages}")

        if total_messages == 0:
            console.print("[yellow]No messages to convert[/yellow]")
            backend.close()
            sys.exit(0)

        # Convert messages
        if not dry_run:
            console.print()
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Converting messages...", total=total_messages
                )

                with MboxWriter(output, output_strategy) as writer:
                    messages = backend.iter_messages(target_folder)
                    count = 0
                    for message in messages:
                        writer._write_message(message)
                        count += 1
                        progress.update(task, advance=1)

            # Get conversion errors
            conversion_errors = backend.get_conversion_errors()

            console.print(f"\n[green]✓[/green] Successfully converted {count} messages")
            if conversion_errors:
                console.print(f"[yellow]⚠[/yellow] {len(conversion_errors)} messages failed to parse from PST")
                if show_errors:
                    for message_id, subject, error in conversion_errors:
                        id_str = f" [{message_id}]" if message_id else ""
                        console.print(f"  [red]•[/red] {subject[:60]}{id_str}: {error}")
            console.print(f"[green]✓[/green] Output written to: {output}")
        else:
            console.print(
                f"\n[yellow]Would convert {total_messages} messages to {output}[/yellow]"
            )

        # Clean up
        backend.close()

    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Conversion interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
