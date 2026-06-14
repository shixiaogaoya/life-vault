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


# 中文高频无义字（单字聚类噪声大，单独剔除）
_STOPWORDS_ZH_CHARS = frozenset(
    "的了是在我有和人这中大为上个国他到说们"
    "里也着时就会来去能对要没而被让把给吗"
    "吧啊呢啦哦哈嗯呀嘛吖哇哪呗嘞"
)


def extract_topic_tokens(text: str) -> list[str]:
    """用于话题聚类的 token 提取

    与 extract_text_tokens 的区别：
    - 英文按词（同上）
    - 中文：提取 2-3 字的连续子串（bigram/trigram）作为候选词，
      过滤纯无义单字。这样能捕捉到如"python"、"工作"、"周末"等
      有语义的片段，而不是拆成孤立单字。
    - 仍忽略英文停用词与中文无义字
    """
    if not text:
        return []
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.findall(text):
        if match.isascii():
            lowered = match.lower()
            if len(lowered) >= 2 and lowered not in STOPWORDS_EN:
                tokens.append(lowered)
        else:
            # 中文片段：取 2-gram 和 3-gram
            chars = [c for c in match if c not in _STOPWORDS_ZH_CHARS]
            for n in (2, 3):
                for i in range(len(chars) - n + 1):
                    gram = "".join(chars[i : i + n])
                    # 跳过包含标点/数字的混合片段（已是纯 CJK）
                    if len(gram) == n:
                        tokens.append(gram)
    return tokens
