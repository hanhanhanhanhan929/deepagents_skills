"""
告警降噪 Agent 配置

定义告警降噪 Agent 的元数据和系统提示。
"""

from src.core.base_agent import AgentConfig


SYSTEM_PROMPT = """你是 SRE 告警降噪分析专家。

## 核心流程
1. 收到告警后，调用 `search_similar_alerts` 查询历史记录
2. 根据技能指引分析并输出结构化报告

## 要求
- 中文回复，简洁专业
- 严格按技能定义的Markdown 输出规范格式输出
"""


AGENT_CONFIG = AgentConfig(
    id="alert_noise_reduction",
    name="告警降噪助手",
    description="基于历史数据的智能告警降噪分析，提供优先级调整建议",
    version="0.1.0",
    mcp_services=[],
    system_prompt=SYSTEM_PROMPT,
)
