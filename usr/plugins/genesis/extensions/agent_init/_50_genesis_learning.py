"""Genesis learning infrastructure wire-up extension.

Runs during agent_init (after _30 perception, _40 cc relay) to:
1. Create MemoryStore (Qdrant + embeddings + linker)
2. Replace stub signal collectors with real ones
3. Create triage pipeline and store on agent
4. Start daily calibration + auto-memory harvest scheduler

Stores on agent: genesis_memory_store, genesis_triage_pipeline,
                 genesis_learning_scheduler
"""

import logging
from functools import partial
from pathlib import Path

from python.helpers.extension import Extension

logger = logging.getLogger("genesis.extensions.learning")


class GenesisLearning(Extension):
    async def execute(self, **kwargs):
        try:
            # ── prerequisites ───────────────────────────────────────────
            db = getattr(self.agent, "genesis_db", None)
            event_bus = getattr(self.agent, "genesis_event_bus", None)
            router = getattr(self.agent, "genesis_router", None)
            loop = getattr(self.agent, "genesis_awareness_loop", None)

            if db is None or router is None:
                logger.warning(
                    "Genesis learning skipped — missing prerequisites "
                    "(db=%s, router=%s)", db is not None, router is not None,
                )
                return

            # ── A. MemoryStore ──────────────────────────────────────────
            memory_store = None
            try:
                from qdrant_client import QdrantClient

                from genesis.memory.embeddings import EmbeddingProvider
                from genesis.memory.linker import MemoryLinker
                from genesis.memory.store import MemoryStore

                qdrant = QdrantClient(url="http://localhost:6333", timeout=5)
                embedding_provider = EmbeddingProvider()
                linker = MemoryLinker(qdrant_client=qdrant, db=db)
                memory_store = MemoryStore(
                    embedding_provider=embedding_provider,
                    qdrant_client=qdrant,
                    db=db,
                    linker=linker,
                )
                self.agent.genesis_memory_store = memory_store
                logger.info("Genesis MemoryStore created")
            except Exception:
                logger.warning(
                    "MemoryStore creation failed (Qdrant down?) — "
                    "continuing without vector memory",
                    exc_info=True,
                )

            # ── B. Replace stub collectors ──────────────────────────────
            if loop is not None:
                from genesis.awareness.signals import (
                    ConversationCollector,
                    OutreachEngagementCollector,
                    ReconFindingsCollector,
                    StrategicTimerCollector,
                )
                from genesis.learning.signals.budget import BudgetCollector
                from genesis.learning.signals.critical_failure import (
                    CriticalFailureCollector,
                )
                from genesis.learning.signals.error_spike import ErrorSpikeCollector
                from genesis.learning.signals.memory_backlog import (
                    MemoryBacklogCollector,
                )
                from genesis.learning.signals.task_quality import TaskQualityCollector
                from genesis.observability.health import (
                    probe_db,
                    probe_ollama,
                    probe_qdrant,
                )

                probes = [
                    partial(probe_db, db),
                    probe_qdrant,
                    probe_ollama,
                ]

                collectors = [
                    ConversationCollector(),        # stub — needs AZ conversation data
                    TaskQualityCollector(db),        # REAL
                    OutreachEngagementCollector(),   # stub — needs outreach MCP
                    ReconFindingsCollector(),        # stub — needs recon MCP
                    MemoryBacklogCollector(db),      # REAL
                    BudgetCollector(db),             # REAL
                    ErrorSpikeCollector(db),         # REAL
                    CriticalFailureCollector(probes),  # REAL
                    StrategicTimerCollector(),       # stub — needs awareness_ticks query
                ]
                loop.replace_collectors(collectors)
                logger.info(
                    "Replaced stub collectors with %d real + %d stub",
                    5, 4,
                )

            # ── C. Learning components ──────────────────────────────────
            from genesis.learning.classification.delta import DeltaAssessor
            from genesis.learning.classification.outcome import OutcomeClassifier
            from genesis.learning.observation_writer import ObservationWriter
            from genesis.learning.pipeline import build_triage_pipeline
            from genesis.learning.triage.calibration import TriageCalibrator
            from genesis.learning.triage.classifier import TriageClassifier

            triage_classifier = TriageClassifier(router)
            outcome_classifier = OutcomeClassifier(router)
            delta_assessor = DeltaAssessor(router)
            observation_writer = ObservationWriter(memory_store=memory_store)

            # ── D. Triage pipeline ──────────────────────────────────────
            pipeline = build_triage_pipeline(
                db=db,
                triage_classifier=triage_classifier,
                outcome_classifier=outcome_classifier,
                delta_assessor=delta_assessor,
                observation_writer=observation_writer,
                event_bus=event_bus,
            )
            self.agent.genesis_triage_pipeline = pipeline
            logger.info("Genesis triage pipeline created")

            # ── E. Calibration + harvest scheduler ──────────────────────
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger

            calibrator = TriageCalibrator(
                router, db,
                memory_store=memory_store,
                event_bus=event_bus,
            )

            learning_scheduler = AsyncIOScheduler()

            learning_scheduler.add_job(
                calibrator.run_daily_calibration,
                CronTrigger(hour=3, minute=0),
                id="triage_calibration_daily",
                max_instances=1,
                misfire_grace_time=3600,
            )

            # ── F. Auto-memory harvest ──────────────────────────────────
            from genesis.learning.harvesting.auto_memory import harvest_auto_memory

            async def _harvest_and_store():
                try:
                    memory_dir = (
                        Path.home() / ".claude" / "projects"
                        / "-home-ubuntu-genesis" / "memory"
                    )
                    items = harvest_auto_memory(memory_dir)
                    for item in items:
                        await observation_writer.write(
                            db,
                            source="auto_memory_harvest",
                            type="cc_memory_file",
                            content=item.get("content", "")[:2000],
                            priority="low",
                        )
                    if items:
                        logger.info("Harvested %d auto-memory items", len(items))
                except Exception:
                    logger.exception("Auto-memory harvest failed")

            learning_scheduler.add_job(
                _harvest_and_store,
                IntervalTrigger(hours=6),
                id="auto_memory_harvest",
                max_instances=1,
                misfire_grace_time=3600,
            )

            learning_scheduler.start()
            self.agent.genesis_learning_scheduler = learning_scheduler
            logger.info("Genesis learning scheduler started (calibration + harvest)")

        except ImportError:
            logger.warning(
                "Genesis learning package not available — "
                "genesis.learning not installed"
            )
        except Exception:
            logger.exception("Failed to initialize Genesis learning")
