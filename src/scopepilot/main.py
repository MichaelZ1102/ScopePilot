"""ScopePilot CLI - AI Sprint Requirement Analyst for Backend Teams."""

import os
import sys
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .jira_client import JiraClient, JiraConfig, JiraError, JiraAuthError
from .analyzer import AnalysisPipeline
from .ai import AIError
from .report import save_reports
from .codebase_scanner import scan_local_repository, CodebaseScanError

app = typer.Typer(
    name="scopepilot",
    help="ScopePilot - AI Sprint Requirement Analyst for Backend Teams",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def callback():
    """ScopePilot CLI - analyze Jira Sprints with AI-powered backend planning."""


@app.command()
def analyze(
    sprint: str = typer.Argument(..., help="Sprint name or JQL query"),
    jira_url: str = typer.Option(
        None, "--jira-url", "-j", help="Jira instance URL (overrides .env)"
    ),
    jira_email: str = typer.Option(
        None, "--jira-email", "-e", help="Jira account email (overrides .env)"
    ),
    jira_token: str = typer.Option(
        None, "--jira-token", "-t", help="Jira API token (overrides .env)"
    ),
    project: str = typer.Option(
        None, "--project", "-p", help="Jira project key"
    ),
    output_dir: str = typer.Option(
        "reports", "--output", "-o", help="Output directory for reports"
    ),
    language: str = typer.Option(
        "zh-CN", "--lang", "-l", help="Report language: zh-CN or en-US"
    ),
    no_env: bool = typer.Option(
        False, "--no-env", help="Don't load .env file"
    ),
):
    """Analyze a Jira Sprint and generate backend execution plan reports."""
    console.print(Panel.fit(
        f"[bold]ScopePilot[/bold] - Analyzing Sprint: [cyan]{sprint}[/cyan]",
        border_style="blue",
    ))

    if not no_env:
        _load_dotenv()

    # --- Step 1: Jira connection ---
    config = JiraConfig.from_env()
    if jira_url and jira_email and jira_token:
        config = JiraConfig(url=jira_url, email=jira_email, api_token=jira_token)

    if not config:
        console.print("\n[red]❌ Jira credentials not found.[/red]")
        console.print("  Set JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env file or pass --jira-* options.")
        console.print("  Or create a .env file in the project root:")
        console.print("  JIRA_URL=https://your-domain.atlassian.net")
        console.print("  JIRA_EMAIL=you@example.com")
        console.print("  JIRA_API_TOKEN=your-api-token")
        raise typer.Exit(1)

    if project:
        config.project_key = project

    try:
        client = JiraClient(config)
    except JiraAuthError as e:
        console.print(f"\n[red]❌ {e}[/red]")
        raise typer.Exit(1)

    # --- Step 2: Find sprint ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task1 = progress.add_task("[yellow]🔍 Finding sprint...", total=None)
        try:
            sprint_data = client.find_sprint(sprint)
        except JiraError as e:
            progress.stop()
            console.print(f"\n[red]❌ Failed to find sprint: {e}[/red]")
            raise typer.Exit(1)

        if not sprint_data:
            progress.stop()
            console.print(f"\n[red]❌ Sprint '{sprint}' not found in any board.[/red]")
            raise typer.Exit(1)

        sprint_id = sprint_data["id"]
        sprint_name = sprint_data["name"]
        progress.update(task1, completed=True, description=f"[green]✅ Found sprint: {sprint_name}[/green]")

    # --- Step 3: Fetch issues ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task2 = progress.add_task("[yellow]📥 Fetching tickets...", total=None)
        try:
            issues = client.get_sprint_issues(sprint_id)
        except JiraError as e:
            progress.stop()
            console.print(f"\n[red]❌ Failed to fetch tickets: {e}[/red]")
            raise typer.Exit(1)

        progress.update(task2, completed=True, description=f"[green]✅ Fetched {len(issues)} tickets[/green]")

    # --- Step 4: Extract ticket data ---
    tickets_data = [client.extract_ticket_data(issue) for issue in issues]
    client.close()

    console.print(f"\n[bold]📋 Tickets:[/bold]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Key", style="cyan")
    table.add_column("Summary", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="magenta")
    for td in tickets_data:
        table.add_row(
            td["key"],
            td["summary"][:60] + "..." if len(td["summary"]) > 60 else td["summary"],
            td["issue_type"],
            td["status"],
            td["priority"],
        )
    console.print(table)

    # --- Step 5: AI Analysis ---
    try:
        pipeline = AnalysisPipeline()
    except AIError as e:
        console.print(f"\n[red]❌ {e}[/red]")
        console.print("  Create a .env file with one of:")
        console.print("  OPENCODE_API_KEY=your-key")
        console.print("  GROQ_API_KEY=your-key")
        console.print("  OPENAI_API_KEY=your-key")
        raise typer.Exit(1)

    # Only analyze tickets that have content (description or comments)
    content_tickets = [td for td in tickets_data if td.get("description", "").strip() or td.get("comments")]
    empty_tickets = [td for td in tickets_data if not td.get("description", "").strip() and not td.get("comments")]

    console.print(f"\n[bold]🤖 Analyzing {len(content_tickets)}/{len(tickets_data)} tickets with content...[/bold]")
    if empty_tickets:
        console.print(f"  [dim]Skipping {len(empty_tickets)} tickets without description or comments[/dim]")

    if content_tickets:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[yellow]🤖 Running AI analysis...", total=None)
            # Use batch analysis (same path as web backend) for consistency
            try:
                ticket_analyses = pipeline.analyze_tickets_batch(content_tickets)
            except Exception as e:
                console.print(f"\n  [red]⚠️ Batch analysis failed, falling back to per-ticket: {e}[/red]")
                # Fallback: per-ticket analysis
                ticket_analyses = []
                for td in content_tickets:
                    try:
                        analysis = pipeline.analyze_ticket(td)
                        ticket_analyses.append(analysis)
                    except Exception as e2:
                        console.print(f"\n  [red]⚠️ {td['key']} analysis failed: {e2}[/red]")

    # Filter out failed analyses and add empty placeholder for skipped tickets
    ticket_analyses = [ta for ta in ticket_analyses if ta is not None]
    completed = len(ticket_analyses)
    console.print(f"[green]✅ Analyzed {completed} tickets[/green]")

    # --- Step 6: Sprint-level analysis ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task4 = progress.add_task("[yellow]📊 Generating sprint summary...", total=None)
        try:
            sprint_analysis = pipeline.analyze_sprint(sprint_name, ticket_analyses)
        except Exception as e:
            console.print(f"\n[yellow]⚠️ Sprint analysis warning: {e}[/yellow]")
            from .analyzer import SprintAnalysis
            sprint_analysis = SprintAnalysis(
                sprint_name=sprint_name,
                total_tickets=len(ticket_analyses),
                open_questions=[f"Sprint analysis failed: {str(e)}"],
                ticket_analyses=ticket_analyses,
            )
        progress.update(task4, completed=True, description="[green]✅ Sprint summary generated[/green]")

    # --- Step 7: Save reports ---
    console.print(f"\n[bold]📄 Saving reports to {output_dir}/...[/bold]")
    save_reports(sprint_analysis, output_dir, language)

    # Summary
    console.print()
    console.print(Panel.fit(
        "[bold green]✅ Analysis complete![/bold green]\n\n"
        f"📁 Reports saved to [cyan]{output_dir}/[/cyan]\n"
        f"📊 {len(ticket_analyses)} tickets analyzed\n"
        f"🌐 Language: {language}",
        border_style="green",
    ))


@app.command()
def login(
    token: str = typer.Option(None, "--token", "-t", help="ScopePilot SaaS token"),
):
    """Login to ScopePilot SaaS platform."""
    console.print("[yellow]Login feature coming in Phase 1 (Web MVP).[/yellow]")


@app.command()
def scan_local(
    path: str = typer.Argument(..., help="Path to local project directory"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch to scan (default: current)"),
    max_files: int = typer.Option(5000, "--max-files", help="Maximum files to index"),
):
    """Scan a local repository for code impact analysis."""
    from rich.table import Table
    from rich import box as rich_box

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Scanning repository...", total=None)
        try:
            result = scan_local_repository(
                path=path, branch=branch, max_files=max_files,
            )
        except CodebaseScanError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(1)

    # Display results
    console.print(f"\n[bold green]✅ Scan complete![/bold green]")
    console.print(f"   📁 {result['total_files']} files")
    console.print(f"   📄 ~{result['total_lines']} lines of code")
    if result.get("is_git"):
        console.print(f"   🌿 Branch: {result['branch']}")
        console.print(f"   📌 Commit: {result['commit_sha'][:8] if result['commit_sha'] else 'N/A'}")
        console.print(f"   🗂️  Git root: {result['git_root']}")

    # Language breakdown table
    if result.get("language_breakdown"):
        lang_table = Table(
            "Language", "Size", box=rich_box.SIMPLE,
        )
        sorted_langs = sorted(
            result["language_breakdown"].items(),
            key=lambda x: x[1], reverse=True,
        )
        for lang, bytes_count in sorted_langs:
            size_str = f"{bytes_count / 1024:.1f} KB" if bytes_count > 1024 else f"{bytes_count} B"
            lang_table.add_row(lang, size_str)
        console.print(lang_table)

    # Top directories
    dirs = result.get("file_tree", {}).get("dirs", [])
    if dirs:
        console.print(f"\n[bold]📂 Top directories:[/bold]")
        for d in dirs[:15]:
            console.print(f"   📂 {d}")
        if len(dirs) > 15:
            console.print(f"   ... and {len(dirs) - 15} more")

    return result


@app.command()
def version():
    """Show ScopePilot version."""
    from importlib.metadata import version as get_version
    try:
        ver = get_version("scopepilot-cli")
    except Exception:
        ver = "0.1.0"
    console.print(f"ScopePilot CLI [bold]v{ver}[/bold]")


def _load_dotenv():
    """Load .env file from current or parent directories."""
    try:
        from dotenv import load_dotenv
        # Try current directory first, then parent
        for p in [Path.cwd(), Path.cwd().parent]:
            env_path = p / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                console.print(f"  [dim]Loaded config from {env_path}[/dim]")
                return
    except ImportError:
        pass


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
