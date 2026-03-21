"""Command line interface."""

from __future__ import annotations

import argparse
import signal
from pathlib import Path

import requests

from .config import config_search_paths, load_config
from .logging_utils import configure_logging
from .service import poll_once, run_forever


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(
        description="Poll SolaxCloud and upload to PVOutput."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to the YAML config file. By default the app checks "
            "the user config directory first and ./config.yml second."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll/upload cycle and exit.",
    )
    return parser


def resolve_config_path(cli_path: Path | None) -> Path:
    """Resolve the config file path from CLI or defaults."""

    if cli_path is not None:
        return cli_path.expanduser()

    for path in config_search_paths():
        if path.exists():
            return path
    return config_search_paths()[0]


def install_signal_handlers() -> None:
    """Install termination handlers for long-running process use."""

    if not hasattr(signal, "SIGTERM"):
        return

    def _handle_termination(signum, _frame) -> None:
        raise KeyboardInterrupt(f"Received signal {signum}")

    signal.signal(signal.SIGTERM, _handle_termination)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = build_parser().parse_args(argv)
    config_path = resolve_config_path(args.config)

    try:
        config = load_config(config_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    logger = configure_logging(config.app.log_level, config.log_path)

    if args.once:
        with requests.Session() as session:
            result = poll_once(config, session, logger)
        return 0 if result is not None and result.ok else 1

    install_signal_handlers()
    return run_forever(config, logger)
