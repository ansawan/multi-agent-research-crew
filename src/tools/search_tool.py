import os
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description="The search query to look up on the web.")

class WebSearchTool(BaseTool):
    name: str = "Web Search Tool"
    description: str = (
        "Searches the web for relevant information. "
        "Uses Tavily API if TAVILY_API_KEY is available in environment, otherwise falls back to DuckDuckGo search. "
        "Returns search results with title, snippet, and source URL."
    )
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str) -> str:
        tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
        
        # 1. Try Tavily Search if key is available
        if tavily_key:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=tavily_key)
                response = client.search(query=query, max_results=5)
                results = response.get("results", [])
                if results:
                    output = []
                    for idx, res in enumerate(results, 1):
                        output.append(
                            f"[{idx}] Title: {res.get('title')}\n"
                            f"    URL: {res.get('url')}\n"
                            f"    Snippet: {res.get('content')}\n"
                        )
                    return "\n".join(output)
            except Exception as e:
                # Fallback to DuckDuckGo if Tavily fails
                pass

        # 2. Fallback to DuckDuckGo Search
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query, max_results=6))
            if ddg_results:
                output = []
                for idx, res in enumerate(ddg_results, 1):
                    output.append(
                        f"[{idx}] Title: {res.get('title')}\n"
                        f"    URL: {res.get('href') or res.get('link')}\n"
                        f"    Snippet: {res.get('body') or res.get('snippet')}\n"
                    )
                return "\n".join(output)
            return f"No results found for query: '{query}'."
        except Exception as e:
            return f"Search error for query '{query}': {str(e)}"
