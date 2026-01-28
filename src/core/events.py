"""
SSE 事件构建工具

为前端提供结构化的 Server-Sent Events 事件。
"""

import json
from typing import Any, Dict, Optional
from datetime import datetime


class EventBuilder:
    """SSE 事件构建器，生成标准化的事件格式"""
    
    @staticmethod
    def _sanitize_data(data: Any) -> Any:
        """清理数据以确保 JSON 可序列化"""
        if isinstance(data, dict):
            return {k: EventBuilder._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [EventBuilder._sanitize_data(v) for v in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            # 对于不可序列化的对象，转换为字符串
            return str(data)
    
    @staticmethod
    def _build_event(event_type: str, data: Any, timestamp: bool = True) -> dict:
        """
        构建标准事件格式
        
        Args:
            event_type: 事件类型
            data: 事件数据（dict 会被 JSON 序列化，str 直接返回）
            timestamp: 是否包含时间戳
        
        Returns:
            符合 SSE 格式的 dict
        """
        if isinstance(data, dict):
            # 清理数据
            data = EventBuilder._sanitize_data(data)
            if timestamp:
                data["timestamp"] = int(datetime.now().timestamp() * 1000)
            event_data = json.dumps(data, ensure_ascii=False)
        else:
            event_data = str(data)
        
        return {
            "event": event_type,
            "data": event_data
        }
    
    # ============================================================
   # Metadata Events
    # ============================================================
    
    @classmethod
    def metadata(cls, thread_id: str, agent_id: str = "travel") -> dict:
        """会话元数据事件"""
        return cls._build_event("metadata", {
            "thread_id": thread_id,
            "agent_id": agent_id
        })
    
    # ============================================================
    # Agent Events
    # ============================================================
    
    @classmethod
    def agent_thinking(cls) -> dict:
        """Agent 思考中事件"""
        return cls._build_event("agent:thinking", {
            "status": "thinking"
        })
    
    # ============================================================
    # Tool Events
    # ============================================================
    
    @classmethod
    def tool_start(cls, tool_name: str, args: Optional[Dict] = None) -> dict:
        """工具调用开始事件"""
        return cls._build_event("tool:start", {
            "tool": tool_name,
            "args": args or {}
        })
    
    @classmethod
    def tool_result(cls, tool_name: str, result: str, truncated: bool = False) -> dict:
        """工具调用结果事件"""
        # 如果结果太长，截断显示
        if len(result) > 500 and not truncated:
            result = result[:500] + "... (truncated)"
            truncated = True
        
        return cls._build_event("tool:result", {
            "tool": tool_name,
            "result": result,
            "truncated": truncated
        })
    
    # ============================================================
    # TodoList Events
    # ============================================================
    
    @classmethod
    def todo_created(cls, todos: list[str]) -> dict:
        """TodoList 创建事件"""
        return cls._build_event("todo:created", {
            "todos": todos,
            "count": len(todos)
        })
    
    @classmethod
    def todo_updated(cls, todo_id: int, status: str, description: str = "") -> dict:
        """TodoList 更新事件"""
        return cls._build_event("todo:updated", {
            "todo_id": todo_id,
            "status": status,  # "in_progress", "completed", "failed"
            "description": description
        })
    
    # ============================================================
    # Skill Events
    # ============================================================
    
    @classmethod
    def skill_loaded(cls, skill_name: str, skill_path: str, description: str = "") -> dict:
        """技能加载事件"""
        return cls._build_event("skill:loaded", {
            "skill": skill_name,
            "path": skill_path,
            "description": description
        })
    
    # ============================================================
    # Message Events
    # ============================================================
    
    @classmethod
    def message_chunk(cls, content: str) -> dict:
        """消息内容片段事件（不带时间戳，提高性能）"""
        return {
            "event": "message:chunk",
            "data": content
        }
    
    @classmethod
    def message_complete(cls, message: str) -> dict:
        """消息完成事件"""
        return cls._build_event("message:complete", {
            "message": message
        })
    
    # ============================================================
    # Control Events
    # ============================================================
    
    @classmethod
    def done(cls, message_count: Optional[int] = None) -> dict:
        """流结束事件"""
        data = {"status": "completed"}
        if message_count is not None:
            data["message_count"] = message_count
        return cls._build_event("done", data)
    
    @classmethod
    def error(cls, error_message: str, error_type: Optional[str] = None) -> dict:
        """错误事件"""
        return cls._build_event("error", {
            "error": error_message,
            "type": error_type or "UnknownError"
        })


# ============================================================
# Event Parser Helpers (for testing)
# ============================================================

def parse_tool_call_from_event(event: dict) -> Optional[dict]:
    """
    从 LangGraph 事件中提取工具调用信息
    
    Args:
        event: LangGraph astream_events 返回的事件
    
    Returns:
        工具调用信息 dict 或 None
    """
    if event.get("event") == "on_tool_start":
        return {
            "name": event.get("name"),
            "input": event.get("data", {}).get("input")
        }
    return None


def parse_tool_result_from_event(event: dict) -> Optional[dict]:
    """
    从 LangGraph 事件中提取工具结果
    
    Args:
        event: LangGraph astream_events 返回的事件
    
    Returns:
        工具结果信息 dict 或 None
    """
    if event.get("event") == "on_tool_end":
        return {
            "name": event.get("name"),
            "output": event.get("data", {}).get("output")
        }
    return None
