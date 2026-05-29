# AI Shopping Guide Agent

> 将自然语言购物需求转化为 **Intent Understanding → RAG Recall → Multi-objective Ranking → Explainable Recommendation → AB Testing** 的可运行电商导购 Agent Demo。

[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)]()

**本地可运行 · 无需 API Key · 面向 AI 产品经理作品集**

---

## 一句话介绍

用 Agent 链路把「帮我搜商品」升级为「帮我做购买决策」：理解需求、召回候选、多目标排序、可解释推荐，并配套埋点与 AB 实验框架。

---

## 项目背景

电商搜索长期依赖关键词匹配。当用户表达复合需求时——例如「适合留学生写代码的轻薄本，预算 6000 左右，续航好」——往往需要多次改写 Query，决策成本高、转化路径长。

本项目回答的问题是：**大模型能力如何产品化为导购 Agent**，而不是做一个只能聊天的 Chatbot。Demo 覆盖从用户输入到推荐输出、再到实验度量的完整产品闭环，便于面试官本地体验。

---

## 目标用户

| 用户类型 | 典型场景 |
|---------|---------|
| **Primary** | 有明确购物意图，但难以用关键词表达复杂需求（学生购机、通勤选耳机等） |
| **Secondary** | 对比型消费者，希望在 2–3 个 SKU 间快速决策 |
| **Platform** | 搜索 / 推荐 / 导购产品、运营与数据团队（关注 CTR、加购、GMV） |

---

## 核心功能

- **Natural Language Intent Parsing**：从中文 Query 解析预算区间、品类、偏好、使用场景（含 `rule_hit_reason` 可解释命中）
- **Manual Constraints**：自然语言为主入口，预算 / 品类 / 偏好可手动微调（Manual Override）
- **RAG Recall**：基于 `products.csv` 商品知识库（24 SKU）进行候选召回
- **Multi-objective Ranking**：7 维加权打分，输出 Top 3
- **Explainable Recommendation**：推荐理由、Score Breakdown、负向解释（Why not others?）
- **Prompt Design**：展示 User Need + Retrieved Products + Business Rules 的 Prompt 结构
- **Follow-up Questions**：Multi-turn 意图澄清
- **Mock AB Test + Tracking**：6 大埋点与 A/B 实验结果展示

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| UI | Streamlit |
| 数据处理 | pandas |
| 知识库 | CSV（`products.csv`） |
| NLU | 规则引擎 + `budget_parser`（预算范围优先） |
| LLM | Mock 优先，预留真实 API 接口（`llm_service.py`） |

---

## 项目架构

```
用户 Query + 可选手动约束（Budget / Category / Preferences）
        │
        ▼
  intent_parser.py      品类 / 偏好 / 场景规则解析
  budget_parser.py      预算范围优先（如 5000–7000）
        │
        ▼
  recommender.py        filter → score → rank → explain
  products.csv          RAG 商品知识库（24 SKU）
        │
        ▼
  prompt_design.py      Prompt 模板（需求 + 召回 + 业务规则）
  llm_service.py          Mock / Optional LLM
        │
        ▼
  analytics.py          埋点定义 · Mock AB 实验
        │
        ▼
  app.py                Streamlit 主界面
```

**文件结构**

```
├── app.py                 # Streamlit 主应用 · parse_user_intent
├── intent_parser.py       # NL 意图解析（品类 / 偏好 / 场景）
├── budget_parser.py       # 预算范围解析（独立模块，稳定导入）
├── recommender.py         # 召回 · 多目标排序 · 负向解释
├── llm_service.py         # Mock / Optional LLM
├── prompt_design.py       # Prompt 设计展示
├── analytics.py           # 埋点 · Mock AB
├── products.csv           # 24 SKU（laptop / phone / headphone / skincare）
├── portfolio_note.md      # 作品集说明（HR / 业务向）
├── interview_pitch.md     # 面试口述稿 · 问答
└── requirements.txt
```

---

## 如何运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

Windows：

```bash
py -3 -m pip install -r requirements.txt
py -3 -m streamlit run app.py
```

浏览器访问 **http://localhost:8501**

**推荐操作顺序**

1. 输入自然语言购物需求（主入口）
2. 点击 **解析需求 / Parse Intent**（自动填充预算 / 品类 / 偏好）
3. 按需微调 Manual Constraints
4. 点击 **Generate Recommendation · 生成推荐**

> 若直接点击生成推荐，系统会先自动解析自然语言。请保持终端窗口运行，关闭后页面将无法访问。

---

## 测试输入示例

### 示例 1：笔记本 · 单预算

**输入**

```
我想买一台适合留学生写代码和上课用的轻薄笔记本，预算 6000 左右，最好续航好一点，偶尔玩游戏。
```

**预期**：品类 Laptop · 场景 coding / study · Top 3 为轻薄本 SKU · 价格围绕 ¥6000

---

### 示例 2：手机 · 预算区间

**输入**

```
我想买一台拍照好、续航强的手机，预算5000到7000，最好评价高一点
```

**预期**

| 字段 | 值 |
|------|-----|
| budget_min | ¥5000 |
| budget_max | ¥7000 |
| parsed_budget | ¥7000 |
| 表单 Budget 默认 | 7000 |

---

### 示例 3：笔记本 · 预算区间

**输入**

```
我想买一台适合留学生写代码和上课用的轻薄笔记本，预算8000到10000，最好续航好一点，性能稳定，评价高
```

**预期**：budget_min=8000 · budget_max=10000 · parsed_budget=10000

---

## Demo 截图占位

> 建议在 `docs/screenshots/` 目录补充以下截图，并替换下方占位链接。

| 模块 | 占位说明 |
|------|---------|
| 首页输入 | `![首页](docs/screenshots/01-home.png)` |
| 意图解析 | `![意图解析](docs/screenshots/02-intent.png)` |
| Top 3 推荐 | `![推荐结果](docs/screenshots/03-top3.png)` |
| Score Breakdown | `![分数拆解](docs/screenshots/04-breakdown.png)` |
| AB 实验 | `![AB实验](docs/screenshots/05-abtest.png)` |

---

## 产品设计亮点

1. **NL-first**：自然语言为主入口，结构化约束为可编辑辅助层，贴近真实导购场景
2. **预算范围识别**：支持 `5000到7000`、`5k到7k`、`8000-10000` 等，区间匹配分最高
3. **可解释推荐**：不只给 Top 3，还展示分数拆解与「为何不推荐其他商品」
4. **Prompt 可视化**：让面试官看到 Agent 的输入约束，而非黑盒对话
5. **PM 视角闭环**：意图 → 召回 → 排序 → 解释 → 追问 → 埋点 → AB

---

## 推荐排序逻辑

**流程**：品类过滤 → 预算上限过滤（`price ≤ budget_max`）→ 7 维打分 → 加权求和 → Top 3

**维度与默认权重**

| 维度 | 权重 | 说明 |
|------|------|------|
| category_score | 15% | 品类是否匹配 |
| budget_score | 20% | 区间内满分；低于下限次优；超上限降分 |
| rating_score | 15% | 用户评分 |
| sales_score | 10% | 销量热度（log 缩放） |
| preference_score | 25% | 偏好 / 场景标签匹配 |
| stock_score | 5% | 库存充足度 |
| profit_score | 10% | 平台收益信号（GMV 平衡） |

**公式**

```
final_score = 0.15×category + 0.20×budget + 0.15×rating
            + 0.10×sales   + 0.25×preference + 0.05×stock + 0.10×profit
```

权重可在 AB 实验中调整，用于验证「体验优先」与「GMV 优先」等策略差异。

---

## AB Test 设计

| 项目 | A 组 · Control | B 组 · Treatment |
|------|----------------|------------------|
| 策略 | 传统关键词搜索结果 | AI 导购 Agent |
| Primary | CTR · 加购率 · 转化率 | 同左 |
| Secondary | Query 改写率 · 用户满意度 | 同左 |
| Guardrail | GMV per session 不显著下降 | 同左 |
| 分流 | 50/50 · 按 user_id 哈希 | 同左 |

Demo 内为 **Mock 数据**（按 Query hash 确定性生成），用于展示实验看板形态，不代表真实线上结果。

---

## 埋点设计

| Event | 触发时机 | 业务意义 |
|-------|---------|---------|
| `exposure` | 导购页 / 推荐卡片曝光 | 漏斗入口 · AB 分母 |
| `search_query_submit` | 提交自然语言需求 | Query 质量 · 意图表达 |
| `recommendation_click` | 点击推荐商品 | **CTR** |
| `add_to_cart` | 加购 | **加购率** · GMV 前置 |
| `product_compare` | 查看对比表 | 决策深度 |
| `recommendation_feedback` | 点赞 / 点踩 | 满意度 · 模型迭代信号 |

详见 `analytics.py` 中 `get_tracking_events()`。

---

## 为什么适合淘天 AI 大模型产品经理岗位

- **场景对齐**：搜索升级、智能导购、转化与 GMV，对应淘天核心业务
- **能力映射清晰**：NLU、RAG、Ranking、Generation、Multi-turn、Prompt、Evaluation 均有产品化落点
- **不是纯 Demo**：包含埋点、AB、业务规则（profit_score）、风险边界说明
- **可现场体验**：本地运行，面试官可实际操作 Parse Intent → Generate Recommendation
- **角色定位准确**：侧重意图设计、解释性、实验度量，而非只展示模型调用

更完整的投递说明见 [`portfolio_note.md`](portfolio_note.md)，面试口述见 [`interview_pitch.md`](interview_pitch.md)。

---

## 后续迭代方向

| 阶段 | 方向 |
|------|------|
| V2 | 接入 Qwen / GPT，Function Calling 调用 recommender |
| V3 | Embedding RAG 替代纯标签匹配，提升语义召回 |
| V4 | 真实埋点 pipeline + Learning-to-Rank |
| V5 | 用户画像个性化 · 跨品类 Bundle · 广告位联动 |

---

## License

MIT · Portfolio demo, free to use and modify.
