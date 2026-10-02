"""``sergio evolve`` — rewrite the user profile from what memory has learned."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markup import escape

console = Console()


@click.command()
@click.option("--force", is_flag=True, help="Run even if nothing new was learned.")
@click.option("--show", is_flag=True, help="Print the resulting profile.")
def evolve(force: bool, show: bool) -> None:
    """Adapt to the user: consolidate learned facts into USER.md."""
    from openjarvis.core.config import load_config
    from openjarvis.unified.evolution import evolve_profile

    result = evolve_profile(load_config(), force=force)
    color = "green" if result.changed else "yellow"
    console.print(f"[{color}]{escape(result.reason)}[/{color}]")
    if result.backup:
        console.print(f"Previous profile saved to {result.backup}")
    if show and result.path and result.path.exists():
        click.echo(result.path.read_text())
