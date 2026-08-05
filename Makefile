.PHONY: dev dev-backend dev-frontend install build
dev:
	@bash dev.sh
dev-backend:
	@cd backend && . venv/bin/activate && exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
dev-frontend:
	@cd frontend && npx vite --host 0.0.0.0 --port 5173
install:
	@cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	@cd frontend && npm install
build:
	@cd frontend && npx vite build
