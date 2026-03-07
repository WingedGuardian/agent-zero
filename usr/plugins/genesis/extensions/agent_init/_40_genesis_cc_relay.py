"""Genesis CC Relay — bridges messaging channels to CC sessions.

Requires: genesis_db (from _10), genesis_event_bus (from _20)
Provides: genesis_cc_invoker, genesis_session_manager,
          genesis_checkpoint_manager, genesis_cc_reflection_bridge
"""

import logging

from python.helpers.extension import Extension

logger = logging.getLogger("genesis.cc_relay")


class GenesisCCRelay(Extension):
    async def execute(self, **kwargs):
        db = getattr(self.agent, "genesis_db", None)
        event_bus = getattr(self.agent, "genesis_event_bus", None)
        if db is None:
            logger.warning("genesis_db not available -- skipping CC relay init")
            return

        try:
            from genesis.cc.checkpoint import CheckpointManager
            from genesis.cc.invoker import CCInvoker
            from genesis.cc.reflection_bridge import CCReflectionBridge
            from genesis.cc.session_manager import SessionManager

            # 1. Create invoker
            invoker = CCInvoker()
            self.agent.genesis_cc_invoker = invoker
            logger.info("Genesis CC invoker created")

            # 2. Create session manager
            session_mgr = SessionManager(
                db=db, invoker=invoker, event_bus=event_bus,
            )
            self.agent.genesis_session_manager = session_mgr
            logger.info("Genesis session manager created")

            # 3. Create checkpoint manager
            checkpoint_mgr = CheckpointManager(
                db=db, session_manager=session_mgr,
                invoker=invoker, event_bus=event_bus,
            )
            self.agent.genesis_checkpoint_manager = checkpoint_mgr
            logger.info("Genesis checkpoint manager created")

            # 4. Create reflection bridge
            bridge = CCReflectionBridge(
                session_manager=session_mgr, invoker=invoker,
                db=db, event_bus=event_bus,
            )
            self.agent.genesis_cc_reflection_bridge = bridge
            logger.info("Genesis CC reflection bridge created")

            # 5. Wire bridge into awareness loop
            loop = getattr(self.agent, "genesis_awareness_loop", None)
            if loop and hasattr(loop, "set_cc_reflection_bridge"):
                loop.set_cc_reflection_bridge(bridge)
                logger.info("CC reflection bridge injected into awareness loop")

        except ImportError:
            logger.warning(
                "Genesis CC package not available -- skipping relay init",
            )
        except Exception:
            logger.exception("Failed to initialize Genesis CC relay")
