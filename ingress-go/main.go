package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

// WebhookPayload represents incoming transcript events
type WebhookPayload struct {
	MeetingID  string `json:"meeting_id"`
	Transcript string `json:"transcript"`
	Source     string `json:"source"`
}

// Response returned instantly to webhook caller
type IngressResponse struct {
	Status    string `json:"status"`
	Message   string `json:"message"`
	Timestamp string `json:"timestamp"`
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/webhook", handleWebhook)
	http.HandleFunc("/health", handleHealth)

	log.Printf("🚀 AsyncPM Go Ingress running on http://localhost:%s", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("❌ Server failed: %v", err)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "online", "service": "AsyncPM Go Ingress"})
}

func handleWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Error reading request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var payload WebhookPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		http.Error(w, "Invalid JSON payload", http.StatusBadRequest)
		return
	}

	if payload.MeetingID == "" || payload.Transcript == "" {
		http.Error(w, "Missing meeting_id or transcript", http.StatusUnprocessableEntity)
		return
	}

	log.Printf("📥 [Go Ingress] Received Webhook for Meeting ID: %s (Source: %s)", payload.MeetingID, payload.Source)

	// ASYNCHRONOUS FORWARDING:
	// Go spins up a lightweight goroutine to forward payload to Python worker
	// while immediately returning 200 OK to the webhook sender (<10ms response time).
	go forwardToPythonWorker(body)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(IngressResponse{
		Status:    "received",
		Message:   "Webhook accepted and queued asynchronously for AsyncPM processing.",
		Timestamp: time.Now().Format(time.RFC3339),
	})
}

func forwardToPythonWorker(payloadBytes []byte) {
	workerURL := os.Getenv("PYTHON_WORKER_URL")
	if workerURL == "" {
		workerURL = "http://localhost:8000/process-transcript"
	}

	log.Printf("⚡ [Go Ingress] Asynchronously dispatching to Python Worker at: %s", workerURL)

	req, err := http.NewRequest("POST", workerURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		log.Printf("❌ [Go Ingress Error] Failed to create request: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("❌ [Go Ingress Error] Failed to reach Python worker: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK || resp.StatusCode == http.StatusAccepted {
		log.Printf("✅ [Go Ingress] Python worker acknowledged payload successfully.")
	} else {
		log.Printf("⚠️ [Go Ingress Warning] Python worker returned status: %d", resp.StatusCode)
	}
}