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
