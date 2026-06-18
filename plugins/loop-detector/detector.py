import difflib
import json
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


def normalize_text(text: str) -> str:
    """類似度比較用にテキストを正規化"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b\d+\b", "{NUM}", text)
    text = re.sub(r"```\w+", "```", text)
    # 思考タグの内容だけ抽出（あれば）
    think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    if think_match:
        text = think_match.group(1)
    return text.strip()


def text_similarity(text1: str, text2: str) -> float:
    """2つのテキストの類似度を計算（0.0-1.0）"""
    n1 = normalize_text(text1)
    n2 = normalize_text(text2)
    if not n1 or not n2:
        return 0.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()


def normalize_tool_call(tool_name: str, args: Dict[str, Any]) -> Tuple[str, str]:
    """ツール呼び出しを正規化した識別子に変換"""
    filtered = {
        k: v
        for k, v in args.items()
        if k not in ("task_id", "session_id", "tool_call_id")
    }
    sorted_args = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return (tool_name, sorted_args)


def detect_thinking_loop(
    messages: List[str],
    window_size: int = 5,
    threshold: float = 0.85,
    min_repetitions: int = 2,
) -> Optional[int]:
    """思考ループを検知。ループ開始インデックスを返す（None = ループなし）"""
    if len(messages) < window_size:
        return None

    recent = messages[-window_size:]
    similar_streak = 0
    loop_start = None

    for i in range(len(recent) - 1):
        sim = text_similarity(recent[i], recent[i + 1])
        if sim >= threshold:
            similar_streak += 1
            if loop_start is None:
                loop_start = max(0, len(messages) - window_size + i)
        else:
            similar_streak = 0
            loop_start = None

        if similar_streak >= min_repetitions:
            return loop_start

    return None


def detect_tool_loop(
    tool_calls: List[Tuple[str, str]],
    window_size: int = 6,
    max_identical: int = 2,
) -> Optional[int]:
    """ツール呼び出しループを検知。ループ開始インデックスを返す（None = ループなし）"""
    if len(tool_calls) < window_size:
        return None

    recent = tool_calls[-window_size:]
    counts = Counter(recent)

    # 同じツール呼び出しがmax_identicalを超えて存在
    for tc, count in counts.items():
        if count > max_identical:
            for i, call in enumerate(tool_calls):
                if call == tc:
                    return i

    # 交互パターン検知（A→B→A→B）
    if len(recent) >= 4:
        for period in range(2, len(recent) // 2 + 1):
            pattern = recent[:period]
            is_repeating = True
            for i in range(period, len(recent), period):
                chunk = recent[i : i + period]
                if len(chunk) < period:
                    break
                if chunk != pattern:
                    is_repeating = False
                    break
            if is_repeating:
                return len(tool_calls) - len(recent)

    return None
