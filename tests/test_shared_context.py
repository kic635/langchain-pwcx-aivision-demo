"""Integration tests: requires a running PowerContext HTTP server."""

import asyncio
import uuid

from demo import Demo, QUESTION_A, QUESTION_B


def test_cross_session_recall_and_controls(monkeypatch):
    monkeypatch.setenv("MODEL_MODE", "fixture")
    monkeypatch.setenv("AIVISION_ENABLED", "false")

    async def scenario():
        demo = Demo()
        scope = f"project:test:{uuid.uuid4().hex}"
        try:
            a = await demo.ask("conversation-a", scope, QUESTION_A)
            b = await demo.ask(
                "conversation-b",
                scope,
                QUESTION_B,
                remember=False,
                retrieval_query="Project Aurora",
            )
            off = await demo.ask(
                "conversation-b", scope, QUESTION_B, remember=False, recall=False
            )
            isolated = await demo.ask(
                "conversation-c",
                scope + ":isolated",
                QUESTION_B,
                remember=False,
                retrieval_query="Project Aurora",
            )
            assert a["session_id"] != b["session_id"]
            assert a["write_result"] is not None
            assert any(
                QUESTION_A in hit["text"] and "conversation-a" in hit["text"]
                for hit in b["hits"]
            )
            assert "12 月 18 日" in b["answer"]
            assert b["hits"][0]["citation"]
            assert b["write_result"] is None
            assert not off["hits"]
            assert not isolated["hits"]
            assert "无法" in isolated["answer"] or "没有" in isolated["answer"]
        finally:
            demo.close()

    asyncio.run(scenario())
