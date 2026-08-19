# monitor — 观测埋点层

`monitor/` 是 A2E 的观测埋点层:基于 **OpenInference** 给各 agent 框架 / SDK 自动打桩,
在 task 跑实验时采集 OTel trace(LLM / TOOL / AGENT / CHAIN / SKILL 等 span),
经 OTLP 写入 `server/`(A2E)。整体架构见根目录 [`DEVELOPMENT.md`](../DEVELOPMENT.md)。

目录:
- `openinference-semantic-conventions/` — **L1** 语义规范(span kind 枚举、各类 `*Attributes`)
- `openinference-instrumentation/` — **L2** instrumentation 辅助(`get_*_attributes` 等)
- `instrumentation/openinference-instrumentation-*` — **L3** 各框架/SDK 的自动埋点
  (claude-agent-sdk / langchain / openai / smolagents / crewai / llama-index /
  google-adk / agno / autogen-agentchat / anthropic / openai-agents)
- `instrumentation-js/openinference-instrumentation-pi/` — Pi Agent 的 TypeScript 扩展埋点
- `instrumentation-js/openinference-instrumentation-deepseek-harness/` — DeepSeek Harness 的 TypeScript
  Cordis 插件埋点；二者都生成 OpenInference span 并通过 OTLP/HTTP 写入 A2E

---

## 变更记录(按日期)

> 新增内容请按日期在本区块顶部追加一个 `### YYYY-MM-DD` 小节。

### 2026-08-10 — Pi Agent 轨迹采集

Pi 是 Node.js/TypeScript Agent Harness，因此不使用 Python monkey patch，而通过其官方事件 API
接入。`instrumentation-js/openinference-instrumentation-pi` 分为两层：底层通过 `pi-agent-core` 的
`Agent.subscribe()` 监听公共 agent/message/tool 生命周期；上层以 Pi Package 扩展形式通过
`pi-coding-agent` 的 `ExtensionAPI.on()` 复用这些事件并补充 prompt、context、provider 和 session
信息，生成 `AGENT` 根 span 以及 `LLM`、`TOOL` 子 span。

- 模型轨迹包含 system/user/assistant 消息、tool-call intent、provider/API/model、token/cache/cost
  和错误状态；
- 工具轨迹按 `toolCallId` 区分并发调用，包含名称、参数、结果与错误状态；
- 属性沿用 A2E 已支持的 OpenInference 约定，可由 server 直接入库，并可通过项目 spans API
  读取；当前前端只在 experiment sample 引用了 trace 时展示 span tree，尚无独立原始 trace 浏览入口；
- 使用独立的 OTel provider，不修改 Pi 的全局 tracer；扩展与导出异常不会传回 Pi 执行路径；
- 测试除使用内存 exporter 校验父子关系、字段映射、并发、失败与未完成 span 清理外，还会
  分别使用官方 Pi 0.84.1 裸 `Agent`（core）和完整 `AgentSession`（coding-agent）+ Faux Provider
  实跑两次模型响应和一次 `read` 工具。
- 另有完整 coding-agent 多步任务测试：通过真实 `write` 创建临时产物，再用真实 `read` 读回
  验证，并检查三轮模型调用与两次工具调用均进入 OTLP 轨迹；隐私测试确保关闭内容采集后不
  保留 prompt、provider payload、工具参数/结果或敏感错误文本。
- 2026-08-12 使用真实 DashScope `qwen-plus` 完成 coding-agent 验收：Pi 实际发起两次模型调用并
  执行内置 `read package.json`；A2E 入库恰好 1 个 `AGENT`、2 个 `LLM`、1 个 `TOOL` span，
  父子关系与状态正确，token、工具输入输出和最终答案齐全；凭据未写入仓库。

安装、配置、验证命令和 smoke test 见
[`instrumentation-js/openinference-instrumentation-pi/README.md`](./instrumentation-js/openinference-instrumentation-pi/README.md)。

### 2026-06-29 — SKILL span 扩展到 agno

把 `2026-06-23` 的 SKILL span 能力扩到第三个有 skill 概念的框架:**agno**。复用已有的
`SKILL` 枚举与 `get_skill_attributes()`(L1/L2 不动),只在 agno 的工具埋点里加分类逻辑。

**关键点:agno 的 skill 走工具路径,无需新增 hook。**
agno 的 `Skills.get_tools()`(`agno/skills/agent_skills.py`)注入 3 个普通 `Function` 工具,
执行时都经过已被包装的 `FunctionCall.execute()/aexecute()`,所以只需在 `_FunctionCallWrapper`
里按工具名重分类即可,**未改 `__init__.py`**。

**改动(仅 1 个源文件)**

| 层 | 文件 | 改动 |
| --- | --- | --- |
| **L3** agno | `instrumentation/openinference-instrumentation-agno/.../_tools_wrapper.py` | 新增 `_classify_function_call()`;`run`/`arun` 动态判 kind 并叠加 `skill.*`;成功处理函数加 `skill_name` 形参,把返回 JSON 写入 `skill.output.value` |

**检测口径**

- `get_skill_instructions`(加载 skill 指令)、`get_skill_reference`(读 references)、
  `get_skill_script`(读/执行 scripts)三个工具 → `SKILL`,用 `skill.source` 区分操作类型
  (`agno_skill:instructions` / `:reference` / `:script`)。其余工具仍为 `TOOL`。
- `skill.name` 取自工具入参 `skill_name`;`skill.input.value` 为入参 JSON;`skill.output.value`
  为工具返回的 JSON(本框架已填充 output,优于 claude)。

**验证**

- 离线 demo `monitor/runs/agno_skill_trace.py`(`LocalSkills` 从临时目录加载一个 `demo-skill`,
  直接驱动三个工具,无需 API key)→ 三个 span 均 `kind=SKILL` 且
  `skill.name / skill.source / skill.input.value / skill.output.value` 齐全,全部 PASS。
  运行:`task/.venv/bin/python monitor/runs/agno_skill_trace.py`(`task/.venv` 是仓库内唯一装了 agno 的环境)。
- 普通工具回归仍为 `TOOL`。

**现状**

| SDK | skill 触发信号 | 落成 |
| --- | --- | --- |
| agno | `get_skill_instructions` / `get_skill_reference` / `get_skill_script` 工具 | `SKILL` span ✅(含 `skill.output.value`) |

---

### 2026-06-23 — SKILL span kind:claude-agent-sdk 一等监控 skill

把"agent 调用了一个 **Skill(技能)**"这一行为从无差别的 `TOOL` span **升级为带语义的 `SKILL` span**,
覆盖当时唯一有 skill 概念的 SDK:**claude-agent-sdk**。背景与最初设计见
[`readme_shangyingjun.md`](./readme_shangyingjun.md)(本次在其基础上修正了检测信号)。

**三层改动**

| 层 | 文件 | 改动 |
| --- | --- | --- |
| **L1** semconv | `openinference-semantic-conventions/.../trace/__init__.py` | 新增 `OpenInferenceSpanKindValues.SKILL` 枚举 + `SkillAttributes` 类(`skill.id/name/version/source/description/input.*/output.*/invocation_id`) |
| **L2** helper | `openinference-instrumentation/.../_attributes.py`、`__init__.py` | 新增 `get_skill_attributes(...)`,导出 `SKILL_*` 常量并加入 `__all__` |
| **L3** claude | `instrumentation/openinference-instrumentation-claude-agent-sdk/.../_wrappers.py` | 新增 `_classify_tool_call()`;`start_tool_span` 动态判 kind |

**检测口径(按真实信号,实测确认)**

- **claude-agent-sdk**:主信号是专门的 `Skill` 工具(入参 `{"skill","args"}`)→ `SKILL`;
  兼容老路径 `Read`/`Bash` 读 `SKILL.md`。其余工具仍为 `TOOL`。

> 修正说明:最初的设计只检测"读 SKILL.md",但**当前 claude-agent-sdk 真实的 skill 触发是专门的 `Skill` 工具**
> (用真实 trace 验证:skill 调用走 `Skill` 工具,而非读 SKILL.md),故 L3 改以 `Skill` 工具为主信号。

**验证**

- claude:真实 demo `monitor/runs/skill_real_trace.py`(挂一个 skill 真跑)→ `Skill` span 从 `kind=TOOL`
  变为 `kind=SKILL`,带 `skill.name / skill.source / skill.input.value`。
- 三个改动文件 `py_compile` 通过;普通工具回归仍为 `TOOL`。

**现状**

| SDK | skill 触发信号 | 落成 |
| --- | --- | --- |
| claude-agent-sdk | `Skill` 工具(+ 老路径 `Read`/`Bash SKILL.md`) | `SKILL` span ✅ |

其余框架(langchain / openai / smolagents / crewai / …)本身无 skill 概念,不涉及。

**未完成 / 后续**

- `skill.version` / `skill.description` 暂未填(需解析 SKILL.md frontmatter,现仅填 name/source/input)。
- 尚未给两个 instrumentation 加 SKILL 专项单测。
