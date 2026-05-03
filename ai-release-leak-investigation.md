# AI + 发布审核不严导致泄露事件调查

调查日期：2026-05-03  
范围：Apple Support App 夹带 `CLAUDE.md`、Claude Code npm 包夹带 source map，以及同类 AI 工作流/AI 产品/AI 研发数据发布审核失效案例。  
原则：只引用公开报道、官方文档和安全厂商披露；不复刻泄露文件正文、不提供镜像仓库或可利用路径。

## 一页结论

这类事故不是“AI 写代码不靠谱”这么简单，而是发布边界变了：

1. AI 工具把过去不会进发布包的上下文文件、记忆文件、提示词、配置和调试产物变成了项目一等公民。
2. 传统审核通常检查功能、崩溃、恶意行为、许可证和常见 secret，却很少把 `CLAUDE.md`、`.claude/`、prompt manifest、chat logs、source map、MCP config、模型数据分享链接当作高危发布物。
3. 一旦进入 App 包、npm tarball、公开 GitHub、公开数据库或搜索引擎索引，修复版本只能降低继续传播，不能真正“收回”已被下载、镜像或缓存的内容。

风险分级：

| 类型 | 典型文件/载体 | 主要损失 | 可逆性 |
| --- | --- | --- | --- |
| AI 开发上下文泄露 | `CLAUDE.md`、agent rules、memory、prompt docs | 架构、内部代号、工作流、未发布功能、工程规范 | 低，可截图传播 |
| 构建调试产物泄露 | `*.map`、debug symbols、unminified bundle | 源码结构、提示词、权限逻辑、防护位置 | 很低，可重构源码 |
| 运行/用户数据泄露 | chat logs、API keys、database logs | 用户隐私、凭据、后端细节 | 极低，需要轮换和通知 |
| AI 研发数据分享泄露 | 训练数据 URL、SAS token、bucket | 大规模内部数据、模型供应链污染 | 极低，且影响面难界定 |
| AI 辅助提交泄露 | `.env`、MCP config、cloud token | 生产凭据、供应链入口 | 中到低，取决于轮换速度 |

## 事件 1：Apple Support App 夹带 `CLAUDE.md`

### 已证实事实

- 公开报道一致指向：Apple Support App 的 2026-04-30 `v5.13` 更新包中被发现夹带两个 `CLAUDE.md` 文件，发现者为开发者 Aaron Perris，后续 `v5.13.1` 版本移除相关文件。
- 新浪/新智元报道提到文件内容涉及 `Juno AI`、`SupportAssistantAPIProvider`、`ChatKit`、`JUNO_ENABLED`、`DEV_BUILD` 等关键词，并将其解释为 Apple Support 内部 AI 客服/支持系统相关线索。
- Yahoo/Tech 报道将事件定位为 Apple 内部 Claude Code 工作流痕迹泄露，而不是用户数据泄露。
- Anthropic 官方 Claude Code 文档说明：`CLAUDE.md` 是给 Claude 的持久项目/组织/个人指令文件，会在会话开始时读取，常包含构建命令、编码标准、项目架构、常见工作流和团队约定。官方还明确 `CLAUDE.md` 是“上下文，不是强制配置”。

### 应谨慎看待的部分

- “Apple 正在用 Claude 构建完整 AI 系统”“坐实外部 LLM 依赖”等属于基于泄露文件名和截图内容的推断。它能证明发布包中出现 Claude Code 风格项目指令文件，不能单独证明生产服务一定调用 Anthropic 模型，也不能证明 Siri/Apple Intelligence 的最终供应商策略。
- 中文报道有明显标题党表达，应采信其中可交叉验证的时间线、版本号、文件名、关键词，不应照单全收商业解读。

### 审核失效点

1. App Store 审核不是企业内部源码保密审计。Apple 官方 App Review 指南强调每个 app 都会被专家审核，并扫描恶意软件或影响用户安全、隐私的软件；但这类审核更关注用户安全、功能完整性、隐藏功能、元数据准确性等，不等于逐文件判断“内部工程文档是否应出现在包内”。
2. 移动端构建产物白名单不足。`CLAUDE.md` 对运行时可能只是无害资源文件，不会触发崩溃、恶意 API、隐私权限或静态漏洞规则。
3. AI 上下文文件从“开发辅助”变成“敏感资产”。它可能不含 API key，却含有架构、后端接口名、条件编译开关、内部代号、开发流程和安全假设，这些足以支持竞争情报、攻击面枚举和社会工程。

### 影响判断

| 维度 | 判断 |
| --- | --- |
| 用户数据泄露 | 未见可靠证据显示用户数据或凭据被泄露 |
| 源码泄露 | 未见完整源码泄露证据 |
| 内部架构泄露 | 高概率存在，取决于文件内容真实性和完整性 |
| 第三方模型依赖暴露 | 只能算线索，不能当作最终架构证明 |
| 修复效果 | `v5.13.1` 可阻止新增下载，但已下载包和截图无法收回 |

## 事件 2：Claude Code npm 包夹带 source map

### 已证实事实

- 2026-03-31，安全研究者 Chaofan Shou 披露 `@anthropic-ai/claude-code` npm 包 `v2.1.88` 中包含 `cli.js.map`。
- 多家报道给出的核心数字一致：约 59.8 MB source map，约 1,900 个 TypeScript 文件，约 512,000 行源代码可被重构。
- InfoQ 报道称 Anthropic 对 CNBC 表示，这是“人因导致的发布打包问题，不是安全入侵”，且没有客户数据或凭据受影响。
- 报道还指出 `.map` 指向 Anthropic Cloudflare R2 上的完整未混淆 TypeScript zip，导致影响明显超过普通 source map。
- npm 官方文档说明：`package.json` 的 `files` 字段是发布 tarball 的包含白名单；缺省时相当于包含所有文件。`.npmignore` 可排除文件；`npm pack --dry-run` 可用于预览打包行为。

### 审核失效点

1. 包发布默认策略过宽。缺少 `files` 白名单或等价发布清单，导致构建目录里“能被 npm pack 看见的东西”都可能进入 tarball。
2. sourcemap 被当成普通调试产物，而不是 IP/安全边界。source map 的 `sourcesContent` 或外链能把混淆后的 JS 还原为可读源码、模块结构、注释和内部命名。
3. CI 没有把“发布包内容”作为独立审计对象。源码扫描、单测、类型检查都可能通过，但 tarball 仍可能多出 `.map`、`.env`、内部文档、测试快照、私有 prompt。
4. AI agent 产品的泄露收益更高。普通 CLI 源码泄露主要是商业 IP；AI agent CLI 还可能泄露提示词、工具权限模型、prompt injection 防线、模型路由、隐藏 feature flag 和内部安全假设。

### 影响判断

| 维度 | 判断 |
| --- | --- |
| 客户数据/凭据 | Anthropic 对外说未受影响 |
| 产品源码/IP | 高影响，源码结构已被重构和镜像 |
| 安全对抗 | 高影响，攻击者可研究权限边界、prompt 防护位置、工具调用逻辑 |
| 供应链风险 | 中到高，npm 安装窗口还叠加了同日 axios 供应链事件报道 |
| 可逆性 | 很低，镜像、fork、离线下载不可完全回收 |

## 同类事件梳理

### 1. Samsung 员工把内部源码/会议内容贴入 ChatGPT

2023 年，Samsung Semiconductor 员工在使用 ChatGPT 辅助修代码、优化流程和整理会议内容时，向外部 AI 服务提交了源代码、半导体相关流程信息和会议记录。后续 Samsung 禁止员工在公司设备上使用 ChatGPT 等生成式 AI 工具，并考虑内部安全 AI 环境。

本质：不是发布包泄露，而是“使用审核/数据出口审核”失效。AI 工具被当成内部 IDE，但实际是外部 SaaS 数据接收端。

### 2. Microsoft AI 研究 GitHub 仓库暴露 38TB 私有数据

Wiz 披露，Microsoft AI 研究团队在 GitHub 仓库分享开源训练数据/模型时，使用 Azure SAS token 暴露了额外 38TB 私有数据，包括员工电脑备份、secret、private key、password 和 30,000+ Teams 消息。根因是 SAS token 范围过大、权限过高，且 token 有效期极长。

本质：AI 研发场景下“大数据分享”审核失效。发布对象看似只是模型/训练数据链接，实际链接权限覆盖了整个存储账户，并且具备写权限，形成数据泄露和模型供应链污染双重风险。

### 3. DeepSeek 暴露 ClickHouse 数据库

Wiz 在 2025-01-29 披露，DeepSeek 公开暴露了未认证 ClickHouse 数据库，包含超过一百万行日志流，涉及 chat history、secret keys、backend details，并允许完整数据库控制。DeepSeek 被通知后修复。

本质：AI 产品上线速度快于基础云安全审核。聊天日志、API secret、后端日志是 AI 服务最敏感的运行数据之一，一旦日志数据库公网无认证，影响面直接覆盖用户和平台内部。

### 4. ChatGPT 共享链接被搜索引擎索引

2025 年，多家媒体报道 ChatGPT shared links 因“可被搜索引擎发现”的分享选项被 Google 等索引，公开聊天内容可被搜索。OpenAI 后续移除/回滚相关 discoverability 功能并协调去索引。

本质：产品分享语义审核失效。用户以为“分享链接”接近半私密，产品实际允许公开索引；AI 对话天然包含高敏个人、代码、商业上下文，索引后变成公开数据集。

### 5. Meta AI Discover feed 造成用户误分享

2025 年，Meta AI 独立 app 的 Discover feed 被报道充满用户误分享的私人问答；后续 Meta 增加更明显的分享前提示。TechCrunch 另报道 Meta 修复过一个可能泄露用户 AI prompts/生成内容的 bug。

本质：AI 对话产品把“聊天”和“内容发布”混合在同一体验中，公开/私密状态提示不足，审核没有覆盖真实用户误操作路径。

### 6. AI 辅助提交与 MCP 配置导致 secrets sprawl

GitGuardian 2026 报告称，2025 年公共 GitHub 新泄露 secret 达约 2,900 万，AI service leaks 同比增长 81%；Claude Code-assisted commits 的 secret 泄露率约 3.2%，约为公共 GitHub baseline 1.5% 的两倍。报告还指出 MCP 配置文件中出现大量凭据暴露。

本质：AI agent 需要本地凭据、MCP server、API key 和工具权限，开发者为了“先跑通”容易把配置写入 repo 或 prompt。传统 secret 扫描没有覆盖 AI 工具的 prompt、memory、MCP config、chat transcript 和本地状态目录。

## 横向根因模型

### 资产边界没更新

过去的敏感资产主要是源码、凭据、用户数据、证书、debug 符号。AI 工作流新增了：

- `CLAUDE.md`、`AGENTS.md`、`.cursor/rules`、`.github/copilot-instructions.md`
- `.claude/`、memory、conversation export、prompt manifest
- MCP server config、tool allowlist、local endpoint、sandbox policy
- prompt injection 防线、system prompt、eval case、red-team notes
- source map、debug bundle、artifact manifest
- 模型权重、训练数据链接、向量库 dump、日志库

这些文件很多不匹配传统 secret 正则，但情报价值很高。

### 审核对象错位

| 审核环节 | 常见检查 | 漏掉的东西 |
| --- | --- | --- |
| App Store / 平台审核 | 恶意软件、权限、崩溃、隐藏功能、隐私声明 | 内部 Markdown、prompt、架构说明、无害资源文件 |
| CI 安全扫描 | CVE、SAST、secret regex、license | source map 外链、prompt 文件、MCP config、memory cache |
| npm publish | 版本、入口、依赖、权限 | tarball 实际内容、`.map`、测试夹具、内部文档 |
| 数据发布 | 数据集可下载、模型可加载 | 链接权限范围、写权限、过期时间、相邻容器 |
| AI 产品 UX 审核 | 功能可用、分享成功 | 用户是否真正理解公开/可索引/可转发 |

### “无 secret”被误当作“无风险”

Apple `CLAUDE.md` 事件和 Claude Code source map 事件都说明：没有 API key 也可能是高价值泄露。内部架构、权限边界、后端接口名、feature flag、防护提示词、代码组织和调试路径足以改变攻击者成本。

## 发布前强制检查清单

### 移动 App / 桌面 App

1. 解包最终产物，而不是只扫源码仓库：`.ipa`、`.app`、`.apk`、`.asar`、`.dmg`。
2. 阻断以下文件进入包体：`CLAUDE.md`、`CLAUDE.local.md`、`AGENTS.md`、`.claude/`、`.cursor/`、`.windsurf/`、`.github/copilot-instructions.md`、`*.map`、`.env*`、`*.pem`、`*.key`、`*.mobileprovision`、内部 ticket/ADR/prompt 文件。
3. 扫描字符串：内部域名、feature flag、`DEV_BUILD`、`DEBUG`、`JIRA`、`Radar`、`rdar://`、`api_key`、`token`、`secret`、`BEGIN PRIVATE KEY`、`sourceMappingURL`。
4. 对资源白名单建模：发布包应只包含运行时需要的 assets、本地化、签名资源和业务配置；其他全部默认拒绝。

### npm / CLI / JS 产品

1. `package.json` 使用 `files` 白名单，而不是依赖 `.npmignore` 黑名单。
2. CI 必跑 `npm pack --dry-run --json` 或等价命令，解析 tarball 文件清单并做 denylist。
3. 发布前解压实际 tarball，检查 `*.map`、`sourcesContent`、`sourceMappingURL`、`.env`、prompt/memory/config 文件。
4. 禁止 source map 内含 `sourcesContent`；如果确需生产 source map，应上传到受控错误追踪系统，不随公开包分发。
5. 对 npm token 使用 trusted publishing / OIDC / 最小权限 / 短生命周期，避免长期自动发布凭据。

### AI agent / coding tool

1. 把 prompt、memory、rules、MCP config 纳入敏感资产登记。
2. `CLAUDE.local.md`、本地 memory、聊天记录、自动总结、tool logs 必须默认 gitignored 且不参与发布。
3. MCP config 不允许内联生产密钥；只引用环境变量或 secret manager。
4. 对 agent 读文件、发请求、提交代码分别做 hook：出站 LLM 请求前 secret 扫描；git commit 前 secret 扫描；artifact 打包前内容扫描。
5. 不把“AI 生成”作为审查豁免。AI 生成代码必须经过同等或更严格的 SAST、依赖、权限、隐私和人工 review。

### AI 产品和分享功能

1. “公开”“可搜索引擎索引”“任何有链接的人可看”“只对团队可见”必须是不同状态，不可用模糊 share 文案混用。
2. 公开发布前必须二次确认，并在确认界面展示将被公开的完整 prompt/response。
3. 默认 `noindex`；只有明确内容平台/社区场景才允许 opt-in indexing。
4. 提供批量撤销共享链接、去索引请求和审计日志。
5. 对用户输入中的 PII、凭据、源码、合同、医疗/法律等高敏内容做本地/服务端提示和阻断策略。

## 组织级防线

### 最小可落地方案

- 建一个 release artifact scanner，输入最终包/压缩包/tarball，而不是源码目录。
- 规则第一版先覆盖：
  - AI 上下文：`CLAUDE.md`、`.claude/**`、`AGENTS.md`、`.cursor/**`、`*.prompt.*`
  - 调试产物：`*.map`、`*.dSYM`、`sourceMappingURL`
  - 凭据：常见 secret regex + 熵检测 + 云 token 特征
  - 内部痕迹：内部域名、ticket 系统、feature flag、`DEV_BUILD`
- CI 中把扫描结果设为 release blocker。
- 每次发布保存 artifact manifest，做到“哪个版本包含了哪些文件”可审计。

### 更成熟方案

- SBOM + ABOM：不仅列依赖，还列 artifact 文件、模型、数据、prompt、MCP 工具和外部服务。
- AI Asset Inventory：登记每个 AI 工作流产生/读取/发布的上下文文件、记忆文件、日志和凭据。
- Preflight policy engine：用 OPA/Rego 或自研策略阻断不合规包。
- Disclosure channel：确保安全研究者能找到有效披露入口；Wiz 对 AI 公司泄露研究显示不少公司没有有效响应渠道。
- Post-release monitoring：发布后自动下载线上 App/npm 包/容器镜像，从外部视角复扫一次。

## 对这两个核心事件的最终判断

Apple `CLAUDE.md` 更像“内部 AI 工作流文件进入消费端 App 包”的内容边界事故。它的严重性不在于运行时漏洞，而在于把内部项目上下文、架构意图和 AI 工具链暴露给外部。平台审核不一定会拦，因为文件本身不一定违法、不一定执行、不一定含凭据。

Claude Code source map 更像“构建/发布管线未审计最终 tarball”的供应链事故。它的严重性更高，因为 source map 直接把私有源码、提示词和安全边界暴露成可重构资料，且 npm 包一旦发布会被快速镜像和缓存。

同类事件共同说明：AI 时代的发布审核不能只问“有没有 key、有没有 malware、功能能不能跑”。必须问“最终交付物里有没有把开发者脑内/agent 上下文/调试结构/数据分享权限一起交付出去”。

## 参考来源

- Anthropic Claude Code memory / `CLAUDE.md` 官方文档：https://code.claude.com/docs/en/memory
- Apple App Review Guidelines：https://developer.apple.com/app-store/review/guidelines/
- npm `package.json` `files` 字段文档：https://docs.npmjs.com/cli/v10/configuring-npm/package-json/
- npm `pack --dry-run` 文档：https://docs.npmjs.com/cli/v10/commands/npm-pack/
- Apple Support `CLAUDE.md` 事件发现者 Aaron Perris 公开帖镜像：https://xcancel.com/aaronp613/status/2049986504617820551
- Apple Support `CLAUDE.md` 事件报道，Yahoo Tech：https://tech.yahoo.com/ai/claude/articles/apple-using-claude-inside-company-114500152.html
- Apple Support `CLAUDE.md` 事件报道，新浪/新智元转载：https://finance.sina.com.cn/stock/t/2026-05-02/doc-inhwnnkk9856748.shtml
- Claude Code source map 事件，InfoQ：https://www.infoq.com/news/2026/04/claude-code-source-leak/
- Claude Code source map 事件，TechSpot：https://www.techspot.com/news/111907-anthropic-accidentally-exposed-claude-code-source-raising-security.html
- GitGuardian State of Secrets Sprawl 2026：https://www.gitguardian.com/state-of-secrets-sprawl-report-2026
- GitGuardian 2026 报告摘要：https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/
- Samsung ChatGPT 泄露事件，TechCrunch：https://techcrunch.com/2023/05/02/samsung-bans-use-of-generative-ai-tools-like-chatgpt-after-april-internal-data-leak/
- Samsung ChatGPT 泄露事件，TechSpot：https://www.techspot.com/news/98181-samsung-warns-employees-chatgpt-privacy-dangers-following-confidential.html
- Microsoft AI 研究数据泄露，Wiz：https://www.wiz.io/blog/38-terabytes-of-private-data-accidentally-exposed-by-microsoft-ai-researchers
- DeepSeek 数据库泄露，Wiz：https://www.wiz.io/blog/wiz-research-uncovers-exposed-deepseek-database-leak
- ChatGPT shared links 索引事件，TechCrunch：https://techcrunch.com/2025/07/31/your-public-chatgpt-queries-are-getting-indexed-by-google-and-other-search-engines/
- OpenAI 回滚 ChatGPT discoverability 功能报道，Search Engine Journal：https://www.searchenginejournal.com/openai-is-pulling-shared-chatgpt-chats-from-google-search/552671/
- Meta AI Discover feed 隐私问题，Mozilla Foundation：https://www.mozillafoundation.org/campaigns/meta-help-users-stop-accidentally-sharing-private-ai-conversations/
- Meta AI prompt/content bug，TechCrunch：https://techcrunch.com/2025/07/15/meta-fixes-bug-that-could-leak-users-ai-prompts-and-generated-content/
