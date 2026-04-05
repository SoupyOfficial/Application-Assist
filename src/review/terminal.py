"""
terminal.py — Terminal-based review UI for filled form fields.

Uses the Rich library to render a clean, readable review session in the
terminal. For each filled field, the user can:
  - Accept (a): use the proposed answer as-is
  - Reject (r): skip the field (leave blank)
  - Edit (e): type a custom answer

Fields with high confidence and auto_submit=True can be batch-approved.
Fields with requires_review=True are always shown individually.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

console = Console()

AUTO_APPROVE_THRESHOLD = 0.8


def review_session(fields: list) -> list:
    """
    Run an interactive terminal review session for all filled fields.

    Args:
        fields: List of fill result dicts from adapter.fill_form().

    Returns:
        List of approved fill result dicts with "final_answer" and "action" keys added.
    """
    console.print(Panel.fit(
        "[bold cyan]Application-Assist — Review Session[/bold cyan]",
        border_style="cyan",
    ))

    if not fields:
        console.print("[yellow]No fields to review.[/yellow]")
        return []

    # Show summary table
    _render_summary_table(fields)

    # Partition into auto-approvable vs needs-review
    auto_approvable = []
    needs_review = []
    for f in fields:
        if (f.get("confidence", 0) >= AUTO_APPROVE_THRESHOLD
                and not f.get("requires_review", False)
                and f.get("proposed_answer") is not None):
            auto_approvable.append(f)
        else:
            needs_review.append(f)

    # Batch approve prompt
    if auto_approvable:
        batch = Prompt.ask(
            f"\n[green]Batch approve {len(auto_approvable)} high-confidence fields?[/green]",
            choices=["y", "n"],
            default="y",
        )
        if batch == "y":
            for f in auto_approvable:
                f["final_answer"] = f.get("proposed_answer", "")
                f["action"] = "accept"
            console.print(f"[green]✓ {len(auto_approvable)} fields auto-approved.[/green]\n")
        else:
            # Move them to manual review
            needs_review = auto_approvable + needs_review
            auto_approvable = []

    # Individual review loop
    if needs_review:
        console.print(f"[cyan]Reviewing {len(needs_review)} field(s) individually...[/cyan]\n")
        for f in needs_review:
            _review_single_field(f)

    # Render decision summary
    all_fields = auto_approvable + needs_review
    _render_decision_summary(all_fields)

    return all_fields


def _render_summary_table(fields: list):
    """Render a Rich table summarizing all fields and their proposed answers."""
    table = Table(
        title="Fields to Review",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Field", min_width=20)
    table.add_column("Proposed Answer", min_width=25)
    table.add_column("Confidence", justify="center", width=12)
    table.add_column("Source", width=14)
    table.add_column("Review?", justify="center", width=8)

    for i, field in enumerate(fields, 1):
        label = field.get("field", {}).get("label", "Unknown")
        answer = str(field.get("proposed_answer", "")) or "[dim]—[/dim]"
        # Truncate long answers for the table
        if len(answer) > 60:
            answer = answer[:57] + "..."
        confidence = field.get("confidence", 0.0)
        source = field.get("source", "none")
        requires_review = field.get("requires_review", False)

        if confidence >= 0.8:
            conf_str = f"[green]{confidence:.2f}[/green]"
        elif confidence >= 0.5:
            conf_str = f"[yellow]{confidence:.2f}[/yellow]"
        else:
            conf_str = f"[red]{confidence:.2f}[/red]"

        review_str = "[red]YES[/red]" if requires_review else "[green]no[/green]"

        table.add_row(str(i), label, answer, conf_str, source, review_str)

    console.print(table)


def _review_single_field(field: dict) -> dict:
    """
    Show a review panel for a single field and prompt for user action.
    Updates field in-place with "final_answer" and "action" keys.
    """
    label = field.get("field", {}).get("label", "Unknown")
    proposed = field.get("proposed_answer", "")
    notes = field.get("notes", "")

    panel_text = (
        f"[bold]Question:[/bold] {label}\n"
        f"[bold]Proposed:[/bold] {proposed or '[dim]no answer[/dim]'}\n"
        f"[bold]Confidence:[/bold] {field.get('confidence', 0.0):.2f}\n"
        f"[bold]Source:[/bold] {field.get('source', 'none')}"
    )
    if notes:
        panel_text += f"\n[bold]Notes:[/bold] [dim]{notes}[/dim]"

    console.print(Panel(
        panel_text,
        title="[cyan]Review Field[/cyan]",
        border_style="blue",
    ))

    choice = Prompt.ask(
        "[bold](a)[/bold]ccept / [bold](r)[/bold]eject / [bold](e)[/bold]dit",
        choices=["a", "r", "e"],
        default="a",
    )

    if choice == "a":
        field["final_answer"] = proposed
        field["action"] = "accept"
        console.print("[green]  ✓ Accepted[/green]\n")
    elif choice == "r":
        field["final_answer"] = None
        field["action"] = "reject"
        console.print("[red]  ✗ Rejected[/red]\n")
    elif choice == "e":
        custom = Prompt.ask("[bold]Enter your answer[/bold]")
        field["final_answer"] = custom
        field["action"] = "edit"
        console.print("[yellow]  ✎ Edited[/yellow]\n")

    return field


def _render_decision_summary(fields: list):
    """Render a summary of all accept/reject/edit decisions."""
    accepted = sum(1 for f in fields if f.get("action") == "accept")
    rejected = sum(1 for f in fields if f.get("action") == "reject")
    edited = sum(1 for f in fields if f.get("action") == "edit")

    console.print(Panel(
        f"[green]Accepted:[/green] {accepted}  |  "
        f"[red]Rejected:[/red] {rejected}  |  "
        f"[yellow]Edited:[/yellow] {edited}  |  "
        f"[bold]Total:[/bold] {len(fields)}",
        title="[bold cyan]Review Complete[/bold cyan]",
        border_style="cyan",
    ))
