"""
Persistent background daemon that runs the APScheduler.
This process must be running for the scheduled jobs to trigger.
"""

import time
import logging
from tools.scheduler_tool import scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("scheduler_daemon")

def start_daemon():
    logger.info("Starting Scheduler Daemon...")
    # The scheduler is already started in tools/scheduler_tool.py upon import
    
    try:
        while True:
            # Keep the main thread alive
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping Scheduler Daemon...")
        scheduler.shutdown()

if __name__ == "__main__":
    start_daemon()
