# Amazon AI Growth OS —— 生产级就绪跟踪文档

> 状态：评估完成，待逐项推进。最后更新：2026-08-15
> 方法：Aegis 有界扫描（README/基线 + 定点取证），未通读全部 143 个源文件。
> 结论：**业务正确性（数据真实性）已修复；工程化 / 运维 / 安全层面距生产仍有较大缺口。**

## 跟踪总览（勾选推进）

### P0 — 上线前阻塞项
- [x] P0-1 建立测试套件（pytest）+ GitHub Actions CI（lint/type/test 门禁）
  - 交付：`backend/tests/{test_agnes,test_util,test_agents_honest_degradation}.py`（共 32 用例，全绿）；
    `backend/pytest.ini`（pythonpath）、`backend/pyproject.toml`（ruff/mypy 配置）、
    `backend/requirements-dev.txt`、` .github/workflows/ci.yml`。
  - **门禁范围**：`ruff` 当前只把「真实正确性」（`F`/`E`/`W`）纳入硬性门禁，风格类（`UP`/`I`/`B`/`SIM`/`E501`/`E402`/`E702`）暂忽略，避免无谓重构；`mypy` 当前为**允许失败的信息性步骤**（全仓 143 文件基本无类型标注，共 114 处类型不一致，含若干潜在真实 bug 如 `lifecycle/service.py` 访问不存在的 `MarketOutput.title`），待 P1-4 / P2-4 收紧。
- [x] P0-2 API 认证 / 授权中间件（Bearer/API Key；写操作强制 token）
  - 交付：`backend/app/security.py`（`get_current_key` 依赖，支持 Bearer / X-API-Key / `?api_key`）；
    `main.py` 对所有业务路由（agent/blue_ocean/tools/lifecycle/workspace/profit/data）统一挂该依赖，
    `/api/health` 与 `/` 静态开放；`API_AUTH_TOKEN` 仅在配置时强制（未配置保持开放，向后兼容）。
  - 测试：`backend/tests/test_auth.py`（6 用例，TestClient 验证开放/401/Bearer/X-API-Key/query/错误 Key）。
  - 验收：未配 key 调用业务接口 200；配 key 无令牌 401；配 key 且正确令牌放行。
- [x] P0-3 速率限制 / 配额（内存限流器 + Bright Data 重试退避 + 并发信号量）
  - 交付：`backend/app/ratelimit.py`（零依赖固定窗口限流器：默认 20/min，重端点 5/min，按 API Key/IP 维度，429 带 `Retry-After` 与 `X-RateLimit-*` 头）；`backend/app/main.py` 受保护路由统一挂 `rate_limit_default`，`backend/app/routers/agent.py` 的 `/run`、`/market_research` 额外挂 `rate_limit_heavy`；`backend/app/mcp/brightdata_client/client.py` 增加指数退避重试（重试 5xx/429/连接错误，尊重 `Retry-After`，**不**重试 4xx/401）、`threading.Semaphore` 并发控制、统一可配超时，新增 `BrightDataRateLimitError`/`BrightDataServerError` 异常。
  - 测试：`backend/tests/test_ratelimit.py`（7 用例，含 TestClient 集成）、`backend/tests/test_brightdata_client.py`（11 用例，重试/429/退避/信号量/解析）。全仓 **57 passed**，ruff 全绿。
  - **设计取舍**：原计划用 slowapi，但其 `@limiter.limit` 装饰器强制端点签名含 `request: Request`，需改动全部 8 个路由文件；故改用零依赖自研限流器（与 Bright Data 客户端「标准库实现」风格一致）。多 worker / 多实例共享配额需把 `Window.bucket` 换成 Redis —— 见 P0-4 docker-compose 注释。
  - 验收：同 IP 连打 25 次受保护端点 → 前 20 次 200、后 5 次 429（带 `Retry-After`）；BD 瞬时 429/5xx 经退避自愈，最终失败仍按既有 `BrightDataError` 触发诚实降级。
- [x] P0-4 可复现构建（Dockerfile + 版本锁定 + gunicorn 多 worker + docker-compose）
  - 交付：`requirements.lock`（锁定与 `requirements.txt` 下限兼容的真实稳定 PyPI 版本，全依赖树精确 `==`，含 gunicorn/uvloop/psycopg2-binary/redis）；`Dockerfile`（`python:3.13-slim` + `pip install -r requirements.lock` + 非 root 用户 + `HEALTHCHECK` 命中 `/api/health` + `gunicorn app.main:app -c gunicorn.conf.py`）；`backend/gunicorn.conf.py`（UvicornWorker，worker 数/超时/日志全由环境变量驱动，`WEB_CONCURRENCY` 可调）；`.dockerignore`（排除缓存/测试/DB/日志/机密）；`docker-compose.yml`（app + postgres:16 + redis:7，健康检查、命名卷、`env_file` 可选注入）；`requirements.txt` 取消 gunicorn 注释并加生产可选 psycopg2-binary/redis。
  - 测试：`backend/tests/test_deploy_config.py`（6 用例：gunicorn worker_class/workers/bind/超时、`WEB_CONCURRENCY` 覆盖、lock 对核心依赖 `==` 锁定、Dockerfile/compose/.dockerignore 存在、`app.main:app` 可导入）。全仓 **63 passed**，ruff 全绿。
  - **版本锁定说明**：本机 venv 的依赖为沙箱合成版本号（如 `fastapi 0.141.1`、`starlette 1.3.1`、`certifi 2026.x`），公共 PyPI 不存在，直接 `freeze` 会导致他人 `docker build` 失败；故 `requirements.lock` 锁定为与 `requirements.txt` `>=` 下限兼容的**当前公共稳定版**（fastapi 0.115.6 / uvicorn 0.34.0 / gunicorn 23.0.0 / pydantic 2.10.4 / SQLAlchemy 2.0.36 等），保证在真实环境可复现构建；可用 `pip-compile` 重新生成。
  - 验收：`docker compose config` 校验通过（拓扑/YAML 合法）；gunicorn 配置与 app 入口经测试守护。**注**：本机 Docker Desktop 的 Linux 引擎当前未启动，未实跑 `docker build`/`docker run`，请在有守护进程的环境执行 `docker build -t amazon-ai-growth-os .` 与 `docker compose up --build` 做最终镜像层验证。

### P1 — 重要（稳定性 / 可观测性）
- [x] P1-1 全局异常处理 + 统一 JSON 错误包（含 trace_id）
  - 交付：`backend/app/errors.py`（统一错误体 `{error, message, trace_id[, details]}`；`StarletteHTTPException` 兜底捕获 FastAPI `HTTPException` 与路由级 404、`RequestValidationError` 422 带 `details`、`Exception` 兜底 500；生产默认不泄露内部细节/堆栈，仅 `EXPOSE_ERRORS=1` 才带；保留限流 `Retry-After`/`X-RateLimit-*` 头）；`backend/app/middleware.py`（`TraceIDMiddleware`：每请求生成/复用 `X-Request-Id`/`X-Trace-Id` 为 `trace_id`，写入 `request.state` 并回写响应头 `X-Trace-Id`）；`backend/app/main.py` 接入中间件与 `install_exception_handlers`。
  - 测试：`backend/tests/test_errors.py`（6 用例：trace_id 头存在、未捕获异常→JSON internal 非 HTML、404→not_found、429 保留 Retry-After、422→validation_error+details、EXPOSE_ERRORS 泄露堆栈）。全仓 **69 passed**，ruff 全绿。
  - **关键坑（已记录）**：①Starlette 中 `(Exception, ...)` 不作兜底，必须挂 `StarletteHTTPException` 才能覆盖 404 与各类 HTTPException；②`TestClient` 默认 `raise_server_exceptions=True` 会把 500 抛给测试，须设 `False` 才能验证 JSON 错误体；③跨异常边界 `contextvars` 不可靠，改为 `request.state.trace_id`。
  - 验收：真实 app 冒烟——404 返回 `{"error":"not_found",...}`、未捕获异常返回 `{"error":"internal","message":"服务器内部错误…","trace_id":...}`（无堆栈）、传入 `X-Request-Id` 被原样回显为 `X-Trace-Id`。
- [x] P1-2 集中日志 + 链路追踪（dictConfig 结构化日志 + 请求 ID）
  - 交付：`backend/app/logging_config.py`（`configure_logging()` 用 `logging.config.dictConfig` 把根日志配为**单行 JSON** 输出到 stdout，字段含 `timestamp`/`level`/`logger`/`message`/`request_id`/`trace_id`/`module`/`func`/`line`/异常 `error`；异常以 `exc_text` 附加）；手写 `JsonFormatter`（零新依赖，沿用标准库风格）；`request_id_var`(contextvars) 由 `TraceIDMiddleware` 在请求内注入（与 P1-1 `trace_id` 同源，`X-Trace-Id` 回显，`X-Request-Id` 复用）；`app/main.py` 在导入期调用 `configure_logging()` 并把 `_migrate` 裸 `print` 改为 logger。
  - 测试：`backend/tests/test_logging.py`（4 用例：JSON 合法单行含全部字段、请求内日志带 `request_id` 且与响应头 `X-Trace-Id` 一致、异常日志经 `extra` 带 `trace_id`、真实 app 接入冒烟）。全仓 **75 passed**，ruff 全绿。
  - 验收：启动期/请求期日志均为 JSON 单行（实测 `advertising`/`httpx` 等 logger 输出含 `request_id`/`trace_id` 字段）；可按 `request_id`/`trace_id` 串联一次调用链（与 P1-1 错误包的 `trace_id` 一致）。
  - 备注：跨异常边界 contextvars 不可靠（同 P1-1），故错误日志在 `errors.py` 以 `extra={"trace_id":...}` 显式注入，确保 JSON 字段始终带 `trace_id`；`OpenTelemetry` 接入留作未来可选增强。
- [x] P1-3 数据库迁移（PostgreSQL + Alembic；替换手动 `_migrate`）
- [x] P1-4 同步阻塞治理 + 请求整体超时（asyncio 并发 / 超时熔断）
- [x] P1-5 生产配置硬化（`/docs` 关闭、CORS 收紧）

### P2 — 优化项
- [x] P2-1 结果缓存层（keyword+country TTL）
- [x] P2-2 前端构建 / 打包（Vite + 哈希 + CSP）
- [x] P2-3 API 版本化（`/api/v1`）
- [ ] P2-4 配置校验（pydantic-settings）
- [ ] P2-5 image agent 接真实生图后端（去掉默认 mock）

---

## 已具备的优势（勿回退）

| 项 | 说明 | 证据 |
|---|---|---|
| Agent 数据真实性 | 真实 Bright Data 抓取 + 真实评论 + 大模型合成；无数据诚实降级 | 本次修复成果 |
| CORS 白名单 | 默认回环地址 + 可配 `CORS_ALLOW_ORIGINS`，非通配 | `backend/app/main.py:90-122` |
| LLM 调用韧性 | `agnes.chat` 统一 `AgnesError` + 自动重试 3 次 | `backend/app/llm/agnes.py` |
| 健康检查 | `/api/health` 返回 `{status, service}` | `backend/app/main.py:134` |
| 配置安全 | 密钥 GET 脱敏；写操作可选 `SETTINGS_API_TOKEN` | `backend/app/config_store.py`、`routers/settings.py:29-48` |
| 数据层抽象 | connector 模式 `auto/live/fixture`，便于切换数据源 | `backend/app/config_store.py` `_CONFIG_SPEC` |

---

## P0 — 上线前阻塞项

### P0-1 测试套件 + CI
- **问题**：无 `tests/` 目录，仅有根目录手写脚本 `qa_test.py` / `test_agent.py` / `test_tools.py`（需手动跑，非回归保护）；无 `.github/workflows`。
- **影响**：任何改动都可能悄悄回归（"编造数据"类问题正是因无回归测试而长期潜伏）。
- **建议方案**：
  - 引入 `pytest`，按 `backend/tests/{unit,integration}` 组织；优先覆盖：`agnes` 异常/重试、各 agent 的"无数据诚实降级"契约、`extract_json` 解析、竞品 `est_market_share` 永不为伪造值。
  - 加 GitHub Actions：`.github/workflows/ci.yml`，步骤 = `ruff` lint + `mypy` 类型（信息性）+ `pytest`。
- **验收标准**：`pytest` 在 CI 全绿；新增 agent 改动必须带对应测试；CI 拦截 lint/type 错误。
- **✅ 已完成（2026-08-04）**：测试套件 32 用例全绿（含 agnes 重试/异常回归、各 agent 诚实降级契约、`extract_json`）；
  CI 已落地，`ruff` 为硬性门禁、`mypy` 为信息性步骤。详见上方总览 P0-1 注释。

### P0-2 认证 / 授权
- **问题**：除 settings 可选 token 外，所有 `/api/agent`、`/api/data`、`/api/blue-ocean` 等端点完全开放（`backend/app/main.py` 仅挂载 `CORSMiddleware`，无 auth 中间件）。
- **影响**：一旦对外暴露，任何人可调用并**烧 Bright Data / Agnes 按量额度**；数据写接口无保护。
- **建议方案**：
  - 加 `FastAPI` 依赖 `get_current_key`：校验 `Authorization: Bearer <API_KEY>` 或 `X-API-Key` 头；密钥存环境变量/`config_store`，不进代码。
  - 全局默认要求 key；`/api/health`、`/` 静态资源可放行。
  - settings 写接口（`PUT /api/settings`）强制 `SETTINGS_API_TOKEN`（现有机制复用并强化）。
- **验收标准**：无有效 key 调用 agent 接口返回 401；写配置无 token 返回 403。
- **✅ 已完成（2026-08-04）**：见上方总览 P0-2 注释。`get_current_key` 已挂到全部业务路由；`API_AUTH_TOKEN` 仅在配置时强制，未配置保持本地开放。settings 写接口沿用 `SETTINGS_API_TOKEN`（本项未改动其逻辑）。

### P0-3 速率限制 / 配额
- **问题**：
  - 端点无节流；外部依赖按量计费，高频调用会烧钱 + 触发 429。
  - **Bright Data 客户端只有 timeout、无重试、无 429 退避、无并发控制**（`backend/app/mcp/brightdata_client/client.py:81,111,191` 仅 `timeout=60`）。
- **建议方案**：
  - API 层加 `slowapi` 限流（按 IP/key，如 20 req/min）；重操作（agent run）单独配额。
  - Bright Data 客户端加：指数退避重试（尊重 `Retry-After`/429）、并发 `Semaphore`、超时统一。
- **验收标准**：压测下单 key 超阈值返回 429；BD 瞬时 429 自愈不报错。
- **✅ 已完成（2026-08-04）**：见上方总览 P0-3 注释。API 层改用零依赖自研限流器（未引入 slowapi，理由见总览），Bright Data 客户端已完成重试退避 + 并发信号量 + 统一超时。

### P0-4 可复现构建 / 部署
- **问题**：`requirements.txt` 全 `>=`、零版本锁定（grep 命中 0 个 `==`）；无 `Dockerfile`；`gunicorn` 在 requirements 被注释。
- **影响**：构建不可复现，依赖漂移/供应链风险；无标准部署形态。
- **建议方案**：
  - 加 `Dockerfile`（python:3.13-slim + `pip install -r requirements.lock` + `gunicorn -k uvicorn.workers.UvicornWorker -w N`）。
  - 生成锁定文件（pip-tools `requirements.lock` 或 `poetry.lock`）；取消注释并启用 `gunicorn`。
  - 提供 `docker-compose.yml`（app + postgres + redis[限流用]）。
- **验收标准**：`docker build` + `docker run` 一条命令起服务；依赖版本锁定可复现。

---

## P1 — 重要（稳定性 / 可观测性）

### P1-1 全局异常处理 + 统一错误包
- **问题**：仅 `routers/agent.py` 有少量 `HTTPException(502/400)`；其余异常直接 500，无一致 JSON 错误体。
- **建议方案**：加 `app.add_exception_handler(Exception, ...)` + `HTTPException` handler，统一返回 `{"error": "internal"|"bad_request", "detail": ..., "trace_id": ...}`；非生产环境才带堆栈。
- **验收标准**：任意未捕获异常返回统一 JSON（非 HTML），含 `trace_id`；生产不泄露内部细节。

### P1-2 集中日志 + 链路追踪
- **问题**：全项目仅 `logging.getLogger`，无 `basicConfig/dictConfig`、无 format/级别/轮转/请求 ID（`backend/app/**` grep 无 `dictConfig`）。排障靠 `server.log` 裸输出。
- **建议方案**：`logging.dictConfig` 结构化(JSON) 日志；请求 ID 中间件（`X-Request-ID`）；可选 OpenTelemetry 接入。
- **验收标准**：日志为 JSON、带 `request_id`/`trace_id`/时间戳/级别；可按请求 ID 串联一次调用链。

### P1-3 数据库迁移（Alembic 托管 schema，双后端 SQLite/PostgreSQL）
- **问题**：默认 SQLite（`backend/app/database.py` `DATABASE_URL`）；`init_db()` 用 `create_all`；`main.py:_migrate()` 仅硬编码 2 个列的 `ALTER`（`category`/`platform`），schema 演进脆弱。无 Alembic；`db/schema.sql`（PostgreSQL）与 ORM 模型不一致（`task_id` 写成 `UUID`、缺 lifecycle/data 多表），未真正用上。
- **方案**：引入 Alembic 作为**唯一权威 schema 来源**，彻底替换手写 `_migrate()`。
  - `backend/alembic.ini`：ASCII-only（Alembic 用平台 locale 编码读 ini，GBK 无法解 UTF-8 注释，故此文件不得含中文）；`script_location=migrations`、`prepend_sys_path=.`；`sqlalchemy.url` 为本地默认，生产由 `DATABASE_URL` 环境变量覆盖。
  - `backend/migrations/env.py`：导入 `app.database.Base` 作 `target_metadata`；优先读 `DATABASE_URL` 覆盖连接；SQLite 下开 `render_as_batch`（后续 ALTER/DROP 列迁移可在 SQLite 生效）；显式把 `backend/` 加入 `sys.path` 保证任意工作目录可导入 `app`。
  - `backend/migrations/versions/0001_initial.py`：手写初始迁移，**完整覆盖全部 8 张业务表**（`research_tasks`/`product_opportunities`/`growth_products`/`stage_artifacts`/`raw_fetches`/`products`/`reviews`/`keyword_metrics`/`ad_metrics`/`image_assets`），`growth_products` 含被原 `_migrate` 硬编码的 `category`/`platform`；`JSON` 列双后端通用（PG→JSON、SQLite→TEXT），时间戳 `server_default=CURRENT_TIMESTAMP` 双后端通用；FK 带 `ON DELETE CASCADE`。
  - `backend/app/migrations_run.py`：`run_migrations()` 以编程方式对当前 `DATABASE_URL` 执行 `alembic upgrade head`（优先 env，回落到 `app.config.DATABASE_URL` 绝对路径，避免 CWD 相对错位），连接串密码脱敏后写日志；由 `main.py` 的 `lifespan` 调用，失败即终止启动。
  - `backend/app/main.py`：**移除 `_migrate()` 与 `init_db()` 启动调用**，改由 `run_migrations()` 在建表；`db/schema.sql` 顶部加弃用说明，指向 Alembic 为权威。
  - 依赖：`requirements.txt` 加 `alembic>=1.13`/`mako>=1.3`；`requirements.lock` 锁定 `alembic==1.19.1`/`Mako==1.4.1`/`MarkupSafe==3.0.3`（CI 经 `requirements-dev.txt -r requirements.txt` 自动获得 alembic）。
- **测试**：`backend/tests/test_migrations.py`（4 用例：alembic 产物齐全、`upgrade head` 在空 SQLite 库建出全部表且 `growth_products` 含 category/platform、重复执行幂等、`app.main` 导入无残留 `init_db`/`engine` 引用）。全仓 **80 passed**（原 75 + 4 新），ruff 全绿。
- **关键坑（已记录）**：①`alembic.ini` 必须 ASCII（Windows 下 `configparser` 用 GBK 读，遇 UTF-8 中文注释 `UnicodeDecodeError`）；②SQLite 下 `JSON` 列用 SQLAlchemy 的 `JSON` 类型即可（底层 TEXT），无需 `JSONB`；③`func.now()` 在 SQLite 编译存在歧义，统一用 `sa.text("CURRENT_TIMESTAMP")` 双后端稳定；④`env.py` 用显式 `sys.path.insert` 而非仅靠 `prepend_sys_path`，确保 gunicorn/docker 任意 cwd 都能定位 `app` 包。
- **验收**：`DATABASE_URL=sqlite:///./_empty.db alembic upgrade head` 实测在空库跑通，生成 11 张表（业务 10 + `alembic_version`）；真实 app 冒烟（`TestClient` 触发 lifespan）→ `/api/health` 200 且 DB 已含全部表。**诚实声明**：本机无真实 PostgreSQL 实例，PostgreSQL 路径通过 `DATABASE_URL` 注入与 `env.py` 双后端兼容配置 + 代码审查保证，未实连 PG 跑通；已在文档注明，请在 PG 环境终验。
- **既有 SQLite 库升级说明（重要）**：Alembic 与旧 `create_all` 是两套 schema 管理体系。已在旧版 `create_all` 上建立的库，直接 `upgrade head` 会因表已存在而报错。新部署请用**空库**让其自举；既有库升级路径为：备份后新建库 `upgrade head` 再迁移数据，或 `alembic stamp head` 标记为已最新（仅在确认表结构与初始迁移一致时）。

### P1-4 同步阻塞治理 + 请求整体超时
- **问题**：agent 端点全为同步 `def`，内部串行调 Agnes（单次 60s × 3 重试 ≈ 180s）与 Bright Data，跑在 uvicorn threadpool；框架无法对长调用超时取消，长调用占死 worker、客户端悬挂。supervisor 编排无超时。
- **方案**：引入 `backend/app/timeout.py` —— `run_blocking_with_timeout(func, *args, timeout=AGENT_TIMEOUT_SECONDS)` 用 `asyncio.to_thread` 在独立线程跑阻塞 IO，并以 `asyncio.wait_for` 设整体超时；超阈值抛 `RequestTimeoutError`。
  - `backend/app/routers/agent.py`：8 个重端点（run/listing/image/advertising/visual/voc/competitor/market_research）全部改为 `async def`，外部调用经 `run_blocking_with_timeout` 包裹。端点改异步后，**外部 IO 期间事件循环不被阻塞**，并发请求仍可得响应；超阈值即返回 504（降级），后台线程由有界默认执行器回收。
  - `backend/app/errors.py`：新增 `request_timeout_handler`（HTTP 504 + 统一 JSON `{"error":"timeout",...}` + `X-Trace-Id`），并注册；`RequestTimeoutError` 不被通用 500 兜底误吞。
  - `backend/app/config.py`：新增 `AGENT_TIMEOUT_SECONDS`（默认 120，环境变量可配）、`REQUEST_TIMEOUT_SECONDS`（默认 300，兜底护栏）。
- **测试**：`backend/tests/test_timeout.py`（4 用例：快速调用正常、慢调用返回 504 JSON timeout 且带 X-Trace-Id、RequestTimeoutError 处理器已注册、5 个 0.3s 阻塞调用经 `asyncio.gather` 并发总耗时 <1.5s）。全仓 **84 passed**，ruff 全绿。
- **关键坑（可复用）**：①同步 `def` 端点无法被框架超时取消，必须用 `async def` + `to_thread` + `wait_for` 才能既释放事件循环又按期熔断；②`wait_for` 超时抛的是 `asyncio.TimeoutError`，需转成自定义异常再映射 504，否则会被通用 500 处理器误判；③`asyncio.to_thread` 受默认执行器线程数上限约束，并发长调用不会无限增长线程。
- **验收**：慢调用在 `AGENT_TIMEOUT_SECONDS` 后返回 `{"error":"timeout",...}`（实测 /slow 测试 1s 超时→504）；5 路并发阻塞调用 ≈0.3s 完成（非串行 1.5s），证明事件循环未被阻塞、线程并发生效。
- **诚实声明**：Agent 内部（如 MarketResearchAgent 内 Bright Data 取数 + 多轮 Agnes）的**细粒度并发**（`asyncio.gather` 并行多个独立外部调用）未在本轮逐 agent 改造——本轮先解决「端点级超时 + 事件循环不被阻塞」这一根因；各 agent 内部可在不破坏既有诚实降级契约前提下逐步引入 `gather`，属后续增量优化。

### P1-5 生产配置硬化
- **问题**：`/docs` `/redoc` `/openapi.json` 默认全开，泄露端点细节；CORS `allow_methods/headers=["*"]` 偏宽。
- **方案**：`backend/app/main.py` 在构造 `FastAPI` 时按 `APP_ENV=="production"` 关闭 `docs_url`/`redoc_url`/`openapi_url`（默认 demo 仍开放，便于本地联调）；CORS 收敛为 `allow_methods=["GET","POST","OPTIONS"]`、`allow_headers=["Content-Type","Authorization","X-API-Key"]`（不再通配）。`pythonpath`/`.env` 写回权限（`0600`）延续既有 `config_store` 既有逻辑，本项未改动。
- **测试**：`backend/tests/test_production_hardening.py`（3 用例：demo 下 /docs 200、production 下 /docs//redoc//openapi.json 全 404、CORS allow-methods/headers 无 `*` 且含 x-api-key/authorization）。全仓 **87 passed**，ruff 全绿。
- **验收**：`APP_ENV=production` 启动后 `/docs` 404、`/openapi.json` 404；跨域预检 `Access-Control-Allow-Methods` 仅 `GET, POST, OPTIONS`、无 `*`。
- **诚实声明**：仅做「开关 + 收敛」最稳妥的一部分；更激进项（如 production 下 CORS 完全不允许浏览器跨域、强制 HTTPS/HSTS、CSRF）属于纵深防御，留作后续。

---

## P2 — 优化项

### P2-1 结果缓存层 ✅ 已完成（2026-08-15）
- **问题**：每次请求都打 Bright Data + LLM，慢且贵（grep 全局无 cache 层）。
- **方案**：零依赖（契合项目标准库哲学）引入 `app/cache.py` 的 `TTLCache`（`threading.Lock` + `time.monotonic()` 过期 + 插入序 dict 的 FIFO 淘汰）。`MarketResearchAgent.run()` 先查 `research_cache`（key=`mr:{country}:{category}:{keyword}:{limit}`），命中则深拷贝并标 `cached=True`；未命中走 `_run_fresh()` 后写回。配置项 `RESEARCH_CACHE_TTL_SECONDS=600` / `RESEARCH_CACHE_MAXSIZE=256`（均 env 可覆盖）。`MarketResearchReport.cached` 字段供前端降权展示（诚实降级契约：缓存结果仍标注非实时，绝不伪造数据）。
- **交付**：`app/cache.py`（TTLCache + 单例 `research_cache`）、`agent.py` 接入、`schemas.py` 加 `cached`、`config.py` 加 TTL/MAXSIZE、`tests/test_cache.py`（4 例：TTL 过期 / FIFO 淘汰 / get_or_set / TTL<=0 关闭 / 集成缓存命中避免二次外呼）。
- **验收**：同输入二次调用 `cached=True` 且 LLM 仅 1 次；TTL 可配；全仓测试 91 通过、ruff 通过。
- **已知限制**：仅 `market_research` agent 接入；其余 agent 如需缓存可复用同一 `TTLCache` 模式后续扩展。

### P2-2 前端构建 / 打包 ✅ 已完成（2026-08-17）
- **问题**：`frontend/` 为 vanilla 静态 SPA（`index.html` + `assets/js/*.js`），无 `package.json`/构建/压缩/哈希/CSP。
- **方案**：
  - **构建**（`frontend/build.mjs` + esbuild）：对 `assets/{js,css}` 做 minify + **内容哈希**重命名，并重写 `index.html` 的资源引用（去掉源码里的 `?v=3` 戳，改由哈希接管缓存击穿）；产物落到 `frontend/dist/`。
  - **为何不用 Vite ESM 重写**：现有 SPA 是全局脚本风格（跨文件引用 `API`/`toast`/各 `renderXxx`，无 import/export），强行改 ESM 是高风险且无测试覆盖的破坏性修改。esbuild 仅做「等价压缩 + 哈希」，运行时语义与源码完全一致，零侵入，且 `dist` 不存在时后端自动回退到源码。
  - **开发服务器**：`frontend/vite.config.js` 提供 `npm run dev`（5173，带 `/static`→`/assets` 重写插件 + `/api` 代理到 8002）。
  - **CSP**（`backend/app/csp.py`）：仅 `APP_ENV=production` 注入。策略收紧 `default-src 'self'`、`object-src 'none'`、`base-uri 'self'`、`connect-src 'self'`、`img-src 'self' data: https:`、仅放开 Google Fonts；因 `views.js` 含受控内联 `onclick=/onerror=` 处理器，`script-src/style-src` 保留 `'unsafe-inline'`（详见模块 docstring 的取舍与后续严格化路径）。
  - **后端适配**（`main.py`）：`FRONTEND_DIR` 优先指向 `frontend/dist`，回退到未构建源码。
  - **Docker**：多阶段构建（node 阶段 `npm ci && npm run build`，仅把 `frontend/dist` 拷入 python 镜像），`.dockerignore` 排除 `node_modules`/`frontend/node_modules`。
- **交付**：`frontend/package.json`、`frontend/build.mjs`、`frontend/vite.config.js`、`backend/app/csp.py`、`main.py`（dist 优先 + CSP 注入）、`Dockerfile`（多阶段）、`.dockerignore`、`tests/test_production_hardening.py`（新增 CSP 用例）。
- **验收**：`npm run build` 产出带内容哈希的压缩资源 + 重写后的 `index.html`；生产模式下所有响应带 CSP 头（测试覆盖）；全仓测试通过、ruff 通过。
- **已知限制**：CSP 因内联处理器保留 `'unsafe-inline'`（非严格态）；后续把 `views.js` 内联处理器改为 `addEventListener` 后可去掉 `'unsafe-inline'` 并引入 nonce。

### P2-3 API 版本化
- **问题**：`/api/agent` 等无版本前缀，迭代会破坏前端。
- **方案**：所有业务路由统一加 `/api/v1` 前缀（`app/routers/*.py` 的 `APIRouter(prefix=...)` 全部改为 `/api/v1/...`）；`/api/health` 作为元端点保持未版本化向后兼容；前端 `api.js`/`views.js` 所有业务调用改为 `/api/v1/`，`/api/health` 保留。
- **前端适配**：`frontend/assets/js/api.js` 批量 `/api/`→`/api/v1/`（仅 health 不动）；`views.js` 的 `/api/settings/status` 同步改 v1。
- **测试**：`tests/test_api_versioning.py` 锁定契约——业务路由全在 `/api/v1/`、`/api/health` 不版本化、旧裸前缀返回 404、v1 端点可达。
- **验收**：`openapi.json` 中 31 个业务端点全部 `/api/v1/`，无遗留 `/api/agent` 等；全仓测试通过。
- **已知限制**：未做旧路径 301 重定向（一次性破坏性迁移，前端已同步）。若需兼容旧前端可后续补 redirect。

### P2-4 配置校验
- **问题**：`config_store` 全字符串、无 pydantic-settings 校验；类型/范围错误只在运行时暴露。
- **建议方案**：引入 `pydantic-settings`；对 `AGNES_TIMEOUT`（int>0）、`CORS_ALLOW_ORIGINS`（list）等做校验与默认值归一。
- **验收标准**：非法配置在启动时/写入时即报错，而非运行时崩溃。

### P2-5 image agent 真实化
- **问题**：`TOOL_BACKEND_IMAGE_GENERATION` 默认 `mock`，生图不走真实链路（之前审计标记未改）。
- **建议方案**：接入真实生图后端（WisArt/`AGNES_IMAGE_MODEL`），保留 mock 作为离线兜底；输出走统一数据层。
- **验收标准**：配置真实后端后生图返回真实图片 URL；mock 仅离线可用。

---

## 建议执行顺序
1. **P0-1（测试+CI）** —— 先建质量门禁，后续每步改动都有回归保护。
2. **P0-2 + P0-3（认证+限流）** —— 决定"能否放心对外"，且保护按量计费额度。
3. **P0-4（Docker+锁定）** —— 让部署可复现、可水平扩展。
4. **P1（日志/异常/迁移/超时/硬化）** —— 提升可观测性与稳定性。
5. **P2（缓存/前端/版本化/校验/image）** —— 性能与体验优化。

> 每完成一项，在上方"跟踪总览"勾选并单独提交（commit message 标注 `P0-x`/`P1-x`），便于回溯。
