import sys
import os
import argparse
import datetime
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Ensure src module can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.models import ResearchInput
from src.flow import ResearchCrewFlow

console = Console()

def run_cli():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Research & Report Crew - CLI Runner"
    )
    parser.add_argument(
        "topic",
        type=str,
        nargs="?",
        default="AI chatbots for dental clinics in Pakistan",
        help="Research topic or brief"
    )
    parser.add_argument(
        "--type",
        type=str,
        default="Market research",
        help="Report type: Market research, Competitor analysis, Industry trends, Custom"
    )
    parser.add_argument(
        "--questions",
        type=str,
        default=None,
        help="Optional specific questions to address in the research"
    )
    parser.add_argument(
        "--audience",
        type=str,
        default="Dentists & Clinic Owners in Pakistan",
        help="Target audience for the report"
    )
    parser.add_argument(
        "--depth",
        type=str,
        default="Quick ~2 pages",
        help="Report depth: Quick ~2 pages or Detailed ~5 pages"
    )
    parser.add_argument(
        "--email",
        type=str,
        default="client@example.com",
        help="Delivery email address"
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Start the FastAPI web server instead of running a CLI report"
    )

    args = parser.parse_args()

    if args.server:
        import uvicorn
        console.print(Panel(f"[bold green]Starting FastAPI Server on http://{config.HOST}:{config.PORT}[/bold green]"))
        uvicorn.run("src.api:app", host=config.HOST, port=config.PORT, reload=True)
        return

    # Validate Config
    is_valid, msg = config.validate_config()
    if not is_valid:
        console.print(Panel(f"[bold red]{msg}[/bold red]", title="Configuration Error"))
        sys.exit(1)

    console.print(Panel.fit(
        f"[bold cyan]🤖 MULTI-AGENT RESEARCH & REPORT CREW[/bold cyan]\n"
        f"Topic: [yellow]{args.topic}[/yellow]\n"
        f"Type: {args.type} | Depth: {args.depth}\n"
        f"Audience: {args.audience}\n"
        f"Delivery Email: {args.email}",
        title="Job Initialized"
    ))

    research_input = ResearchInput(
        topic=args.topic,
        report_type=args.type,
        specific_questions=args.questions,
        audience=args.audience,
        depth=args.depth,
        delivery_email=args.email
    )

    flow = ResearchCrewFlow()
    
    try:
        final_markdown, final_html, qa_score, sources = flow.run(research_input)

        # Save output report
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        slug = args.topic.lower().replace(" ", "-")
        slug = "".join([c for c in slug if c.isalnum() or c == '-'])[:40]
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        filepath = os.path.join(reports_dir, f"{today_str}-{slug}.md")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        console.print("\n" + "="*80)
        console.print(Panel(Markdown(final_markdown), title="Final Generated Research Report"))
        console.print(f"\n[bold green]✅ Success! Report saved to {filepath}[/bold green]")
        console.print(f"[bold blue]QA Quality Score: {qa_score}/10 | Verified Sources Count: {len(sources)}[/bold blue]")

    except Exception as e:
        console.print(f"\n[bold red]❌ Execution failed: {str(e)}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    run_cli()
