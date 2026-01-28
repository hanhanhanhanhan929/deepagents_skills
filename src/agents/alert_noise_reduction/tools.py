"""
告警降噪 Agent 工具

提供 Milvus 向量数据库查询功能。
"""

import os
import requests
from typing import List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.config import config as app_config

# 设置 DashScope API Key
os.environ["DASHSCOPE_API_KEY"] = app_config.EMBEDDING_API_KEY or app_config.ALIYUN_API_KEY


class AlertSearchResult(BaseModel):
    """告警搜索结果"""
    alert_name: str = Field(description="告警名称")
    alert_content: str = Field(description="告警内容")
    similarity: float = Field(description="相似度 (0-1)")
    resolution: str = Field(description="处理方式")
    outcome: str = Field(description="处理结果")
    priority_change: Optional[str] = Field(default=None, description="优先级变更（升级/降级/维持）")
    timestamp: Optional[str] = Field(default=None, description="处理时间")


def _get_embedding_vector(text: str) -> List[float]:
    """使用 DashScope SDK 获取文本向量"""
    import dashscope
    from dashscope import TextEmbedding
    
    resp = TextEmbedding.call(
        model=app_config.EMBEDDING_MODEL,
        input=text,
        dimension=1024,  # 使用 1024 维度
    )
    
    if resp.status_code != 200:
        raise Exception(f"Embedding API 调用失败: {resp.code} - {resp.message}")
    
    return resp.output['embeddings'][0]['embedding']


def _rerank_results(query: str, documents: List[str], top_n: int = 5) -> List[dict]:
    """使用 Rerank API 对结果进行重排序"""
    url = app_config.RERANK_BASE_URL
    api_key = app_config.RERANK_API_KEY or app_config.EMBEDDING_API_KEY or app_config.ALIYUN_API_KEY
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": app_config.RERANK_MODEL,
        "input": {
            "query": query,
            "documents": documents,
        },
        "parameters": {
            "return_documents": True,
            "top_n": top_n,
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    return result.get("output", {}).get("results", [])


def _get_valid_config(value: str) -> str:
    """过滤配置值中的注释和空白"""
    if not value:
        return ""
    # 去掉注释部分
    if "#" in value:
        value = value.split("#")[0]
    return value.strip()


def _get_milvus_client():
    """获取 Milvus 客户端连接"""
    from pymilvus import MilvusClient
    
    uri = f"http://{app_config.MILVUS_ADDRESS}"
    db_name = _get_valid_config(app_config.MILVUS_DATABASE) or "default"
    
    print(f"🔗 连接 Milvus: {uri}, database={db_name}")
    
    client = MilvusClient(
        uri=uri,
        user=app_config.MILVUS_USERNAME if app_config.MILVUS_USERNAME else None,
        password=app_config.MILVUS_PASSWORD if app_config.MILVUS_PASSWORD else None,
        db_name=db_name,
    )
    
    return client


def _search_milvus_direct(query_text: str, top_k: int = 5) -> list:
    """直接使用 pymilvus 进行搜索"""
    client = _get_milvus_client()
    
    # 生成查询向量
    query_vector = _get_embedding_vector(query_text)
    
    # 获取有效的 collection 配置
    collection_name = _get_valid_config(app_config.MILVUS_COLLECTION)
    vector_field = _get_valid_config(app_config.MILVUS_VECTOR_FIELD) or "vector"
    text_field = _get_valid_config(app_config.MILVUS_TEXT_FIELD) or "summary"
    
    # 如果指定了 collection，直接搜索
    if collection_name:
        print(f"🔍 搜索指定 collection: {collection_name}")
        results = client.search(
            collection_name=collection_name,
            data=[query_vector],
            anns_field=vector_field,
            limit=top_k,
            output_fields=[text_field, "*"],
        )
        client.close()
        return results
    
    # 否则搜索数据库中所有 collection
    collections = client.list_collections()
    print(f"📚 发现 {len(collections)} 个 collections: {collections}")
    
    all_results = []
    
    for coll_name in collections:
        try:
            print(f"🔍 搜索 collection: {coll_name}")
            results = client.search(
                collection_name=coll_name,
                data=[query_vector],
                anns_field=vector_field,
                limit=top_k,
                output_fields=[text_field, "*"],
            )
            if results and results[0]:
                # 给每个结果添加 collection 来源
                for hit in results[0]:
                    hit["_collection"] = coll_name
                all_results.extend(results[0])
                print(f"  ✅ 找到 {len(results[0])} 条结果")
        except Exception as e:
            # 某些 collection 可能字段不匹配，跳过
            print(f"  ⚠️ 跳过 collection {coll_name}: {e}")
            continue
    
    # 按相似度排序，取 top_k
    all_results.sort(key=lambda x: x.get("distance", 0), reverse=True)
    
    client.close()
    return [all_results[:top_k]] if all_results else []


@tool
def search_similar_alerts(
    alert_content: str,
    top_k: int = 5,
) -> str:
    """
    搜索向量数据库中与当前告警相似的历史处理记录，返回结构化的分析数据。
    
    Args:
        alert_content: 当前告警的完整内容（包括名称、描述、指标、tags等）
        top_k: 返回最相似的记录数量，默认5条
    
    Returns:
        结构化的历史告警分析数据，包含：
        - 统计信息：发送次数、ACK率、趋势
        - 最相似记录：时间、根因、处理方式
        - 历史知识：从处理记录中提取的经验
    """
    try:
        # 1. 向量召回：先召回更多候选（top_k * 3）
        recall_k = min(top_k * 3, 20)
        results = _search_milvus_direct(alert_content, recall_k)
        
        if not results or not results[0]:
            return _format_no_history_response()
        
        text_field = _get_valid_config(app_config.MILVUS_TEXT_FIELD) or "summary"
        vector_field = _get_valid_config(app_config.MILVUS_VECTOR_FIELD) or "vector"
        
        # 2. 提取文档内容用于 rerank
        hits = results[0]
        documents = []
        hit_map = {}
        
        for hit in hits:
            entity = hit.get("entity", {})
            text_content = entity.get(text_field, "")
            if text_content:
                documents.append(text_content)
                hit_map[text_content] = hit
        
        # 3. Rerank 重排序
        final_hits = hits[:top_k]
        if documents and app_config.RERANK_API_KEY:
            try:
                print(f"🔄 使用 Rerank 对 {len(documents)} 条结果重排序...")
                reranked = _rerank_results(alert_content, documents, top_n=top_k)
                if reranked:
                    final_hits = []
                    for item in reranked:
                        doc_text = item.get("document", {}).get("text", "")
                        if doc_text in hit_map:
                            hit = hit_map[doc_text]
                            hit["_relevance_score"] = item.get("relevance_score", 0)
                            final_hits.append(hit)
            except Exception as e:
                print(f"⚠️ Rerank 失败，使用向量召回结果: {e}")
        
        # 4. 构建结构化输出
        return _format_structured_response(final_hits, text_field, vector_field)
        
    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            return f"⚠️ 无法连接到 Milvus 数据库 ({app_config.MILVUS_ADDRESS})。请检查：\n1. Milvus 服务是否运行\n2. 网络连接是否正常\n3. 认证信息是否正确\n\n错误详情: {error_msg}"
        return f"⚠️ 搜索历史告警时出错: {error_msg}"


def _format_no_history_response() -> str:
    """格式化无历史数据的响应"""
    return """## 历史数据查询结果

### 统计概览
- **历史发送记录**: 无历史数据
- **历史处理记录**: 无历史数据
- **ACK率**: N/A

### 最相似记录
未找到相似的历史告警记录。

### 分析建议
这是一个新类型的告警，无历史数据可参考。
- 建议按标准流程处理
- 记录处理过程便于后续分析
- 噪音判定：非噪音（保守处理）"""


def _format_structured_response(hits: list, text_field: str, vector_field: str) -> str:
    """格式化结构化响应，便于 Agent 生成标准输出"""
    output_lines = ["## 历史数据查询结果\n"]
    
    # 统计信息（从元数据中提取，如果有的话）
    total_records = len(hits)
    ack_count = 0
    total_with_status = 0
    
    for hit in hits:
        entity = hit.get("entity", {})
        status = entity.get("status", entity.get("处理状态", ""))
        if status:
            total_with_status += 1
            if "ack" in str(status).lower() or "已处理" in str(status) or "已确认" in str(status):
                ack_count += 1
    
    ack_rate = (ack_count / total_with_status * 100) if total_with_status > 0 else 0
    
    output_lines.append("### 统计概览")
    output_lines.append(f"- **检索到的历史记录数**: {total_records}条")
    output_lines.append(f"- **ACK率估算**: {ack_rate:.1f}% ({ack_count}/{total_with_status}条有状态记录)")
    output_lines.append("")
    
    # 最相似记录详情
    output_lines.append("### 最相似的历史记录\n")
    
    for idx, hit in enumerate(hits, 1):
        entity = hit.get("entity", {})
        
        # 获取相似度/相关性
        relevance = hit.get("_relevance_score")
        distance = hit.get("distance", 0)
        if relevance is not None:
            score_str = f"相关性: {relevance:.3f}"
        else:
            similarity = distance * 100 if distance <= 1 else max(0, 1 - distance / 2) * 100
            score_str = f"相似度: {similarity:.1f}%"
        
        output_lines.append(f"#### 记录 {idx} ({score_str})")
        
        # 提取关键字段
        text_content = entity.get(text_field, "")
        timestamp = entity.get("timestamp", entity.get("time", entity.get("报警时间", entity.get("created_at", ""))))
        root_cause = entity.get("root_cause", entity.get("根因", entity.get("原因", "")))
        resolution = entity.get("resolution", entity.get("处理方式", entity.get("处理结果", "")))
        status = entity.get("status", entity.get("处理状态", ""))
        tags = entity.get("tags", entity.get("标签", ""))
        impact = entity.get("impact", entity.get("影响", entity.get("业务影响", "")))
        
        output_lines.append(f"- **历史告警摘要**: {text_content[:300]}{'...' if len(text_content) > 300 else ''}")
        if timestamp:
            output_lines.append(f"- **报警时间**: {timestamp}")
        if root_cause:
            output_lines.append(f"- **根因**: {root_cause}")
        if resolution:
            output_lines.append(f"- **处理方式**: {resolution}")
        if status:
            output_lines.append(f"- **处理状态**: {status}")
        if tags:
            output_lines.append(f"- **Tags**: {tags}")
        if impact:
            output_lines.append(f"- **业务影响**: {impact}")
        
        # 输出其他元数据字段
        skip_fields = {text_field, vector_field, "id", "_relevance_score", "_collection",
                       "timestamp", "time", "报警时间", "created_at",
                       "root_cause", "根因", "原因",
                       "resolution", "处理方式", "处理结果",
                       "status", "处理状态",
                       "tags", "标签",
                       "impact", "影响", "业务影响"}
        
        for key, value in entity.items():
            if key not in skip_fields and value:
                output_lines.append(f"- **{key}**: {value}")
        
        output_lines.append("")
    
    # 知识提取建议
    output_lines.append("### 知识提取提示")
    output_lines.append("请基于以上历史记录，提取以下信息用于输出：")
    output_lines.append("1. 综合多条记录判断该告警的产生原因")
    output_lines.append("2. 从处理方式中提取推荐SOP步骤")
    output_lines.append("3. 对比当前告警与历史告警的tags是否一致")
    output_lines.append("4. 总结历史处理经验作为\"从历史处理记录中学到的知识\"")
    
    return "\n".join(output_lines)


def get_alert_tools() -> list:
    """获取告警降噪相关工具列表"""
    return [search_similar_alerts]
