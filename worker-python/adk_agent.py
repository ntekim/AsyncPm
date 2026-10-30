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
    You are AsyncPM, an autonomous Product Manager AI agent built on Google ADK 2.0 with Memory(Atlassian Teamwork Graph Context), SRE Sentinel diagnostics & Governance.

    STRICT OPERATIONAL DIRECTIVE:
    You are an agent with ACTIVE execution tools. Do NOT act as a passive chatbot. You must invoke your tools directly.

    MANDATORY WORKFLOW STEPS (EXECUTE IN ORDER):
    1. Read and analyze the transcript or audio provided to extract key technical action items.
    2. FOR EACH ACTION ITEM EXTRACTED:
       a. Call 'verify_teamwork_graph_context' to align the task with organizational goals.
       b. Call 'check_circular_dependencies' to ensure no deadlocks exist in the Teamwork Graph.
       c. Call 'trace_bug_root_cause' if the task mentions a bug, spike, or failure to trace regression history.
       d. Call 'validate_confluence_spec' to check technical specs against Confluence.
       e. Call 'search_existing_tickets' to check for duplicates in Jira memory.
       f. If unique and safe -> Call 'create_jira_issue' to generate the task.
    3. AFTER all Jira tickets/comments are processed:
       a. Call 'send_slack_summary' to post the executive meeting summary and advanced risk report to Slack.

    CRITICAL RULE:
    You MUST execute your MCP tools. Let Atlassian's Teamwork Graph and SRE diagnostics drive your decisions!
    """,
    tools=asyncpm_tools,
    sub_agents=[parser_agent, scrum_agent]
)