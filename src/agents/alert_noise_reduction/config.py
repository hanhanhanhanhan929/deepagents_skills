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
    mcp_services=["amap"],
    system_prompt=SYSTEM_PROMPT,
)

SYSTEM_PROMPT_CHAT="""
# Role (角色设定)
你是一个专业、高效、逻辑严密的顶级AI助手。你的目标是通过提供准确、深入且具有建设性的回答，帮助用户解决问题。你具备跨领域的知识，尤其擅长逻辑分析、技术解答和复杂问题的拆解。

## 要求
- 中文回复，简洁专业
- 严格按技能定义的Markdown 输出规范格式输出
"""

AGENT_CONFIG_CHAT = AgentConfig(
    id="Intelligent_Chatbot",
    name="智能聊天机器人",
    description="基于大模型的聊天机器人",
    version="0.1.0",
    mcp_services=["amap"],
    system_prompt=SYSTEM_PROMPT_CHAT,
)




