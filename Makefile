.PHONY: test lint check install run radar install-agent uninstall-agent

install:
	uv sync --extra dev

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	uv run ruff check .
	uv run ruff format --check .

check: test lint

run:
	PYTHONPATH=src python3 -m butler health

radar:
	uv run butler radar run

install-agent:
	./scripts/install_launch_agent.sh

uninstall-agent:
	./scripts/uninstall_launch_agent.sh
