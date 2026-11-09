# 真实链路验证记录

验证日期：2026-11-09。使用真实 Qwen `qwen3.8-max`、独立 PowerContext Server 与 AI Vision 开发环境；通过 SDK 实时上报，没有导入或补造 Trace。

- PowerContext core：`1.5.1.dev225+gf27c0c287`，与官方 LangChain adapter 固定到同一提交。
- LangChain：`1.4.9`；Langfuse：`5.2.0`。
- Server 启用真实 `topic-memory` 提取，未启用服务端 exporter。
- 运行标识：`cb9574a81988`。

## 问答结果

A 的输入：

> Project Aurora-cb9574a81988 的上线时间能否定为12月18日，预算控制在8万元？请记住这是我提出的待确认方案。

B 的输入（不同 thread，没有 A 的消息）：

> 我在另一段对话里提出过 Project Aurora-cb9574a81988 什么上线时间和预算方案？当时已经确认了吗？

B 的真实回答：

根据召回记录，你曾提出：**Project Aurora-cb9574a81988 拟于 12 月 18 日上线，预算控制在 8 万元**。当时**没有确认**，只是作为“待确认方案”记录。

引用证据：  
> “用户询问 Project Aurora-cb9574a81988 的上线时间能否定为12月18日，并将预算控制在8万元……目前没有可确认该上线时间或预算的证据，因此该事项不能作为已确定决定。当前状态应保留为：用户提出的待确认方案，尚未被证据确认。”

## 平台读回与页面核对

| 项目 | 对话 A | 对话 B |
| --- | --- | --- |
| Trace ID | `20b3cd7bc1e98d48c4ff436c325e00d3` | `97d6e64fa769fe994501a930d144fcce` |
| session/thread | `chat-A-cb9574a81988` | `chat-B-cb9574a81988` |
| Span 数 | 9 | 9 |
| 根节点数 | 1 | 1 |
| 缺失父节点 | 0 | 0 |
| 召回状态 | empty | ready |
| 模型输入、输出 | 已记录 | 已记录 |

通过 AI Vision 详情接口读回原始 Span，并在浏览器中核对：

- A 的初始召回为空；官方 middleware 在完成后写入含用户问题与助手回答的 Source。
- 后台生成 Topic Memory，其来源引用指向该 Source；B 在发布后才执行。
- B 的“召回记忆”输入只有自己的问题，输出包含 Topic Memory 的 Scope、Artifact、revision、summary 和 snippet。
- B 的 `ChatOpenAI` 输入包含 middleware 注入的历史证据，输出找回日期和预算，并保留待确认状态。
- 每条调用树独立且完整；详情页识别到准备上下文和采集内容两次记忆调用。
- 两条详情页面加载成功，没有失败的 API 请求。召回正文需要点击“展开完整文本”；模型的系统上下文在“其它输入消息”中。

这些结果验证了本次运行，不是所有模型、部署或数据库组合的保证。CI 的确定性模型与手工记忆 fixture 只验证 middleware 的 HTTP 行为和会话隔离，不替代上述真实链路验收。
