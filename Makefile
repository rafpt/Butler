.PHONY: test lint check install run radar install-agent uninstall-agent telegram-configure

install:
	uv sync --extra dev

test:
	uv run python -m unittest discover -s tests -v

lint:
	uv run ruff check .
	uv run ruff format --check .

check: test lint

run:
	uv run butler health

radar:
	uv run butler radar run

install-agent:
	./scripts/install_launch_agent.sh

uninstall-agent:
	./scripts/uninstall_launch_agent.sh

telegram-configure:
	./scripts/configure_telegram.sh
