"""Real HTTP integration; extraction and model quality are verified separately live."""

import asyncio
import os
from uuid import uuid4

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from powercontext.client import PowerContextClient
from powercontext.http import CreateArtifactRequest, CreateScopeRequest
from powercontext_langchain import PowerContextMiddleware, PowerContextScope
from pydantic import Field


class EvidenceModel(BaseChatModel):
    """Answer only when the middleware actually delivers the fixture in system context."""

    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "deterministic-integration-test"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages)
        system = "\n".join(m.text for m in messages if m.type == "system")
        answer = "12月18日，8万元，尚未确认" if "12月18日" in system else "没有找到记忆"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=answer))])


def test_official_middleware_capture_recall_and_thread_isolation(monkeypatch):
    monkeypatch.setenv(
        "POWERCONTEXT_LANGCHAIN_BASE_URL",
        os.getenv("TEST_POWERCONTEXT_URL", "http://127.0.0.1:8000"),
    )
    monkeypatch.setenv(
        "POWERCONTEXT_LANGCHAIN_CONTEXT_ASSEMBLY",
        '{"sections":[{"family":"topic-memory","limit":4}]}',
    )

    async def scenario():
        async with PowerContextClient(os.environ["POWERCONTEXT_LANGCHAIN_BASE_URL"]) as client:

            async def new_scope():
                return await client.create_scope(
                    CreateScopeRequest(
                        title="Middleware integration test",
                        summary="Isolated test",
                        idempotency_key=uuid4().hex,
                    )
                )

            shared, unrelated = await new_scope(), await new_scope()
            model = EvidenceModel()
            agent = create_agent(
                model=model,
                tools=[],
                system_prompt="Use recalled evidence.",
                middleware=[PowerContextMiddleware(auto_capture=True)],
                context_schema=PowerContextScope,
                checkpointer=InMemorySaver(),
            )
            question_a = "Aurora 的上线时间能否为12月18日，预算8万元？尚未确认。"
            await agent.ainvoke(
                {"messages": [{"role": "user", "content": question_a}]},
                config={"configurable": {"thread_id": "A"}},
                context=PowerContextScope(scope_id=shared.scope_id),
            )
            captured = await client.list_sources(shared.scope_id)
            assert any(question_a in source.content for source in captured.items)

            # Deterministic published-memory fixture. No fake extraction claim: the demo
            # itself uses a real generation worker and never seeds a memory this way.
            await client.create_artifact(
                shared.scope_id,
                CreateArtifactRequest.model_validate(
                    {
                        "family": "topic-memory",
                        "content": {
                            "title": "Aurora",
                            "summary": question_a,
                            "detail": question_a,
                        },
                    }
                ),
            )
            question_b = "Aurora"
            b = await agent.ainvoke(
                {"messages": [{"role": "user", "content": question_b}]},
                config={"configurable": {"thread_id": "B"}},
                context=PowerContextScope(scope_id=shared.scope_id),
            )
            assert b["messages"][-1].text == "12月18日，8万元，尚未确认"
            assert [m.text for m in b["messages"] if m.type == "human"] == [question_b]
            assert all(m.type != "system" for m in b["messages"])
            assert any("12月18日" in m.text for m in model.seen[-1] if m.type == "system")

            c = await agent.ainvoke(
                {"messages": [{"role": "user", "content": question_b}]},
                config={"configurable": {"thread_id": "C"}},
                context=PowerContextScope(scope_id=unrelated.scope_id),
            )
            assert c["messages"][-1].text == "没有找到记忆"

    asyncio.run(scenario())
