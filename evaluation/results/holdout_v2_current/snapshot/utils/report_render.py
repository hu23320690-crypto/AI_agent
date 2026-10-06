def render_lookup(result: dict) -> str:
    """Render facts from the lookup, never numeric conclusions invented by an LLM."""
    user_id, month = result["user_id"], result["month"]
    if result["status"] == "not_found":
        return f"未找到演示用户 {user_id} 在 {month} 的使用记录，无法生成该月报告。请确认用户 ID 和月份；内置演示记录覆盖 2025 年。"
    data = result["data"]
    sections = [("使用概况", "特征"), ("清洁表现", "效率"),
                ("耗材状态", "耗材"), ("使用对比", "对比")]
    parts = [f"# 扫地机器人 {month} 使用报告", f"演示用户：{user_id}"]
    for title, key in sections:
        value = data.get(key) or "未提供"
        lines = str(value).replace("\\n", "\n").splitlines()
        parts.append(f"## {title}\n" + "\n".join(f"- {line}" for line in lines))
    parts.append("以上为本地演示记录。未提供的指标不作推算；剩余寿命与比例不转换为未经记录支持的更换日期。")
    return "\n\n".join(parts)
