# LangChain Agent Playground

This project is a full-stack LangChain agent playground with a FastAPI backend and a React frontend. It includes:

- a reusable agent framework under `backend/agents`
- a basic agent with offline tools and human-in-the-loop approval
- a research agent built on the same backend structure
- voice input/output with client-side and server-side fallbacks
- streamed agent activity updates in the chat UI

## Project Structure

- `backend/`
  FastAPI app, reusable agent framework, voice services, logs, and model storage.
- `frontend/`
  React + Vite chat UI.
- `docker-compose.yml`
  Runs backend and frontend together with mounted source and model folders.

## Local Setup

### Backend

1. Create `backend/.env` from [backend/.env.example](/Users/hp/Desktop/Projects/langchain_agent/backend/.env.example).
2. Install dependencies:

```bash
cd backend
uv sync
```

3. Start the backend:

```bash
uv run main.py
```

The backend runs on `http://127.0.0.1:8000`.

### Frontend

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Optional: create `frontend/.env` from [frontend/.env.example](/Users/hp/Desktop/Projects/langchain_agent/frontend/.env.example) if you want to override the backend proxy target.

3. Start the frontend:

```bash
npm run dev
```

The frontend runs on `http://127.0.0.1:5173`.

## Docker Setup

The project includes Dockerfiles for both backend and frontend plus a root Compose file.

### Before Running

1. Make sure `backend/.env` exists.
2. Review `frontend/.env.docker` if you want to change the frontend proxy target.

### Start Everything

```bash
docker compose up --build
```

Services:

- frontend: `http://127.0.0.1:5173`
- backend: `http://127.0.0.1:8000`

### Mounted Volumes

The Compose setup mounts these folders so changes persist outside the containers:

- `./backend:/app`
- `./backend/models:/app/models`
- `./backend/logs:/app/logs`
- `./backend/research:/app/research`
- `./frontend:/app`

Whisper STT models are stored in:

- `backend/models/whisper`

This keeps model downloads inside the project instead of using a user-level cache directory.

## Notes

- Daily backend logs are written to `backend/logs/`.
- Server-side STT uses Whisper and stores downloaded models in `backend/models/whisper`.
- Server-side TTS behavior can depend on the OS and voices available inside the runtime environment.
- If `PG_MEMORY_DB_URL` points to `localhost`, Docker containers may not be able to reach that database unless it is also running inside Docker or exposed correctly.

## Agents

The reusable backend agent structure is documented in [backend/README.md](/Users/hp/Desktop/Projects/langchain_agent/backend/README.md).
