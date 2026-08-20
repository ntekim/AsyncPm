import os
import sys
from google.adk.agents import Agent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool import StdioConnectionParams
from pydantic import BaseModel, Field
from mcp import StdioServerParameters

# 1. Path to local MCP Tool Server
mcp_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))

# 1. Define MCP Toolset connected to our mcp_server.py
mcp_params = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=[mcp_server_path],
        env=os.environ.copy()
    )
)

asyncpm_mcp_tools = McpToolset(connection_params=mcp_params)

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

    MANDATORY WORKFLOW STEPS (EXECUTE IN ORDER):
    1. Read and analyze the transcript or audio provided to extract key technical action items.
    2. FOR EACH ACTION ITEM EXTRACTED:
       a. Call 'search_existing_tickets' FIRST to check for duplicate tasks in persistent memory.
       b. If an existing ticket is found -> Call 'update_existing_jira_issue' to add new notes instead of creating a duplicate.
       c. If NO existing ticket is found -> Call 'create_jira_issue' to generate the task on Jira.
    3. AFTER all Jira tickets/comments are processed:
       a. Call 'send_slack_summary' to post the executive meeting summary to Slack.

    CRITICAL RULE:
    You MUST execute your MCP tools ('search_existing_tickets', 'create_jira_issue', 'send_slack_summary'). Do NOT just generate text summaries without executing the tools.
    """,
    tools=[asyncpm_mcp_tools], # Native ADK MCP Toolset Injection!
    sub_agents=[parser_agent, scrum_agent] # Sub-agents explicitly attached!
)