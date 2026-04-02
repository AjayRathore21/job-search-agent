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
    """Placeholder function that the cron job will actually execute."""
    print(f"Executing scheduled task: {task_name} at {datetime.now()}")
    # Here you would typically trigger the specific scraper or agent logic
    # For now, it just logs.

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
