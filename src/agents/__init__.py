"""
Agent 模块

包含所有可用的 Agent 实现。
"""

from src.core.base_agent import AGENT_REGISTRY, AgentFactory

# 导入所有 Agent 以触发注册
from src.agents.alert_noise_reduction import AlertNoiseReductionAgent


def get_agent(agent_id: str):
    """获取 Agent 实例的便捷函数"""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(AgentFactory.get(agent_id))


async def get_agent_async(agent_id: str):
    """异步获取 Agent 实例"""
    return await AgentFactory.get(agent_id)


def list_agents():
    """列出所有注册的 Agent"""
    return AgentFactory.list_agents()


__all__ = [
    "AGENT_REGISTRY",
    "AgentFactory", 
    "AlertNoiseReductionAgent",
    "get_agent",
    "get_agent_async",
    "list_agents",
]
