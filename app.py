"""
Main FastAPI Backend for Job Search Agent
Includes a chat endpoint that interacts with the LangGraph agent
and implicitly manages the background APScheduler in the same process.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Load environment before anything else
from dotenv import load_dotenv
load_dotenv()

from agents.job_search_agent import trigger_agent, trigger_agent_stream
from tools.scheduler_tool import scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure scheduler is running when the app starts
    if not scheduler.running:
        scheduler.start()
    print("🚀 FastAPI Server and APScheduler Started!")
    yield
    # Safely shutdown the scheduler when the app stops
    print("🛑 Shutting down APScheduler...")
    if scheduler.running:
        scheduler.shutdown(wait=False)

app = FastAPI(title="AI Job Search Agent API", lifespan=lifespan)

# Configure CORS so any frontend (React/Next.js) can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_user_session"

class ChatResponse(BaseModel):
    response: str

from tools.cloudinary_tool import delete_excel_from_cloudinary
from utils.db import get_db
from bson import ObjectId

import asyncio
from fastapi.responses import StreamingResponse

TIMEOUT_SECONDS = 90.0 # 1.5 minutes safety limit

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Standard endpoint with proper cancellation support.
    If it times out, the async task is cancelled, stopping the agent.
    """
    try:
        final_msg = ""
        # We manually consume the stream to get the final response
        # This makes the operation async and CANCELLABLE
        async def get_final_response():
            nonlocal final_msg
            async for chunk in trigger_agent_stream(req.message, req.thread_id):
                if chunk.startswith('data: {"type": "final"'):
                    import json
                    data = json.loads(chunk.replace("data: ", ""))
                    final_msg = data["content"]
            return final_msg

        response = await asyncio.wait_for(get_final_response(), timeout=TIMEOUT_SECONDS)
        
        if not response:
            return {"response": "The agent finished but didn't provide a clear answer. Please try again."}
        return {"response": response}

    except asyncio.TimeoutError:
        print(f"🛑 [CIRCUIT BREAKER] Hard cancellation for user '{req.thread_id}' due to timeout.")
        return {
            "response": "🛑 Timeout: The search was taking too long and has been FORCIBLY STOPPED. Please try a more specific query."
        }
    except Exception as e:
        return {"response": f"An error occurred: {str(e)}"}


@app.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """
    SSE endpoint that streams agent progress with a global timeout safety.
    """
    async def timeout_wrapper():
        try:
            # We wrap the generator to monitor time
            start_time = asyncio.get_event_loop().time()
            async for chunk in trigger_agent_stream(req.message, req.thread_id):
                yield chunk
                
                # Check for global timeout during streaming
                if (asyncio.get_event_loop().time() - start_time) > TIMEOUT_SECONDS:
                    import json
                    error_data = json.dumps({
                        "type": "error", 
                        "content": "Circuit Breaker: Search timed out after 90s. Results may still appear in history later."
                    })
                    yield f"data: {error_data}\n\n"
                    yield "data: [DONE]\n\n"
                    return
        except Exception as e:
            import json
            yield f'data: {{"type": "error", "content": "Server Error: {str(e)}"}}\n\n'
            yield "data: [DONE]\n\n"

    return StreamingResponse(timeout_wrapper(), media_type="text/event-stream")


@app.get("/job-results")
async def get_job_results(user_id: str):
    """Fetch all excel results for a specific user."""
    db = get_db()
    cursor = db["excel_results"].find({"user_id": user_id}).sort("created_at", -1)
    results = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id")) # convert ObjectId to string
        results.append(doc)
    return {"results": results}

@app.delete("/job-results")
async def delete_job_results(record_id: str = None, user_id: str = None):
    """
    Deletes search history.
    - If record_id is provided, deletes that specific entry.
    - If only user_id is provided, deletes ALL entries for that user.
    Cleans up both MongoDB and Cloudinary.
    """
    db = get_db()
    collection = db["excel_results"]
    
    # 1. Identify records to delete
    query = {}
    if record_id:
        query["_id"] = ObjectId(record_id)
    elif user_id:
        query["user_id"] = user_id
    else:
        return {"error": "Provide either record_id or user_id"}, 400

    records = list(collection.find(query))
    if not records:
        return {"message": "No records found to delete", "deleted_count": 0}

    # 2. Delete from Cloudinary first
    deleted_files = 0
    for rec in records:
        public_id = rec.get("public_id")
        if public_id:
            success = delete_excel_from_cloudinary(public_id)
            if success:
                deleted_files += 1

    # 3. Delete from MongoDB
    result = collection.delete_many(query)
    
    return {
        "message": "Cleanup successful",
        "mongodb_count": result.deleted_count,
        "cloudinary_count": deleted_files
    }

@app.get("/health")
async def health_check():

    """Simple check to see if the server and scheduler are running."""
    return {
        "status": "online",
        "scheduler_running": scheduler.running,
        "active_jobs": len(scheduler.get_jobs())
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

