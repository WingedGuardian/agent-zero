import asyncio
from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
from initialize import initialize_agent
from python.extensions.hist_add_tool_result import _90_save_tool_call_file as save_tool_call_file
from python.helpers.guardrails import log_guardrail_block

MAX_AGENT_DEPTH = 5
SUBAGENT_TIMEOUT = 300  # 5 minutes wall-clock


class Delegation(Tool):

    async def execute(self, message="", reset="", **kwargs):
        # Depth limit check
        if self.agent.number >= MAX_AGENT_DEPTH:
            await log_guardrail_block(
                "call_subordinate", "max_depth_reached",
                self.agent.number, MAX_AGENT_DEPTH,
            )
            return Response(
                message=f"Cannot create subordinate: maximum delegation depth ({MAX_AGENT_DEPTH}) reached. "
                        f"You are agent level {self.agent.number}. Solve the task directly.",
                break_loop=False,
            )

        # create subordinate agent using the data object on this agent and set superior agent to his data object
        if (
            self.agent.get_data(Agent.DATA_NAME_SUBORDINATE) is None
            or str(reset).lower().strip() == "true"
        ):
            # initialize default config
            config = initialize_agent()

            # set subordinate prompt profile if provided, if not, keep original
            agent_profile = kwargs.get("profile", kwargs.get("agent_profile", ""))
            if agent_profile:
                config.profile = agent_profile

            # crate agent
            sub = Agent(self.agent.number + 1, config, self.agent.context)
            # register superior/subordinate
            sub.set_data(Agent.DATA_NAME_SUPERIOR, self.agent)
            self.agent.set_data(Agent.DATA_NAME_SUBORDINATE, sub)

        # add user message to subordinate agent
        subordinate: Agent = self.agent.get_data(Agent.DATA_NAME_SUBORDINATE)  # type: ignore
        subordinate.hist_add_user_message(UserMessage(message=message, attachments=[]))

        # run subordinate monologue with wall-clock timeout
        try:
            result = await asyncio.wait_for(
                subordinate.monologue(), timeout=SUBAGENT_TIMEOUT
            )
        except asyncio.TimeoutError:
            await log_guardrail_block(
                "call_subordinate", "timeout",
                SUBAGENT_TIMEOUT, SUBAGENT_TIMEOUT,
            )
            # Kill orphaned child processes from subordinate's shell sessions
            await _cleanup_agent_shells(subordinate)
            result = f"Subordinate agent timed out after {SUBAGENT_TIMEOUT}s."

        # seal the subordinate's current topic so messages move to `topics` for compression
        subordinate.history.new_topic()

        # hint to use includes for long responses
        additional = None
        if len(result) >= save_tool_call_file.LEN_MIN:
            hint = self.agent.read_prompt("fw.hint.call_sub.md")
            if hint:
                additional = {"hint": hint}

        # result
        return Response(message=result, break_loop=False, additional=additional)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="subagent",
            heading=f"icon://communication {self.agent.agent_name}: Calling Subordinate Agent",
            content="",
            kvps=self.args,
        )


async def _cleanup_agent_shells(agent: Agent) -> None:
    """Kill all shell sessions owned by an agent (and its subordinates recursively)."""
    import logging
    logger = logging.getLogger("guardrails")

    # Clean up this agent's shells
    state = agent.get_data("_cet_state")
    if state and hasattr(state, "shells"):
        for session_id, shell_wrap in list(state.shells.items()):
            try:
                await shell_wrap.session.close()
                logger.info(
                    "Killed orphaned shell session %d for agent %s",
                    session_id, agent.agent_name,
                )
            except Exception as e:
                logger.warning(
                    "Failed to close shell session %d for agent %s: %s",
                    session_id, agent.agent_name, e,
                )
        state.shells.clear()

    # Recurse into subordinate if it exists
    sub = agent.get_data(Agent.DATA_NAME_SUBORDINATE)
    if sub is not None:
        await _cleanup_agent_shells(sub)
