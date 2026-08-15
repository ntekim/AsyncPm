import os
from fastapi import FastAPI, BackgroundTasks
from dotenv import load_dotenv
from google import genai
from google.genai import types

from models import TranscriptRequest, TranscriptAnalysis
from tools import create_jira_ticket, send_slack_notification
from db import init_db, save_meeting_log

load_dotenv()
init_db()

app = FastAPI(title="AsyncPM Intelligence Worker")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("⚠️ WARNING: GEMINI_API_KEY environment variable is missing! Export it in your shell.")

# Initialize Google GenAI client
client = genai.Client(api_key=api_key) if api_key else None

def run_agent_pipeline(meeting_id: str, transcript: str):
    if not client:
        print("❌ Cannot execute agent pipeline: GEMINI_API_KEY is not configured.")
        return

    print(f"\n⚙️ [AsyncPM Agent] Processing Meeting ID: {meeting_id}...")

    prompt = f"""
    You are AsyncPM, an autonomous Product Manager agent.
    Analyze the following meeting transcript. Extract:
    1. A concise meeting title
    2. An executive summary (2-3 sentences)
    3. Actionable tasks that should become engineering/product tickets.

    Transcript:
    {transcript}
    """

    try:
        # Call Gemini Flash with Structured Schema Enforcement
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TranscriptAnalysis,
                temperature=0.2,
            )
        )

        # Validate structured JSON using Pydantic
        analysis = TranscriptAnalysis.model_validate_json(response.text)
        print(f"🎯 [Extraction Complete] Title: '{analysis.meeting_title}' | Tasks Extracted: {len(analysis.action_items)}")

        # Execute Tools (Jira Ticket Creation)
        created_tickets = []
        for item in analysis.action_items:
            ticket = create_jira_ticket(
                summary=item.summary,
                description=f"{item.description}\n\n*Assignee Hint:* {item.assignee_hint or 'Unassigned'}",
                issue_type=item.issue_type,
                priority=item.priority
            )
            ticket["summary"] = item.summary
            created_tickets.append(ticket)

        # Execute Tools (Slack Summary)
        send_slack_notification(analysis.meeting_title, analysis.executive_summary, created_tickets)

        # Save Persistent Audit Log
        save_meeting_log(meeting_id, analysis.meeting_title, analysis.executive_summary, created_tickets)
        print(f"🎉 [Pipeline Finished] Meeting {meeting_id} successfully logged to local database.\n")

    except Exception as e:
        print(f"❌ [Pipeline Error] {str(e)}")

@app.get("/")
def health_check():
    return {"status": "online", "agent": "AsyncPM Worker"}

@app.post("/process-transcript")
def process_transcript_endpoint(req: TranscriptRequest, background_tasks: BackgroundTasks):
    # Respond immediately (<50ms) to caller, processing agent logic in background
    background_tasks.add_task(run_agent_pipeline, req.meeting_id, req.transcript)
    return {
        "status": "accepted",
        "message": f"Transcript for '{req.meeting_id}' received and queued for processing.",
        "meeting_id": req.meeting_id
    }