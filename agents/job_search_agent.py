"""
LangGraph agent implementation with a custom StateGraph.
Provides more control over the workflow and built-in persistence.
"""

import os
import json
from datetime import datetime
from typing import Annotated, TypedDict, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, message_to_dict, messages_from_dict
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools.linkedin_tool import search_linkedin_jobs
from tools.excel_tool import save_jobs_to_excel
from tools.ats_tools import search_google_jobs, search_greenhouse_lever_jobs
from tools.resume_tool import read_resume
from tools.scheduler_tool import schedule_cron_job, remove_cron_job, list_cron_jobs


# 1. Define the state of our graph
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    summary: str # Store condensed context here

SYSTEM_PROMPT = (
    "You are a sophisticated Job Matcher & Search Agent. "
    "Your current workflow is:"
    "1. FIRST, use read_resume() to understand the user's background. "
    "2. Based on the resume, search for matching jobs using available tools. "
    "3. Save matching jobs (>= 80% match) to Excel using save_jobs_to_excel. "
    "4. Manage background cron jobs: you can schedule, remove, or list them. "
    "\nMEMORY & CONTEXT:"
    "- Use the provided 'summary' of previous interactions to maintain context. "
    "- You have access to user's previous actions (like roles searched, results deleted, etc). "
    "\nAlways provide a summary of your actions to the user."
)


def create_job_search_agent():
    """Build and return a custom LangGraph StateGraph agent."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("Set OPENROUTER_API_KEY in .env.")

    tools = [
        read_resume,
        search_linkedin_jobs, 
        save_jobs_to_excel, 
        search_google_jobs, 
        search_greenhouse_lever_jobs,
        schedule_cron_job,
        remove_cron_job,
        list_cron_jobs
    ]
    tool_node = ToolNode(tools)

    llm = ChatOpenAI(
        model=os.environ.get("CURRENT_LLM"),
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    ).bind_tools(tools)

    # --- Node: Call Model ---
    def call_model(state: AgentState):
        messages = state["messages"]
        user_id = state.get("user_id", "default_user")
        summary = state.get("summary", "")
        
        # Inject system prompt + summary + user context
        context_prompt = f"{SYSTEM_PROMPT}\n\nCURRENT CONTEXT:\n- User ID: {user_id}"
        if summary:
            context_prompt += f"\n- Summary of previous interactions: {summary}"
        
        # Always place the latest system prompt/context at the start
        model_messages = [HumanMessage(content=context_prompt)] + messages
            
        print(f"🤖 [AGENT] Processing request for {user_id}... (History size: {len(messages)})")
        response = llm.invoke(model_messages)
        return {"messages": [response]}

    # --- Node: Summarize Conversation ---
    def summarize_conversation(state: AgentState):
        """Summarizes history when it gets too long (> 20 messages)."""
        messages = state["messages"]
        existing_summary = state.get("summary", "")
        
        if len(messages) < 20:
            return {}

        print(f"📝 [AGENT] Summarizing long conversation history ({len(messages)} messages)...")
        
        # Draft a new summary including the old one
        summary_prompt = (
            f"Please create a concise summary of the following conversation. "
            f"Focus on important details: user's targeted job roles, resume highlights, and past actions like search results saved or deleted. "
            f"If there is an existing summary, extend it with new key points.\n\n"
            f"Existing Summary: {existing_summary}\n\n"
            f"Conversation to summarize:\n"
        )
        for m in messages:
            summary_prompt += f"{m.type}: {m.content}\n"
            
        summary_resp = llm.invoke([HumanMessage(content=summary_prompt)])
        new_summary = summary_resp.content

        # Delete first 15 messages (keep the last 5 for immediate flow)
        # In LangGraph/add_messages, returning the IDs with a 'delete' tag or just slicing works depending on implementation
        # For simplicity in this graph, we keep the messages as they are but rely on the 'summary' flag for LLM
        return {"summary": new_summary, "messages": messages[-5:]} # Truncate history to last 5

    def should_continue(state: AgentState) -> Literal["tools", "summarize", END]:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        if len(state["messages"]) > 20:
            return "summarize"
        return END

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.add_node("summarize", summarize_conversation)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    workflow.add_edge("summarize", END)

    memory = MemorySaver()
    agent = workflow.compile(checkpointer=memory)
    return agent


# Global instance for the application process
_global_agent = None

from utils.db import get_db

def load_user_context(user_id: str) -> dict:
    """Fetch stored summary and messages for a user from MongoDB."""
    db = get_db()
    data = db["user_memory"].find_one({"user_id": user_id})
    if not data:
        return {"summary": "", "messages": []}
    
    # Convert BSON/Dict back to LangChain message objects
    raw_msgs = data.get("messages", [])
    messages = messages_from_dict(raw_msgs)
    return {
        "summary": data.get("summary", ""),
        "messages": messages
    }

def save_user_context(user_id: str, summary: str, messages: list):
    """Persist summary and messages to MongoDB."""
    db = get_db()
    # Convert LangChain messages to dicts for MongoDB storage
    msg_dicts = [message_to_dict(m) for m in messages]
    
    db["user_memory"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "summary": summary,
                "messages": msg_dicts,
                "updated_at": datetime.now()
            }
        },
        upsert=True
    )

async def trigger_agent_stream(query: str, thread_id: str):
    """
    Refined trigger with MongoDB persistence & summarization.
    """
    global _global_agent
    if not _global_agent:
        _global_agent = create_job_search_agent()

    # 1. Load context from MongoDB
    context = load_user_context(thread_id)
    
    config = {"configurable": {"thread_id": thread_id}}
    
    yield f'data: {json.dumps({"type": "status", "content": "Loading persistent profile..."})}\n\n'
    print(f"📡 [STREAM] Persistent session loaded for '{thread_id}'")

    try:
        final_state = None
        # Start state includes history from DB + new query
        input_state = {
            "messages": context["messages"] + [HumanMessage(content=query)],
            "user_id": thread_id,
            "summary": context["summary"]
        }

        async for event in _global_agent.astream_events(
            input_state,
            config=config,
            version="v2"
        ):
            kind = event["event"]
            
            if kind == "on_tool_start":
                tool_name = event["name"]
                status_msg = f"Executing tool: {tool_name}..."
                print(f"🛠️  [AGENT] {status_msg}")
                yield f"data: {json.dumps({'type': 'status', 'content': status_msg})}\n\n"
                
            elif kind == "on_chat_model_start":
                yield f"data: {json.dumps({'type': 'status', 'content': 'Thinking...'})}\n\n"

            elif kind == "on_chain_end" and event["name"] == "LangGraph":
                final_state = event.get("data", {}).get("output", {})
                messages = final_state.get("messages", [])
                if messages:
                    final_content = messages[-1].content
                    yield f"data: {json.dumps({'type': 'final', 'content': final_content})}\n\n"
        
        # 2. Save UPDATED context back to MongoDB
        if final_state:
            save_user_context(
                thread_id, 
                final_state.get("summary", context["summary"]), 
                final_state.get("messages", [])
            )
            print(f"💾 [STREAM] Saved persistent context for '{thread_id}'")

    except Exception as e:
        error_msg = f"Error during streaming: {str(e)}"
        print(f"❌ [AGENT] {error_msg}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

    yield "data: [DONE]\n\n"


def trigger_agent(query: str, thread_id: str) -> str:
    """Helper function to execute the agent synchronously with MongoDB persistence."""
    global _global_agent
    if not _global_agent:
        _global_agent = create_job_search_agent()
        
    print(f"🚀 [AGENT] Persistent sync trigger for '{thread_id}'...")
    
    context = load_user_context(thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    
    result = _global_agent.invoke(
        {
            "messages": context["messages"] + [HumanMessage(content=query)],
            "user_id": thread_id,
            "summary": context["summary"]
        },
        config=config
    )
    
    save_user_context(
        thread_id,
        result.get("summary", context["summary"]),
        result.get("messages", [])
    )
    
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return "Error: No response generated by the agent."


