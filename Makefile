.PHONY: help build up down logs restart shell-back shell-front shell-db db clean clean-all

# Default target
help:
	@echo ""
	@echo "  AgentReach — Docker commands"
	@echo ""
	@echo "  make build       Build both images from scratch"
	@echo "  make up          Start all services (detached)"
	@echo "  make down        Stop all services"
	@echo "  make logs        Tail logs from all containers"
	@echo "  make logs-back   Tail backend logs only"
	@echo "  make logs-front  Tail frontend logs only"
	@echo "  make restart     Rebuild + restart everything"
	@echo "  make shell-back  Open shell inside backend container"
	@echo "  make shell-front Open shell inside frontend container"
	@echo "  make shell-db    Open mongosh on the local database"
	@echo "  make db          Start only the local MongoDB (for make dev-back)"
	@echo "  make clean       Remove containers and images (keeps the database)"
	@echo "  make clean-all   Remove everything INCLUDING all users and saved searches"
	@echo ""

build:
	docker compose build --no-cache

up:
	@cp -n .env.example .env 2>/dev/null || true
	docker compose up -d
	@echo ""
	@echo "  ✓  Backend:  http://localhost:8000"
	@echo "  ✓  Frontend: http://localhost:3000"
	@echo "  ✓  API docs: http://localhost:8000/docs"
	@echo ""

down:
	docker compose down

logs:
	docker compose logs -f

logs-back:
	docker compose logs -f backend

logs-front:
	docker compose logs -f frontend

restart:
	docker compose down
	docker compose build
	docker compose up -d

shell-back:
	docker compose exec backend /bin/bash

shell-front:
	docker compose exec frontend /bin/sh

shell-db:
	docker compose exec mongo mongosh agentreach

clean:
	docker compose down --rmi local
	docker system prune -f

# Deletes the mongo_data volume — every user account and saved search
clean-all:
	docker compose down -v --rmi local
	docker system prune -f

# Dev shortcuts (run without Docker)
# dev-back needs a database: run `make db` first, or set MONGO_URI to Atlas
db:
	docker compose up -d mongo

dev-back:
	cd backend && uvicorn main:app --reload --port 8000

dev-front:
	cd frontend && npm run dev