---
name: agent-development-guide
description: 创建新 Agent 的开发指南，包含目录结构、代码模板、技能配置和验证步骤
globs:
  - src/agents/**/*.py
  - src/agents/**/skills_data/**/*.md
  - src/agents/__init__.py
---

# Agent 开发指南

当用户要求创建新 Agent 时，按照以下步骤和模板操作。

## 目录结构

```
src/agents/{agent_name}/
├── __init__.py          # 模块入口
├── agent.py             # Agent 核心实现
├── config.py            # 配置和元数据
├── tools.py             # Agent 专用工具（可选）
└── skills_data/         # 技能目录
    └── {skill-name}/
        └── SKILL.md
```

## 步骤一：创建 config.py

```python
from src.core.base_agent import AgentConfig

SYSTEM_PROMPT = """你是一位专业的 {角色描述}。

## 核心流程
1. 收到请求后，调用相关工具
2. 根据技能指引分析并输出结构化报告

## 要求
- 中文回复，简洁专业
- 严格按技能定义的格式输出
"""

AGENT_CONFIG = AgentConfig(
    id="agent_name",           # API 路由标识符
    name="Agent 显示名称",
    description="Agent 功能描述",
    version="0.1.0",
    mcp_services=[],           # MCP 服务列表
    system_prompt=SYSTEM_PROMPT,
)
```

## 步骤二：创建 agent.py

```python
import os
from typing import AsyncGenerator, List, Dict
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage

from src.core.base_agent import BaseAgent, register_agent
from src.core.mcp_registry import get_mcp_tools
from src.core.events import EventBuilder
from src.core.text_buffer import TextBuffer
from src.config import config as app_config
from .config import AGENT_CONFIG


@register_agent("agent_name")  # 必须与 config.py 中的 id 一致
class AgentNameAgent(BaseAgent):
    def __init__(self):
        super().__init__(AGENT_CONFIG)
        self._skills_dir = None
    
    async def initialize(self) -> None:
        self._skills_dir = os.path.join(os.path.dirname(__file__), "skills_data")
        
        llm = ChatOpenAI(
            model=app_config.MODEL_NAME,
            temperature=app_config.MODEL_TEMPERATURE,
            api_key=app_config.ALIYUN_API_KEY,
            base_url=app_config.ALIYUN_BASE_URL,
        )
        
        backend = FilesystemBackend(root_dir=os.getcwd())
        tools = await self._get_tools()
        
        self._graph = create_deep_agent(
            model=llm,
            tools=tools,
            system_prompt=self.config.system_prompt,
            backend=backend,
            skills=[self._skills_dir],
            checkpointer=MemorySaver(),
        )
        self._graph = self._graph.with_config({"recursion_limit": 100})
        print(f"✅ {self.name} 初始化完成 (skills: {self._skills_dir})")
    
    async def _get_tools(self) -> list:
        from .tools import get_agent_tools
        tools = get_agent_tools()
        
        if self.config.mcp_services:
            try:
                mcp_tools = await get_mcp_tools(self.config.mcp_services)
                tools.extend(mcp_tools)
            except Exception as e:
                print(f"⚠️ 加载 MCP 工具失败: {e}")
        return tools
    
    async def chat(self, message: str, thread_id: str = "default") -> str:
        if self._graph is None:
            await self.initialize()
        
        result = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            {"configurable": {"thread_id": thread_id}, "recursion_limit": 100},
        )
        
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                return msg.content
        return "抱歉，我暂时无法处理您的请求。"
    
    async def stream_chat(self, message: str, thread_id: str = "default") -> AsyncGenerator[dict, None]:
        if self._graph is None:
            await self.initialize()
        
        config_dict = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
        yield EventBuilder.metadata(thread_id, self.agent_id)
        
        text_buffer = TextBuffer(flush_threshold=150)
        
        async for event in self._graph.astream_events(
            {"messages": [HumanMessage(content=message)]}, config_dict, version="v2"
        ):
            event_type = event.get("event")
            
            if event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    for formatted_chunk in text_buffer.add(chunk.content):
                        yield EventBuilder.message_chunk(formatted_chunk)
            
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                
                if tool_name == "read_file":
                    path = tool_input.get("path", "") if isinstance(tool_input, dict) else str(tool_input)
                    if "SKILL.md" in path:
                        skill_name = path.split("/")[-2] if "/" in path else "unknown"
                        yield EventBuilder.skill_loaded(skill_name, path)
                        continue
                yield EventBuilder.tool_start(tool_name, tool_input)
            
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", "")
                if tool_name not in ["read_file", "read_todos", "write_todos"]:
                    yield EventBuilder.tool_result(tool_name, str(tool_output))
        
        remaining = text_buffer.flush()
        if remaining:
            yield EventBuilder.message_chunk(remaining)
    
    def list_skills(self) -> List[Dict[str, str]]:
        skills = []
        if self._skills_dir and os.path.exists(self._skills_dir):
            for entry in os.listdir(self._skills_dir):
                entry_path = os.path.join(self._skills_dir, entry)
                skill_md = os.path.join(entry_path, "SKILL.md")
                if os.path.isdir(entry_path) and os.path.exists(skill_md):
                    description = self._parse_skill_description(skill_md)
                    skills.append({"name": entry, "description": description})
        return skills
    
    def _parse_skill_description(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].split("\n"):
                        if line.startswith("description:"):
                            return line.split(":", 1)[1].strip()
            return f"专业技能: {os.path.basename(os.path.dirname(path))}"
        except Exception:
            return ""
```

## 步骤三：创建 __init__.py

```python
from .agent import AgentNameAgent
from .config import AGENT_CONFIG

__all__ = ["AgentNameAgent", "AGENT_CONFIG"]
```

## 步骤四：注册 Agent

在 `src/agents/__init__.py` 中添加：

```python
from src.agents.{agent_name} import AgentNameAgent
```

## 步骤五：创建技能文件

创建 `skills_data/{skill-name}/SKILL.md`：

```markdown
---
name: skill-name
description: 技能简短描述
---

# 技能名称

## 流程
1. 步骤一
2. 步骤二

## 输出模板
[定义结构化输出格式]
```

**命名规范**：使用小写字母和连字符，如 `noise-reduction-analysis`

## 步骤六：创建工具（可选）

```python
from langchain_core.tools import tool

@tool
def my_tool(query: str, top_k: int = 5) -> str:
    """工具描述（会显示给 LLM）。
    
    Args:
        query: 查询内容
        top_k: 返回数量
    """
    return "结果"

def get_agent_tools() -> list:
    return [my_tool]
```

## 验证

```bash
# 验证注册
uv run python -c "from src.agents import AGENT_REGISTRY; print(list(AGENT_REGISTRY.keys()))"

# 启动测试
uv run uvicorn src.api:app --port 8001

# API 测试
curl http://localhost:8001/agents | jq
curl -X POST http://localhost:8001/agents/{agent_name}/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

## 参考示例

项目中的 `src/agents/alert_noise_reduction/` 是完整示例，包含：
- Milvus 向量搜索工具
- DashScope Rerank 集成
- 多技能配置
