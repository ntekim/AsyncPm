.PHONY: help dev-python dev-go drive-watcher docker-up docker-down test-transcript test-audio deploy-worker deploy-ingress deploy-all logs-worker logs-ingress

# Project & Virtual Environment Configuration
PROJECT_ID ?= asyncpm-agentic-2026
REGION ?= us-central1
PYTHON_WORKER_URL ?= https://asyncpm-worker-uc.a.run.app/process-transcript

VENV ?= $(HOME)/Desktop/venv
PYTHON ?= $(VENV)/bin/python
UVICORN ?= $(VENV)/bin/uvicorn

help:
	@echo "======================================================================="
	@echo "AsyncPM - Autonomous Product Manager Agent (Google ADK 2.0 + MCP)"
	@echo "======================================================================="
	@echo "Local Development:"
	@echo "  make dev-python       Start Python ADK Worker locally (port 8000)"
	@echo "  make dev-go           Start Go Ingress Server locally (port 8080)"
	@echo "  make drive-watcher    Start Google Drive Watcher service"
	@echo ""
	@echo "Docker Management:"
	@echo "  make docker-up        Build & run all containers via Docker Compose"
	@echo "  make docker-down      Stop and remove all running containers"
	@echo ""
	@echo "Testing Commands:"
	@echo "  make test-transcript  Send test text transcript curl to local ingress"
	@echo "  make test-audio       Send test audio file curl to local worker"
	@echo ""
	@echo "Google Cloud Run Deployment:"
	@echo "  make deploy-worker    Deploy worker-python to Cloud Run"
	@echo "  make deploy-ingress   Deploy ingress-go to Cloud Run"
	@echo "  make deploy-all       Deploy both worker and ingress to Cloud Run"
	@echo "  make logs-worker      Stream GCP Cloud Run logs for worker"
	@echo "  make logs-ingress     Stream GCP Cloud Run logs for ingress"
	@echo "======================================================================="

# --- LOCAL DEVELOPMENT ---
dev-python:
	cd worker-python && $(UVICORN) main:app --reload --port 8000

dev-go:
	cd ingress-go && go run main.go

drive-watcher:
	cd worker-python && $(PYTHON) drive_watcher.py

# --- DOCKER ---
docker-up:
	docker compose up --build

docker-down:
	docker compose down

# --- TESTING ---
test-transcript:
	curl -X POST "http://localhost:8080/webhook" \
		-H "Content-Type: application/json" \
		-d '{"meeting_id": "MAKE-TEST-001", "source": "local_make", "transcript": "Dave: Sarah, please update the SSL certificate on Google Cloud Load Balancer. Priority is High."}'

test-audio:
	curl -X POST "http://localhost:8000/process-audio?meeting_id=MAKE-AUDIO-001" \
		-F "file=@sample_meeting.mp3"

# --- GCP CLOUD RUN DEPLOYMENT ---
deploy-worker:
	cd worker-python && gcloud run deploy asyncpm-worker \
		--source . \
		--platform managed \
		--region $(REGION) \
		--allow-unauthenticated \
		--min-instances 0 \
		--max-instances 2 \
		--set-env-vars GEMINI_API_KEY="$$(grep GEMINI_API_KEY .env | cut -d '=' -f2)",JIRA_DOMAIN="$$(grep JIRA_DOMAIN .env | cut -d '=' -f2)",JIRA_EMAIL="$$(grep JIRA_EMAIL .env | cut -d '=' -f2)",JIRA_API_TOKEN="$$(grep JIRA_API_TOKEN .env | cut -d '=' -f2)",JIRA_PROJECT_KEY="$$(grep JIRA_PROJECT_KEY .env | cut -d '=' -f2)",SLACK_WEBHOOK_URL="$$(grep SLACK_WEBHOOK_URL .env | cut -d '=' -f2)"

deploy-ingress:
	cd ingress-go && gcloud run deploy asyncpm-ingress \
		--source . \
		--platform managed \
		--region $(REGION) \
		--allow-unauthenticated \
		--min-instances 0 \
		--max-instances 2 \
		--set-env-vars PYTHON_WORKER_URL="$(PYTHON_WORKER_URL)"

deploy-all: deploy-worker deploy-ingress

logs-worker:
	gcloud run services logs tail asyncpm-worker --region $(REGION)

logs-ingress:
	gcloud run services logs tail asyncpm-ingress --region $(REGION)

set-gcp-project:
	gcloud config set project $(PROJECT_ID)
	gcloud config set run/region $(REGION)