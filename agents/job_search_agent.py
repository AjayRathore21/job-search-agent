"""
LangGraph agent implementation with a custom StateGraph.
Provides more control over the workflow and built-in persistence.
"""

import os
import json
from typing import Annotated, TypedDict, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
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


SYSTEM_PROMPT = (
    "You are a sophisticated Job Matcher & Search Agent. "
    "Your current workflow is:"
    "1. FIRST, use read_resume() to understand the user's background. "
    "2. Based on the resume, search for matching jobs using available tools. "
    "3. Save matching jobs (>= 80% match) to Excel using save_jobs_to_excel. "
    "   IMPORTANT: Always pass the current session's `user_id` to this tool. "
    "4. Manage background cron jobs: you can schedule, remove, or list them. "
    "Example: 'Schedule a daily scrape at 9 AM' -> use schedule_cron_job."
    "\nAlways provide a summary of your actions to the user. "
    "If you save to excel, show the user the download link from the tool's response."
)


def create_job_search_agent():
    """Build and return a custom LangGraph StateGraph agent."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("Set OPENROUTER_API_KEY in .env.")

    # Tools available to the agent
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

    # Initialize LLM and bind tools
    llm = ChatOpenAI(
        model=os.environ.get("CURRENT_LLM"),
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    ).bind_tools(tools)

    # Define the core logic nodes
    def call_model(state: AgentState):
        messages = state["messages"]
        user_id = state.get("user_id", "default_user")
        
        # Inject current context (user_id) and system prompt
        context_prompt = f"{SYSTEM_PROMPT}\n\nCURRENT CONTEXT:\n- Current session User ID: {user_id}"
        
        if not any(isinstance(m, HumanMessage) for m in messages) or len(messages) == 1:
            messages = [HumanMessage(content=context_prompt)] + messages
        else:
            # Update system context in case it changed or for visibility
            messages = [HumanMessage(content=context_prompt)] + messages
            
        response = llm.invoke(messages)
        return {"messages": [response]}

    # Define the edge logic (should we call tools or stop?)
    def should_continue(state: AgentState) -> Literal["tools", END]:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    # Initialize the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.add_edge(START, "agent")

    # Add conditional edge from agent to tools/END
    workflow.add_conditional_edges(
        "agent",
        should_continue,
    )

    # Add fixed edge from tools back to agent
    workflow.add_edge("tools", "agent")

    # Add persistence (MemorySaver for now, can swap for Postgres/Sqlite later)
    memory = MemorySaver()

    # Compile the graph
    agent = workflow.compile(checkpointer=memory)

    return agent


# Global instance for the application process
_global_agent = None

async def trigger_agent_stream(query: str, thread_id: str):
    """
    Async generator that streams events from the graph.
    Yields JSON strings for the frontend to consume via SSE.
    """
    global _global_agent
    if not _global_agent:
        _global_agent = create_job_search_agent()

    config = {"configurable": {"thread_id": thread_id}}
    
    # Immediate yield to avoid buffering delay
    yield f'data: {json.dumps({"type": "status", "content": "Initializing Agent..."})}\n\n'
    print(f"📡 [STREAM] Connection established for user '{thread_id}'")

    # We use astream_events to get granular updates

    try:
        async for event in _global_agent.astream_events(
            {
                "messages": [{"role": "user", "content": query}],
                "user_id": thread_id
            },
            config=config,
            version="v2"
        ):
            kind = event["event"]
            
            # 1. Start of a tool call
            if kind == "on_tool_start":
                tool_name = event["name"]
                status_msg = f"Executing tool: {tool_name}..."
                print(f"🛠️  [AGENT] {status_msg}")
                data = json.dumps({"type": "status", "content": status_msg})
                yield f"data: {data}\n\n"
                
            # 2. Start of the agent model call (Thinking state)
            elif kind == "on_chat_model_start":
                print(f"🧠 [AGENT] Thinking...")
                data = json.dumps({"type": "status", "content": "Thinking..."})
                yield f"data: {data}\n\n"

            # 3. Final output from the graph (Payload found in event['data']['output'] for v2)
            elif kind == "on_chain_end" and event["name"] == "LangGraph":
                # Correct nesting for v2: event['data']['output']
                payload = event.get("data", {})
                output = payload.get("output", {})
                messages = output.get("messages", [])
                
                if messages:
                    final_content = messages[-1].content
                    print(f"✅ [AGENT] Finished. Response length: {len(final_content)}")
                    data = json.dumps({"type": "final", "content": final_content})
                    yield f"data: {data}\n\n"


    except Exception as e:
        error_msg = f"Error during streaming: {str(e)}"
        print(f"❌ [AGENT] {error_msg}")
        
        import traceback
        traceback.print_exc() # Print full error to terminal
        
        data = json.dumps({"type": "error", "content": error_msg})
        yield f"data: {data}\n\n"


    yield "data: [DONE]\n\n"


def trigger_agent(query: str, thread_id: str) -> str:
    """Helper function to execute the agent. Re-uses the global instance to maintain persistence memory."""
    global _global_agent
    if not _global_agent:
        _global_agent = create_job_search_agent()
        
    print(f"🚀 [AGENT] Triggering job search agent (sync) for user '{thread_id}'...")
    config = {"configurable": {"thread_id": thread_id}}
    result = _global_agent.invoke(
        {
            "messages": [{"role": "user", "content": query}],
            "user_id": thread_id
        },
        config=config
    )
    
    messages = result.get("messages", [])
    if messages:
        resp = messages[-1].content
        print(f"✅ [AGENT] Done. Response length: {len(resp)} chars.")
        return resp
    return "Error: No response generated by the agent."


