import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import datetime
from fastmcp import FastMCP
from dotenv import load_dotenv

from db import search_past_tickets, save_ticket_memory

load_dotenv()

mcp = FastMCP("AsyncPM Enterprise Tool Server")

# Add global account ID cache variable at top
CACHED_OWNER_ACCOUNT_ID = None

def get_slack_webhook(channel_type: str) -> str:
    if channel_type == "governance":
        return os.getenv("SLACK_WEBHOOK_GOVERNANCE") or os.getenv("SLACK_WEBHOOK_URL")
    elif channel_type == "deadlines":
        return os.getenv("SLACK_WEBHOOK_DEADLINES") or os.getenv("SLACK_WEBHOOK_URL")
    elif channel_type == "meetings":
        return os.getenv("SLACK_WEBHOOK_MEETINGS") or os.getenv("SLACK_WEBHOOK_URL")
    return os.getenv("SLACK_WEBHOOK_URL")

def get_jira_owner_account_id() -> str:
    global CACHED_OWNER_ACCOUNT_ID
    if CACHED_OWNER_ACCOUNT_ID:
        return CACHED_OWNER_ACCOUNT_ID

    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_domain, jira_email, jira_token]):
        return None

    url = f"https://{jira_domain}/rest/api/3/myself"
    try:
        res = requests.get(url, auth=(jira_email, jira_token), headers={"Accept": "application/json"}, timeout=3)
        if res.status_code == 200:
            CACHED_OWNER_ACCOUNT_ID = res.json().get("accountId")
            print(f"👤 [JIRA OWNER CACHED] Account ID: {CACHED_OWNER_ACCOUNT_ID}", file=sys.stderr, flush=True)
            return CACHED_OWNER_ACCOUNT_ID
    except Exception as e:
        print(f"⚠️ Could not fetch Jira account ID: {e}", file=sys.stderr, flush=True)
    return None


def execute_approved_jira_creation(summary: str, description: str, issue_type: str = "Task", due_date: str = None) -> str:
    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY")

    if not all([jira_domain, jira_email, jira_token, jira_project_key]):
        save_ticket_memory("MOCK-99", summary, "LOCAL")
        return f"MOCK_JIRA_CREATED: {summary} [{issue_type}]"

    # Default Due Date = Tomorrow (YYYY-MM-DD) if not specified
    if not due_date:
        due_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    url = f"https://{jira_domain}/rest/api/3/issue"
    auth = (jira_email, jira_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    fields = {
        "project": {"key": jira_project_key},
        "summary": summary,
        "description": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
        },
        "issuetype": {"name": issue_type},
        "duedate": due_date
    }

    # Jira Cloud API v3 requires {"accountId": owner_account_id}
    owner_account_id = get_jira_owner_account_id()
    if owner_account_id:
        fields["assignee"] = {"accountId": owner_account_id}

    payload = {"fields": fields}
    res = requests.post(url, json=payload, auth=auth, headers=headers)
    if res.status_code == 201:
        key = res.json()["key"]
        save_ticket_memory(key, summary, "LIVE_MEETING")
        print(f"  ✅ [JIRA CREATED & AUTO-ASSIGNED TO OWNER] Ticket {key} due on {due_date}!", file=sys.stderr, flush=True)
        return f"SUCCESS: Created Jira Ticket {key} (Assigned to Owner, Due: {due_date}) at https://{jira_domain}/browse/{key}"
    
    print(f"❌ [JIRA CREATION FAILED] Status {res.status_code}: {res.text}", file=sys.stderr, flush=True)
    return f"ERROR: Failed to create Jira ticket: {res.text}"


@mcp.tool()
def generate_release_notes(sprint_name: str = "Sprint 1") -> str:
    """Scans completed Jira tickets in the sprint and generates executive customer-facing Release Notes."""
    print(f"\n📦 [RELEASE NOTES] Generating changelog for {sprint_name}...", file=sys.stderr, flush=True)

    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY")
    webhook_url = get_slack_webhook("meetings")

    if not all([jira_domain, jira_email, jira_token, jira_project_key]):
        return "MOCK_RELEASE_NOTES: Generated for Sprint 1"

    # Updated Atlassian Search Endpoint: /rest/api/3/search/jql
    url = f"https://{jira_domain}/rest/api/3/search/jql"
    auth = (jira_email, jira_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    search_payload = {
        "jql": f"project = {jira_project_key} ORDER BY updated DESC",
        "maxResults": 10,
        "fields": ["summary", "status"]
    }

    try:
        res = requests.post(url, json=search_payload, auth=auth, headers=headers)
        if res.status_code != 200:
            get_url = f"https://{jira_domain}/rest/api/3/search/jql?jql={requests.utils.quote(f'project = {jira_project_key}')}"
            res = requests.get(get_url, auth=auth, headers={"Accept": "application/json"})

        if res.status_code == 200:
            issues = res.json().get("issues", [])
            ticket_summaries = [f"• {i['fields']['summary']}" for i in issues[:5]]
            
            release_text = (
                f"🚀 *AsyncPM Automated Release Notes — {sprint_name}*\n\n"
                f"*What's New & Improved:*\n" + "\n".join(ticket_summaries) + "\n\n"
                f"_Generated automatically by AsyncPM Agent Core._"
            )

            if webhook_url:
                requests.post(webhook_url, json={"text": release_text})

            return f"SUCCESS: Published Release Notes for {sprint_name} to Slack."
        return f"ERROR: Failed to fetch issues {res.status_code}"
    except Exception as e:
        return f"EXCEPTION: {str(e)}"


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
def create_jira_issue(summary: str, description: str, issue_type: str = "Task", priority: str = "Medium", due_date: str = None) -> str:
    """Tool exposed to Gemini. Creates Low/Medium tickets automatically, but routes High Priority to Governance Channel."""
    
    urgent_keywords = ["URGENT", "CRITICAL", "SECURITY", "ALARM", "EMERGENCY", "FIREWALL"]
    if any(k in summary.upper() or k in description.upper() for k in urgent_keywords):
        priority = "High"

    if priority.lower() == "high":
        print(f"\n🛡️ [HITL GOVERNANCE GATE] High priority task '{summary}' sent to Governance Channel!", file=sys.stderr, flush=True)

        slack_blocks = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "⚠️ High Priority Task Requires Governance Approval", "emoji": True}
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

        webhook = get_slack_webhook("governance")
        if webhook:
            requests.post(webhook, json=slack_blocks)
        
        return f"HITL_APPROVAL_GATE_HALTED: High priority task '{summary}' sent to Governance Channel for PM approval."

    return execute_approved_jira_creation(summary, description, issue_type, due_date)


@mcp.tool()
def send_slack_summary(meeting_title: str, summary: str, created_tickets: str) -> str:
    webhook = get_slack_webhook("meetings")
    if not webhook:
        return f"MOCK_SLACK_POSTED: {meeting_title}"

    message = {
        "text": f"🤖 *AsyncPM Executive Report: {meeting_title}*\n\n*Summary:* {summary}\n\n*Action Items Generated:* {created_tickets}"
    }
    res = requests.post(webhook, json=message)
    return "SUCCESS: Summary posted to Slack Meetings Channel." if res.status_code == 200 else f"ERROR: {res.text}"


@mcp.tool()
def check_approaching_deadlines(days_threshold: int = 2) -> str:
    """Queries Jira Cloud for open tickets using the new Atlassian POST /rest/api/3/search/jql endpoint."""
    print(f"\n⏰ [DEADLINE RADAR] Checking Jira for tickets due within {days_threshold} days...", file=sys.stderr, flush=True)

    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY")
    webhook = get_slack_webhook("deadlines")

    if not all([jira_domain, jira_email, jira_token, jira_project_key]):
        mock_alert = "MOCK_DEADLINE_ALERT: Ticket SCRUM-12 ('Optimize database queries') is due tomorrow!"
        if webhook:
            requests.post(webhook, json={"text": f"⏰ *AsyncPM Deadline Radar:* {mock_alert}"})
        return mock_alert

    url = f"https://{jira_domain}/rest/api/3/search/jql"
    auth = (jira_email, jira_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    search_payload = {
        "jql": f"project = {jira_project_key} AND status != Done ORDER BY created DESC",
        "maxResults": 10,
        "fields": ["summary", "duedate", "assignee", "status"]
    }

    try:
        res = requests.post(url, json=search_payload, auth=auth, headers=headers)
        if res.status_code != 200:
            get_url = f"https://{jira_domain}/rest/api/3/search/jql?jql={requests.utils.quote(f'project = {jira_project_key}')}"
            res = requests.get(get_url, auth=auth, headers={"Accept": "application/json"})

        if res.status_code == 200:
            issues = res.json().get("issues", [])
            alerts = []

            for issue in issues[:5]:
                key = issue["key"]
                summary = issue["fields"]["summary"]
                duedate = issue["fields"].get("duedate", "No Due Date")
                assignee = issue["fields"].get("assignee")
                assignee_name = assignee["displayName"] if assignee else "Unassigned"
                alerts.append(f"• *<{f'https://{jira_domain}/browse/{key}'}|{key}>*: {summary}\n  └ 👤 *Assignee:* {assignee_name} | 📅 *Due Date:* `{duedate}`")

            alert_summary = "\n\n".join(alerts) if alerts else "No approaching deadlines found."
            
            if webhook and alerts:
                slack_card = {
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "⏰ AsyncPM Deadline & Risk Radar", "emoji": True}
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Upcoming Sprint Deadlines Needing PM Attention:*\n\n{alert_summary}"}
                        }
                    ]
                }
                requests.post(webhook, json=slack_card)

            return f"DEADLINE_CHECK_COMPLETE: Sent {len(alerts)} deadline alerts to Slack."
        
        print(f"❌ [JIRA SEARCH FAILED] Status {res.status_code}: {res.text}", file=sys.stderr, flush=True)
        return f"ERROR: Jira Search failed (Status {res.status_code}): {res.text}"
    except Exception as e:
        return f"EXCEPTION: {str(e)}"

if __name__ == "__main__":
    mcp.run()