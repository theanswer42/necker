#!/usr/bin/env python3
"""CLI command for running the Flask development server."""

from logger import get_logger

logger = get_logger()


def cmd_serve(args, db_manager, config):
    """Run the Flask development server.

    Args:
        args: Parsed command-line arguments (host, port, debug)
        db_manager: Database manager instance
        config: Application configuration
    """
    from app.app import create_app

    app = create_app(config=config, db_manager=db_manager)

    logger.info(f"Starting Necker web server on http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=args.debug)


def setup_parser(subparsers):
    """Setup serve subcommand parser.

    Args:
        subparsers: The subparsers object from the main CLI
    """
    parser = subparsers.add_parser(
        "serve",
        help="Run the Flask development server",
        description="Start the Necker web interface",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )
    parser.set_defaults(func=cmd_serve)
