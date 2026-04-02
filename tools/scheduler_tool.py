"""
Tool for managing background job scheduling (cron jobs).
Uses APScheduler with a SQLite job store for persistence.
"""

import os
import logging
from typing import Optional
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from langchain_core.tools import tool

# Configure logging
logger = logging.getLogger(__name__)

# Define DB path for persistence
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "jobs.sqlite")

# Initialize scheduler
jobstores = {
    'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_PATH}')
}
scheduler = BackgroundScheduler(jobstores=jobstores)

# Start if not already running
if not scheduler.running:
    scheduler.start()

def _dummy_job_func(task_name: str):
    """Function that the cron job executes to trigger the agent."""
    # To avoid circular imports, import the agent creation inside the function
    from agents.job_search_agent import create_job_search_agent
    
    print(f"\n[{datetime.now()}] 🔔 SCHEDULER TRIGGERED: Task '{task_name}' started!")
    print(f"🤖 Booting up the LangGraph Agent to perform the background search...\n")

    try:
        agent = create_job_search_agent()
        # Create an automated system prompt for the task
        query = (
            f"AUTOMATED JOB: The scheduled background task '{task_name}' has been triggered! "
            f"Please execute a quick automated job search on LinkedIn for relevant roles and save to Excel. "
            f"Do not ask the user for clarification. Use your tools immediately to finish the job."
        )
        
        # Give this run a unique thread_id so it doesn't mess with the main user chat conversation
        config = {"configurable": {"thread_id": f"cron_thread_{task_name}"}}
        
        result = agent.invoke(
            {"messages": [{"role": "user", "content": query}]},
            config=config
        )
        
        messages = result.get("messages", [])
        if messages:
            last_msg = messages[-1].content
            print(f"\n[{datetime.now()}] ✅ AGENT FINISHED TASK '{task_name}':\n{last_msg}\n")
            
    except Exception as e:
        print(f"\n[{datetime.now()}] ❌ ERROR IN AGENT EXECUTION for '{task_name}': {e}\n")

@tool
def schedule_cron_job(task_name: str, hour: str, minute: str = "0", description: str = "") -> str:
    """
    Schedule a recurring job.
    
    Args:
        task_name: Unique name for the task (e.g. 'daily_linkedin_scrape')
        hour: Hour in 24h format (0-23)
        minute: Minute (0-59)
        description: Brief description of what this job does
    """
    try:
        # Remove if exists to 'update'
        if scheduler.get_job(task_name):
            scheduler.remove_job(task_name)
            
        scheduler.add_job(
            _dummy_job_func,
            'cron',
            args=[task_name],
            hour=hour,
            minute=minute,
            id=task_name,
            replace_existing=True
        )
        return f"Successfully scheduled '{task_name}' for {hour}:{minute} daily."
    except Exception as e:
        return f"Error scheduling job: {str(e)}"

@tool
def remove_cron_job(task_name: str) -> str:
    """
    Remove an existing scheduled job by its unique task name.
    """
    try:
        if scheduler.get_job(task_name):
            scheduler.remove_job(task_name)
            return f"Successfully removed job '{task_name}'."
        else:
            return f"Job '{task_name}' not found."
    except Exception as e:
        return f"Error removing job: {str(e)}"

@tool
def list_cron_jobs() -> str:
    """
    List all currently scheduled background jobs.
    """
    jobs = scheduler.get_jobs()
    if not jobs:
        return "No active scheduled jobs."
    
    output = "Current Scheduled Jobs:\n"
    for job in jobs:
        output += f"- {job.id}: Next run at {job.next_run_time}\n"
    return output
