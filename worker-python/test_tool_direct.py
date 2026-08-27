import os
from dotenv import load_dotenv
from mcp_server import create_jira_issue

load_dotenv()

print("🧪 Testing create_jira_issue tool directly...")
result = create_jira_issue(
    summary="Critical Security Patch for Payment Gateway",
    description="Emergency data leak vulnerability fix required immediately.",
    issue_type="Task",
    priority="High"
)
print(f"Tool Result: {result}")