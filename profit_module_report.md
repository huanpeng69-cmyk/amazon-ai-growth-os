# 产品利润测算模块 — 交付说明

> 项目：Amazon AI Growth OS | 模块：Profit Analysis
> 服务状态：运行于 `http://localhost:8002`（PID 11820）
> 数据策略：本模块**全部为真实数据驱动的确定性计算**，不调用 LLM 编造任何数字；所有金额来自用户/数据源输入或启发式估算公式（公式可见、可审计）。

---

## 1. 模块能做什么

让 AI 不仅判断「产品有没有市场」，更进一步判断「值不值得投入」。对单个产品输入售价与成本后，自动产出一份**产品盈利报告**，包含：

- 售价 / 单件成本（产品、头程物流、FBA、佣金、广告、其他）
- Amazon 平台费用（佣金 + FBA）
- 广告费用（按 ACOS 反推）
- 单件毛利 / 单件净利 / 净利率
- 月度毛利 / 月度净利 / 月经营净利
- 盈利评分（0–100）
- 投资建议（invest / cautious / avoid）+ 理由
- 风险提示（6 维风险 + 缓解建议）
- 销量预测（月销量）+ 回本周期 + 盈亏平衡销量

## 2. 架构：三个 Agent + 编排器

```
                ┌─────────────────────────────────────────┐
   成本/售价 ──▶ │            ProfitReport (编排器)           │
   数据源    ──▶ │  build_profit_report(inp)                │
                └───────┬───────────────┬──────────────────┘
                        │               │
            ┌───────────▼───┐    ┌──────▼──────────┐    ┌──────────▼───────┐
            │ Profit Agent   │    │ Sales Forecast  │    │ Risk Agent        │
            │ 成本/费用/利润  │    │ 销量/回本/盈亏  │    │ 6维风险/评分/建议 │
            │ 确定性计算      │    │ 启发式估算      │    │ 加权评估          │
            └───────────────┘    └─────────────────┘    └──────────────────┘
                        │               │                    │
                        └───────────────┴────────────────────┘
                                    │
                            产品盈利报告 (JSON)
                                    │
                    ┌───────────────┴───────────────┐
              前端「利润分析」页面              产品空间回写 (mod_profit)
```

- **Profit Agent** (`app/agents/profit/agent.py`)：单件与月维度利润拆解、盈利评分、投资建议。纯计算。
- **Sales Forecast Agent** (`app/agents/sales_forecast/agent.py`)：按类目基准需求 × 价格竞争力 × 广告流量 × 竞争强度 启发式估算月销量，并算回本周期与盈亏平衡销量。
- **Risk Agent** (`app/agents/risk/agent.py`)：利润率 / 广告依赖 / 回本 / 价格竞争 / 供应链 / 平台政策 六维风险，加权得 `risk_score` 与 `risk_level`，输出每条风险的缓解建议。

## 3. 三种数据来源（已打通）

| 来源 | 取值方式 | 接口 |
|------|----------|------|
| ① 手动输入 | 前端表单填写售价与各项成本 | `POST /api/agent/profit` (`cost_source=manual`) |
| ② Excel/CSV 上传 | 上传成本表，服务端自动解析字段（中英文同义词映射、百分比归一化） | `POST /api/profit/upload_cost` |
| ③ 供应链接口 | 服务端调用 Supply Chain Connector 拉取成本（当前为 **Mock Connector**，契约预留真实接口替换点） | `GET /api/profit/supply_chain` |

> 解析器 `app/agents/profit/sources.py` 支持「表头+数值行」与「名称|数值」两种表格形态，并对 `product_cost / 采购成本 / 产品成本`、`shipping / 头程 / 物流` 等做同义词归一；数值 >1 视为百分比自动转 0–1。

## 4. 产品盈利报告（实时样例）

请求：`POST /api/agent/profit`（manual）
产品：Cat Water Fountain（US / Pet Supplies，售价 $29.99）

| 指标 | 数值 |
|------|------|
| 单件售价 | $29.99 |
| 单件成本合计（产品+物流+平台费+广告+其他） | $21.10 |
| 单件毛利 | $13.29 |
| 单件净利 | $8.89 |
| **净利率** | **29.65%** |
| 预测月销量 | 316 件 |
| 月度经营净利 | $2,750.09 |
| 盈亏平衡月销量 | 6.7 件 |
| 回本周期 | 0.5 个月 |
| **盈利评分** | **87.4 / 100** |
| **投资建议** | **invest（建议投入）** |
| 风险等级 | low（risk_score 24.9） |

> 建议理由原文：「单件净利率 29.6%，盈利质量较好，建议投入。建议先小批量验证转化，再逐步加大广告与备货。」
> 风险最高项：供应链风险（severity 55）——建议多供应商 / 安全库存对冲断货。

## 5. 前端页面（利润分析）

路径：`#/profit`（侧边栏「利润分析」入口）

- **盈利评分环** (`scoreRing`)：一眼看清值不值得投。
- **利润瀑布图** (`waterfallChart`)：售价 → 逐级扣减成本/费用 → 净利，直观展示钱去哪了。
- **成本结构环形图** (`donutChart`)：产品 / 物流 / 平台费 / 广告 / 其他 占比。
- **指标行 + 投资建议 + 风险提示列表**：完整报告。
- 表单支持：手动填成本、**上传 Excel 成本表**、**调用供应链接口** 三种入口，数据源下拉切换。

## 6. 与规划中 Data Hub 的衔接

利润模块的三种来源正好对应 Data Hub 规划里的两大部分，可作为 Data Hub 的首批落地抓手：

```
                         Data Hub (规划中)
   ┌─────────────────────────────────────────────────────┐
   │ External Data Connector        User Upload Center     │
   │  • 供应链接口 (Supply Chain)  • CSV/Excel 成本表      │
   │    └─ profit/sources.py         └─ profit/upload_cost  │
   │       SupplyChainConnector        + parse_cost_bytes    │
   │                                                    │
   │ Data Processing Pipeline                            │
   │  • 字段识别 / 百分比归一化 / 同义词映射              │
   │    └─ sources.extract_cost_fields                   │
   │                                                    │
   │ Agent Data Interface                               │
   │  • Profit/SalesForecast/Risk Agent 只经 Data Layer  │
   │    取数，绝不自行生成数据  ✓ 已实现                  │
   └─────────────────────────────────────────────────────┘
```

即：利润模块已经**提前实现了 Data Hub 的「Agent 禁止自行编造数据、必须经数据层取数」这一核心约束**，并落地了 User Upload Center（成本表上传）与一条 External Connector（供应链 Mock）。待 Data Hub 主线启动时，可直接把 `profit/sources.py` 提升为 `data/connectors/` 与 `data/parser/` 的标准组件。

## 7. 验证结果

- `POST /api/agent/profit` → HTTP 200，净利率/评分/建议/月维度全部正确。
- `GET /api/profit/supply_chain` → HTTP 200，返回 `is_mock=true`、SKU `MOCK-2695`、派生成本字段。
- `POST /api/profit/upload_cost` → HTTP 200，CSV/XLSX 解析单测通过（中英文表头、百分比、混合形态）。
- 前端 `api.js / app.js / views.js / visuals.js` 的 `node --check` 全部通过；后端 `py_compile` 全部通过。
- 报告已可回写产品空间（`mod_profit` stage），供后续联动图消费。

## 8. 下一步建议（待排期）

1. **Data Hub 架构升级（主线，此前被本模块打断）**：新增 `data/` 目录（connectors / upload / parser / cleaner / schemas），External Data Connector、Data Processing Pipeline、Agent Data Interface；产出数据流架构图、数据库设计、接口设计。利润模块的来源层可直接并入。
2. **联动图补全**：将 `profit / forecast / risk` 产出接入 `build_linkage` 的 upstream / injections，使「利润结论」能反向驱动市场/竞品/广告建议。
3. **供应链真实接口**：把 `SupplyChainConnector` 的 Mock 替换为真实 ERP / 供应商 API（契约已预留）。
