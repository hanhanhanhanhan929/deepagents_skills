"""
告警降噪 Agent 实现

基于 Milvus 向量数据库的智能告警降噪分析。
"""

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
from .tools import get_alert_tools


@register_agent("alert_noise_reduction")
class AlertNoiseReductionAgent(BaseAgent):
    """
    告警降噪智能助手
    
    通过向量数据库检索历史告警处理记录，提供智能降噪建议。
    """
    
    def __init__(self):
        super().__init__(AGENT_CONFIG)
        self._skills_dir = None
    
    async def initialize(self) -> None:
        """初始化 Agent"""
        # 1. 配置技能目录
        self._skills_dir = os.path.join(os.path.dirname(__file__), "skills_data")
        
        # 2. 配置 LLM
        llm = ChatOpenAI(
            model=app_config.MODEL_NAME,
            temperature=app_config.MODEL_TEMPERATURE,
            api_key=app_config.ALIYUN_API_KEY,
            base_url=app_config.ALIYUN_BASE_URL,
        )
        
        # 3. 配置 Backend
        project_root = os.getcwd()
        backend = FilesystemBackend(root_dir=project_root)
        
        # 4. 获取工具
        tools = await self._get_tools()
        
        # 5. 创建 deep agent
        self._graph = create_deep_agent(
            model=llm,
            tools=tools,
            system_prompt=self.config.system_prompt,
            backend=backend,
            skills=[self._skills_dir] if os.path.exists(self._skills_dir) else [],
            checkpointer=MemorySaver(),
        )
        
        self._graph = self._graph.with_config({"recursion_limit": 100})
        print(f"✅ {self.name} 初始化完成 (skills: {self._skills_dir})")
    
    async def _get_tools(self) -> list:
        """获取告警降噪相关工具"""
        tools = []
        
        # 添加 Milvus 搜索工具
        tools.extend(get_alert_tools())
        print(f"✅ 已加载告警降噪工具: {[t.name for t in tools]}")
        
        # 加载 MCP 工具（如果有）
        if self.config.mcp_services:
            try:
                mcp_tools = await get_mcp_tools(self.config.mcp_services)
                tools.extend(mcp_tools)
                print(f"✅ 已加载 MCP 工具: {[t.name for t in mcp_tools]}")
            except Exception as e:
                print(f"⚠️ 加载 MCP 工具失败: {e}")
        
        return tools
    
    async def chat(self, message: str, thread_id: str = "default") -> str:
        """非流式聊天"""
        if self._graph is None:
            await self.initialize()
        
        config_dict = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100,
        }
        
        result = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config_dict,
        )
        
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                return msg.content
        
        return "抱歉，我暂时无法处理您的请求。"
    
    async def stream_chat(
        self, 
        message: str, 
        thread_id: str = "default"
    ) -> AsyncGenerator[dict, None]:
        """流式聊天"""
        if self._graph is None:
            await self.initialize()
        
        config_dict = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100,
        }
        
        # 发送元数据
        yield EventBuilder.metadata(thread_id, self.agent_id)
        
        active_tools = {}
        text_buffer = TextBuffer(flush_threshold=150)
        
        async for event in self._graph.astream_events(
            {"messages": [HumanMessage(content=message)]},
            config_dict,
            version="v2",
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
                run_id = event.get("run_id")
                
                if run_id:
                    active_tools[run_id] = tool_name
                
                # 检测 SKILL.md 读取
                if tool_name == "read_file":
                    path = tool_input.get("path", "") if isinstance(tool_input, dict) else str(tool_input)
                    if "SKILL.md" in path:
                        skill_name = path.split("/")[-2] if "/" in path else "unknown"
                        yield EventBuilder.skill_loaded(skill_name, path)
                        continue
                
                # TodoList 处理
                elif tool_name == "write_todos":
                    raw_todos = tool_input.get("todos", []) if isinstance(tool_input, dict) else []
                    current_todos = []
                    for t in raw_todos:
                        if isinstance(t, dict):
                            content = t.get("content") or t.get("description") or t.get("task") or ""
                            status = t.get("status", "pending")
                            if content:
                                current_todos.append({"content": content, "status": status})
                    
                    prev_todos = active_tools.get("_todos", [])
                    new_todos = [
                        todo["content"] 
                        for i, todo in enumerate(current_todos) 
                        if i >= len(prev_todos)
                    ]
                    
                    if new_todos:
                        yield EventBuilder.todo_created(new_todos)
                    
                    for i, todo in enumerate(current_todos):
                        if i < len(prev_todos):
                            prev_status = prev_todos[i].get("status", "pending")
                            if prev_status != todo["status"]:
                                yield EventBuilder.todo_updated(i, todo["status"], todo["content"])
                    
                    active_tools["_todos"] = current_todos
                else:
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
        """列出可用技能"""
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
        """解析 SKILL.md 获取描述"""
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
