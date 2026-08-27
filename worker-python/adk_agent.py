import os
import sys
from google.adk.agents import Agent
# from google.adk.tools import McpToolset
# from google.adk.tools.mcp_tool import StdioConnectionParams
# from pydantic import BaseModel, Field
# from mcp import StdioServerParameters
from mcp_server import (
    search_existing_tickets,
    update_existing_jira_issue,
    create_jira_issue,
    send_slack_summary,
    check_approaching_deadlines,
    generate_release_notes
)

# 1. Path to local MCP Tool Server
# mcp_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))

# # 1. Define MCP Toolset connected to our mcp_server.py
# mcp_params = StdioConnectionParams(
#     server_params=StdioServerParameters(
#         command=sys.executable,
#         args=[mcp_server_path],
#         env=os.environ.copy()
#     )
# )

# 2. Define the tools list directly without the broken Stdio subprocess wrapper
asyncpm_tools = [
    search_existing_tickets,
    update_existing_jira_issue,
    create_jira_issue,
    send_slack_summary,
    check_approaching_deadlines,
    generate_release_notes
]

# # Define your root agent
# root_agent = Agent(
#     name="AsyncPMAgent",
#     model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
#     instruction="""
#     You are AsyncPM, an autonomous Product Manager AI agent built on Google ADK 2.0.
#     Analyze the meeting transcript provided. Parse technical decisions, format them into 
#     Scrum user stories, and use available tools to create Jira tickets and post summaries to Slack.
#     """
# )

# 2. Agent 1: Transcript Parser Agent
parser_agent = Agent(
    name="TranscriptParserAgent",
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    instruction="""
    You are an expert transcript analyst. Your ONLY job is to read raw meeting transcripts and extract:
    1. A concise meeting title
    2. Key technical decisions made
    3. Unprocessed raw action items mentioned by participants.
    """
)

# 3. Agent 2: Scrum Master Agent
scrum_agent = Agent(
    name="ScrumMasterAgent",
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    instruction="""
    You are a Certified Scrum Master. Your ONLY job is to take raw action items and format them into professional 
    Agile User Stories or Technical Tasks with crisp summaries, acceptance criteria, priority 
    (High, Medium, Low), and issue types (Task, Bug, Story).
    """
)

# 4. Agent 3: Action Dispatcher Agent (Root Agent with MCP Tools)
head_agent = Agent(
    name="AsyncPMOrchestrator",
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    instruction="""
    You are AsyncPM, an autonomous Product Manager AI agent built on Google ADK 2.0 with Memory & Governance.

    STRICT OPERATIONAL DIRECTIVE:
    You are an agent with ACTIVE execution tools. Do NOT act as a passive chatbot. You must invoke your tools directly.

    STEP-BY-STEP EXECUTION:
    1. Parse the provided transcript or audio to identify distinct tasks and their priorities.
    2. For EVERY task found:
       - You MUST call the tool: search_existing_tickets(task_description="...")
       - Based on the result, you MUST call the tool: create_jira_issue(summary="...", description="...", priority="...")
    3. Once all tasks are handled, you MUST call the tool: send_slack_summary(meeting_title="...", summary="...", created_tickets="...")

    EXECUTE THE TOOLS NOW.
    """,
    tools=asyncpm_tools,
    sub_agents=[parser_agent, scrum_agent]
)