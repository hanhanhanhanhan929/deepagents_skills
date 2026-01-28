"""
核心框架层

提供 Agent 构建的通用基础设施：
- BaseAgent: Agent 基类
- MCPRegistry: MCP 服务注册
- EventBuilder: SSE 事件构建器
- TextBuffer: 流式输出文本缓冲器
"""

from .base_agent import BaseAgent, AgentFactory, AGENT_REGISTRY
from .mcp_registry import MCPRegistry, get_mcp_tools
from .events import EventBuilder
from .text_buffer import TextBuffer, format_stream_output

__all__ = [
    "BaseAgent",
    "AgentFactory", 
    "AGENT_REGISTRY",
    "MCPRegistry",
    "get_mcp_tools",
    "EventBuilder",
    "TextBuffer",
    "format_stream_output",
]
