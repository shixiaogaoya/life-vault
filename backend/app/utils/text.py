"""文本分析工具：emoji 检测、词频提取（用于统计与可视化）。"""
from __future__ import annotations

import re


# Emoji Unicode 范围（覆盖主流 emoji，避免引入第三方库）
EMOJI_CODEPOINT_RANGES = (
    (0x1F300, 0x1FAFF),  # Symbols & Pictographs, Supplemental Symbols, Extended-A
    (0x2600, 0x27BF),    # Misc symbols, Dingbats
    (0x1F1E6, 0x1F1FF),  # Regional indicators (flags)
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1F018, 0x1F270),  # Various extended emoji ranges
    (0xFE0F, 0xFE0F),    # Variation selector
)


def is_emoji_char(ch: str) -> bool:
    """判断单个字符是否为 emoji（基于 Unicode 码点范围）"""
    if not ch:
        return False
    cp = ord(ch[0])
    return any(lo <= cp <= hi for lo, hi in EMOJI_CODEPOINT_RANGES)


# 中文/常见词分割正则：连续的 CJK 字符或 ASCII 单词各算一个 token
_TOKEN_PATTERN = re.compile(r"[一-鿿]+|[A-Za-z]{2,}|\d+")


STOPWORDS_EN = frozenset({
    "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "should", "could", "may", "might", "must", "can", "shall",
    "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "as", "an", "and", "or", "but", "if", "then", "so", "no",
    "not", "this", "that", "these", "those", "it", "its", "they",
    "them", "their", "we", "you", "your", "he", "she", "his", "her",
    "i", "me", "my", "yes", "ok", "okay", "oh", "ah", "hi", "hey",
})


def extract_text_tokens(text: str) -> list[str]:
    """从文本中提取 token（中文按字、英文按词、忽略停用词）"""
    if not text:
        return []
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.findall(text):
        if match.isascii():
            lowered = match.lower()
            if lowered not in STOPWORDS_EN:
                tokens.append(lowered)
        else:
            tokens.extend(list(match))
    return tokens
