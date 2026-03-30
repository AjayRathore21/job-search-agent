"""
LangChain agent that uses the LinkedIn scraper tool.
Uses LangGraph's prebuilt ReAct agent for tool-calling.
"""

import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from tools.linkedin_tool import search_linkedin_jobs
from tools.excel_tool import save_jobs_to_excel


SYSTEM_PROMPT = (
    "You are a helpful job search assistant. "
    "When the user asks about jobs, use the search_linkedin_jobs tool to find listings. "
    "If the user asks to save the results to a file or Excel, use the save_jobs_to_excel tool. "
    "Present the results clearly, and if you saved a file, provide the full absolute path."
)


def create_job_search_agent():
    """Build and return the LangGraph ReAct agent."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Set the OPENROUTER_API_KEY environment variable in .env. "
            "Get one at https://openrouter.ai/"
        )

    llm = ChatOpenAI(
        model="stepfun/step-3.5-flash",
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )

    tools = [search_linkedin_jobs, save_jobs_to_excel]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent
