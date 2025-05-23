"""Implementation of AXS for IGP2."""

import logging
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

import axs
from axs import cli

from .macroaction import IGP2MacroAction
from .policy import IGP2Policy
from .query import IGP2Query
from .verbalize import IGP2Verbalizer
from .wrapper import IGP2QueryableWrapper

__all__ = [
    "IGP2MacroAction",
    "IGP2Policy",
    "IGP2Query",
    "IGP2QueryableWrapper",
    "IGP2Verbalizer",
]


logger = logging.getLogger(__name__)


class FunctionNames(str, Enum):
    """Function names for IGP2."""

    run = "run"
    evaluate = "evaluate"


def init_igp2(ctx: typer.Context, fn_name: str, save_logs: bool) -> None:
    """Initialize IGP2 configurations."""
    import gofi
    import igp2

    config = ctx.obj["config"]
    debug = config.debug
    output_dir = config.output_dir
    axs.util.init_logging(
        level="DEBUG" if debug else "INFO",
        warning_only=[
            None if not debug else "igp2.core.velocitysmoother",
            "matplotlib",
            "httpcore",
            "openai",
            "httpx",
        ],
        log_dir=Path(output_dir, "logs") if save_logs else None,
        log_name=fn_name[:4],
    )
    logging.getLogger("igp2.simplesim.simulation_env").setLevel(
        logging.DEBUG if debug else logging.INFO,
    )
    logging.getLogger("gofi.osimulation_env").setLevel(
        logging.DEBUG if debug else logging.INFO,
    )


@axs.app.command()
def run(
    ctx: typer.Context,
    save_logs: Annotated[bool, typer.Option(help="Save logs to file.")] = False,
) -> None:
    """Run an AXS agent with the IGP2 configurations."""
    init_igp2(ctx, "run", save_logs)
    axs.run(ctx)


@axs.app.command()
def explain(
    ctx: typer.Context,
    save_logs: Annotated[bool, typer.Option(help="Save logs to file.")] = False,
) -> None:
    """Evaluate an AXS agent with the IGP2 configurations."""
    init_igp2(ctx, "run", save_logs)
    axs.explain(ctx)
