import streamlit as st
from agent.react_agent import ReactAgent
from utils.logger_hander import logger

st.title("扫地机器人智能客服")
st.divider()

with st.sidebar:
    st.subheader("演示会话")
    user_id = st.text_input("演示用户 ID", value="1001").strip()
    city = st.text_input("所在城市（可选）", value="").strip()
    st.caption("内置使用记录覆盖 2025 年。可试：生成我 2025 年 8 月的使用报告。")
    st.caption("用户 ID 用于选择演示数据；天气服务尚未接入。")
    clear = st.button("清空对话")

identity = (user_id, city)
if "agent" not in st.session_state or st.session_state.get("identity") != identity or clear:
    st.session_state["agent"] = ReactAgent(user_id=user_id, city=city)
    st.session_state["message"] = []
    st.session_state["identity"] = identity

for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

prompt = st.chat_input("请输入问题")
if prompt:
    st.chat_message("user").write(prompt)
    try:
        with st.spinner("正在查询和生成回答，首次知识问答需要建立索引…"):
            answer = "".join(st.session_state["agent"].execute_stream(prompt))
        st.chat_message("assistant").write(answer)
        st.session_state["message"].extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ])
    except Exception:
        logger.exception("本轮回答未完成")
        st.error("本轮暂时无法完成，可以重试；若持续失败，请检查 Ollama 和项目日志。此前成功对话已保留。")
