"""
配置管理模块

集中管理所有配置项，包括 LLM、API Keys 等。
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """应用配置类。"""
    
    # 阿里云 OpenAI 兼容 API 配置
    ALIYUN_API_KEY: str = os.getenv("ALIYUN_API_KEY", "")
    ALIYUN_BASE_URL: str = os.getenv(
        "ALIYUN_BASE_URL", 
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    # 模型配置
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3-coder-plus")
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    
    # LangSmith 配置
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "travel-planner-agent")
    
    # 高德地图 MCP 配置
    AMAP_API_KEY: str = os.getenv("AMAP_API_KEY", "")
    
    # Milvus 向量数据库配置
    MILVUS_ADDRESS: str = os.getenv("MILVUS_ADDRESS", "localhost:19530")
    MILVUS_USERNAME: str = os.getenv("MILVUS_USERNAME", "")
    MILVUS_PASSWORD: str = os.getenv("MILVUS_PASSWORD", "")
    MILVUS_DATABASE: str = os.getenv("MILVUS_DATABASE", "sre_events_f9b8ff38_5f99_4ebf_8795_2dfbf12acdab")
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "")  # 留空则搜索所有 collection
    MILVUS_VECTOR_FIELD: str = os.getenv("MILVUS_VECTOR_FIELD", "vector")
    MILVUS_TEXT_FIELD: str = os.getenv("MILVUS_TEXT_FIELD", "summary")
    
    # Embedding 模型配置
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    
    # Rerank 模型配置
    RERANK_BASE_URL: str = os.getenv("RERANK_BASE_URL", "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank")
    RERANK_API_KEY: str = os.getenv("RERANK_API_KEY", "")
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "gte-rerank-v2")
    
    @classmethod
    def validate(cls) -> list[str]:
        """
        验证必需的配置项。
        
        Returns:
            缺失的配置项列表
        """
        missing = []
        
        if not cls.ALIYUN_API_KEY:
            missing.append("ALIYUN_API_KEY")
        
        return missing
    
    @classmethod
    def setup_langsmith(cls):
        """配置 LangSmith 追踪。"""
        if cls.LANGSMITH_API_KEY and cls.LANGSMITH_TRACING:
            os.environ["LANGSMITH_API_KEY"] = cls.LANGSMITH_API_KEY
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_PROJECT"] = cls.LANGSMITH_PROJECT


# 应用启动时验证配置
def init_config():
    """初始化配置并验证。"""
    missing = Config.validate()
    if missing:
        print(f"⚠️ 警告: 以下配置项未设置: {', '.join(missing)}")
    
    Config.setup_langsmith()
    return Config


config = init_config()
