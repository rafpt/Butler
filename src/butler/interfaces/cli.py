"""Butler command-line interface."""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import date
from io import TextIOBase
from pathlib import Path
from types import TracebackType
from typing import Self

from butler import __version__
from butler.config import Settings
from butler.core.research import FeedbackAction
from butler.integrations.breach_outbox import PrivateBreachConsumer
from butler.integrations.llm import ModelError, OpenAICompatibleClient
from butler.integrations.macos import MacNotifier
from butler.integrations.notifications import CompositeNotifier
from butler.integrations.sources import default_sources
from butler.integrations.telegram import TelegramNotifier, discover_telegram_chats
from butler.memory import ResearchRepository, SqliteStore
from butler.observability import configure_logging
from butler.policies.autonomy import AutonomyPolicy
from butler.research import RadarService
from butler.services.tasks import TaskService


class RadarLock(AbstractContextManager["RadarLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: TextIOBase | None = None

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        opened = self.path.open("w", encoding="utf-8")
        try:
            fcntl.flock(opened.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            opened.close()
            raise RuntimeError("Já existe uma execução do Cyber Radar em curso") from error
        self._file = opened
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._file:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="butler")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("health", help="Check local runtime state")

    task = subcommands.add_parser("task", help="Manage tasks")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    add = task_commands.add_parser("add", help="Create a task")
    add.add_argument("title")
    add.add_argument("--priority", type=int, default=3, choices=range(1, 6))
    add.add_argument("--tag", action="append", default=[])
    add.add_argument("--notes", default="")
    list_command = task_commands.add_parser("list", help="List tasks")
    list_command.add_argument("--all", action="store_true")
    done = task_commands.add_parser("done", help="Complete a task")
    done.add_argument("task_id")

    radar = subcommands.add_parser("radar", help="Generate and inspect the Cyber Radar")
    radar_commands = radar.add_subparsers(dest="radar_command", required=True)
    radar_run = radar_commands.add_parser("run", help="Collect and render a radar")
    radar_run.add_argument("--date", type=date.fromisoformat)
    radar_run.add_argument("--dry-run", action="store_true")
    radar_run.add_argument("--no-notify", action="store_true")
    radar_commands.add_parser("latest", help="Print the latest radar")
    explain = radar_commands.add_parser("explain", help="Explain an item's priority")
    explain.add_argument("item_id")

    watch = subcommands.add_parser("watch", help="Manage Cyber Radar watch terms")
    watch_commands = watch.add_subparsers(dest="watch_command", required=True)
    watch_add = watch_commands.add_parser("add", help="Add a watch term")
    watch_add.add_argument("term")
    watch_add.add_argument("--kind", default="topic")
    watch_add.add_argument("--weight", type=float, default=1.0)
    watch_commands.add_parser("list", help="List active watch terms")
    watch_remove = watch_commands.add_parser("remove", help="Disable a watch term")
    watch_remove.add_argument("watch_id")

    feedback = subcommands.add_parser("feedback", help="Record a radar disposition")
    feedback.add_argument("item_id")
    feedback.add_argument("action", choices=[action.value for action in FeedbackAction])
    feedback.add_argument("--note", default="")

    research = subcommands.add_parser("research", help="Generate an item deep dive")
    research.add_argument("item_id")
    research.add_argument("--deep-dive", action="store_true", required=True)
    research.add_argument("--cloud", action="store_true")

    notify = subcommands.add_parser("notify", help="Test configured notification channels")
    notify_commands = notify.add_subparsers(dest="notify_command", required=True)
    notify_commands.add_parser(
        "telegram-test",
        help="Send a test alert to the configured Telegram chat",
    )
    notify_commands.add_parser(
        "telegram-chats",
        help="List chats that have sent a message to the configured bot",
    )

    breach = subcommands.add_parser(
        "breach",
        help="Consume private Data Breach Scanner events",
    )
    breach_commands = breach.add_subparsers(dest="breach_command", required=True)
    breach_consume = breach_commands.add_parser("consume")
    breach_consume.add_argument("--dry-run", action="store_true")
    breach_consume.add_argument("--limit", type=int, default=20)
    return parser


def _telegram_notifier(settings: Settings) -> TelegramNotifier:
    if not settings.telegram_configured:
        raise ValueError(
            "Telegram não configurado; guarde bot-token e chat-id no Keychain "
            "com scripts/configure_telegram.sh"
        )
    return TelegramNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        bot_username=settings.telegram_bot_username,
        timeout_seconds=settings.telegram_timeout_seconds,
    )


def _radar_service(settings: Settings, store: SqliteStore, *, with_sources: bool) -> RadarService:
    local_model = OpenAICompatibleClient(
        base_url=settings.omlx_base_url,
        model=settings.omlx_model,
        api_key=settings.omlx_api_key,
    )
    return RadarService(
        settings=settings,
        repository=ResearchRepository(store),
        sources=default_sources(settings) if with_sources else (),
        local_model=local_model,
        policy=AutonomyPolicy(settings.autonomy_level),
        notifier=CompositeNotifier(
            MacNotifier(),
            *([_telegram_notifier(settings)] if settings.telegram_configured else []),
        ),
    )


def _handle_task(args: argparse.Namespace, service: TaskService) -> int:
    if args.task_command == "add":
        task = service.create(
            args.title,
            priority=args.priority,
            notes=args.notes,
            tags=tuple(args.tag),
        )
        print(json.dumps({"id": task.id, "title": task.title, "status": task.status.value}))
        return 0
    if args.task_command == "list":
        result = [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority,
            }
            for task in service.list(include_closed=args.all)
        ]
        print(json.dumps({"tasks": result, "count": len(result)}))
        return 0
    task = service.complete(args.task_id)
    print(json.dumps({"id": task.id, "status": task.status.value}))
    return 0


def _handle_radar(args: argparse.Namespace, settings: Settings, store: SqliteStore) -> int:
    service = _radar_service(
        settings,
        store,
        with_sources=args.radar_command == "run",
    )
    if args.radar_command == "run":
        with RadarLock(settings.data_dir / "radar.lock"):
            result = service.run(
                report_date=args.date,
                dry_run=args.dry_run,
                notify=not args.no_notify,
            )
        if args.dry_run:
            print(result.markdown)
        else:
            print(
                json.dumps(
                    {
                        "status": "degraded" if result.report.degraded else "ok",
                        "report": str(result.path),
                        "must": result.report.must_count,
                        "items": len(result.report.items),
                    }
                )
            )
        return 0
    if args.radar_command == "latest":
        print(service.latest_markdown())
        return 0
    print(service.explain(args.item_id))
    return 0


def _handle_watch(args: argparse.Namespace, settings: Settings, store: SqliteStore) -> int:
    service = _radar_service(settings, store, with_sources=False)
    if args.watch_command == "add":
        entry = service.add_watch(term=args.term, kind=args.kind, weight=args.weight)
        print(json.dumps({"id": entry.id, "term": entry.term, "kind": entry.kind}))
        return 0
    if args.watch_command == "list":
        watches = ResearchRepository(store).list_watches()
        print(
            json.dumps(
                {
                    "watches": [
                        {
                            "id": entry.id,
                            "term": entry.term,
                            "kind": entry.kind,
                            "weight": entry.weight,
                        }
                        for entry in watches
                    ],
                    "count": len(watches),
                }
            )
        )
        return 0
    service.remove_watch(args.watch_id)
    print(json.dumps({"id": args.watch_id, "status": "removed"}))
    return 0


def _handle_feedback(args: argparse.Namespace, settings: Settings, store: SqliteStore) -> int:
    service = _radar_service(settings, store, with_sources=False)
    event = service.add_feedback(
        item_id=args.item_id,
        action=FeedbackAction(args.action),
        note=args.note,
    )
    print(json.dumps({"id": event.id, "item_id": event.item_id, "action": event.action.value}))
    return 0


def _handle_research(args: argparse.Namespace, settings: Settings, store: SqliteStore) -> int:
    service = _radar_service(settings, store, with_sources=False)
    if args.cloud:
        if not settings.cloud_base_url or not settings.cloud_model or not settings.cloud_api_key:
            raise ValueError(
                "Cloud manual não configurada; defina base URL, modelo e API key no ambiente"
            )
        client = OpenAICompatibleClient(
            base_url=settings.cloud_base_url,
            model=settings.cloud_model,
            api_key=settings.cloud_api_key,
        )
    else:
        client = OpenAICompatibleClient(
            base_url=settings.omlx_base_url,
            model=settings.omlx_model,
            api_key=settings.omlx_api_key,
        )
    print(service.deep_dive(item_id=args.item_id, client=client, cloud=args.cloud))
    return 0


def _handle_notify(args: argparse.Namespace, settings: Settings) -> int:
    if args.notify_command == "telegram-test":
        delivered = _telegram_notifier(settings).notify(
            title="Butler Cyber Radar",
            message=(
                "✅ Teste concluído. Os alertas diários e os avisos MUST serão "
                f"enviados por @{settings.telegram_bot_username}."
            ),
        )
        if not delivered:
            raise RuntimeError("O Telegram recusou ou não recebeu o alerta de teste")
        print(
            json.dumps(
                {
                    "status": "sent",
                    "channel": "telegram",
                    "bot": f"@{settings.telegram_bot_username}",
                }
            )
        )
        return 0
    if args.notify_command == "telegram-chats":
        if not settings.telegram_bot_token:
            raise ValueError(
                "Telegram não configurado; guarde bot-token no Keychain "
                "com scripts/configure_telegram.sh"
            )
        chats = discover_telegram_chats(
            bot_token=settings.telegram_bot_token,
            timeout_seconds=settings.telegram_timeout_seconds,
        )
        print(
            json.dumps(
                {
                    "bot": f"@{settings.telegram_bot_username}",
                    "chats": [
                        {
                            "id": chat.id,
                            "type": chat.kind,
                            "name": chat.name,
                            "username": chat.username,
                        }
                        for chat in chats
                    ],
                    "count": len(chats),
                },
                ensure_ascii=False,
            )
        )
        return 0
    return 2


def _handle_breach(args: argparse.Namespace, settings: Settings) -> int:
    if args.breach_command != "consume":
        return 2
    consumer = PrivateBreachConsumer(
        outbox_root=settings.scanner_outbox_root,
        notifier=None if args.dry_run else _telegram_notifier(settings),
    )
    result = consumer.consume(dry_run=args.dry_run, limit=args.limit)
    print(
        json.dumps(
            {
                "status": "ok" if not result.failed and not result.invalid else "partial",
                "delivered": result.delivered,
                "failed": result.failed,
                "invalid": result.invalid,
                "pending": result.pending,
            }
        )
    )
    return 0 if not result.failed and not result.invalid else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        configure_logging(settings.log_level)
        store = SqliteStore(settings.database_path)
        store.initialize()

        if args.command == "health":
            print(
                json.dumps(
                    {
                        "service": "butler",
                        "version": __version__,
                        "radar_reports": str(settings.radar_reports_dir),
                        **store.health(),
                    }
                )
            )
            return 0
        if args.command == "task":
            return _handle_task(
                args,
                TaskService(store, AutonomyPolicy(settings.autonomy_level)),
            )
        if args.command == "radar":
            return _handle_radar(args, settings, store)
        if args.command == "watch":
            return _handle_watch(args, settings, store)
        if args.command == "feedback":
            return _handle_feedback(args, settings, store)
        if args.command == "research":
            return _handle_research(args, settings, store)
        if args.command == "notify":
            return _handle_notify(args, settings)
        if args.command == "breach":
            return _handle_breach(args, settings)
    except (ValueError, LookupError, PermissionError, RuntimeError, ModelError, OSError) as error:
        print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
        return 1
    return 2
