import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class ReadPageInput(BaseModel):
    url: str = Field(description="The exact HTTP/HTTPS URL of the web page to read.")

class PageReaderTool(BaseTool):
    name: str = "Web Page Reader"
    description: str = (
        "Fetches a web page URL and extracts clean readable main text content. "
        "Useful for deep reading articles and extracting detailed facts and data."
    )
    args_schema: type[BaseModel] = ReadPageInput

    def _run(self, url: str) -> str:
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            return f"Invalid URL scheme: '{url}'. Must start with http:// or https://"

        # 1. Try Trafilatura for clean text extraction
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_links=True, include_tables=True)
                if text and len(text.strip()) > 100:
                    truncated = text[:5000]
                    if len(text) > 5000:
                        truncated += "\n\n[... Content truncated for length limit ...]"
                    return f"--- Content from {url} ---\n{truncated}"
        except Exception:
            pass

        # 2. Fallback to Requests + BeautifulSoup
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Remove scripts, styles, header, nav, footer
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                element.decompose()

            paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "h1", "h2", "h3", "li"])]
            text_content = "\n".join([p for p in paragraphs if p])
            
            if not text_content:
                text_content = soup.get_text(separator=" ", strip=True)

            truncated = text_content[:5000]
            if len(text_content) > 5000:
                truncated += "\n\n[... Content truncated for length limit ...]"
            return f"--- Content from {url} ---\n{truncated}"
        except Exception as e:
            return f"Failed to read content from URL '{url}': {str(e)}"
