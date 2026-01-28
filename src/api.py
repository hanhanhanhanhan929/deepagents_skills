"""
FastAPI 服务入口

提供多 Agent REST API 访问。
支持流式 (SSE) 和非流式两种响应方式。
通过 /agents/{agent_type}/ 路由访问不同的 Agent。
"""

import uuid
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.config import config

 
# ============================================================
# 数据模型
# ============================================================

class ChatRequest(BaseModel):
    """聊天请求模型。"""
    message: str = Field(..., description="用户消息内容", min_length=1)
    thread_id: Optional[str] = Field(
        default=None, 
        description="会话线程ID，用于保持对话上下文。如不提供则自动生成"
    )


class ChatResponse(BaseModel):
    """聊天响应模型（非流式）。"""
    message: str = Field(..., description="助手回复内容")
    thread_id: str = Field(..., description="会话线程ID")
    agent_id: str = Field(..., description="处理请求的 Agent ID")


class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str = "ok"
    version: str = "0.3.0"
    framework: str = "multi-agent"


class AgentInfo(BaseModel):
    """Agent 信息模型。"""
    id: str
    name: str
    description: str
    version: str = "0.1.0"


# ============================================================
# 生命周期管理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    print("🚀 正在启动多 Agent API 服务...")
    
    # 导入以触发 Agent 注册
    from src.agents import AGENT_REGISTRY, list_agents
    
    print(f"📋 已注册 {len(AGENT_REGISTRY)} 个 Agent: {list(AGENT_REGISTRY.keys())}")
    print("✅ 服务启动完成")
    print(f"📍 API 文档: http://localhost:8000/docs")
    
    yield
    
    print("👋 服务正在关闭...")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="多 Agent 智能服务平台",
    description="""
## 🤖 多 Agent 智能服务平台

基于 LangChain/Deepagents 构建的多 Agent Web 服务框架。

### 可用 Agent

- **travel** - 🗺️ 旅游行程策划助手：目的地研究、行程规划、交通指南
- **sre** - 🛡️ SRE 智能助手：告警分析、根因定位、事件响应

### API 端点

- `GET /agents` - 获取所有可用 Agent 列表
- `POST /agents/{agent_type}/chat` - 非流式聊天
- `POST /agents/{agent_type}/chat/stream` - 流式聊天（SSE）
- `GET /agents/{agent_type}/skills` - 获取指定 Agent 的技能列表
- `GET /health` - 健康检查

### 使用示例

```bash
# 获取 Agent 列表
curl http://localhost:8000/agents

# 与旅游 Agent 聊天
curl -X POST http://localhost:8000/agents/travel/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message": "帮我规划一个杭州3日游"}'

# 与 SRE Agent 聊天
curl -X POST http://localhost:8000/agents/sre/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message": "分析这个告警: CPU使用率超过90%"}'
```
    """,
    version="0.3.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 系统路由
# ============================================================

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查端点。"""
    return HealthResponse()


@app.get("/agents", tags=["Agent 管理"])
async def list_agents():
    """
    获取所有可用 Agent 列表。
    
    返回每个 Agent 的 ID、名称、描述等元数据。
    """
    from src.agents import list_agents as get_agents
    
    agents = get_agents()
    return {
        "agents": agents,
        "count": len(agents)
    }


# ============================================================
# Agent 聊天路由
# ============================================================

@app.post("/agents/{agent_type}/chat", response_model=ChatResponse, tags=["聊天"])
async def agent_chat(
    agent_type: str = Path(..., description="Agent 类型，如 'travel' 或 'sre'"),
    request: ChatRequest = None
):
    """
    非流式聊天接口。
    
    一次性返回完整的助手回复。
    """
    from src.agents import get_agent_async, AgentFactory
    
    # 验证 Agent 存在
    if not AgentFactory.is_registered(agent_type):
        from src.core.base_agent import AGENT_REGISTRY
        available = list(AGENT_REGISTRY.keys())
        raise HTTPException(
            status_code=404, 
            detail=f"Agent '{agent_type}' 不存在。可用的 Agent: {available}"
        )
    
    thread_id = request.thread_id or str(uuid.uuid4())
    
    try:
        agent = await get_agent_async(agent_type)
        response = await agent.chat(request.message, thread_id)
        return ChatResponse(
            message=response, 
            thread_id=thread_id,
            agent_id=agent_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理请求时发生错误: {str(e)}")


@app.post("/agents/{agent_type}/chat/stream", tags=["聊天"])
async def agent_chat_stream(
    agent_type: str = Path(..., description="Agent 类型"),
    request: ChatRequest = None
):
    """
    流式聊天接口 (Server-Sent Events)。
    
    实时推送助手回复内容和结构化事件。
    
    **事件类型**:
    - `metadata` - 会话元数据
    - `message:chunk` - 消息内容片段
    - `tool:start` - 工具调用开始
    - `tool:result` - 工具调用结果
    - `todo:created` - TodoList创建
    - `todo:updated` - TodoList更新
    - `skill:loaded` - 技能加载
    - `done` - 流结束
    """
    from src.agents import get_agent_async, AgentFactory
    from src.core.events import EventBuilder
    
    # 验证 Agent 存在
    if not AgentFactory.is_registered(agent_type):
        from src.core.base_agent import AGENT_REGISTRY
        available = list(AGENT_REGISTRY.keys())
        raise HTTPException(
            status_code=404, 
            detail=f"Agent '{agent_type}' 不存在。可用的 Agent: {available}"
        )
    
    thread_id = request.thread_id or str(uuid.uuid4())
    
    async def event_generator():
        """生成 SSE 事件流。"""
        try:
            agent = await get_agent_async(agent_type)
            
            async for event in agent.stream_chat(request.message, thread_id):
                yield event
            
            yield EventBuilder.done()
            
        except Exception as e:
            yield EventBuilder.error(str(e), type(e).__name__)
    
    return EventSourceResponse(event_generator())


@app.get("/agents/{agent_type}/skills", tags=["Agent 管理"])
async def get_agent_skills(
    agent_type: str = Path(..., description="Agent 类型")
):
    """
    获取指定 Agent 的可用技能列表。
    """
    from src.agents import get_agent_async, AgentFactory
    
    # 验证 Agent 存在
    if not AgentFactory.is_registered(agent_type):
        from src.core.base_agent import AGENT_REGISTRY
        available = list(AGENT_REGISTRY.keys())
        raise HTTPException(
            status_code=404, 
            detail=f"Agent '{agent_type}' 不存在。可用的 Agent: {available}"
        )
    
    try:
        agent = await get_agent_async(agent_type)
        skills = agent.list_skills() if hasattr(agent, 'list_skills') else []
        return {
            "agent_id": agent_type,
            "skills": skills,
            "count": len(skills)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# 开发模式入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
