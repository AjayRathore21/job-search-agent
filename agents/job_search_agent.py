"""
LangChain agent that uses the LinkedIn scraper tool.
Uses LangGraph's prebuilt ReAct agent for tool-calling.
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from tools.linkedin_tool import search_linkedin_jobs


SYSTEM_PROMPT = (
    "You are a helpful job search assistant. "
    "When the user asks about jobs, use the search_linkedin_jobs tool to find listings. "
    "Present the results clearly with job title and URL."
)


def create_job_search_agent():
    """Build and return the LangGraph ReAct agent."""

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Set the GOOGLE_API_KEY environment variable. "
            "Get one free at https://aistudio.google.com/apikey"
        )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0,
    )

    tools = [search_linkedin_jobs]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent
