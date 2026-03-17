SHELL := sh

COMPOSE_FILE := docker-compose.yml
INFRA_COMPOSE_FILE := infra/docker-compose.yml

PYTHON ?= python
PIP ?= pip
NPM ?= npm

BACKEND_DIR := backend
FRONTEND_DIR := frontend
NODE_SIM_DIR := node_simulator
TESTS_DIR := tests

.DEFAULT_GOAL := help

.PHONY: help install install-backend install-frontend install-node \
	up down restart logs ps \
	infra-up infra-down \
	backend frontend simulator \
	test test-unit test-load \
	lint build clean demo

help:
	@echo "ThreatScope Makefile commands"
	@echo ""
	@echo "Setup"
	@echo "  make install           Install backend, frontend, and node simulator deps"
	@echo "  make install-backend   Install backend Python dependencies"
	@echo "  make install-frontend  Install frontend npm dependencies"
	@echo "  make install-node      Install node simulator Python dependencies"
	@echo ""
	@echo "Local stack"
	@echo "  make up                Start repo-root Docker Compose stack"
	@echo "  make down              Stop repo-root Docker Compose stack"
	@echo "  make restart           Restart repo-root Docker Compose stack"
	@echo "  make logs              Tail repo-root Docker Compose logs"
	@echo "  make ps                Show repo-root Docker Compose service status"
	@echo "  make infra-up          Start infra Docker Compose stack"
	@echo "  make infra-down        Stop infra Docker Compose stack"
	@echo ""
	@echo "App dev"
	@echo "  make backend           Run FastAPI backend locally"
	@echo "  make frontend          Run Vite frontend locally"
	@echo "  make simulator         Run node simulator locally"
	@echo "  make demo              Start the demo simulator workload"
	@echo ""
	@echo "Quality"
	@echo "  make test              Run unit tests"
	@echo "  make test-unit         Run unit tests"
	@echo "  make test-load         Print Locust command for load testing"
	@echo "  make lint              Run available frontend lint checks"
	@echo "  make build             Build frontend bundle"
	@echo "  make clean             Remove common local cache artifacts"

install: install-backend install-frontend install-node

install-backend:
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt

install-frontend:
	cd $(FRONTEND_DIR) && $(NPM) install

install-node:
	$(PIP) install -r $(NODE_SIM_DIR)/requirements.txt

up:
	docker compose -f $(COMPOSE_FILE) up --build

down:
	docker compose -f $(COMPOSE_FILE) down

restart: down up

logs:
	docker compose -f $(COMPOSE_FILE) logs -f

ps:
	docker compose -f $(COMPOSE_FILE) ps

infra-up:
	docker compose -f $(INFRA_COMPOSE_FILE) up --build

infra-down:
	docker compose -f $(INFRA_COMPOSE_FILE) down

backend:
	cd $(BACKEND_DIR) && $(PYTHON) main.py

frontend:
	cd $(FRONTEND_DIR) && $(NPM) run dev

simulator:
	cd $(NODE_SIM_DIR) && $(PYTHON) signal_sender.py --nodes 3 --interval 5

demo:
	cd $(NODE_SIM_DIR) && $(PYTHON) signal_sender.py --nodes 5 --interval 2

test: test-unit

test-unit:
	pytest $(TESTS_DIR)/unit -v

test-load:
	@echo "Run Locust with:"
	@echo "  locust -f $(TESTS_DIR)/load/locustfile.py --host=http://localhost:8000"

lint:
	cd $(FRONTEND_DIR) && $(NPM) run lint

build:
	cd $(FRONTEND_DIR) && $(NPM) run build

clean:
	-find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	-find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	-find . -type d -name "node_modules" -prune -exec rm -rf {} +
	-find . -type d -name "dist" -prune -exec rm -rf {} +
