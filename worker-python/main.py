import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json
import requests
from fastapi import FastAPI, Request, BackgroundTasks, File, UploadFile
from dotenv import load_dotenv

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from models import TranscriptRequest
from adk_agent import head_agent
from db import init_db, save_meeting_log
from telemetry import init_telemetry, tracer

load_dotenv()
init_db()

app = FastAPI(title="AsyncPM Enterprise Agent (ADK 2.0 + MCP + Multimodal)")
init_telemetry(app)

session_service = InMemorySessionService()
runner = Runner(
    agent=head_agent,
    app_name="asyncpm_app",
    session_service=session_service
)

# Pipeline 1: Text Transcript Processing
async def run_adk_agent_pipeline(meeting_id: str, transcript: str):
    # Start Root OpenTelemetry Span
    with tracer.start_as_current_span("run_adk_agent_pipeline") as parent_span:
        parent_span.set_attribute("meeting.id", meeting_id)
        print(f"\n⚙️ [AsyncPM Text Pipeline] Processing Meeting ID: {meeting_id}...")

        prompt = f"Meeting ID: {meeting_id}\n\nTranscript:\n{transcript}"

        try:
            with tracer.start_as_current_span("adk_session_creation"):
                try:
                    session = await session_service.create_session(
                        app_name="asyncpm_app",
                        user_id="default_user",
                        session_id=meeting_id
                    )
                except Exception:
                    session = await session_service.get_session(
                        app_name="asyncpm_app",
                        user_id="default_user",
                        session_id=meeting_id
                    )

            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )

            final_response_text = ""
            with tracer.start_as_current_span("gemini_adk_reasoning_stream") as reasoning_span:
                async for event in runner.run_async(
                    user_id="default_user",
                    session_id=session.id,
                    new_message=user_content
                ):
                    if event.is_final_response() and event.content:
                        if hasattr(event.content, "parts") and event.content.parts:
                            final_response_text = "".join([p.text for p in event.content.parts if hasattr(p, "text") and p.text])

                reasoning_span.set_attribute("response.length", len(final_response_text))

            print(f"🎯 [Text Pipeline Execution Complete]:\n{final_response_text}")

            with tracer.start_as_current_span("audit_log_persistence"):
                save_meeting_log(meeting_id, f"Meeting {meeting_id}", "Text Pipeline Completed", [])
                
            print(f"🎉 [Pipeline Finished] Meeting {meeting_id} logged to database.\n")

        except Exception as e:
            parent_span.record_exception(e)
            print(f"❌ [Text Pipeline Error] {str(e)}")


# Pipeline 2: Multimodal Audio File Processing
async def run_audio_agent_pipeline(meeting_id: str, audio_bytes: bytes, mime_type: str):
    # Start Root OpenTelemetry Span
    with tracer.start_as_current_span("run_audio_agent_pipeline") as parent_span:
        parent_span.set_attribute("meeting.id", meeting_id)
        print(f"\n🎙️ [AsyncPM Audio Pipeline] Processing Meeting ID: {meeting_id} ({mime_type})...")

        try:
            with tracer.start_as_current_span("adk_session_creation"):
                session = await session_service.create_session(
                    app_name="asyncpm_app",
                    user_id="default_user",
                    session_id=meeting_id
                )

            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            instruction_part = types.Part.from_text(text=f"Listen to this meeting recording (ID: {meeting_id}). Extract action items, search past memory for duplicates, and execute Jira/Slack tool calls.")

            user_content = types.Content(
                role="user",
                parts=[audio_part, instruction_part]
            )

            with tracer.start_as_current_span("audio_processing"):
                final_text = ""
                async for event in runner.run_async(
                    user_id="default_user",
                    session_id=session.id,
                    new_message=user_content
                ):
                    if event.is_final_response() and event.content:
                        if hasattr(event.content, "parts") and event.content.parts:
                            final_text = "".join([p.text for p in event.content.parts if hasattr(p, "text") and p.text])
                parent_span.set_attribute("response.length", len(final_text))

            print(f"🎯 [Audio Pipeline Execution Complete]:\n{final_text}")

            with tracer.start_as_current_span("audit_log_persistence"):
                save_meeting_log(meeting_id, f"Audio Meeting {meeting_id}", "Audio Pipeline Completed", [])

            print(f"🎉 [Pipeline Finished] Meeting {meeting_id} logged to database.\n")

        except Exception as e:
            parent_span.record_exception(e)
            print(f"❌ [Audio Pipeline Error] {str(e)}")

@app.get("/")
def health_check():
    return {"status": "online", "features": ["ADK 2.0", "MCP Tools", "Memory Search", "HITL Governance", "Multimodal Audio"]}

@app.post("/process-audio")
async def process_audio_endpoint(background_tasks: BackgroundTasks, meeting_id: str = "AUDIO-001", file: UploadFile = File(...)):
    audio_bytes = await file.read()
    mime_type = file.content_type or "audio/mp3"
    background_tasks.add_task(run_audio_agent_pipeline, meeting_id, audio_bytes, mime_type)
    return {
        "status": "accepted",
        "message": f"Audio file '{file.filename}' received and queued for multimodal Gemini processing.",
        "meeting_id": meeting_id
    }

@app.post("/process-transcript")
def process_transcript_endpoint(req: TranscriptRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_adk_agent_pipeline, req.meeting_id, req.transcript)
    return {
        "status": "accepted",
        "message": f"Transcript for '{req.meeting_id}' received and queued for ADK 2.0 processing.",
        "meeting_id": req.meeting_id
    }

@app.post("/approve")
def approve_task_endpoint(summary: str, description: str = "Approved via HITL Slack Gate", issue_type: str = "Task"):
    from mcp_server import create_jira_issue
    # Calls create_jira_issue with approved=True to bypass the HITL gate
    result = create_jira_issue(
        summary=summary,
        description=description,
        issue_type=issue_type,
        priority="High",
        approved=True
    )
    return {
        "status": "approved_and_executed",
        "result": result
    }

@app.post("/")
@app.post("/slack/interactive")
async def slack_interactive_endpoint(request: Request):
    """Handles button clicks from Slack Interactive Cards."""
    form_data = await request.form()
    payload_str = form_data.get("payload")
    
    if not payload_str:
        return {"status": "no_payload"}

    payload = json.loads(payload_str)
    actions = payload.get("actions", [])
    response_url = payload.get("response_url")

    if actions:
        action_val = actions[0].get("value", "")
        
        if action_val.startswith("approve_"):
            task_summary = action_val.replace("approve_", "")
            print(f"\n✅ [SLACK INTERACTIVE BUTTON CLICKED] PM approved: '{task_summary}'")
            
            from mcp_server import execute_approved_jira_creation
            jira_result = execute_approved_jira_creation(
                summary=task_summary,
                description="Approved by PM via Slack Interactive Button",
                issue_type="Task"
            )
            
            if response_url:
                requests.post(response_url, json={
                    "replace_original": "true",
                    "text": f"✅ *APPROVED & CREATED:* '{task_summary}'\n*Jira Status:* {jira_result}"
                })

        elif action_val.startswith("dismiss_"):
            task_summary = action_val.replace("dismiss_", "")
            print(f"\n❌ [SLACK INTERACTIVE BUTTON CLICKED] PM dismissed: '{task_summary}'")
            
            if response_url:
                requests.post(response_url, json={
                    "replace_original": "true",
                    "text": f"❌ *DISMISSED:* Task '{task_summary}' was dismissed by PM."
                })

    return {"status": "ok"}

@app.post("/check-deadlines")
def trigger_deadline_check():
    from mcp_server import check_approaching_deadlines
    result = check_approaching_deadlines(days_threshold=2)
    return {"status": "success", "result": result}

@app.post("/generate-release-notes")
def trigger_release_notes(sprint_name: str = "Sprint 1"):
    from mcp_server import generate_release_notes
    result = generate_release_notes(sprint_name=sprint_name)
    return {"status": "success", "result": result}

@app.post("/slack/command")
async def slack_slash_command_endpoint(request: Request, background_tasks: BackgroundTasks):
    """Handles /asyncpm Slash Command directly from Slack."""
    form_data = await request.form()
    user_text = form_data.get("text", "")
    user_name = form_data.get("user_name", "Slack User")
    
    if not user_text:
        return {
            "response_type": "ephemeral",
            "text": "⚠️ *Please provide a transcript after `/asyncpm`.*\n*Example:* `/asyncpm Dave: Sarah, please update the SSL certificate. Priority is High.`"
        }

    # Safe timestamp ID generation
    timestamp_id = int(datetime.now().timestamp())
    meeting_id = f"SLACK-CMD-{timestamp_id}"
    background_tasks.add_task(run_adk_agent_pipeline, meeting_id, user_text)
    
    return {
        "response_type": "in_channel",
        "text": f"🤖 *AsyncPM Agent Triggered by @{user_name}!*\n> _{user_text}_\n\n*Status:* Ingesting transcript and running ADK 2.0 multi-agent pipeline..."
    }