# Jarvis: Agentic Marketing Agency OS (Variant)

**Jarvis** is a production-grade, zero-code Agency OS designed to automate content creation, client management, and multi-channel publishing using autonomous AI agents.

## 🚀 Key Features
- **Lead Orchestrator:** Natural language command center for managing agency operations.
- **WhatsApp Human-in-the-Loop:** Interactive approval workflow for scheduled posts.
- **Dynamic Agency Settings:** Manage owner configurations and client profiles directly from the dashboard.
- **Automated Pipeline:** End-to-end content generation, image synthesis, and social media publishing.
- **Real-time Telemetry:** Live log streaming and agent thought tracking.

## 🛠️ Technology Stack
- **Backend:** FastAPI (Python)
- **Frontend:** Vanilla HTML/JS with Premium CSS Aesthetics
- **Agents:** LangGraph / OpenAI / OpenRouter
- **Database:** JSON-based state management (`schedule.json`, `pending_approvals.json`)
- **Messaging:** Meta WhatsApp Cloud API

## 📦 Installation & Setup
1. Clone the repository into WSL.
2. Initialize the virtual environment: `python3 -m venv venv`.
3. Install dependencies: `./venv/bin/pip install -r requirements.txt`.
4. Configure your `.env` file (see `.env.example`).
5. Run the server: `./venv/bin/python3 -m uvicorn webhook_server:app --host 0.0.0.0 --port 8000`.

## 🔒 Security
Sensitive API keys and configuration settings are excluded from this repository. Ensure your `.env` is configured locally.
