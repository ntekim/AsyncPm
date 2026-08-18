import os
import sys
import requests
from fastmcp import FastMCP
from dotenv import load_dotenv

from db import search_past_tickets, save_ticket_memory

load_dotenv()

mcp = FastMCP("AsyncPM Enterprise Tool Server")

# Helper function called EXCLUSIVELY by Slack Button click (Not exposed to Gemini)
def execute_approved_jira_creation(summary: str, description: str, issue_type: str = "Task") -> str:
    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY")

    if not all([jira_domain, jira_email, jira_token, jira_project_key]):
        save_ticket_memory("MOCK-99", summary, "LOCAL")
        return f"MOCK_JIRA_CREATED: {summary} [{issue_type}]"

    url = f"https://{jira_domain}/rest/api/3/issue"
    auth = (jira_email, jira_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "project": {"key": jira_project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            },
            "issuetype": {"name": issue_type}
        }
    }
    
    res = requests.post(url, json=payload, auth=auth, headers=headers)
    if res.status_code == 201:
        key = res.json()["key"]
        save_ticket_memory(key, summary, "LIVE_MEETING")
        print(f"  ✅ [JIRA EXECUTED VIA SLACK APPROVAL] Ticket {key} created!", file=sys.stderr, flush=True)
        return f"SUCCESS: Created Jira Ticket {key} at https://{jira_domain}/browse/{key}"
    return f"ERROR: Failed to create Jira ticket: {res.text}"

@mcp.tool()
def search_existing_tickets(task_description: str) -> str:
    print(f"\n🧠 [MCP MEMORY] Searching past meeting memory for: '{task_description}'", file=sys.stderr, flush=True)
    matches = search_past_tickets(task_description)
    if matches:
        match_info = [f"Ticket {m['ticket_key']}: '{m['summary']}' (from meeting {m['meeting_id']})" for m in matches]
        return f"FOUND_EXISTING_MATCHES: {'; '.join(match_info)}"
    return "NO_DUPLICATES_FOUND: Task is unique."

@mcp.tool()
def update_existing_jira_issue(ticket_key: str, additional_notes: str) -> str:
    print(f"\n🔄 [MCP JIRA] Updating existing ticket {ticket_key} with new notes.", file=sys.stderr, flush=True)
    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_domain, jira_email, jira_token]):
        return f"MOCK_UPDATED: Ticket {ticket_key} updated."

    url = f"https://{jira_domain}/rest/api/3/issue/{ticket_key}/comment"
    auth = (jira_email, jira_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": f"📝 [AsyncPM Update]: {additional_notes}"}]}]
        }
    }
    res = requests.post(url, json=payload, auth=auth, headers=headers)
    return f"SUCCESS: Updated {ticket_key} with comment." if res.status_code == 201 else f"ERROR: {res.text}"

@mcp.tool()
def create_jira_issue(summary: str, description: str, issue_type: str = "Task", priority: str = "Medium") -> str:
    """Tool exposed to Gemini. Creates Low/Medium tickets automatically, but routes High Priority to Slack Buttons."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    # Safeguard for Urgent Keywords
    urgent_keywords = ["URGENT", "CRITICAL", "SECURITY", "ALARM", "EMERGENCY", "FIREWALL"]
    if any(k in summary.upper() or k in description.upper() for k in urgent_keywords):
        priority = "High"

    # Feature 3: Un-bypassable HITL Gate for High Priority Tasks
    if priority.lower() == "high":
        print(f"\n🛡️ [HITL GATE TRIGGERED] High priority task '{summary}' halted for PM approval!", file=sys.stderr, flush=True)

        slack_blocks = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "⚠️ High Priority Task Requires PM Approval", "emoji": True}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Task Summary:*\n{summary}"},
                        {"type": "mrkdwn", "text": f"*Priority:*\n🚨 High ({issue_type})"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Context & Description:*\n{description}"}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve & Create Jira Ticket", "emoji": True},
                            "style": "primary",
                            "value": f"approve_{summary}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Dismiss", "emoji": True},
                            "style": "danger",
                            "value": f"dismiss_{summary}"
                        }
                    ]
                }
            ]
        }

        if webhook_url:
            requests.post(webhook_url, json=slack_blocks)
        
        # Gemini receives this text and stops because it has no tool parameter to force approval!
        return f"HITL_APPROVAL_GATE_HALTED: High priority task '{summary}' sent to Slack for PM approval. Do not attempt creation."

    # Immediate Creation for Medium / Low Priority Tasks
    return execute_approved_jira_creation(summary, description, issue_type)

@mcp.tool()
def send_slack_summary(meeting_title: str, summary: str, created_tickets: str) -> str:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return f"MOCK_SLACK_POSTED: {meeting_title}"

    message = {
        "text": f"🤖 *AsyncPM Report: {meeting_title}*\n\n*Summary:* {summary}\n\n*Action Items:* {created_tickets}"
    }
    res = requests.post(webhook_url, json=message)
    return "SUCCESS: Slack message posted" if res.status_code == 200 else f"ERROR: Slack returned {res.status_code}"
    
if __name__ == "__main__":
    mcp.run()