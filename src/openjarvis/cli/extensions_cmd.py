"""``jarvis extensions`` — manage the bundled OpenClacky agent and 3D globe."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()

_NAMES = click.Choice(["all", "clacky", "globe"])


def _supervisor():
    from openjarvis.core.config import load_config
    from openjarvis.unified.supervisor import Supervisor

    return Supervisor(load_config())


def start_extensions(names: tuple[str, ...] = ("all",)) -> None:
    """Start extensions and print one line per service (used by ``jarvis gui``)."""
    sup = _supervisor()
    for svc in sup.services():
        if "all" in names or svc.name in names:
            console.print(f"[cyan]{svc.title}[/cyan]: {escape(sup.start(svc))}")


def stop_extensions() -> None:
    for name, stopped in _supervisor().stop_all().items():
        if stopped:
            console.print(f"[cyan]{name}[/cyan]: stopped")


@click.group()
def extensions() -> None:
    """Bundled extensions: OpenClacky (computer agent) and the 3D globe."""


@extensions.command("status")
def status() -> None:
    """Show whether each extension is available and running."""
    table = Table("Extension", "State", "URL / problem")
    for row in _supervisor().status():
        if row["running"]:
            state, detail = "[green]running[/green]", row["url"]
        elif row["available"]:
            state, detail = "stopped", row["url"]
        else:
            state, detail = "[yellow]unavailable[/yellow]", escape(row["problem"])
        table.add_row(row["title"], state, detail)
    console.print(table)


@extensions.command("start")
@click.argument("name", type=_NAMES, default="all")
def start(name: str) -> None:
    """Start one extension or all of them in the background."""
    start_extensions((name,))


@extensions.command("stop")
@click.argument("name", type=_NAMES, default="all")
def stop(name: str) -> None:
    """Stop one extension or all of them."""
    if name == "all":
        stop_extensions()
    elif _supervisor().stop(name):
        console.print(f"[cyan]{name}[/cyan]: stopped")
    else:
        console.print(f"{name} was not running")


@extensions.command("logs")
@click.argument("name", type=click.Choice(["clacky", "globe"]))
@click.option("-n", "--lines", default=40, show_default=True)
def logs(name: str, lines: int) -> None:
    """Print the last lines of an extension's log."""
    path = _supervisor().log_file(name)
    if not path.exists():
        raise click.ClickException(f"No log yet at {path}")
    tail = path.read_text(errors="replace").splitlines()[-lines:]
    click.echo("\n".join(tail))
