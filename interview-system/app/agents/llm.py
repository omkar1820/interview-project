"""Thin AutoGen wrapper. AutoGen is imported lazily so the app (and tests) run without an API key."""
import logging
from typing import Optional

from ..config import get_settings

log = logging.getLogger("llm")


def make_agent(name: str, system_message: str, temperature: float = 0.4):
    from autogen import ConversableAgent

    s = get_settings()
    llm_config = {
        "config_list": [{"model": s.openai_model, "api_key": s.openai_api_key}],
        "temperature": temperature,
        "timeout": 60,
        "cache_seed": None,
    }
    return ConversableAgent(
        name=name,
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
    )


async def ask(agent, prompt: str) -> Optional[str]:
    reply = await agent.a_generate_reply(messages=[{"role": "user", "content": prompt}])
    if isinstance(reply, dict):
        reply = reply.get("content")
    return (reply or "").strip() or None
