import re
import json
import html
from typing import Tuple, List, Callable, Optional
from crewai import Task, Crew, Process
import markdown
from rich.console import Console

from src.models import ResearchInput, QAResults
from src.agents.crew import (
    get_llms,
    create_researcher_agent,
    create_writer_agent,
    create_qa_agent,
    run_with_retry
)

console = Console()

def markdown_to_styled_html(md_content: str, topic: str) -> str:
    """
    Converts Markdown report to clean, beautifully styled standalone HTML suitable for Gmail and web view.
    """
    body_html = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "nl2br"]
    )
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(topic)} - Research Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            max-width: 850px;
            margin: 0 auto;
            padding: 30px 20px;
            background-color: #f8fafc;
        }}
        .report-container {{
            background: #ffffff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
        }}
        h1 {{
            color: #0f172a;
            font-size: 2rem;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 12px;
            margin-top: 0;
        }}
        h2 {{
            color: #1e293b;
            font-size: 1.4rem;
            margin-top: 28px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
        }}
        h3 {{
            color: #334155;
            font-size: 1.15rem;
        }}
        ul, ol {{
            padding-left: 24px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px 15px;
            border: 1px solid #cbd5e1;
            text-align: left;
        }}
        th {{
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
        blockquote {{
            border-left: 4px solid #3b82f6;
            background-color: #eff6ff;
            margin: 18px 0;
            padding: 12px 20px;
            border-radius: 0 8px 8px 0;
        }}
        code {{
            background-color: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .qa-footer {{
            margin-top: 35px;
            padding: 16px 20px;
            background-color: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            color: #166534;
        }}
        a {{
            color: #2563eb;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="report-container">
        {body_html}
    </div>
</body>
</html>"""
    return html_template

def extract_sources_from_markdown(md_content: str) -> List[str]:
    """
    Extracts source URLs listed in the Sources section or inline markdown links.
    """
    sources = []
    # Match markdown links: [text](http...)
    link_matches = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', md_content)
    for title, url in link_matches:
        if url not in sources:
            sources.append(url)
    
    # Also catch plain URLs
    raw_urls = re.findall(r'https?://[^\s\)]+', md_content)
    for url in raw_urls:
        url_clean = url.rstrip(".,;")
        if url_clean not in sources:
            sources.append(url_clean)
            
    return sources

def parse_qa_response(raw_response: str) -> QAResults:
    """
    Safely parses QA Reviewer text into structured QAResults.
    Handles JSON snippets or text output safely.
    """
    raw_clean = raw_response.strip()
    # Try finding json block
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_clean, re.DOTALL)
    if json_match:
        raw_clean = json_match.group(1)
    
    try:
        data = json.loads(raw_clean)
        score = min(max(float(data.get("score", 0.0)), 0.0), 10.0)
        return QAResults(
            approved=bool(data["approved"]) if "approved" in data else score >= 8.0,
            score=score,
            issues=data.get("issues", []),
            required_fixes=data.get("required_fixes", [])
        )
    except Exception:
        # Fallback parsing heuristics if not strict JSON
        score = 0.0
        score_match = re.search(r'score[:\s]*([0-9]+(?:\.[0-9]+)?)', raw_clean, re.IGNORECASE)
        if score_match:
            try:
                score = min(max(float(score_match.group(1)), 0.0), 10.0)
            except ValueError:
                pass
        
        approved = "approved: true" in raw_clean.lower() or "status: approved" in raw_clean.lower() or score >= 8.0
        
        return QAResults(
            approved=approved,
            score=score,
            issues=["Minor QA feedback extracted from text"] if not approved else [],
            required_fixes=[raw_clean[:200]] if not approved else []
        )

class ResearchCrewFlow:
    """
    Orchestrates the CrewAI Research -> Write -> QA Review -> Revision flow.
    """
    def __init__(self, progress_callback: Optional[Callable[[str, str], None]] = None):
        """
        progress_callback: function(stage, message) to update FastAPI job status or terminal logs
        """
        self.progress_callback = progress_callback

    def notify(self, stage: str, message: str):
        console.print(f"[bold cyan][{stage.upper()}][/bold cyan] {message}")
        if self.progress_callback:
            self.progress_callback(stage, message)

    def run(self, input_data: ResearchInput) -> Tuple[str, str, float, List[str]]:
        """
        Executes the research brief workflow.
        Returns: (final_markdown, final_html, qa_score, sources)
        """
        researcher_llm, writer_llm, qa_llm = get_llms()

        researcher = create_researcher_agent(researcher_llm)
        writer = create_writer_agent(writer_llm)
        qa_reviewer = create_qa_agent(qa_llm)

        # STAGE 1: RESEARCH
        self.notify("researching", f"Starting research for topic: '{input_data.topic}' ({input_data.report_type})")
        
        research_task = Task(
            description=(
                f"Formulate 4-6 search queries and research the topic: '{input_data.topic}'.\n"
                f"Report Type: {input_data.report_type}\n"
                f"Target Audience: {input_data.audience}\n"
                f"Specific Questions to Answer: {input_data.specific_questions or 'N/A'}\n"
                f"Depth: {input_data.depth}\n\n"
                f"REQUIREMENTS:\n"
                f"1. Conduct web searches using Web Search Tool.\n"
                f"2. Read the most relevant URLs using Web Page Reader.\n"
                f"3. Produce comprehensive structured research notes.\n"
                f"4. EVERY fact, metric, quote, or competitor detail MUST include its full source URL."
            ),
            expected_output="Structured research notes with verified facts and source URLs.",
            agent=researcher
        )

        research_crew = Crew(agents=[researcher], tasks=[research_task], process=Process.sequential, verbose=True)
        research_output = run_with_retry(lambda: research_crew.kickoff())
        research_notes = str(research_output)

        self.notify("writing", "Research complete. Drafting initial report...")

        # STAGE 2: WRITING INITIAL DRAFT
        write_task = Task(
            description=(
                f"Turn the following research notes into a publication-ready Markdown research report.\n\n"
                f"Topic: {input_data.topic}\n"
                f"Audience: {input_data.audience}\n"
                f"Depth: {input_data.depth}\n"
                f"Specific Questions: {input_data.specific_questions or 'N/A'}\n\n"
                f"RAW RESEARCH NOTES:\n{research_notes}\n\n"
                f"REQUIRED MARKDOWN STRUCTURE:\n"
                f"# Title\n"
                f"## Executive Summary (Exactly 5 bullet points)\n"
                f"## Key Findings\n"
                f"## Competitor / Market Comparison Table (Include Markdown table if relevant)\n"
                f"## Opportunities & Risks\n"
                f"## Recommendations\n"
                f"## Sources (Numbered list of full URLs used)\n\n"
                f"INLINE CITATIONS:\n"
                f"Use inline citations like [1], [2] throughout the text corresponding to your Sources list.\n"
                f"STRICT RULE: Only use facts explicitly present in the research notes."
            ),
            expected_output="Full structured Markdown research report with inline citations and Sources section.",
            agent=writer
        )

        writer_crew = Crew(agents=[writer], tasks=[write_task], process=Process.sequential, verbose=True)
        draft_output = run_with_retry(lambda: writer_crew.kickoff())
        current_draft = str(draft_output)

        # STAGE 3: QA REVIEW & REVISION LOOP (Max 2 Rounds)
        max_revisions = 2
        round_count = 0
        final_qa = QAResults(approved=True, score=8.5, issues=[], required_fixes=[])

        while round_count <= max_revisions:
            self.notify("reviewing", f"Performing QA fact-check & review (Round {round_count + 1})...")

            qa_task = Task(
                description=(
                    f"Audit the following report draft against the research notes and brief requirements.\n\n"
                    f"USER BRIEF: {input_data.topic} | {input_data.report_type} | Questions: {input_data.specific_questions}\n\n"
                    f"RESEARCH NOTES:\n{research_notes}\n\n"
                    f"REPORT DRAFT:\n{current_draft}\n\n"
                    f"CHECKLIST:\n"
                    f"1. Does every claim/number have an inline citation [1], [2]?\n"
                    f"2. Do citation numbers match valid URLs in Sources?\n"
                    f"3. Are there invented facts or missing sections?\n"
                    f"4. Are specific questions answered?\n\n"
                    f"OUTPUT FORMAT: Return JSON format:\n"
                    f"{{\n"
                    f'  "approved": true or false,\n'
                    f'  "score": float between 0.0 and 10.0,\n'
                    f'  "issues": ["list of issues..."],\n'
                    f'  "required_fixes": ["actionable instructions for writer..."]\n'
                    f"}}\n"
                ),
                expected_output='JSON object with fields "approved", "score", "issues", and "required_fixes".',
                agent=qa_reviewer
            )

            qa_crew = Crew(agents=[qa_reviewer], tasks=[qa_task], process=Process.sequential, verbose=True)
            qa_output = run_with_retry(lambda: qa_crew.kickoff())
            qa_res = parse_qa_response(str(qa_output))
            final_qa = qa_res

            self.notify("reviewing", f"QA Audit Score: {qa_res.score}/10 | Approved: {qa_res.approved}")

            if qa_res.approved or qa_res.score >= 8.0 or round_count >= max_revisions:
                break

            # Send back to writer for revision
            round_count += 1
            self.notify("revising", f"QA rejected draft (Score: {qa_res.score}/10). Initiating Revision Round {round_count}...")

            revision_task = Task(
                description=(
                    f"Revise and improve the report draft based on QA Reviewer feedback.\n\n"
                    f"QA ISSUES IDENTIFIED:\n" + "\n".join(f"- {iss}" for iss in qa_res.issues) + "\n\n"
                    f"REQUIRED FIXES:\n" + "\n".join(f"- {fix}" for fix in qa_res.required_fixes) + "\n\n"
                    f"ORIGINAL DRAFT:\n{current_draft}\n\n"
                    f"RAW RESEARCH NOTES:\n{research_notes}\n\n"
                    f"Provide the complete revised Markdown report incorporating all required fixes."
                ),
                expected_output="Revised full Markdown research report addressing all QA feedback.",
                agent=writer
            )

            revision_crew = Crew(agents=[writer], tasks=[revision_task], process=Process.sequential, verbose=True)
            revised_output = run_with_retry(lambda: revision_crew.kickoff())
            current_draft = str(revised_output)

        # STAGE 4: FINALIZE REPORT & FOOTER
        self.notify("done", "Finalizing report and generating output formats...")

        qa_footer = (
            f"\n\n---\n"
            f"### 📋 QA Review Notes\n"
            f"- **Quality Score:** {final_qa.score}/10\n"
            f"- **Approval Status:** {'Approved ✅' if final_qa.approved else 'Completed with QA feedback ⚠️'}\n"
            f"- **Revision Rounds:** {round_count}\n"
        )
        if final_qa.issues:
            qa_footer += "- **Notes:** " + "; ".join(final_qa.issues) + "\n"

        final_markdown = current_draft + qa_footer
        final_html = markdown_to_styled_html(final_markdown, input_data.topic)
        sources = extract_sources_from_markdown(final_markdown)

        return final_markdown, final_html, final_qa.score, sources
