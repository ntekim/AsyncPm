# 🚀 AsyncPM — Autonomous Product Manager Agent

> Built for the **All Things Agentic Hackathon** (Taskmaster Track)  
> Powered by **Google ADK 2.0**, **Gemini 3.6 Flash**, **MCP (Model Context Protocol)**, and **Google Cloud**.

AsyncPM is an autonomous background AI agent that eliminates administrative product management overhead. It turns unstructured meeting transcripts into formalized Agile User Stories, creates Jira tickets, and broadcasts summaries to Slack—operating silently with zero manual intervention.

---

## 🏗️ Technical Architecture

* **Framework:** Google Agent Development Kit (ADK 2.0)
* **LLM Reasoning:** Gemini 3.5 Flash via Google GenAI SDK
* **Tool Protocol:** Model Context Protocol (MCP Toolset)
* **Ingress Engine:** Golang (Ultra-fast, zero cold-start webhook receiver)
* **Agent Backend:** Python FastAPI + ADK Runner
* **Infrastructure:** Google Cloud Run + Pub/Sub + Firestore

---

## 🛠️ Local Setup & Spin-Up Instructions

### Prerequisites
* Python 3.11+
* Golang 1.26+
* Docker & Docker Compose (optional)

### 1. Environment Configuration
Create a `.env` file in `worker-python/`:

```env
GEMINI_API_KEY=your_gemini_api_key
JIRA_DOMAIN=yourdomain.atlassian.net
JIRA_EMAIL=youremail@example.com
JIRA_API_TOKEN=your_jira_token
JIRA_PROJECT_KEY=SCRUM
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...