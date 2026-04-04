"""
🕒 Scheduler Service
Standalone process to handle background cron jobs for the AI Job Search Agent.
This service connects to the shared MongoDBJobStore and executes agents on schedule.
"""

import os
import time
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pymongo import MongoClient

# Import the agent logic
from agents.job_search_agent import trigger_agent
from utils.db import get_mongodb_uri

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SchedulerService")

# Load environment variables
load_dotenv()

def run_job_execution(query: str, user_id: str):
    """The function that runs when a cron job is triggered."""
    logger.info(f"🔔 [CRON] Triggering scheduled search for user '{user_id}': '{query}'")
    try:
        response = trigger_agent(query, user_id)
        logger.info(f"✅ [CRON] Completed. Summary: {response[:100]}...")
    except Exception as e:
        logger.error(f"❌ [CRON] Failed for user '{user_id}': {str(e)}")

def start_scheduler():
    """Initialize and start the background scheduler."""
    
    uri = get_mongodb_uri()
    client = MongoClient(uri)
    
    # Get the default database name from the URI
    db_name = client.get_default_database().name
    logger.info(f"💾 Connecting to MongoDB JobStore: {db_name}")

    jobstores = {
        'default': MongoDBJobStore(database=db_name, collection='scheduled_jobs', client=client)
    }

    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start()
    
    logger.info("🕒 Scheduler Service is ONLINE and monitoring MongoDB...")
    
    try:
        # Keep the process alive
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Scheduler Service is shutting down...")
        scheduler.shutdown()

if __name__ == "__main__":
    start_scheduler()
