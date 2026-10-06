import time
from crewai import Agent, LLM
from rich.console import Console

from src import config
from src.tools.search_tool import WebSearchTool
from src.tools.reader_tool import PageReaderTool

console = Console()

def get_llms():
    """
    Initializes CrewAI LLM instances for Gemini with appropriate temperatures.
    Raises helpful error if GEMINI_API_KEY is missing.
    """
    is_valid, msg = config.validate_config()
    if not is_valid:
        console.print(f"[bold red]{msg}[/bold red]")
        raise ValueError(msg)

    # Use LiteLLM gemini format e.g. gemini/gemini-2.5-flash
    model = config.MODEL_NAME if config.MODEL_NAME else "gemini/gemini-2.5-flash"
    api_key = config.GEMINI_API_KEY

    researcher_llm = LLM(model=model, api_key=api_key, temperature=0.1)
    writer_llm = LLM(model=model, api_key=api_key, temperature=0.5)
    qa_llm = LLM(model=model, api_key=api_key, temperature=0.1)

    return researcher_llm, writer_llm, qa_llm

def create_researcher_agent(llm: LLM) -> Agent:
    return Agent(
        role="Lead Web & Market Researcher",
        goal="Conduct targeted web searches and read source web pages to compile comprehensive factual notes with exact source URLs.",
        backstory=(
            "You are a meticulous market and technology researcher. "
            "You break down complex research briefs into 4-6 targeted search queries, "
            "search the web, read key pages, and extract detailed facts, stats, and quotes. "
            "CRITICAL: Every single fact or statistic you record MUST have its full source URL attached."
        ),
        tools=[WebSearchTool(), PageReaderTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

def create_writer_agent(llm: LLM) -> Agent:
    return Agent(
        role="Senior Report Writer & Business Strategist",
        goal="Synthesize structured research notes into a highly professional, well-formatted Markdown research report with strict citations.",
        backstory=(
            "You are an executive-level report writer. You craft compelling, clear, and actionable market intelligence reports. "
            "You write in clean Markdown using precise structure: Title, Executive Summary (5 bullet points), Key Findings, "
            "Competitor/Market Comparison Table, Opportunities & Risks, Recommendations, and a numbered Sources section. "
            "CRITICAL: You ONLY use facts present in the research notes. You NEVER invent data or URLs."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

def create_qa_agent(llm: LLM) -> Agent:
    return Agent(
        role="Strict Quality Assurance & Fact-Checking Editor",
        goal="Audit report drafts against raw research notes to verify all facts, numbers, structure, and citations.",
        backstory=(
            "You are an uncompromising editor. You verify that every single claim in the draft has a matching inline citation [1], [2], "
            "that the citation numbers map to real URLs in the Sources list, that no numbers were invented, and that the report "
            "completely answers the user's research brief."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

def run_with_retry(func, max_retries=3, initial_delay=5):
    """
    Executes a function with backoff retry logic for Gemini rate limits or temporary API hiccups.
    """
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "ResourceExhausted" in err_str or "quota" in err_str.lower()
            if attempt < max_retries:
                console.print(
                    f"[bold yellow]⚠️ API warning (Attempt {attempt}/{max_retries}): {err_str[:120]}...\n"
                    f"   Urdu: Gemini API limit ya temporary error aya hai. {delay}s baad dubara try kar rahe hain.\n"
                    f"   English: Retrying in {delay} seconds...[/bold yellow]"
                )
                time.sleep(delay)
                delay *= 2
            else:
                console.print(
                    f"[bold red]❌ Failed after {max_retries} attempts: {err_str}\n"
                    f"   Urdu: Tamam retries nakam ho gayen. Kripya GEMINI_API_KEY aur rate limit check karen.\n"
                    f"   English: All retry attempts failed. Please check your Gemini API key & rate limits.[/bold red]"
                )
                raise e
