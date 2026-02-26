from __future__ import annotations

from datetime import datetime
from typing import List

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_community.tools import DuckDuckGoSearchRun, WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from pydantic import BaseModel


load_dotenv()


class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: List[str]
    tools_used: List[str]


@tool("save_text_to_file")
def save_to_txt(data: str, filename: str = "research_output.txt") -> str:
    """
    Save a text block to a local .txt file for later reading.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"--- Research Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"

    with open(filename, "a", encoding="utf-8") as file:
        file.write(formatted_text)

    return f"Data successfully saved to {filename}"


search_tool = DuckDuckGoSearchRun()
wiki_tool = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=400)
)

tools = [search_tool, wiki_tool, save_to_txt]

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

system_prompt = """
You are a research assistant that can search the web and summarize results.
Use the available tools (web search, Wikipedia, saving to file) whenever they
help answer the question. Prefer returning concrete links (for example YouTube
URLs) when the user asks for videos or online content.

Always return a structured response that matches the `ResearchResponse` schema.
""".strip()

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
    response_format=ResearchResponse,
)


def run_research_query(query: str) -> str:
    """
    Run a research-style agent query and convert the structured response into
    plain text that we can feed to TTS / show in the chat UI.
    """
    result = agent.invoke({"messages": [HumanMessage(query)]})
    structured = result.get("structured_response")
    if structured is None:
        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return str(result)

    summary = structured.summary
    sources = structured.sources or []
    text = summary
    if sources:
        text += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)
    return text

