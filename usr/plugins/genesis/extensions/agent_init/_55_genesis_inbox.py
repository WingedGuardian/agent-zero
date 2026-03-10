"""Genesis inbox monitor wire-up extension.

Runs during agent_init (after _40 cc relay, _50 learning) to:
1. Load inbox_monitor config
2. Create ResponseWriter + InboxMonitor
3. Start the monitor (if enabled)
4. Register health probe

Stores on agent: genesis_inbox_monitor
"""

import logging
from functools import partial
from pathlib import Path

from python.helpers.extension import Extension

logger = logging.getLogger("genesis.extensions.inbox")


class GenesisInbox(Extension):
    async def execute(self, **kwargs):
        try:
            # ── prerequisites ───────────────────────────────────────────
            db = getattr(self.agent, "genesis_db", None)
            event_bus = getattr(self.agent, "genesis_event_bus", None)
            invoker = getattr(self.agent, "genesis_cc_invoker", None)
            session_manager = getattr(self.agent, "genesis_session_manager", None)

            if db is None:
                logger.warning("Genesis inbox skipped — no genesis_db")
                return

            if invoker is None or session_manager is None:
                logger.warning(
                    "Genesis inbox skipped — missing CC prerequisites "
                    "(invoker=%s, session_manager=%s)",
                    invoker is not None, session_manager is not None,
                )
                return

            # ── load config ──────────────────────────────────────────────
            config_path = Path.home() / "genesis" / "config" / "inbox_monitor.yaml"
            if not config_path.exists():
                logger.info("No inbox_monitor.yaml — inbox monitor not configured")
                return

            from genesis.inbox.config import load_inbox_config

            config = load_inbox_config(config_path)

            if not config.enabled:
                logger.info("Inbox monitor disabled in config")
                return

            # ── create watch_path if missing ─────────────────────────────
            config.watch_path.mkdir(parents=True, exist_ok=True)

            # ── create writer ────────────────────────────────────────────
            from genesis.inbox.writer import ResponseWriter

            response_base = config.watch_path / config.response_dir
            writer = ResponseWriter(response_base_path=response_base)

            # ── create and start monitor ─────────────────────────────────
            from genesis.inbox.monitor import InboxMonitor

            monitor = InboxMonitor(
                db=db,
                invoker=invoker,
                session_manager=session_manager,
                config=config,
                writer=writer,
                event_bus=event_bus,
            )

            await monitor.start()
            self.agent.genesis_inbox_monitor = monitor
            logger.info("Genesis inbox monitor started (watch=%s)", config.watch_path)

            # ── register health probe ────────────────────────────────────
            try:
                from genesis.observability.health import probe_scheduler

                status_agg = getattr(self.agent, "genesis_status_aggregator", None)
                if status_agg is not None:
                    status_agg.add_probe(
                        partial(
                            probe_scheduler,
                            monitor._scheduler,
                            name="inbox_scheduler",
                        )
                    )
                    logger.info("Inbox health probe registered")
            except Exception:
                logger.warning("Could not register inbox health probe", exc_info=True)

        except ImportError:
            logger.warning(
                "Genesis inbox package not available — genesis.inbox not installed"
            )
        except Exception:
            logger.exception("Failed to initialize Genesis inbox monitor")
