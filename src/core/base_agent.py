"""
Agent 基类和工厂

提供 Agent 的通用接口定义和实例管理。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Optional, List
from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Agent 配置元数据"""
    id: str                           # Agent 唯一标识
    name: str                         # 显示名称
    description: str                  # 描述
    version: str = "0.1.0"            # 版本
    skills_dir: Optional[str] = None  # 技能目录路径
    mcp_services: List[str] = field(default_factory=list)  # 依赖的 MCP 服务
    system_prompt: str = ""           # 系统提示


class BaseAgent(ABC):
    """
    Agent 基类
    
    所有 Agent 实现都应继承此类并实现抽象方法。
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._graph = None
    
    @property
    def agent_id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def description(self) -> str:
        return self.config.description
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化 Agent（加载工具、技能等）"""
        pass
    
    @abstractmethod
    async def chat(self, message: str, thread_id: str = "default") -> str:
        """非流式聊天"""
        pass
    
    @abstractmethod
    async def stream_chat(
        self, 
        message: str, 
        thread_id: str = "default"
    ) -> AsyncGenerator[dict, None]:
        """流式聊天，返回 SSE 事件"""
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取 Agent 元数据"""
        return {
            "id": self.config.id,
            "name": self.config.name,
            "description": self.config.description,
            "version": self.config.version,
            "mcp_services": self.config.mcp_services,
        }


# ============================================================
# Agent 注册表
# ============================================================

# 全局 Agent 注册表: agent_id -> Agent 类
AGENT_REGISTRY: Dict[str, type] = {}

# 全局 Agent 实例缓存: agent_id -> Agent 实例
_agent_instances: Dict[str, BaseAgent] = {}


def register_agent(agent_id: str):
    """
    Agent 注册装饰器
    
    Usage:
        @register_agent("sre")
        class SREAgent(BaseAgent):
            ...
    """
    def decorator(cls: type):
        AGENT_REGISTRY[agent_id] = cls
        return cls
    return decorator


class AgentFactory:
    """Agent 工厂类"""
    
    @staticmethod
    async def get(agent_id: str) -> BaseAgent:
        """
        获取 Agent 实例（单例模式）
        
        Args:
            agent_id: Agent 标识符
        
        Returns:
            Agent 实例
        
        Raises:
            ValueError: Agent 未注册
        """
        # 检查缓存
        if agent_id in _agent_instances:
            return _agent_instances[agent_id]
        
        # 检查注册表
        if agent_id not in AGENT_REGISTRY:
            available = list(AGENT_REGISTRY.keys())
            raise ValueError(
                f"Agent '{agent_id}' 未注册。可用的 Agent: {available}"
            )
        
        # 创建实例
        agent_cls = AGENT_REGISTRY[agent_id]
        agent = agent_cls()
        
        # 初始化
        await agent.initialize()
        
        # 缓存
        _agent_instances[agent_id] = agent
        
        return agent
    
    @staticmethod
    def list_agents() -> List[Dict[str, Any]]:
        """列出所有注册的 Agent"""
        agents = []
        for agent_id, agent_cls in AGENT_REGISTRY.items():
            # 尝试获取元数据
            try:
                if agent_id in _agent_instances:
                    agents.append(_agent_instances[agent_id].get_metadata())
                else:
                    # 临时创建实例获取元数据
                    temp = agent_cls()
                    agents.append(temp.get_metadata())
            except Exception:
                agents.append({"id": agent_id, "name": agent_id})
        return agents
    
    @staticmethod
    def is_registered(agent_id: str) -> bool:
        """检查 Agent 是否已注册"""
        return agent_id in AGENT_REGISTRY
