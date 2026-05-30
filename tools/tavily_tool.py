from langchain.tools import tool
from tavily import TavilyClient

def create_tavily_search(tavily_client: TavilyClient):
	@tool
	def tavily_search(query: str):
		'''Search information in the Internet to make answer for user query'''
		result = tavily_client.search(query=query, include_answer=True, max_results=5)
		lines = []
		answer = result.get("answer")
		if answer:
			lines.append(f"Summary: {answer}")
			lines.append("")
		for r in result.get("results", []):
			lines.append(f"• {r.get('title', '')}")
			lines.append(f"  {r.get('url', '')}")
		return "\n".join(lines) if lines else str(result)
	return tavily_search