"""
LangChain agent that uses the LinkedIn scraper tool.
Uses LangGraph's prebuilt ReAct agent for tool-calling.
"""

import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from tools.linkedin_tool import search_linkedin_jobs
from tools.excel_tool import save_jobs_to_excel
from tools.ats_tools import search_google_jobs, search_greenhouse_lever_jobs
from tools.resume_tool import read_resume


SYSTEM_PROMPT = (
    "You are a sophisticated Job Matcher & Search Agent. "
    "Your workflow MUST be:"
    "1. FIRST, use read_resume() to understand the user's background, skills, and experience. "
    "2. Based on the resume, decide on the best keywords for searching jobs. "
    "3. Use search_linkedin_jobs, search_google_jobs, or search_greenhouse_lever_jobs to find listings. "
    "4. For EACH job found, compare its title and company with the resume content. "
    "5. ONLY keep jobs that are at least an 80% match for the user's profile. "
    "6. For each kept job, create a brief 'match_summary' (1 sentence) explaining why it's a good fit. "
    "7. Finally, use save_jobs_to_excel to save ONLY the matching jobs. Include the 'match_summary' field. "
    "\nPresent a summary of how many total jobs you found and how many were a good match."
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

    tools = [
        read_resume,
        search_linkedin_jobs, 
        save_jobs_to_excel, 
        search_google_jobs, 
        search_greenhouse_lever_jobs
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent
