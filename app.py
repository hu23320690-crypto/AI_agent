import streamlit as st
from pathlib import Path
from uuid import uuid4
from agent.react_agent import ReactAgent
from agent.toolset import load_toolset
from utils.logger_hander import logger
from agent.runtime import RuntimeControlError

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
toolset = load_toolset()
if ("agent" not in st.session_state or st.session_state.get("identity") != identity or clear
        or st.session_state['agent'].toolset != toolset):
    if "agent" in st.session_state:
        st.session_state["agent"].clear_history()
    if toolset == 'service':
        st.session_state['session_id'] = str(uuid4())
        st.session_state["agent"] = ReactAgent(user_id=user_id, city=city,
                                               session_id=st.session_state['session_id'])
    else:
        st.session_state["agent"] = ReactAgent(user_id=user_id, city=city)
    st.session_state["message"] = []
    st.session_state["identity"] = identity

for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

agent = st.session_state['agent']
service_mode = agent.toolset == 'service'
database_ready = not service_mode or Path(agent.service_state['service_db_path']).is_file()
if not database_ready:
    st.warning('请先运行 scripts/manage.py service-db init')

prompt = st.chat_input("请输入问题")
if prompt and database_ready:
    st.chat_message("user").write(prompt)
    try:
        with st.spinner("正在查询和生成回答，首次知识问答需要建立索引…"):
            answer = "".join(st.session_state["agent"].execute_stream(prompt))
        st.chat_message("assistant").write(answer)
        st.session_state["message"].extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ])
    except RuntimeControlError as exc:
        st.error(str(exc) + " 此前成功对话已保留。")
    except Exception:
        logger.exception("本轮回答未完成")
        st.error("本轮暂时无法完成，可以重试；若持续失败，请检查 Ollama 和项目日志。此前成功对话已保留。")


if service_mode and database_ready:
    from service_desk.actions import confirm_action, list_actions, reject_action

    def decide_card(operation, action_id):
        try:
            with agent._state_lock:
                if agent._active_run is not None:
                    from agent.runtime import RunBusy
                    raise RunBusy('当前会话已有任务运行，请等待后重试。')
                execute = confirm_action if operation == 'confirm' else reject_action
                result = execute(agent.service_state, action_id)
                if result['status'] == 'denied':
                    st.error(result['message'])
                    return
                if agent.record_action_event(result | {'operation': operation}):
                    st.session_state['message'].append({'role': 'assistant', 'content': result['message']})
        except RuntimeControlError as exc:
            st.error(str(exc))
            return
        except Exception:
            logger.exception('卡片操作未完成')
            st.error('卡片暂时无法处理，请刷新后重试。')
            return
        st.rerun()

    try:
        cards = list_actions(agent.service_state)
    except Exception:
        logger.exception('确认卡片读取失败')
        st.error('确认卡片暂时无法读取，请检查演示用户和服务数据库。')
        cards = []
    labels = {'pending': '待确认', 'executed': '已执行', 'rejected': '已拒绝',
              'expired': '已过期', 'superseded': '已取代', 'failed': '未执行（条件已变化）'}
    for card in cards:
        with st.container(border=True):
            st.caption('状态：' + labels[card['status']])
            if card['status'] == 'pending':
                st.write(card['summary'])
                st.caption('有效期至：' + card['expires_at'])
                yes, no = st.columns(2)
                with yes:
                    if st.button('确认', key='confirm-' + card['action_id']):
                        decide_card('confirm', card['action_id'])
                with no:
                    if st.button('拒绝', key='reject-' + card['action_id']):
                        decide_card('reject', card['action_id'])
