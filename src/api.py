import os
import uuid
import datetime
import re
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from rich.console import Console

from src import config
from src.models import ResearchInput, JobStatusResponse, FinalReportResponse
from src.flow import ResearchCrewFlow

console = Console()

app = FastAPI(
    title="Multi-Agent Research & Report Crew API",
    description="FastAPI service triggering CrewAI Multi-Agent research workflow",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for jobs
jobs: Dict[str, Dict[str, Any]] = {}

def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    api_key_header: str = Header(None, alias="API-Key")
):
    """
    Validates API_KEY header against configuration.
    """
    provided_key = x_api_key or api_key_header
    expected_key = config.API_KEY.strip()

    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Server Misconfigured",
                "message_en": "API_KEY is not set on the server. Add API_KEY to your .env file.",
                "message_ur": "Server par API_KEY set nahi hai. Kripya .env file mein API_KEY add karen."
            }
        )

    if provided_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Unauthorized",
                "message_en": "Invalid or missing API_KEY in header. Pass X-API-Key or API-Key.",
                "message_ur": "Ghalat ya ghair-maujood API_KEY. Kripya header mein X-API-Key bhejain."
            }
        )
    return provided_key

def slugify(text: str) -> str:
    """Creates a clean filename slug from a string."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)

async def execute_crew_job(job_id: str, input_data: ResearchInput):
    """
    Background worker function running the ResearchCrewFlow.
    """
    def update_progress(stage: str, message: str):
        if job_id in jobs:
            jobs[job_id]["stage"] = stage
            jobs[job_id]["progress"].append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}")

    try:
        update_progress("researching", "Job started in background thread.")
        flow = ResearchCrewFlow(progress_callback=update_progress)
        
        # Run Crew flow in thread pool to prevent blocking event loop
        loop = asyncio.get_running_loop()
        final_markdown, final_html, qa_score, sources = await loop.run_in_executor(
            None, flow.run, input_data
        )

        # Save report to /reports/{date}-{slug}.md
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        slug = slugify(input_data.topic)[:40]
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"{today_str}-{slug}.md"
        filepath = os.path.join(reports_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        console.print(f"[bold green]Saved report to {filepath}[/bold green]")

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["stage"] = "done"
        jobs[job_id]["report_markdown"] = final_markdown
        jobs[job_id]["report_html"] = final_html
        jobs[job_id]["qa_score"] = qa_score
        jobs[job_id]["sources"] = sources
        jobs[job_id]["saved_file"] = filepath

        # Trigger n8n Webhook if configured
        webhook_url = config.N8N_DELIVERY_WEBHOOK_URL.strip()
        if webhook_url:
            try:
                update_progress("done", f"Delivering report to n8n webhook: {webhook_url}")
                async with httpx.AsyncClient(timeout=15.0) as client:
                    payload = {
                        "job_id": job_id,
                        "topic": input_data.topic,
                        "report_type": input_data.report_type,
                        "email": input_data.delivery_email,
                        "report_markdown": final_markdown,
                        "report_html": final_html,
                        "qa_score": qa_score,
                        "sources": sources
                    }
                    resp = await client.post(webhook_url, json=payload)
                    console.print(f"[bold green]Posted report to n8n webhook ({resp.status_code})[/bold green]")
                    update_progress("done", f"Report successfully delivered to n8n webhook (Status {resp.status_code}).")
            except Exception as web_err:
                console.print(f"[bold yellow]Webhook post failed: {web_err}[/bold yellow]")
                update_progress("done", f"Warning: Webhook delivery failed: {str(web_err)}")

    except Exception as e:
        console.print(f"[bold red]Job {job_id} failed: {e}[/bold red]")
        if job_id in jobs:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["stage"] = "failed"
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["progress"].append(f"ERROR: {str(e)}")

@app.get("/")
def root():
    return {
        "service": "Multi-Agent Research & Report Crew API",
        "status": "online",
        "docs": "/docs"
    }

@app.post("/research", dependencies=[Depends(verify_api_key)])
async def start_research(input_data: ResearchInput, background_tasks: BackgroundTasks):
    """
    Validates input, starts research crew job in background, returns job_id immediately.
    """
    is_valid, msg = config.validate_config()
    if not is_valid:
        raise HTTPException(status_code=500, detail={"error": "Configuration error", "message": msg})

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "topic": input_data.topic,
        "email": input_data.delivery_email,
        "status": "running",
        "stage": "starting",
        "progress": ["Job registered successfully."],
        "created_at": datetime.datetime.now().isoformat(),
        "report_markdown": None,
        "report_html": None,
        "qa_score": None,
        "sources": [],
        "error": None
    }

    background_tasks.add_task(execute_crew_job, job_id, input_data)

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Research crew triggered for topic '{input_data.topic}'. Check progress at /status/{job_id}"
    }

@app.get("/status/{job_id}", dependencies=[Depends(verify_api_key)])
def get_job_status(job_id: str):
    """
    Returns stage, progress log, status, and qa_score of a research job.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")
    
    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        stage=job["stage"],
        status=job["status"],
        progress=job["progress"],
        qa_score=job.get("qa_score"),
        error=job.get("error")
    )

@app.get("/report/{job_id}", dependencies=[Depends(verify_api_key)])
def get_final_report(job_id: str):
    """
    Returns completed markdown and rendered HTML report.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")

    job = jobs[job_id]
    if job["status"] == "running":
        return JSONResponse(
            status_code=202,
            content={"message": "Report is still generating", "stage": job["stage"], "progress": job["progress"]}
        )
    elif job["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Job failed: {job.get('error')}")

    return FinalReportResponse(
        job_id=job_id,
        topic=job["topic"],
        delivery_email=job["email"],
        qa_score=job.get("qa_score"),
        report_markdown=job["report_markdown"] or "",
        report_html=job["report_html"] or "",
        sources=job.get("sources", [])
    )

@app.get("/report/{job_id}/view", response_class=HTMLResponse)
def view_html_report(job_id: str):
    """
    Renders HTML report directly in browser.
    """
    if job_id not in jobs or not jobs[job_id].get("report_html"):
        raise HTTPException(status_code=404, detail="Report HTML not found or job incomplete.")
    return jobs[job_id]["report_html"]
