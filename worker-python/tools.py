import os
import requests

def create_jira_ticket(summary: str, description: str, issue_type: str = "Task", priority: str = "Medium") -> dict:
    jira_domain = os.getenv("JIRA_DOMAIN")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY")

    # Fallback to MOCK mode if real credentials aren't set yet
    if not all([jira_domain, jira_email, jira_token, jira_project_key]):
        mock_key = f"MOCK-{abs(hash(summary)) % 1000}"
        print(f"  📌 [MOCK JIRA] Created Ticket {mock_key}: '{summary}' [{issue_type} | {priority}]")
        return {"id": "10000", "key": mock_key, "url": f"https://mock.atlassian.net/browse/{mock_key}"}

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
    
    try:
        res = requests.post(url, json=payload, auth=auth, headers=headers)
        if res.status_code == 201:
            data = res.json()
            data["url"] = f"https://{jira_domain}/browse/{data['key']}"
            print(f"  ✅ [LIVE JIRA] Created Ticket {data['key']}")
            return data
        else:
            print(f"  ❌ [JIRA ERROR] {res.status_code}: {res.text}")
            return {"key": "ERROR", "url": "#"}
    except Exception as e:
        print(f"  ❌ [JIRA EXCEPTION] {str(e)}")
        return {"key": "ERROR", "url": "#"}

def send_slack_notification(meeting_title: str, summary: str, tickets: list) -> bool:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    # Fallback to MOCK mode if Slack webhook isn't set
    if not webhook_url:
        print(f"  💬 [MOCK SLACK] Sent summary for '{meeting_title}' ({len(tickets)} tickets linked).")
        return True

    ticket_lines = "\n".join([f"• *<{t.get('url', '#')}|{t.get('key')}>*: {t.get('summary', 'Task')}" for t in tickets])
    message = {
        "text": f"🤖 *AsyncPM Report: {meeting_title}*\n\n*Summary:* {summary}\n\n*Created Tickets:*\n{ticket_lines}"
    }
    
    try:
        res = requests.post(webhook_url, json=message)
        print("  ✅ [LIVE SLACK] Posted notification.")
        return res.status_code == 200
    except Exception as e:
        print(f"  ❌ [SLACK ERROR] {str(e)}")
        return False