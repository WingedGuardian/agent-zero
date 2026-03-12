"""Flask blueprint for Genesis health API and neural monitor dashboard."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory

logger = logging.getLogger("genesis.api_health")

blueprint = Blueprint(
    "genesis_health",
    __name__,
    template_folder="templates",
)


@blueprint.route("/api/genesis/health")
def health_snapshot():
    """Return full health snapshot as JSON."""
    try:
        from genesis.runtime import GenesisRuntime

        rt = GenesisRuntime.instance()
        if not rt.is_bootstrapped or not rt.health_data:
            return jsonify({"status": "unknown", "message": "not bootstrapped"})

        # Run async snapshot in the existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    asyncio.run, rt.health_data.snapshot()
                ).result(timeout=10)
        else:
            result = loop.run_until_complete(rt.health_data.snapshot())

        return jsonify(result)
    except Exception:
        logger.exception("Health snapshot failed")
        return jsonify({"status": "error", "message": "snapshot failed"}), 500


@blueprint.route("/genesis/monitor")
def neural_monitor():
    """Serve the neural monitor dashboard."""
    return send_from_directory(
        str(Path(__file__).parent / "templates"),
        "neural_monitor.html",
    )
