import os
import asyncio
from fastapi import FastAPI, BackgroundTasks
from dotenv import load_dotenv

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from models import TranscriptRequest
from adk_agent import dispatcher_agent, asyncpm_mcp_tools
from db import init_db, save_meeting_log

load_dotenv()
init_db()

app = FastAPI(title="AsyncPM Intelligence Worker (ADK 2.0 + MCP)")

# Initialize ADK Session Service & Runner
session_service = InMemorySessionService()
runner = Runner(
    agent=dispatcher_agent,
    app_name="asyncpm_app",
    session_service=session_service
)

async def run_adk_agent_pipeline(meeting_id: str, transcript: str):
    print(f"\n⚙️ [AsyncPM ADK 2.0] Processing Meeting ID: {meeting_id}...")

    prompt = f"Meeting ID: {meeting_id}\n\nTranscript:\n{transcript}"

    try:
        # Create an ADK session for this meeting
        session = await session_service.create_session(
            app_name="asyncpm_app",
            user_id="default_user",
            session_id=meeting_id
        )

        # Wrap text in Google GenAI Content type required by ADK
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        )

        final_response_text = ""

        # Execute agent stream using ADK Runner
        async for event in runner.run_async(
            user_id="default_user",
            session_id=session.id,
            new_message=user_content
        ):
            if event.is_final_response() and event.content:
                if hasattr(event.content, "parts") and event.content.parts:
                    final_response_text = "".join([p.text for p in event.content.parts if hasattr(p, "text") and p.text])

        print(f"🎯 [ADK Agent Execution Complete]:\n{final_response_text}")

        # Save Audit Log
        save_meeting_log(meeting_id, f"Meeting {meeting_id}", "ADK Pipeline Executed Successfully", [])
        print(f"🎉 [Pipeline Finished] Meeting {meeting_id} logged to database.\n")

    except Exception as e:
        print(f"❌ [ADK Pipeline Error] {str(e)}")

@app.get("/")
def health_check():
    return {"status": "online", "framework": "Google ADK 2.0 + MCP"}

@app.post("/process-transcript")
def process_transcript_endpoint(req: TranscriptRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_adk_agent_pipeline, req.meeting_id, req.transcript)
    return {
        "status": "accepted",
        "message": f"Transcript for '{req.meeting_id}' received and queued for ADK 2.0 processing.",
        "meeting_id": req.meeting_id
    }