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


def review_session(fields: list) -> list:
    """
    Run an interactive terminal review session for all filled fields.

    Args:
        fields: List of fill result dicts (from adapter.fill_form()):
          [
            {
              "field":            <field descriptor dict>,
              "proposed_answer":  <str | None>,
              "confidence":       <float>,
              "source":           <"answers_bank" | "profile" | "llm" | "manual">,
              "requires_review":  <bool>,
              "filled":           <bool>,
            },
            ...
          ]

    Returns:
        List of approved fill result dicts with "final_answer" added:
          Each entry gets: "final_answer": <str>, "action": <"accept"|"reject"|"edit">

    Session flow:
      1. Show a summary table of all fields and their proposed answers.
      2. Prompt: "Batch approve all high-confidence, non-review fields? (y/n)"
         If yes: auto-accept all fields where confidence >= 0.8 and requires_review=False.
      3. For each remaining field (requires_review=True or confidence < 0.8):
         Show a panel with: question, proposed answer, confidence, source, notes.
         Prompt: "(a)ccept / (r)eject / (e)dit"
         Handle the user's choice.
      4. Return the final list with decisions applied.

    TODO: Implement the full review session using Rich.
    """
    console.print(Panel.fit(
        "[bold cyan]Application-Assist — Review Session[/bold cyan]",
        border_style="cyan",
    ))

    if not fields:
        console.print("[yellow]No fields to review.[/yellow]")
        return []

    # --- Show summary table ---
    _render_summary_table(fields)

    # --- TODO: Batch approve prompt ---
    # auto_approvable = [f for f in fields if f["confidence"] >= 0.8 and not f["requires_review"]]
    # if auto_approvable:
    #     batch = Prompt.ask(
    #         f"[green]Batch approve {len(auto_approvable)} high-confidence fields?[/green]",
    #         choices=["y", "n"], default="y"
    #     )

    # --- TODO: Individual review loop ---
    # for field in fields:
    #     if field["requires_review"] or field["confidence"] < 0.8:
    #         _review_single_field(field)

    # Placeholder: return fields unchanged
    console.print("[yellow]Review UI not yet fully implemented — returning all fields as-accepted.[/yellow]")
    for field in fields:
        field["final_answer"] = field.get("proposed_answer", "")
        field["action"] = "accept"

    return fields


def _render_summary_table(fields: list):
    """
    Render a Rich table summarizing all fields and their proposed answers.

    TODO: Build the table with columns:
      # | Field Label | Proposed Answer | Confidence | Source | Review?
    Color code confidence: green (high), yellow (medium), red (low/none).
    Flag requires_review fields with a warning symbol.
    """
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
        confidence = field.get("confidence", 0.0)
        source = field.get("source", "none")
        requires_review = field.get("requires_review", False)

        # Color confidence
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

    Args:
        field: Fill result dict for a single field.

    Returns:
        Updated field dict with "final_answer" and "action" keys set.

    TODO: Implement:
      - Render a Panel with field label, proposed answer, confidence, source, notes
      - Prompt: "(a)ccept / (r)eject / (e)dit [a]"
      - On "a": field["final_answer"] = field["proposed_answer"], field["action"] = "accept"
      - On "r": field["final_answer"] = None, field["action"] = "reject"
      - On "e": prompt for custom answer text, field["action"] = "edit"
    """
    # TODO: Implement single field review
    label = field.get("field", {}).get("label", "Unknown")
    proposed = field.get("proposed_answer", "")

    console.print(Panel(
        f"[bold]Question:[/bold] {label}\n"
        f"[bold]Proposed:[/bold] {proposed or '[dim]no answer[/dim]'}\n"
        f"[bold]Confidence:[/bold] {field.get('confidence', 0.0):.2f}\n"
        f"[bold]Source:[/bold] {field.get('source', 'none')}",
        title="[cyan]Review Field[/cyan]",
        border_style="blue",
    ))

    # TODO: Replace with actual Prompt once review loop is implemented
    field["final_answer"] = proposed
    field["action"] = "accept"
    return field
