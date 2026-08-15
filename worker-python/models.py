from pydantic import BaseModel, Field
from typing import List, Optional

# Schema for Gemini Structured Output
class ActionItem(BaseModel):
    summary: str = Field(description="Short, crisp title for the Jira ticket")
    description: str = Field(description="Detailed context, acceptance criteria, or technical implementation notes")
    issue_type: str = Field(description="Must be one of: 'Task', 'Bug', 'Story'")
    priority: str = Field(description="Must be one of: 'High', 'Medium', 'Low'")
    assignee_hint: Optional[str] = Field(description="Name or team role mentioned for this task, if any")

class TranscriptAnalysis(BaseModel):
    meeting_title: str = Field(description="Extracted or inferred concise title of the meeting")
    executive_summary: str = Field(description="2-3 sentence executive summary of key discussions and decisions")
    action_items: List[ActionItem] = Field(description="List of action items extracted from the transcript")

# HTTP Request Payload for Worker API Endpoint
class TranscriptRequest(BaseModel):
    meeting_id: str
    transcript: str
    source: Optional[str] = "webhook"  # e.g., zoom, google_drive, slack