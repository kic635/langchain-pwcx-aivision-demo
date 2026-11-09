"""Fixed questions, local PowerContext, and AI Vision: uv run python demo_simple.py."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.memory import InMemorySaver
from powercontext.client import PowerContextClient
from powercontext.http import CreateScopeRequest, ListArtifactsRequest
from powercontext_langchain import PowerContextMiddleware, PowerContextScope
from powercontext_langchain.settings import PowerContextLangChainSettings


async def main():
    load_dotenv(Path(__file__).with_name(".env"))
    settings = PowerContextLangChainSettings()
    langfuse = get_client()
    run_id = uuid4().hex
    questions = [
        ("A", "Project Aurora 的上线时间能否定为12月18日，预算控制在8万元？请记住这是待确认方案。"),
        ("B", "我在另一段对话里提出过 Project Aurora 什么上线时间和预算方案？当时已经确认了吗？"),
    ]

    try:
        async with PowerContextClient(
            settings.base_url,
            token=settings.token.get_secret_value() if settings.token else None,
            allow_insecure_http=settings.allow_insecure_http,
        ) as client:
            # Each experiment gets a fresh shared Scope; the chat threads stay separate.
            scope = await client.create_scope(
                CreateScopeRequest(
                    title="Shared context experiment",
                    summary="Two independent conversations",
                    idempotency_key=run_id,
                )
            )
            context = PowerContextScope(scope_id=scope.scope_id)
            print(f"PowerContext: {settings.base_url}\n共享 Scope: {scope.scope_id}", flush=True)

            model = ChatOpenAI(
                model=os.environ["OPENAI_MODEL"],
                base_url=os.getenv("OPENAI_BASE_URL"),
                temperature=0,
                use_responses_api=False,
            )
            tools = []
            prompt = "用中文简短回答，只根据当前消息及召回证据回答；没有证据不要猜测，待确认方案不能说成已确定。"
            middleware = [PowerContextMiddleware(auto_capture=True, trace_content=True)]
            agent = create_agent(
                model=model,
                tools=tools,
                system_prompt=prompt,
                middleware=middleware,
                context_schema=PowerContextScope,
                checkpointer=InMemorySaver(),
            )

            # Two ainvoke calls, each in an isolated task and thread; only the Scope is shared.
            for name, question in questions:
                callback = CallbackHandler()
                callback.run_inline = True
                thread_id = f"{name}-{run_id}"
                print(f"\n{name} 用户：{question}", flush=True)
                result = await asyncio.create_task(
                    agent.ainvoke(
                        {"messages": [{"role": "user", "content": question}]},
                        config={
                            "configurable": {"thread_id": thread_id},
                            "callbacks": [callback],
                            "run_name": f"simple-conversation-{name}",
                            "metadata": {"langfuse_session_id": thread_id},
                        },
                        context=context,
                    )
                )
                print(f"{name} 助手：{result['messages'][-1].text}\n{name} Trace：{callback.last_trace_id}", flush=True)

                # Capture saves a Source; B must wait for the server to extract a memory.
                if name == "A":
                    print("\n等待本地 PowerContext 发布 Topic Memory……", flush=True)
                    for _ in range(90):
                        if (
                            await client.list_artifacts(scope.scope_id, "topic-memory", ListArtifactsRequest(limit=1))
                        ).items:
                            break
                        await asyncio.sleep(2)
                    else:
                        raise TimeoutError("记忆未发布，请检查本地 Server 的生成模型与 topic-memory worker。")
    finally:
        langfuse.flush()
        langfuse.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
