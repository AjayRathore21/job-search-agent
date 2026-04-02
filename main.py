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

from agents.job_search_agent import create_job_search_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Find full stack developer jobs on LinkedIn"

    print(f"\n🔍 Query: {query}\n")

    agent = create_job_search_agent()
    
    # LangGraph with Checkpointer needs a thread_id in the config
    config = {"configurable": {"thread_id": "user_session_1"}}
    
    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config
    )

    print("\n" + "=" * 60)
    print("📋 AGENT RESPONSE:")
    print("=" * 60)

    # Get the last AI message from the response
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        print(last_msg.content)


if __name__ == "__main__":
    main()
