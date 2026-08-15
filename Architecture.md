graph TD
    A[Event Trigger / Webhook] -->|Instant HTTP <10ms| B(Golang Ingress Server)
    B -->|Async Dispatch / PubSub| C(FastAPI Worker Engine)
    
    subgraph "Google ADK 2.0 Multi-Agent Core"
        C --> D[ADK Runner & Session Manager]
        D --> E[AsyncPMAgent - Gemini 3.5 Flash]
        E --> F[Scrum Master Reasoning Module]
    end
    
    subgraph "MCP Tooling & Execution"
        E -->|Stdio JSON-RPC| G[MCP Tool Server]
        G -->|REST API v3| H[Jira Cloud]
        G -->|Incoming Webhook| I[Slack Channel]
    end
    
    subgraph "Persistence & Audit"
        D --> J[(Firestore / Audit Log DB)]
    end