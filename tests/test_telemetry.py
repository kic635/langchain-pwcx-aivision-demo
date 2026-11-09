"""Verify real SDK export to a local OTLP receiver, not AI Vision persistence."""

import gzip
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)


def test_langchain_and_memory_spans_export():
    requests = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            payload = ExportTraceServiceRequest()
            payload.ParseFromString(body)
            requests.append((self.path, payload))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = dict(
        os.environ,
        MODEL_MODE="fixture",
        AIVISION_ENABLED="true",
        LANGFUSE_BASE_URL=f"http://127.0.0.1:{server.server_port}",
        LANGFUSE_PUBLIC_KEY="demo-public-not-a-real-key",
        LANGFUSE_SECRET_KEY="demo-secret-not-a-real-key",
        LANGFUSE_TRACING_ENVIRONMENT="test",
    )
    try:
        completed = subprocess.run(
            [sys.executable, "demo.py"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert completed.returncode == 0, completed.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    spans = [
        span
        for _, req in requests
        for resource in req.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    ]
    names = [span.name for span in spans]
    assert names.count("shared-context-chat") == 3
    assert "powercontext.search_memory" in names
    assert "powercontext.remember_memory" in names
    assert any("FakeListChatModel" in name for name in names), names
    assert all(path == "/api/public/otel/v1/traces" for path, _ in requests)
    roots = [span for span in spans if span.name == "shared-context-chat"]
    assert len({span.trace_id for span in roots}) == 3
    assert all(not span.parent_span_id for span in roots)
    root_ids = {span.span_id for span in roots}
    memory_spans = [span for span in spans if span.name.startswith("powercontext.")]
    assert all(span.parent_span_id in root_ids for span in memory_spans)
