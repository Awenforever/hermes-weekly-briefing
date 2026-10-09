# Hermes Weekly Briefing

> 把散落在一周里的新论文，变成一份真正值得读的个人研究周报。

Weekly Briefing 会围绕你的研究方向发现并筛选论文，完成基于原文元数据的深度分析与作者团队调研，生成适合中文阅读的 PDF，并按你的时间表通过邮件交付。

[![Hermes](https://img.shields.io/badge/Hermes-%E2%89%A50.21.3-111827)](https://github.com/NousResearch/hermes-agent)
[![Delivery](https://img.shields.io/badge/delivery-email--only-2563eb)](#交付边界)
[![License](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

## 一眼看懂

| 能力 | 你会得到什么 |
|---|---|
| 论文发现 | 跨开放索引、预印本、会议评审与可选商业数据库广泛召回，不依赖单一平台 |
| 智能选稿 | 关键词用于搜索和研究画像；模型比较候选的语义相关性、方法价值、新颖性与组合互补性 |
| 搜索体检 | 自动发现并实测学术搜索源；不可用时先引导配置，不带病启用计划任务 |
| 深度解读 | 研究问题、方法步骤、证据、对照、局限与跨论文关系 |
| 团队画像 | 作者机构、研究主题、代表性工作与研究路径线索 |
| 精美报告 | 中文 PDF、方法卡片、比较表、作者卡片和可点击原文链接 |
| 交付质检 | 发送前检查分析完整性、作者身份、原文链接、封面统计与 PDF 文件 |
| 稳定交付 | 邮件发送、投递回执、失败可诊断、历史报告可追溯 |
| 防止漂移 | 研究方向只来自你的明确设置；“下周关注”和模型输出不会反向改写偏好 |

## 让 Hermes 帮你安装

把仓库链接交给 Hermes，并直接说：

> 帮我安装 Weekly Briefing。请先了解我的研究方向、收件邮箱、邮件里对我的称呼、Hermes 的署名、期望篇数、发送时间和时区，再引导我完成邮件登录；全部检查通过后先试运行，不要直接开启计划任务。

Hermes 读取本 README 与插件 Skill 后，会主动完成以下流程：

1. 检查旧版数据并安全迁移，不覆盖已有配置和历史报告；
2. 逐项询问尚未确定的个性化设置，而不是让你手写配置文件；
3. 检查分析模型、PDF 渲染器与 Agently 邮件工具；
4. 实测所选学术搜索源，并说明开放来源与需要凭据的可选来源；
5. 如缺少 Agently，在征得同意后安装；
6. 打开 Agently 的交互式登录流程，由你在终端或浏览器中完成授权；
7. 验证登录状态，生成一份测试周报；
8. 经你确认后再安装每周计划任务。

> [!IMPORTANT]
> 邮件密码、令牌、Cookie 或 OAuth 验证码不应发送给 Hermes。需要人工授权时，Hermes 会明确告诉你在哪个终端或浏览器完成，并在你确认后继续检查。

## 个性化内容

首次设置会围绕你的真实需求确认：

- 核心研究方向与关键词；
- 可选的研究概念组与排除项；默认由模型理解其语义，只有你明确选择严格模式时才作 Boolean 硬约束；
- 每期论文数量（默认 5 篇）；
- 收件邮箱；
- 邮件正文中对你的称呼，以及结尾使用的 Hermes 署名；
- 每周发送时间与时区；
- 可选的分析模型与备用模型（留空时动态继承 Hermes）；
- 学术搜索源；开放来源默认开箱即用，凭据型来源只引用 Hermes 环境中的变量；
- 可选的显式反馈偏好；没有确认记录时不启用，添加第一条时自动生效，全部撤销后自动停用。

插件不会推荐作者的研究方向，也不会从历史周报、邮件回信或普通聊天中暗中推断你的兴趣。首次设置只接受你明确给出的关键词。以后若想调整偏好，可以在任意 Hermes 对话渠道告诉 Hermes；Hermes 必须先复述并确认，再写入可查看、可撤销的反馈记录。

计划任务按 Hermes profile 的 IANA 时区运行。若你选择的时区与 profile 不一致，体检会明确拦截，而不会在错误的本地时间悄悄发送。

## 报告长什么样

每次邮件包含两个职责不同的成品：邮件正文是一封简洁、拟人化的导读信，告诉你本期为什么值得读、时间有限时先看什么，并使用你设置的称呼和 Hermes 署名；附件 `report.pdf` 才是完整报告。插件不会再把 PDF 的 Markdown 正文原样复制进邮件。

每篇入选论文都会尽可能包含：

- 可点击的 DOI 或 arXiv 原文链接；
- 研究问题及其价值；
- 清晰的方法步骤；
- 摘要能够支持的证据、对照与局限；
- 与本期其他论文的联系；
- 作者团队的机构、研究主题、近期工作与影响力线索。

缺失的信息会明确标为“摘要未说明”或“需阅读全文核验”，不会由模型猜测补齐。

## 学术搜索源

Weekly Briefing 默认同时使用 `OpenAlex`、`Semantic Scholar`、`Crossref`、`arXiv`、`DBLP` 与 `OpenReview`。同一论文从多个索引返回时会合并为一条，保留完整来源轨迹并择优补全摘要、作者、DOI 和发布日期。关键词只帮助这些来源召回候选；模型会逐篇评审，再从全局比较中决定本期组合，不用字面命中数或来源配额代替选稿。

还可以按研究领域扩展官方机器接口：`Europe PMC`（生命科学论文与预印本）、`CORE`（开放获取全文与仓储）、`HAL`（多学科开放仓储）、`Zenodo`（论文、预印本与研究产物）和 `DataCite`（更广的 DOI 研究记录）。这些来源与默认来源互补，不要求新用户盲目全开；安装引导会根据研究领域说明覆盖差异，再实测所选接口。

还可按需启用 `Scopus` 和 `Google Scholar`：Scopus 使用 Elsevier API Key（机构环境可另配 Insttoken）；Google Scholar 没有公开官方检索 API，因此插件只支持用户主动配置的 SerpApi，不直接抓取 Scholar 网页。没有这些凭据不会影响开放来源工作。

OpenAlex 的少量匿名请求可用于试用；生产周报建议注册免费 key。注册地址是 [OpenAlex API Settings](https://openalex.org/settings/api)，插件只记录环境变量名，例如 `OPENALEX_API_KEY`，不会复制 key。

```bash
# 查看配置来源及实时连通性
hermes weekly-briefing search-status

# 自选开放来源
hermes weekly-briefing setup \
  --search-source openalex \
  --search-source semantic_scholar \
  --search-source crossref \
  --search-source arxiv \
  --search-source dblp \
  --search-source openreview \
  --search-source europe_pmc \
  --search-source core \
  --search-source hal \
  --search-source zenodo \
  --search-source datacite

# 默认语义模式下，这些概念用于画像与检索，不会按字面淘汰论文。
# 只有明确加 --selection-mode strict 才启用下面的严格 Boolean 约束。
# 每个 --require-all 是一个必需概念；竖线内是同义词
# 下例表示：(概念A 或其同义词) AND (概念B 或其同义词)
# 同时还须在 optional-X/Y/Z 中至少命中 1 个，并排除 unwanted-topic
# 严格模式还要求必需概念出现在标题或同一句摘要中，避免“各自出现但互不相关”
hermes weekly-briefing setup \
  --selection-mode strict \
  --require-all "CONCEPT-A|SYNONYM-A" \
  --require-all "CONCEPT-B|SYNONYM-B" \
  --require-any "OPTIONAL-X|OPTIONAL-Y|OPTIONAL-Z" \
  --minimum-any 1 \
  --exclude-term "UNWANTED-TOPIC" \
  --match-field title \
  --match-field abstract \
  --match-field keywords

# 可选：使用由 Hermes/系统环境管理的 Semantic Scholar 密钥
hermes weekly-briefing setup \
  --search-source semantic_scholar \
  --semantic-scholar-api-key-env SEMANTIC_SCHOLAR_API_KEY

hermes weekly-briefing setup \
  --search-source openalex \
  --openalex-api-key-env OPENALEX_API_KEY

hermes weekly-briefing setup \
  --search-source core \
  --core-api-key-env CORE_API_KEY

# 可选：把凭据留在 Hermes/系统环境，插件只保存变量名
hermes weekly-briefing setup \
  --search-source scopus \
  --scopus-api-key-env SCOPUS_API_KEY \
  --scopus-insttoken-env SCOPUS_INSTTOKEN

hermes weekly-briefing setup \
  --search-source google_scholar \
  --google-scholar-api-key-env SERPAPI_API_KEY
```

插件只保存“使用哪个环境变量”的选择，不接管、复制或输出密钥。安装过程会真实请求每个已选来源；如果全部不可达，引导会停在搜索配置步骤，并说明需要配置来源、凭据、网络出口或代理。

所有外部索引元数据都按“不可信数据”处理：超长、重复、代码化或试图向 AI/爬虫下指令的仓储内容会在模型分析前被统一拦截；其余摘要进入分析模型时也明确作为数据隔离，不能改变分析规则。

## 选稿原则

默认链路是“研究画像 → 多源召回 → 客观清洗 → 模型语义评审 → 全局组合选稿 → 深度分析”。固定代码只负责重复记录、未来日期、无效论文记录、缺失证据、元数据污染和用户明确排除项；它不会因为摘要没有出现某个关键词原词就判定论文不相关。

模型会先逐篇判断核心相关性、方法迁移价值、新颖性、证据可信度和不确定性，再比较候选之间的重复与互补关系，给出正式入选和备用顺序。模型及 Hermes 配置的备用路由全部不可用时，当期任务会明确失败，不会悄悄降级为机械关键词选稿。

短暂的模型或网络异常会按有限次数重新尝试，并继续遵循 Hermes 的主模型与备用模型路由；系统性故障不会被放大成逐篇请求。若最终仍失败，运行记录会保留已脱敏的原因与尝试次数，便于修复后重跑。

## 反馈与偏好

周报通过邮件发送，但反馈**不要求回复邮件**，插件也不会监控收件箱。你可以通过当前 Hermes 已有的任意对话渠道表达明确反馈；确认后，Hermes 调用下面的本地命令记录偏好：

```bash
# 多看、少看或主动探索某个由用户自己给出的主题
hermes weekly-briefing feedback --topic "YOUR TOPIC" --direction more
hermes weekly-briefing feedback --topic "YOUR TOPIC" --direction less
hermes weekly-briefing feedback --topic "YOUR TOPIC" --direction explore

# 查看、撤销或清空
hermes weekly-briefing feedback
hermes weekly-briefing feedback --remove "YOUR TOPIC"
hermes weekly-briefing feedback --clear
```

每次变更同时写入当前偏好和追加式审计记录。只有 `source=user` 的确认记录能影响检索和排序；报告正文、“下周关注”、模型推测及邮件内容都不能自行成为反馈。插件不再宣称存在自动画像学习：跨会话推断研究兴趣需要独立、可审计的生产数据链，本插件目前没有也不会伪装拥有这条链。

## 交付边界

Weekly Briefing **只负责生成周报并发送邮件**，不直接向微信发送任何周报或失败通知。若 Email Watchdog 监测到这封周报邮件并将其提醒到微信，那是另一个完全独立插件的行为。

## 手动管理

通常让 Hermes 操作即可；下面的命令适合排障和自动化：

```bash
# 从 GitHub 安装并启用插件
hermes plugins install Awenforever/hermes-weekly-briefing --enable

# 查看还缺哪些设置
hermes weekly-briefing setup

# 完整体检：研究配置、模型、PDF 与邮件登录
hermes weekly-briefing doctor

# 仅在体检提示缺少 PDF 依赖、且你确认后执行；依赖保存在插件数据目录
hermes weekly-briefing runtime-install --yes

# 手动生成；加 --send-email 才会投递
hermes weekly-briefing run
hermes weekly-briefing run --send-email

# 体检通过后安装计划任务
hermes weekly-briefing schedule-install --schedule "0 2 * * 5"
hermes weekly-briefing schedule-status
```

Agently 邮件工具由插件显式管理：

```bash
hermes weekly-briefing mail-status
hermes weekly-briefing mail-install --yes
hermes weekly-briefing mail-login
```

`mail-login` 是交互步骤，可能打开浏览器或要求在当前终端确认。插件不会伪造登录成功；只有身份检查真实通过，计划任务才允许安装。身份、登录和发送固定使用 Hermes 的持久化 Agently 工作区：`mail-status` 已通过时不会重复要求登录。

PDF 渲染依赖保存在当前 Hermes profile 的 `plugin-data/hermes-weekly-briefing/runtime/`，不会写入或污染 Hermes 核心 Python 环境；升级 Hermes 后也不会被核心依赖同步清除。

在 Docker 中，请让插件命令使用 gateway 的实际运行用户。用 `root` 刷新普通运行用户的 Agently 凭据可能改变文件属主，造成“令牌仍有效但 gateway 无权读取”的假性登录失败。

Agently 可能先返回“邮件已准备、等待确认”。Weekly Briefing 会继续完成确认调用；待确认状态不会被记作 `sent`。

首次安装启用后，Hermes 会提示重启 gateway 以加载插件。重启后继续运行 `setup` 即可；已完成的信息会被识别，不会从头再问。

## 数据、升级与恢复

个人配置、论文索引、作者缓存、报告、投递回执和运行日志都保存在当前 Hermes profile 的：

```text
plugin-data/hermes-weekly-briefing/
```

插件升级不会覆盖该目录。重新安装会优先识别已有数据；计划任务只能在完整体检通过后启用。每次完成分析都会保存可重渲染快照，排版升级可以在不重新调用模型、不改写论文去重历史的前提下安全重建报告。发送失败时，报告仍保留在本地，且不会偷偷改走微信。

## 运行要求

- Hermes `>=0.21.3,<0.22`
- Python 3.11+
- Hermes 中已配置且可用的模型；默认继承主模型与回退链
- WeasyPrint 或 ReportLab，以及可显示中文的系统字体
- Node.js/npm（仅在需要安装 Agently CLI 时）
- Agently CLI 的有效邮件登录

## License

[MIT](LICENSE)
