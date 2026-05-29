# AI Shopping Guide Agent · 作品集说明

**投递方向**：淘天集团 · AI 大模型产品经理  
**项目性质**：可运行的电商智能导购 Agent Demo（作品集项目，非课程作业）  
**作者定位**：AI 产品经理 — 将 LLM 能力转化为可度量、可迭代的电商产品功能

---

## 写在前面

这份材料面向 **HR、业务面试官、产品面试官**，帮助你在 3–5 分钟内理解项目价值。

项目目标不是证明「我会写 Python」，而是说明：

> **我熟悉淘天类电商场景，能把 Search / Recommend / Agent / RAG / AB Test 串成一条对 GMV 和用户体验都有交代的产品链路。**

Demo 可在本地一键运行，建议配合 [`README.md`](README.md) 与 [`interview_pitch.md`](interview_pitch.md) 一起阅读。

---

## 一、项目背景

淘天电商承载大规模搜索与导购流量，商业模型是 **流量 → 转化 → GMV**。当前体系常见三类瓶颈：

1. **Query 理解偏浅**：复合需求（如「留学生写代码 + 轻薄 + 续航」）难以被关键词引擎完整表达  
2. **决策成本高**：用户需在大量 SKU 中自行对比，跳出率与路径长度上升  
3. **推荐难建立信任**：「为什么推这个」说不清，影响点击与加购  

行业方向是 Search 从 **Search Engine** 向 **Agent / Answer Engine** 演进。本项目是该方向下的 **产品化 Demo**，用于展示意图、召回、排序、解释与实验的完整闭环。

---

## 二、用户痛点

| 痛点 | 用户侧表现 | 业务侧影响 |
|------|-----------|-----------|
| 不会写搜索词 | 多次改写 Query、放弃搜索 | Query 改写率高、首搜命中率低 |
| 选择困难 | 长时间浏览、反复对比 | 停留长但转化低 |
| 不信任推荐 | 不愿点击系统推荐 | CTR、加购率受限 |
| 一次搜不准 | 换词重搜、跳出 | 漏斗损耗 |
| 平台难迭代 | 缺乏 Agent 专属数据 | 排序与话术优化缺少依据 |

---

## 三、产品目标

**用户体验目标**

- 降低表达门槛（自然语言主入口）  
- 缩短决策路径（Top 3 + 对比 + 理由）  
- 提升推荐可信度（分数拆解 + 负向解释）  

**业务目标（实验验证方向，非 Demo 承诺值）**

- CTR、加购率提升  
- Query 改写率下降  
- GMV per session 在 Guardrail 下保持稳定或提升  

---

## 四、解决方案

用 **导购 Agent** 替代「只返回商品列表」的搜索体验：

```
自然语言需求
  → Intent Parsing（预算区间 / 品类 / 偏好 / 场景）
  → RAG 召回候选 SKU
  → Multi-objective Ranking（Top 3）
  → Explainable Recommendation + Follow-up
  → 埋点上报 → AB 实验 → 迭代权重与策略
```

**与 Chatbot 的差异**：有明确商品知识库约束、结构化排序、可解释输出与实验度量，而不是开放式闲聊。

---

## 五、核心流程

1. 用户输入中文购物需求（主入口）  
2. 点击「解析需求」→ 自动填充预算 / 品类 / 偏好（可 Manual Override）  
3. 系统从 CSV 知识库召回候选（品类 + 预算过滤）  
4. 7 维加权排序，输出 Top 3  
5. 展示推荐理由、Score Breakdown、「为何不推荐其他商品」  
6. 生成追问，支持 Multi-turn 澄清  
7. 侧边栏展示埋点说明与 Mock AB 结果  

---

## 六、AI 能力映射

| AI / LLM 能力 | 电商产品功能 | Demo 体现 |
|--------------|-------------|----------|
| NLU | 自然语言意图解析 | `intent_parser` + `budget_parser` + rule_hit |
| RAG | 商品知识库召回 | `products.csv` → RAG Recall 面板 |
| Ranking | 多目标推荐 | `recommender.py` 7 维打分 |
| Generation | 导购话术 / 理由 | Explanation + Mock LLM |
| Multi-turn | 意图澄清 | Follow-up Questions |
| Prompt Engineering | Agent 行为约束 | Prompt Design 模块 |
| Evaluation | 效果验证 | 埋点 + Mock AB Test |

---

## 七、数据与实验设计

### 埋点（6 个核心 Event）

| Event | 用途 |
|-------|------|
| exposure | 曝光基数 |
| search_query_submit | 需求表达与 Query 质量 |
| recommendation_click | CTR |
| add_to_cart | 加购率 |
| product_compare | 决策深度 |
| recommendation_feedback | 满意度 / 迭代信号 |

### AB 实验

- **A 组**：传统关键词搜索  
- **B 组**：AI 导购 Agent  
- **Primary**：CTR、加购率、转化率  
- **Secondary**：Query 改写率、满意度  
- **Guardrail**：GMV per session  

Demo 内 AB 为 **Mock 看板**，用于展示 PM 对实验设计的理解；上线需接真实分流与统计显著性检验。

### 排序权重（可调参）

偏好匹配 25%、预算匹配 20%、品类 15%、评分 15%、销量 10%、利润 10%、库存 5% — 支持在 AB 中验证不同策略（如「体验优先」vs「GMV 优先」）。

---

## 八、业务价值

1. **用户**：更少改写 Query、更快收敛到 2–3 个可选 SKU  
2. **平台**：导购漏斗数据可沉淀，支撑排序与话术迭代  
3. **商业化**：`profit_score` 纳入排序，在体验与 GMV 之间留出可调空间  
4. **组织**：产品、算法、运营对「Agent 导购」有共同语言和度量口径  

---

## 九、风险与边界

| 风险 | 应对思路 |
|------|---------|
| LLM 幻觉（编造参数） | RAG 仅基于 CSV 真实字段；超预算标注风险 |
| 推荐偏差（只推高价 / 高利润） | 多目标权重 + AB Guardrail |
| 冷启动 SKU | 降低销量权重，加强标签 / 内容匹配 |
| 延迟 | 排序与规则本地完成；LLM 可用于异步生成文案 |
| 合规与承诺 | 理由中提示风险，避免绝对化表述 |

当前 Demo 使用 **Mock LLM + 规则 NLU**，适合作品集验证产品形态；生产环境需接真实模型、商品中台与风控。

---

## 十、后续迭代

| 版本 | 内容 |
|------|------|
| V1（当前） | Mock LLM + CSV + 规则排序 + 可解释 UI |
| V2 | 真实 LLM + Function Calling |
| V3 | 向量 RAG、语义召回 |
| V4 | 在线反馈 → Learning-to-Rank |
| V5 | 画像个性化、跨品类组合、广告联动 |

---

## 十一、与淘天岗位 JD 的匹配点

| JD 常见要求 | 本项目对应 |
|------------|-----------|
| 大模型 / Agent 产品化 | 完整 Agent 链路 Demo，非单点 Chat |
| 搜索 / 推荐 / 导购 | NLU + RAG + Ranking + Explanation |
| 业务理解（GMV、转化） | profit_score、埋点、AB、Guardrail |
| 数据驱动 | 6 埋点 + 实验看板设计 |
| 跨团队协作 | 意图 / 召回 / 排序 / 解释模块边界清晰 |
| 创新与落地平衡 | 可运行 Demo + 分阶段 Roadmap |

---

## 十二、如何体验（给面试官）

```bash
pip install -r requirements.txt
streamlit run app.py
```

**建议体验路径**

1. 用手机预算区间例句：`预算5000到7000` → 查看 budget_min / budget_max / parsed_budget  
2. 用笔记本例句生成 Top 3 → 展开 Score Breakdown 与 Why not others  
3. 查看 Prompt Design、Follow-up、侧边栏埋点与 AB 模块  

---

## 一句话 Summary

> **用 Agent 把「搜商品」升级为「帮用户做购买决策」—— 可解释、可度量、可实验，对应淘天 Search → Agent 导购的演进方向。**

---

*配套文档：[`README.md`](README.md) · [`interview_pitch.md`](interview_pitch.md) · 运行环境 Python 3.10+ · 无需 API Key*
