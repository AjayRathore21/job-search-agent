"""
Entry point — run the LangChain agent to search LinkedIn jobs.

Usage:
    python main.py
    python main.py "backend developer jobs in Bangalore"
"""

import sys
import logging
from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv()

from agents.job_search_agent import trigger_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Find full stack developer jobs on LinkedIn"

    print(f"\n🔍 Query: {query}\n")

    last_msg = trigger_agent(query, "user_session_1")

    print("\n" + "=" * 60)
    print("📋 AGENT RESPONSE:")
    print("=" * 60)
    print(last_msg)


if __name__ == "__main__":
    main()
