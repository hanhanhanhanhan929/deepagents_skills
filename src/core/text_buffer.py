"""
文本缓冲器

用于累积 LLM 流式输出的 token，并在发送前进行格式化处理。
解决 tokenizer 分割导致的中文空格和 Markdown 格式问题。
"""

import re
from typing import Generator


class TextBuffer:
    """
    智能文本缓冲器
    
    累积 token，在安全边界处刷新，避免 Markdown 语法被分割。
    """
    
    def __init__(self, flush_threshold: int = 150):
        """
        Args:
            flush_threshold: 强制刷新的字符阈值
        """
        self.buffer = ""
        self.flush_threshold = flush_threshold
    
    def add(self, text: str) -> Generator[str, None, None]:
        """
        添加文本到缓冲区，在安全边界处刷新
        
        Args:
            text: 新到达的 token
            
        Yields:
            格式化后的文本块
        """
        if not text:
            return
            
        self.buffer += text
        
        # 检查是否应该在安全边界刷新
        flush_point = self._find_safe_flush_point()
        
        if flush_point > 0:
            # 刷新到安全点
            to_flush = self.buffer[:flush_point]
            self.buffer = self.buffer[flush_point:]
            
            processed = self._format_text(to_flush)
            if processed:
                yield processed
    
    def _find_safe_flush_point(self) -> int:
        """
        找到安全的刷新点
        
        规则：
        1. 在句子结束处（。！？.!?）
        2. 在换行符后（如果换行后有足够内容）
        3. 缓冲区超过阈值时，找最近的安全点
        
        Returns:
            可以安全刷新到的位置（0 表示不刷新）
        """
        buf = self.buffer
        
        # 太短不刷新，但如果是换行符，可能是一个列表或标题的开始，考虑刷新
        if len(buf) < 10:
            return 0
        
        # 查找句子结束符
        sentence_endings = ['。', '！', '？', '.\n', '!\n', '?\n']
        best_point = 0
        
        for ending in sentence_endings:
            pos = buf.rfind(ending)
            if pos > best_point:
                best_point = pos + len(ending)
        
        # 如果找到了清晰的句子结束点
        if best_point > 10:
            return best_point
        
        # 超过阈值或发现换行符
        if len(buf) >= self.flush_threshold or '\n' in buf:
            # 找最后一个换行符
            last_newline = buf.rfind('\n')
            if last_newline > 0:
                return last_newline + 1
            
            # 找最后一个中文标点
            for punct in ['，', '、', '；', '：']:
                pos = buf.rfind(punct)
                if pos > 0:
                    best_point = max(best_point, pos + 1)
            
            if best_point > 0:
                return best_point
            
            # 如果实在找不到安全点且超过阈值，才强制刷新
            if len(buf) >= self.flush_threshold:
                return len(buf)
        
        
        return 0
    
    def flush(self) -> str:
        """强制刷新缓冲区，返回所有剩余内容"""
        if self.buffer:
            processed = self._format_text(self.buffer)
            self.buffer = ""
            return processed
        return ""
    
    @staticmethod
    def _format_text(text: str) -> str:
        """
        格式化文本，修复 tokenizer 导致的问题
        """
        s = text
        
        # === 1. 修复中文 tokenizer 空格 ===
        # 连续中文字符之间的空格: "地 理" -> "地理"
        for _ in range(5):
            s = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', s)
        
        # === 2. 修复数字列表 ===
        # "1 ." -> "1."
        s = re.sub(r'(\d)\s+\.', r'\1.', s)
        
        # === 3. 修复数字分割 ===
        # IP 地址: "10 .182" -> "10.182"
        s = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', s)
        # 百分比: "267 %" -> "267%"
        s = re.sub(r'(\d)\s+%', r'\1%', s)
        
        # === 4. 修复英文符号分割 ===
        # 下划线词: "read _file" -> "read_file"
        s = re.sub(r'(\w)\s+_', r'\1_', s)
        s = re.sub(r'_\s+(\w)', r'_\1', s)
        # 注意：不再自动合并所有英文单词，避免把 "hello world" 变成 "helloworld"
        # 仅修复特定的大写字母连写 (如 "DeepSe ek" -> "DeepSeek" 的一半，但很难泛化，不建议用正则硬做)
        
        
        # === 5. 修复 Markdown 语法 ===
        # 加粗: "** 文字 **" -> "**文字**"
        s = re.sub(r'\*\*\s+', '**', s)
        s = re.sub(r'\s+\*\*', '**', s)
        
        # === 6. 修复中文标点前的空格 ===
        s = re.sub(r'\s+([，。！？：；])', r'\1', s)
        
        # === 7. 修复列表项 ===
        # 1) "-\n内容" -> "- 内容" (处理被换行符切开的列表标记)
        s = re.sub(r'(\n[-*•])\s*\n\s*', r'\1 ', s)
        s = re.sub(r'^([-*•])\s*\n\s*', r'\1 ', s, flags=re.MULTILINE)
        
        # 2) "内容-项目" 或 "内容 - 项目" -> 强制换行
        # 强制在 - 或 * 前面加换行，如果它不在行首
        s = re.sub(r'([^\n\s])\s*([-*•])\s+([\u4e00-\u9fff\w])', r'\1\n\2 \3', s)
        
        # 3) "项目-\n下一项" -> "项目\n- 下一项"
        s = re.sub(r'([^\n\s])([-])\n\s*', r'\1\n\2 ', s)
        
        # === 8. 数字列表和标题换行与补空格 (关键修复) ===
        # 1) 处理 1.xxx -> \n1. xxx
        s = re.sub(r'([^\n\s])\s*(\d+\.)([^\s\d])', r'\1\n\2 \3', s)
        # 2) 处理 1. xxx (仅换行)
        s = re.sub(r'([^\n\s])\s+(\d+\.)\s+', r'\1\n\2 ', s)
        
        # 3) 处理 ###标题 -> \n### 标题
        s = re.sub(r'([^\n\s])\s*(#{1,6})([^\s#])', r'\1\n\2 \3', s)
        # 4) 处理 ### 标题 (仅换行)
        s = re.sub(r'([^\n\s])\s+(#{1,6}\s+)', r'\1\n\2', s)
        
        # === 9. 加粗和数字粘连 ===
        # "**加粗**1." -> "**加粗**\n1. "
        s = re.sub(r'\*\*(\d+\.)([^\s\d]?)', r'**\n\1 \2', s)
        
        # === 10. 代码块换行 (修复图二黑盒问题) ===
        # 同时处理开始和结束的 ```
        s = re.sub(r'([^\n])\s*(```)', r'\1\n\2', s)
        s = re.sub(r'(```)\s*([^\n\s\w])', r'\1\n\2', s)
        
        # === 11. 字段列表换行 (极端强化，修复 -功能: 问题) ===
        # 只要识别到 -** 或 -[中文]: 且不在行首，就强制换行
        s = re.sub(r'([^\n])\s*(-\s?(\*\*|\b)[\u4e00-\u9fff\w]{2,10}(\*\*|\b)[:：])', r'\1\n\2', s)
        
        # === 12. 确保字段列表冒号后有空格 ===
        s = re.sub(r'([:：])([^\n\s])', r'\1 \2', s)
        
        return s


def format_stream_output(text: str) -> str:
    """
    格式化流式输出文本的便捷函数
    """
    return TextBuffer._format_text(text)
