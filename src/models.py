from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class ResearchInput(BaseModel):
    topic: str = Field(..., description="Topic of research brief")
    report_type: str = Field("Market research", description="Type of report: Market research, Competitor analysis, Industry trends, Custom")
    specific_questions: Optional[str] = Field(None, description="Optional specific questions to answer")
    audience: str = Field("Business Executives & Practitioners", description="Target audience for the report")
    depth: str = Field("Quick ~2 pages", description="Depth: Quick ~2 pages or Detailed ~5 pages")
    delivery_email: str = Field(..., description="Email address to deliver the report to")

class QAResults(BaseModel):
    approved: bool = Field(..., description="True if draft passes all checks, False otherwise")
    score: float = Field(..., ge=0.0, le=10.0, description="Quality and accuracy score out of 10")
    issues: List[str] = Field(default_factory=list, description="List of identified issues or missing citations")
    required_fixes: List[str] = Field(default_factory=list, description="Actionable instructions for the Writer to fix draft")

class JobStatusResponse(BaseModel):
    job_id: str
    stage: str
    status: str
    progress: List[str]
    qa_score: Optional[float] = None
    error: Optional[str] = None

class FinalReportResponse(BaseModel):
    job_id: str
    topic: str
    delivery_email: str
    qa_score: Optional[float]
    report_markdown: str
    report_html: str
    sources: List[str]
