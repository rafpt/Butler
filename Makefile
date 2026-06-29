.PHONY: test lint check install run radar breach-consume install-agent uninstall-agent install-breach-agent uninstall-breach-agent telegram-configure

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

breach-consume:
	uv run butler breach consume

install-agent:
	./scripts/install_launch_agent.sh

uninstall-agent:
	./scripts/uninstall_launch_agent.sh

install-breach-agent:
	./scripts/install_breach_consumer.sh

uninstall-breach-agent:
	./scripts/uninstall_breach_consumer.sh

telegram-configure:
	./scripts/configure_telegram.sh
