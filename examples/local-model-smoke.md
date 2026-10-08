# Local model smoke — incomplete

2026-10-08，发布前工程检查。真实 qwen3:4b 请求在 90 秒超时窗口内没有返回回答。

| Task | Profile | Status | Completed model steps | Tool calls |
|---|---|---|---:|---:|
| live-health | baseline | uncertain | 0 | 0 |
| live-health | grounded | uncertain | 0 | 0 |
| search-errors | baseline | uncertain | 0 | 0 |
| search-errors | grounded | uncertain | 0 | 0 |
| search-latency | baseline | uncertain | 0 | 0 |

实验在连续超时后停止，未完成计划的六条 trial；未完成部分不计为成功，也不用于模型对照结论。丢失响应的 token 用量未知，不能记为免费。

这是加入整套评测 fail-fast 之前的调用记录。最终实现已在 provider uncertain 时立即保存结果并停止后续任务，该行为由集成测试验证。

服务查询显示 qwen3:4b 在 CPU 上运行（size_vram=0），这只是环境观察，不能证明超时的单一原因。模型 digest、量化和 Ollama 版本见 [JSON record](local-model-smoke.json)。没有宣称成功完成模型任务或实现模型提升。

已验证：20 项单元/集成测试通过；6 条合成轨迹跑通；fixture SFT 导出为 0；本地 bge-m3 构建 5 个知识块，并用 1024 维向量完成混合检索，首个来源为 search.md。
