"""
tools/main.py — Root Typer application.

Registers all group sub-apps and serves as the entry point for the `tools` CLI.

To add a new group:
  1. Create a new package under tools/ (e.g. tools/text/).
  2. Define a Typer app in its __init__.py (e.g. text_app).
  3. Import it here and call app.add_typer(text_app, name="text").
"""

import typer

from tools.media import media_app

app = typer.Typer(
    help="Personal CLI toolkit.",
    no_args_is_help=True,
)

app.add_typer(media_app, name="media")
