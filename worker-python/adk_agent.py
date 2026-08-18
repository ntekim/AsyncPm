import os
import sys
from google.adk.agents import Agent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool import StdioConnectionParams
from pydantic import BaseModel, Field
from mcp import StdioServerParameters

# 1. Path to local MCP Tool Server
mcp_server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")

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
    You are the AsyncPM Chief Product Orchestrator managing a specialized team of AI agents.

    WORKFLOW DELEGATION STEPS:
    1. First, delegate the raw transcript to 'TranscriptParserAgent' to isolate technical decisions.
    2. Next, delegate those technical decisions to 'ScrumMasterAgent' to format them into Agile User Stories.
    3. For EACH resulting user story:
       a. Call 'search_existing_tickets' FIRST to check for duplicates in persistent memory.
       b. If a duplicate exists -> Call 'update_existing_jira_issue'.
       c. If it is unique -> Call 'create_jira_issue'.
    4. Call 'send_slack_summary' once all tickets are created or routed.
    """,
    sub_agents=[parser_agent, scrum_agent], # Sub-agents explicitly attached!
    tools=[asyncpm_mcp_tools] # Native ADK MCP Toolset Injection!
)