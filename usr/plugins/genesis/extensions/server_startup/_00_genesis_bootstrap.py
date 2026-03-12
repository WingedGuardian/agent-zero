"""Genesis server startup bootstrap.

Fires from run_ui.py:init_a0() BEFORE any agent is created, so Genesis
background infrastructure (awareness loop, learning scheduler, inbox monitor)
starts immediately — not on first chat message.

This is the ONLY entry point for GenesisRuntime.bootstrap().  The agent_init
extensions just copy references from the singleton to self.agent for backward
compatibility.
"""

import logging

from python.helpers.extension import Extension

logger = logging.getLogger("genesis.bootstrap")


class GenesisBootstrap(Extension):
    async def execute(self, **kwargs):
        try:
            from genesis.runtime import GenesisRuntime

            await GenesisRuntime.instance().bootstrap()
        except ImportError:
            pass  # Genesis not installed
        except Exception:
            logger.exception("Genesis bootstrap failed")

        # Register health API blueprint on the Flask app
        try:
            import sys
            # Access the module-level webapp from run_ui
            run_ui = sys.modules.get("__main__")
            webapp = getattr(run_ui, "webapp", None)
            if webapp is None:
                # Try importing directly
                import run_ui as run_ui_mod
                webapp = getattr(run_ui_mod, "webapp", None)

            if webapp is not None:
                import importlib.util
                from pathlib import Path

                spec = importlib.util.spec_from_file_location(
                    "genesis_api_health",
                    Path(__file__).parent.parent.parent / "api_health.py",
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                blueprint = mod.blueprint

                # Avoid duplicate registration
                if "genesis_health" not in webapp.blueprints:
                    webapp.register_blueprint(blueprint)
                    logger.info("Genesis health blueprint registered")
            else:
                logger.warning("Could not find Flask webapp for health blueprint")
        except Exception:
            logger.exception("Failed to register health blueprint")
