def final_answer(text: str) -> str:
    """Do not display a reasoning-only or incomplete response as an answer."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text or not text.strip():
        raise RuntimeError("模型没有生成完整的最终回答，请重试。")
    return text.strip()
