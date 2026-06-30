# ScopePilot 优化方案（基于 2026-06-28 代码现状）

> 适用范围：`backend/app/` + `frontend/src/` + `docker-compose.yml`  
> 目标：先修真实阻塞与高风险问题，再清理结构债务，最后做体验与可维护性优化。

---

## 一、结论摘要

当前项目整体可用，但存在几类明确问题：

1. **生产安全默认值不安全**：`DEBUG=True`、`SECRET_KEY` 默认值、Docker Compose 的 CORS 默认值都需要立刻修正。
2. **数据层写入方式偏重**：`SqliteStore._save_to_disk()` 仍然是全量重写，随着数据增长会放大写放大和锁竞争。
3. **前端还缺少基础工程护栏**：没有全局 `ErrorBoundary`，auth 入口存在重复检查，401 处理方式偏粗暴。
4. **一些结构债务可以顺手清**：`datetime.utcnow()`、遗留空壳目录/文件、日志轮转、tier 配置外置化。

---

## 二、P0：必须先修

### 1) 关闭默认调试模式
- **位置**：`backend/app/config.py`
- **现状**：`debug: bool = True`
- **问题**：生产环境可能暴露调试信息、堆栈和配置细节。
- **建议**：默认改为 `False`，开发环境通过环境变量显式开启。

### 2) 去掉危险的 secret 默认值
- **位置**：`backend/app/config.py`
- **现状**：`secret_key: str = "change-me-in-production"`
- **问题**：虽然有 validator 拦截，但默认值本身仍然危险，容易在部署链路里漏掉。
- **建议**：移除默认值，启动时强制要求提供真实密钥。

### 3) 修正 Docker Compose 的 CORS 默认值
- **位置**：`docker-compose.yml`
- **现状**：默认只允许 `http://localhost:8000`
- **问题**：前端开发常见端口是 `5173` 或 `3000`，默认配置会导致跨域失败。
- **建议**：默认值改成包含前端开发端口，至少覆盖 `5173` 和 `3000`。

---

## 三、P1：尽快修

### 4) 改造 SQLite 的全量写盘
- **位置**：`backend/app/database.py`
- **现状**：`_save_to_disk()` 先清表，再整表插入。
- **问题**：数据量增长后会变成明显的性能瓶颈，也会加重写锁压力。
- **建议**：拆成增量写入路径：新增 `INSERT`、更新 `UPDATE`、删除 `DELETE`，只有初始化/修复时才允许全量重建。

### 5) 降低同步 SQLite 对事件循环的影响
- **位置**：`backend/app/database.py` 及所有调用方
- **现状**：FastAPI 路由里直接走同步 `sqlite3`。
- **问题**：高并发下会阻塞事件循环，吞吐和延迟都会受影响。
- **建议**：短期可把 DB 写入包到线程池；中期再评估 `aiosqlite` 或更明确的单写线程模型。

### 6) 收敛内存态与持久化态的双写逻辑
- **位置**：`backend/app/services/*.py`、`backend/app/api/v1/*.py`
- **现状**：很多 service 仍同时依赖模块级 `_store` 和 SQLite 落盘。
- **问题**：多 worker / 多副本时，一致性和可见性会变复杂。
- **建议**：明确单写源；至少把读路径尽量收敛到持久层，减少对进程内缓存正确性的依赖。

### 7) 增加登录保护措施
- **位置**：`backend/app/api/v1/auth.py`
- **现状**：登录接口暂无速率限制。
- **问题**：存在暴力尝试风险。
- **建议**：加入基础限流（按 IP 或按账号维度），先做轻量版即可。

### 8) 增加日志轮转
- **位置**：`backend/app/main.py`
- **现状**：当前日志配置没有看到轮转控制。
- **问题**：生产日志可能无限增长。
- **建议**：补 `RotatingFileHandler` 或等价方案，设置大小和保留份数。

---

## 四、P2：结构与可维护性

### 9) 清理 `datetime.utcnow()`
- **位置**：`backend/app/api/v1/auth.py`、`backend/app/services/team.py`、`backend/app/services/jira.py`、`backend/app/services/codebase.py` 等
- **问题**：Python 3.12+ 会持续给出弃用警告。
- **建议**：统一替换为 `datetime.now(timezone.utc)`，并在序列化层保持一致格式。

### 10) 清理遗留空壳文件/目录
- **位置**：`backend/app/stores.py`、`backend/app/models/__init__.py`、`backend/alembic/`
- **问题**：这些位置容易让人误判当前架构状态。
- **建议**：确认无引用后删除，或补充清晰说明，避免“看起来还在用”的错觉。

### 11) 让 tier 配置外置化
- **位置**：`backend/app/services/team.py`
- **现状**：套餐、价格、额度都硬编码在代码里。
- **问题**：运营调整需要改代码并重新部署。
- **建议**：迁到配置文件或数据库表，至少先把核心额度配置化。

### 12) 收紧并统一依赖策略
- **位置**：`backend/pyproject.toml`、`pyproject.toml`
- **现状**：部分依赖上界可再收紧，项目内还存在双份依赖定义需要统一审视。
- **问题**：供应链风险和维护成本都会增加。
- **建议**：按项目规范检查后统一收口，避免一边收紧、一边漂移。

---

## 五、前端优化

### 13) 合并 auth 检查逻辑
- **位置**：`frontend/src/App.tsx`
- **现状**：`ProtectedRoute` 和 `App` 各做了一次 auth 探测。
- **问题**：重复请求 `/auth/me`，也让状态流更绕。
- **建议**：收敛到一个 auth context/provider 或统一初始化流程。

### 14) 增加全局 `ErrorBoundary`
- **位置**：`frontend/src/`
- **现状**：没有全局错误边界。
- **问题**：任一子组件异常都可能白屏。
- **建议**：补一个顶层兜底组件，展示降级 UI。

### 15) 改善 401 处理方式
- **位置**：`frontend/src/lib/client.ts`
- **现状**：401 时直接 `window.location.href = '/login'`。
- **问题**：会打断 SPA 体验并丢失当前页面状态。
- **建议**：改成路由跳转或由应用状态统一接管。

### 16) 补 loading / empty / error 基础状态
- **位置**：`frontend/src/pages/*.tsx`
- **现状**：部分页面只有简化 loading 文案。
- **问题**：页面跳变明显，错误态也不统一。
- **建议**：做统一 Skeleton、空状态、错误状态组件，先覆盖主要页面。

---

## 六、建议执行顺序

### Sprint 1：安全底线
- `backend/app/config.py`
- `docker-compose.yml`
- `backend/app/api/v1/auth.py` 的限流
- `backend/app/main.py` 的日志轮转

### Sprint 2：数据层稳定性
- `backend/app/database.py` 的增量持久化
- 同步 DB 调用的执行模型调整
- 多 worker 一致性策略收敛

### Sprint 3：前端基础工程
- `frontend/src/App.tsx` 的 auth 收敛
- `ErrorBoundary`
- 401 跳转和统一加载态

### Sprint 4：结构清理
- `datetime.utcnow()` 统一替换
- 空壳文件/目录处理
- tier 配置外置化
- 依赖上界与依赖定义统一检查

---

## 七、补充说明

- 这份方案优先保留“**已经在代码里真实存在**”的问题，不把预防性建议和实际漏洞混在一起。
- `SprintDetail` 的 JSX 目前还是纯文本渲染，不应直接归类为当前 XSS 漏洞；如果后续改成 HTML 渲染，再单独补安全设计。
- 如果你要继续推进，我建议下一步把这些项拆成 Kanban，按 `P0 → P1 → P2` 顺序落地。
