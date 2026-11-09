import asyncio
import uuid

import streamlit as st
from demo import Demo, QUESTION_A, QUESTION_B

st.set_page_config(page_title="跨对话共享上下文", layout="wide")
st.title("LangChain × PowerContext × AI Vision")
st.caption("两个独立会话，通过 PowerContext 共享问题上下文")
if "run_id" not in st.session_state:
    st.session_state.run_id = uuid.uuid4().hex
run = st.session_state.run_id
scope = f"project:shared-context-demo:{run}"
st.code(f"共享范围：{scope}")
st.info(
    "默认 fixture 使用确定性 LangChain 模型；PowerContext 写入和检索均为真实服务调用。"
    "在 .env 中设置 MODEL_MODE=live 可切换真实模型，AIVISION_ENABLED=true 可启用真实上报。"
)
if st.button("开始全新演示"):
    st.session_state.clear()
    st.rerun()


def submit(key, question, **options):
    instance = Demo()
    try:
        with st.spinner("调用 LangChain 和 PowerContext…"):
            st.session_state[key] = asyncio.run(
                instance.ask(f"{key}-{run}", scope, question, **options)
            )
    except Exception as exc:
        st.error(f"调用失败（{type(exc).__name__}），请检查本地终端和服务配置。")
        raise
    finally:
        instance.close()


left, right = st.columns(2)
with left:
    st.subheader("对话 A · 提问并保存")
    a = st.text_area("原问题", QUESTION_A, key="question_a")
    if st.button("发送到对话 A"):
        submit("A", a)
    if "A" in st.session_state:
        st.write(st.session_state.A["answer"])
        st.json(st.session_state.A)
with right:
    st.subheader("对话 B · 新会话检索")
    b = st.text_area("新问题", QUESTION_B, key="question_b")
    query = st.text_input("检索关键词（FTS）", "Project Aurora")
    recall = st.checkbox("启用 PowerContext 检索", value=True)
    if st.button("发送到对话 B"):
        submit("B", b, remember=False, recall=recall, retrieval_query=query)
    if "B" in st.session_state:
        result = st.session_state.B
        st.write(result["answer"])
        st.metric("检索命中数", len(result["hits"]))
        st.json(result)
st.caption(
    "B 的模型输入只包含 B 的问题与检索证据。关闭检索再次提问可做对照。"
    "Trace ID 用于在 AI Vision 中核对调用链；上报结果需到平台确认。"
)
