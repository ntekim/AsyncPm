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
    You are an expert transcript analyst. Read raw meeting transcripts and extract:
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
    You are a Certified Scrum Master. Take raw action items and format them into professional 
    Agile User Stories or Technical Tasks with crisp summaries, acceptance criteria, priority 
    (High, Medium, Low), and issue types (Task, Bug, Story).
    """
)

# 4. Agent 3: Action Dispatcher Agent (Root Agent with MCP Tools)
dispatcher_agent = Agent(
    name="ActionDispatcherAgent",
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    instruction="""
    You are AsyncPM, an autonomous Product Manager AI agent built on Google ADK 2.0.

    CRITICAL EXECUTION INSTRUCTIONS:
    1. Analyze the meeting transcript provided to extract key technical tasks.
    2. For EVERY task extracted, you MUST invoke the tool `create_jira_issue` with the summary, description, issue_type, and priority.
    3. After creating the Jira issues, you MUST invoke the tool `send_slack_summary` with the meeting title, executive summary, and created ticket IDs.
    4. ABSOLUTELY DO NOT write text pretending or simulating tool execution (e.g., NEVER write "Simulated Jira creation"). You MUST execute real function calls using your tools.
    """,
    tools=[asyncpm_mcp_tools] # Native ADK MCP Toolset Injection!
)