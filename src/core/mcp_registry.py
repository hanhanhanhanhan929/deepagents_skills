"""
MCP 服务注册和加载机制

支持按 Agent 类型加载不同的 MCP 服务。
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MCPServiceConfig:
    """MCP 服务配置"""
    name: str                            # 服务名称
    transport: str = "stdio"             # 传输方式：stdio / streamable_http / sse
    # stdio 专用
    command: str = "npx"                 # 启动命令
    args: List[str] = field(default_factory=list)   # 命令参数
    env: Dict[str, str] = field(default_factory=dict)  # 环境变量
    # streamable_http / sse 专用
    url: str = ""                        # 服务端点 URL
    headers: Dict[str, str] = field(default_factory=dict)  # HTTP 请求头
    for_agents: List[str] = field(default_factory=list)  # 支持的 Agent 类型


# ============================================================
# MCP 服务注册表
# ============================================================
# 预定义的 MCP 服务配置
MCP_SERVICES: Dict[str, MCPServiceConfig] = {
    # stdio 模式示例（本地启动进程）
    # "amap": MCPServiceConfig(
    #     name="amap",
    #     transport="stdio",
    #     command="npx",
    #     args=["-y", "@amap/amap-maps-mcp-server"],
    #     env={},  # 运行时填充 AMAP_API_KEY
    #     for_agents=["travel"],
    # ),

    # streamable_http 模式示例（连接远程 MCP Server）
    "amap": MCPServiceConfig(
        name="amap",
        transport="streamable_http",
        url="https://mcp.api-inference.modelscope.net/7d6f9c780eaf46/mcp",
        # headers={"Authorization": "Bearer <token>"},  # 若需鉴权可在此添加
        for_agents=["travel"],
    ),
    # 可以添加更多 MCP 服务
    # "prometheus": MCPServiceConfig(
    #     name="prometheus",
    #     transport="streamable_http",
    
    #     url="http://localhost:9090/mcp",
    #     for_agents=["sre"],
    # ),
}


class MCPRegistry:
    """
    MCP 服务注册管理器
    
    管理多个 MCP 服务的配置和工具加载。
    """
    
    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._tools_cache: Dict[str, List] = {}
    
    async def get_tools(self, service_names: List[str]) -> List:
        """
        获取指定 MCP 服务的工具列表
        
        Args:
            service_names: 服务名称列表，如 ["amap"]
        
        Returns:
            合并后的工具列表
        """
        all_tools = []
        
        for name in service_names:
            if name in self._tools_cache:
                all_tools.extend(self._tools_cache[name])
                continue
            
            if name not in MCP_SERVICES:
                logger.warning(f"MCP 服务 '{name}' 未注册")
                continue
            
            tools = await self._load_service_tools(name)
            self._tools_cache[name] = tools
            all_tools.extend(tools)
        
        return all_tools
    
    async def _load_service_tools(self, service_name: str) -> List:
        """加载单个 MCP 服务的工具"""
        config = MCP_SERVICES[service_name]
        
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient

            if config.transport in {"streamable_http", "streamable-http", "http", "sse"}:
                # HTTP 类传输：只需 url + headers
                if not config.url:
                    logger.error(f"MCP 服务 '{service_name}' 使用 {config.transport} 传输但未配置 url")
                    return []
                connection: Dict[str, Any] = {
                    "transport": config.transport,
                    "url": config.url,
                }
                if config.headers:
                    connection["headers"] = config.headers
            else:
                # stdio 传输：command + args + env
                env = dict(config.env)
                # 特殊处理：高德地图需要 API Key
                if service_name == "amap":
                    api_key = os.getenv("AMAP_API_KEY", "")
                    if not api_key:
                        logger.warning("AMAP_API_KEY 未配置，高德地图服务不可用")
                        return []
                    env["AMAP_API_KEY"] = api_key
                    env["AMAP_MAPS_API_KEY"] = api_key
                connection = {
                    "transport": config.transport,
                    "command": config.command,
                    "args": config.args,
                    "env": env,
                }

            # 创建客户端
            client = MultiServerMCPClient({service_name: connection})
            
            tools = await client.get_tools()
            self._clients[service_name] = client
            
            logger.info(f"✅ 已加载 MCP 服务 '{service_name}' 工具: {[t.name for t in tools]}")
            return tools
            
        except ImportError:
            logger.error("未安装 langchain-mcp-adapters")
            return []
        except Exception as e:
            logger.error(f"加载 MCP 服务 '{service_name}' 失败: {e}")
            return []
    
    def get_services_for_agent(self, agent_id: str) -> List[str]:
        """获取指定 Agent 应该使用的 MCP 服务列表"""
        services = []
        for name, config in MCP_SERVICES.items():
            if not config.for_agents or agent_id in config.for_agents:
                services.append(name)
        return services


# 全局注册表实例
_registry: Optional[MCPRegistry] = None


def get_mcp_registry() -> MCPRegistry:
    """获取全局 MCP 注册表实例"""
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry


async def get_mcp_tools(service_names: List[str]) -> List:
    """便捷函数：获取 MCP 工具"""
    registry = get_mcp_registry()
    return await registry.get_tools(service_names)
