from agent.runtime import RuntimeControlError


class IncompleteModelOutput(RuntimeControlError):
    pass


def ensure_complete_response(message):
    """Provider truncation is not a completed answer, even without think tags."""
    metadata = getattr(message, 'response_metadata', {}) or {}
    if metadata.get('done_reason') == 'length' or metadata.get('finish_reason') in {'length', 'max_tokens'}:
        raise IncompleteModelOutput('模型在生成额度内未完成回答，本轮未提交，请缩短问题或调整生成预算。')


def final_answer(text: str) -> str:
    """Do not display a reasoning-only or incomplete response as an answer."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text or not text.strip():
        raise RuntimeError("模型没有生成完整的最终回答，请重试。")
    return text.strip()
