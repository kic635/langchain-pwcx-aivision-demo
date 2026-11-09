# LangChain × PowerContext × AI Vision

一个 Python 脚本，用官方 `PowerContextMiddleware` 展示跨对话共享上下文，同时通过 Langfuse SDK 将真实执行过程上报到 AI Vision。无需 Streamlit。

## 演示什么

1. 对话 A 提问：“Project Aurora-随机编号 的上线时间能否定为12月18日，预算控制在8万元？请记住这是我提出的待确认方案。”
2. 官方 middleware 在 Agent 完成后，自动将这一轮用户问题和助手回答保存为 PowerContext Source。
3. PowerContext Server 使用真实模型将 Source 提取为 Topic Memory。脚本等待发布，并打印原文及记忆证据；超时明确报错。
4. 对话 B 使用另一个 `thread_id` 提问：“我在另一段对话里提出过这个项目什么上线时间和预算方案？当时已经确认了吗？”
5. middleware 召回共享 Scope 中的证据，B 回答日期、预算及“尚未确认”，并附上记忆引用。

B 的输入没有日期、预算，也没有 A 的消息。两个线程使用同一个 PowerContext Scope，但 `InMemorySaver` 中的消息分别保存。每次运行新建 Scope 和项目编号，避免已有记忆干扰演示。Scope 是共享范围，生产环境还需要认证与访问控制。

## 安装与配置

需要 Python 3.11–3.14、[uv](https://docs.astral.sh/uv/)、一个真实模型和可访问的 AI Vision。

```bash
uv sync --locked
cp .env.example .env
```

填写 `.env`：

- `OPENAI_*`：支持 OpenAI Chat Completions 的模型。Agent 和本地 PowerContext 记忆提取共用此配置，都会产生真实模型费用。
- `LANGFUSE_*`：在 AI Vision 的 Agent Framework 接入页面获取地址及写入凭据。使用平台给出的地址，不要混用其他 Langfuse 项目的凭据。
- `POWERCONTEXT_LANGCHAIN_*`：官方 middleware 的连接配置。示例默认使用下面启动的独立本地 Server。

core 和 LangChain adapter 固定在同一个 PowerContext 上游提交，`uv.lock` 固定其余依赖。adapter 尚未发布到 PyPI，因此通过 Git 安装。

## 运行

终端一启动独立演示 Server；看到 `Application startup complete` 后继续：

```bash
uv run python demo.py --serve
```

终端二运行两次真实对话：

```bash
uv run python demo.py
```

本地 Server 监听 `127.0.0.1:18012`，使用 `.demo-data/powercontext.db`。它启用 `topic-memory` 后台提取，没有启用 MCP 和服务端 OTel exporter。已有 Server 也可以直接使用，但必须配置生成模型、启用 `topic-memory` 处理，并允许当前身份创建 Scope、保存 Source 和读取记忆；只保存 Source、未提取记忆的 Server 无法完成本例。

脚本按顺序打印：共享 Scope、独立线程、装配过程、A 的问答、自动保存的原文、发布的记忆、B 的问答、Trace ID。运行结果另存于忽略提交的 `.demo-data/result.json`。可选填写 `DEMO_AIVISION_BASE_URL`、`DEMO_AIVISION_SPACE_ID`、`DEMO_AIVISION_AGENT_UUID` 以打印可直接打开的 Trace 链接；这些字段只控制链接，不改变上报路由。

## 代码如何装配

直接阅读 [`demo.py`](demo.py) 中的 `main()`：

```python
model = ChatOpenAI(...)
tools = []
prompt = "..."
middleware = [PowerContextMiddleware(auto_capture=True, trace_content=True)]
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=prompt,
    middleware=middleware,
    context_schema=PowerContextScope,
    checkpointer=InMemorySaver(),
)
# 两次 agent.ainvoke：不同 configurable.thread_id，相同 PowerContextScope。
```

`tools=[]` 是有意的：本例的记忆能力全部由官方 middleware 承担，没有手写保存工具、召回中间件或 Span。SDK 读接口仅用于展示和确认服务端结果，Scope 创建仅用于隔离演示。`trace_content=True` 明确授权采集召回正文，仅用于可展示的演示数据。

每个对话在独立的 `asyncio` Task 中执行，模拟两个独立请求，避免共享调用上下文。每次调用使用一个普通 Langfuse `CallbackHandler`，`run_inline=True` 让异步 LangChain 调用中的追踪上下文保持正确。示例不指定 trace/span 父 ID，也不手工补造调用树。

## 在 AI Vision 验收

按输出的两个 Trace ID 搜索；等待采集落库后检查：

| 检查项 | 预期 |
| --- | --- |
| 最终结果 | B 找回 A 提出的12月18日、8万元，并说明尚未确认 |
| 会话隔离 | A、B 的 session/thread 不同，B 根节点输入只有自己的问题 |
| 召回细节 | `PowerContextMiddleware recall`：A 为空；B 输出包含已发布的记忆及引用 |
| 模型细节 | B 的 `ChatOpenAI` 输入包含 middleware 注入的证据，输出为真实模型回答 |
| 调用链 | 每个 Agent Trace 只有一个完整根节点，middleware/SDK 调用与模型挂在该次执行下 |
| 记忆观测 | PowerContext 的 SDK 召回调用被识别；无需为本例导入 MCP 配置 |

中文界面中的召回节点名为“召回记忆”，点击“展开完整文本”查看完整证据。SDK 子节点“解析记忆范围”等主要展示操作元数据，召回正文集中在父节点。

结果正确与追踪完整是两个独立验收项：脚本打印 Trace ID 只证明产生了 ID，平台实际收到内容需要在 AI Vision 中核对。默认不启动服务端 exporter，因此不会出现服务端内部 `memory.search` 等 Span；middleware/SDK 的输入输出可见性以其自身采集契约为准。

遇到“原文已保存，但记忆尚未发布”，检查 Server 的生成模型、网络/TLS、worker 日志及等待时间；不要直接把 A 的消息复制给 B 来绕过。模型连接失败时检查代理和私有 CA，保持证书校验开启。

实际模型回答与平台核对结果见 [真实链路验证记录](docs/verification.md)。

## 自动检查

CI 验证官方 middleware 的自动 Source 保存、召回注入与线程隔离。测试使用真实本地 HTTP Server 和确定性测试模型，不代表真实模型或 AI Vision 已验证；完整演示需按上述步骤运行。
