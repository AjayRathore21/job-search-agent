"""
Tool for managing background job scheduling (cron jobs).
Uses APScheduler with MongoDB job store for persistence.
Also stores schedule metadata in the 'scheduled_jobs' collection.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from langchain_core.tools import tool
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

logger = logging.getLogger(__name__)

# ─── MongoDB JobStore Setup ────────────────────────────────────────────────────
_mongo_uri = os.environ.get("MONGODB_URI", "")

# Create a shared MongoClient using the full URI (supports mongodb+srv://)
_mongo_client = MongoClient(_mongo_uri)

# Extract DB name from URI, with a safe fallback
try:
    _db_name = _mongo_client.get_default_database().name
except Exception:
    _db_name = "job_search_agent"          # fallback if not in URI

# Pass the client instance directly — MongoDBJobStore does NOT accept full URIs in 'host'
jobstores = {
    "default": MongoDBJobStore(
        client=_mongo_client,
        database=_db_name,
        collection="apscheduler_jobs",
    )
}

scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")

# NOTE: We do NOT call scheduler.start() here anymore.
# The API workers (app.py) only use this to add/remove jobs from the MongoDB JobStore.
# The actual execution loop is started in the standalone 'scheduler_service.py'.




# ─── Internal: Write / Update scheduled_jobs metadata in MongoDB ───────────────
def _upsert_schedule_record(
    job_id: str,
    user_id: str,
    query: str,
    hour: str,
    minute: str,
    status: str,
    description: str = "",
):
    """Write or update a schedule metadata document in 'scheduled_jobs'."""
    try:
        from utils.db import get_db
        db = get_db()
        db["scheduled_jobs"].update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "job_id":      job_id,
                    "user_id":     user_id,
                    "query":       query,
                    "hour":        hour,
                    "minute":      minute,
                    "description": description,
                    "status":      status,
                    "updated_at":  datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Could not write schedule record to MongoDB: {e}")


def _mark_schedule_status(job_id: str, status: str):
    """Update only the status field on a scheduled_jobs document."""
    try:
        from utils.db import get_db
        db = get_db()
        db["scheduled_jobs"].update_one(
            {"job_id": job_id},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        logger.warning(f"Could not update schedule status: {e}")


# ─── The function APScheduler calls when a job fires ──────────────────────────
def _run_scheduled_job(job_id: str, user_id: str, query: str):
    """Executed by APScheduler at the scheduled time."""
    from agents.job_search_agent import trigger_agent

    logger.info(f"[{datetime.now()}] 🔔 SCHEDULER TRIGGERED: job='{job_id}' user='{user_id}'")
    _mark_schedule_status(job_id, "running")

    try:
        full_query = (
            f"AUTOMATED JOB TRIGGERED for user '{user_id}': {query}. "
            f"Execute a job search immediately using your tools. "
            f"Save matching results to Excel and upload to Cloudinary. "
            f"Do not ask for clarification."
        )
        thread_id = f"cron_{user_id}_{job_id}"
        result = trigger_agent(full_query, thread_id)
        logger.info(f"✅ Scheduled job '{job_id}' completed for user '{user_id}'.")
        _mark_schedule_status(job_id, "completed")
        return result

    except Exception as e:
        logger.error(f"❌ Scheduled job '{job_id}' failed: {e}")
        _mark_schedule_status(job_id, "failed")


# ─── LangChain Tools ──────────────────────────────────────────────────────────

@tool
def schedule_cron_job(
    task_name: str,
    hour: str,
    query: str,
    user_id: str = "default_user",
    minute: str = "0",
    description: str = "",
) -> str:
    """
    Schedule a recurring background job search for a user.

    Args:
        task_name:   Unique name for this job (e.g. 'daily_search').
        hour:        Hour in 24h format (0-23) when the job should run.
        query:       The job search query to run at schedule time.
        user_id:     The user this schedule belongs to.
        minute:      Minute (0-59). Defaults to '0'.
        description: Optional brief description.
    """
    try:
        job_id = f"{user_id}__{task_name}"

        # Remove old job if exists (update scenario)
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            _run_scheduled_job,
            trigger="cron",
            args=[job_id, user_id, query],
            hour=int(hour),
            minute=int(minute),
            id=job_id,
            replace_existing=True,
            name=description or task_name,
        )

        # Persist metadata to MongoDB
        _upsert_schedule_record(
            job_id=job_id,
            user_id=user_id,
            query=query,
            hour=hour,
            minute=minute,
            status="active",
            description=description,
        )

        return (
            f"✅ Scheduled '{task_name}' at {hour}:{minute} UTC daily for user '{user_id}'.\n"
            f"Query: {query}"
        )
    except Exception as e:
        return f"Error scheduling job: {str(e)}"


@tool
def remove_cron_job(task_name: str, user_id: str = "default_user") -> str:
    """
    Remove a scheduled background job.

    Args:
        task_name: The name used when the job was scheduled.
        user_id:   The owner of this job.
    """
    try:
        job_id = f"{user_id}__{task_name}"

        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            _mark_schedule_status(job_id, "removed")
            return f"✅ Removed scheduled job '{task_name}' for user '{user_id}'."
        else:
            return f"⚠️ Job '{task_name}' not found for user '{user_id}'."
    except Exception as e:
        return f"Error removing job: {str(e)}"


@tool
def list_cron_jobs(user_id: str = "default_user") -> str:
    """
    List all active scheduled jobs for a user (reads from MongoDB metadata).

    Args:
        user_id: The user whose jobs to list.
    """
    try:
        from utils.db import get_db
        db = get_db()
        jobs = list(
            db["scheduled_jobs"].find(
                {"user_id": user_id, "status": {"$in": ["active", "running", "completed"]}},
                {"_id": 0}
            )
        )

        if not jobs:
            return f"No active scheduled jobs found for user '{user_id}'."

        output = f"Scheduled Jobs for user '{user_id}':\n"
        for j in jobs:
            output += (
                f"- [{j.get('status','?').upper()}] {j['job_id']} "
                f"| runs at {j.get('hour','?')}:{j.get('minute','0').zfill(2)} UTC "
                f"| query: {j.get('query','')[:60]}...\n"
            )
        return output
    except Exception as e:
        return f"Error listing jobs: {str(e)}"
