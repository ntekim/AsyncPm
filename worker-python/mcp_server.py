import os
import requests
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# Initialize FastMCP Server
mcp = FastMCP("AsyncPM Tool Server")

@mcp.tool()
def create_jira_issue(summary: str, description: str, issue_type: str = "Task", priority: str = "Medium") -> str:
    """Creates a Jira ticket on Atlassian Cloud using REST API v3."""
    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY")

    if not all([jira_domain, jira_email, jira_token, jira_project_key]):
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
        return f"✅ [LIVE JIRA] Created Ticket {key} at https://{jira_domain}/browse/{key}"
    return f"❌ [JIRA ERROR]: Failed to create ticket: {res.text}"

@mcp.tool()
def send_slack_summary(meeting_title: str, summary: str, created_tickets: str) -> str:
    """Posts a formatted executive meeting summary to Slack."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return f"❌ [SLACK ERROR]: Slack webhook not configured for {meeting_title}"

    message = {
        "text": f"🤖 *AsyncPM Report: {meeting_title}*\n\n*Executive Summary:* {summary}\n\n*Action Items Created:*\n{created_tickets}"
    }
    res = requests.post(webhook_url, json=message)
    return "  ✅ [LIVE SLACK] Posted notification." if res.status_code == 200 else f"❌ [SLACK ERROR]: Returned {res.status_code}"

if __name__ == "__main__":
    mcp.run()