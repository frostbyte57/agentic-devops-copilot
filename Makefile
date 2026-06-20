PORT_API ?= 8000
PORT_WEB ?= 3000

.PHONY: help install install-py install-web dev backend frontend test clean

help:
	@echo "make install   - install Python (all extras) + web dependencies"
	@echo "make dev       - run the API + web UI together (Ctrl-C stops both)"
	@echo "make backend   - run only the FastAPI backend on :$(PORT_API)"
	@echo "make frontend  - run only the Next.js UI on :$(PORT_WEB)"
	@echo "make test      - run the Python test suite"

install: install-py install-web

install-py:
	pip install -e '.[server,openai,local,github,dev]'

install-web:
	cd web && npm install

# One command to run everything. Starts the API and the web UI, and stops
# both when you press Ctrl-C (the trap kills the whole process group).
dev:
	@echo "API  -> http://localhost:$(PORT_API)"
	@echo "Web  -> http://localhost:$(PORT_WEB)"
	@trap 'kill 0' EXIT INT TERM; \
	uvicorn copilot.server:app --reload --port $(PORT_API) & \
	( cd web && npm run dev -- --port $(PORT_WEB) ) & \
	wait

backend:
	uvicorn copilot.server:app --reload --port $(PORT_API)

frontend:
	cd web && npm run dev -- --port $(PORT_WEB)

test:
	pytest -q

clean:
	rm -rf web/dist
