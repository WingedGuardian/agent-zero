"""Genesis initialization — agent_init wrapper.

Ensures GenesisRuntime is bootstrapped (fallback if server_startup didn't fire)
and copies DB + awareness loop references to self.agent for backward compat.
"""

import logging
import os

from dotenv import load_dotenv
from python.helpers.extension import Extension
from python.helpers.files import get_abs_path

logger = logging.getLogger(__name__)

# Load secrets at module level (same as before) so os.environ is populated
# regardless of whether bootstrap() or this extension runs first.
_secrets_path = get_abs_path("usr/secrets.env")
if os.path.isfile(_secrets_path):
    load_dotenv(_secrets_path, override=True)


class InitializeGenesis(Extension):
    async def execute(self, **kwargs):
        try:
            from genesis.runtime import GenesisRuntime

            rt = GenesisRuntime.instance()

            if not rt.is_bootstrapped:
                # Fallback: server_startup didn't fire (tests, standalone)
                await rt.bootstrap()

            # Wire references for backward compat
            self.agent.genesis_db = rt.db
            self.agent.genesis_awareness_loop = rt.awareness_loop
            logger.info("Genesis init wired to agent")

        except ImportError:
            logger.warning("Genesis package not available — not installed")
        except Exception:
            logger.exception("Failed to initialize Genesis")
