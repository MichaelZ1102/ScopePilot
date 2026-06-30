

> 生成时间：2026-06-28  
> 审查范围：Backend (`backend/app/`) + Frontend (`frontend/src/`) + 部署配置  
> 结论：功能架构清晰，但存在 **3 个生产级阻塞问题**、**6 个高优先级稳定性/安全问题**，以及若干结构债务。

---

## 一、Critical（P0）— 必须立即修复

| # | 问题 | 文件 | 行号 | 影响 | 建议修复 |
|---|------|------|------|------|----------|
| 1 | `DEBUG=True` 默认开启 | `backend/app/config.py` | 12 | 生产环境泄露异常堆栈、配置细节、路径信息 | 默认改为 `False`；开发环境通过 `.env` 显式启用 |
| 2 | Docker Compose CORS 默认值错误 | `docker-compose.yml` | 12 | `CORS_ORIGINS` 默认 `http://localhost:8000`，但前端运行在 `5173`/`3000`，直接导致前端跨域失败 | 默认值改为 `http://localhost:5173,http://localhost:3000` |
| 3 | JWT Secret 硬编码默认值 | `backend/app/config.py` | 13 | 虽有 validator 拦截，但 `.env.example` 和文档仍提示用户"改这里"，容易遗漏 | 移除代码中的默认值；`.env.example` 加粗警告；validator 改为启动时一次性校验 |

---

## 二、High（P1）— 影响稳定性/性能/安全

| # | 问题 | 文件 | 行号 | 影响 | 建议修复 |
|---|------|------|------|------|----------|
| 4 | `_save_to_disk()` 全表 DELETE + INSERT | `backend/app/database.py` | 166-177 | 每次写操作 O(n) 重写整张表；Tickets/Sprints 增长后会出现明显卡顿 | 改为增量写入：新增用 `INSERT`，更新用 `UPDATE`，删除用 `DELETE WHERE id=?` |
| 5 | 同步 SQLite 阻塞异步事件循环 | `backend/app/database.py` | 全文件 | FastAPI 是 async，但 `sqlite3` 是同步驱动；所有 DB 调用都会阻塞 event loop，高并发下吞吐骤降 | 替换为 `aiosqlite`，或在 `run_in_executor` 中执行同步调用（短期） |
| 6 | 多 Worker 内存状态不共享 | 所有 `*Store._store` 模块全局变量 | — | 用 `uvicorn --workers > 1` 或 Docker 多副本时，内存字典完全隔离，SQLite 文件虽共享但内存脏写导致数据丢失 | 去掉对内存字典的强依赖；读请求直接查 SQLite；写请求通过队列或单 worker 模式 |
| 7 | Jira/Figma description 直接渲染，无 sanitize | `frontend/src/pages/SprintDetail.tsx` | 118 | Jira/HTML 描述若含 `<script>` 等，虽 React 默认转义，但若后续改成 `dangerouslySetInnerHTML` 会立刻出现 XSS | 后端增加 `bleach`/`nh3` sanitize；前端只渲染纯文本或白名单 HTML |
| 8 | 登录接口无速率限制 | `backend/app/api/v1/auth.py` | 109-125 | 暴力破解风险 | 增加 `slowapi` 或基于 Redis 的 IP 限流（如 5 次/分钟） |
| 9 | 日志没有 rotating handler | `backend/app/main.py` | 15-19 | 生产环境 `agent.log` 无限增长，最终占满磁盘 | 增加 `RotatingFileHandler`（如 10MB × 5 份） |

---

## 三、Medium（P2）— 结构/可维护性

| # | 问题 | 文件 | 行号 | 影响 | 建议修复 |
|---|------|------|------|------|----------|
| 10 | `stores.py` 空壳遗留 | `backend/app/stores.py` | 1-4 | 应直接删除，减少认知噪音 | 删除文件；确认无引用后移除 |
| 11 | `models/__init__.py` 空壳遗留 | `backend/app/models/__init__.py` | 1-3 | SQLAlchemy/Alembic/asyncpg 已移除，目录和注释应清理 | 删除目录或更新注释说明当前架构 |
| 12 | `datetime.utcnow()` 已废弃 | `jira.py`, `codebase.py`, `team.py` 等 | 多处 | Python 3.12+ 警告 | 统一改 `datetime.now(timezone.utc)` |
| 13 | Alembic 目录遗留未使用 | `backend/alembic/` | — | 当前用 SQLite 建表，但 migrations 目录保留造成"有版本控制"的错觉 | 删除目录或补齐迁移流程；二选一 |
| 14 | 团队/计费 tier 硬编码在代码 | `backend/app/services/team.py` | 49-69 | 改价格/额度需要改代码并重新部署 | 移到 `config.yaml` 或数据库表，支持运营后台调整 |
| 15 | `pyproject.toml` 依赖上界过松 | `backend/pyproject.toml` | 6-12 | 如 `httpx>=0.27,<1`、`pydantic>=2.0,<3` 上界过远，供应链攻击面大 | 按项目规范收紧：`>=0.27,<0.29`；`>=2.0,<3` 可接受（pydantic 已 major） |

---

## 四、前端代码不足（除样式外的架构问题）

| # | 问题 | 文件 | 行号 | 影响 | 建议修复 |
|---|------|------|------|------|----------|
| 16 | 重复的 auth 校验 | `App.tsx` + `ProtectedRoute` | 42-49 / 17-30 | 每次进入页面调用两次 `/auth/me` | 合并为一个 auth context/provider |
| 17 | 无 ErrorBoundary | 全项目 | — | 任意子组件抛异常会导致整棵 React 树白屏 | 增加全局 `ErrorBoundary`，展示降级 UI |
| 18 | axios 401 拦截器直接 `window.location.href` | `frontend/src/lib/client.ts` | 17 | 破坏 SPA 体验，丢失当前页面状态 | 改为路由跳转 (`navigate('/login')`) 或展示登录弹窗 |
| 19 | i18n 回退字符串泛滥 | `Layout.tsx` 等 | 多处 | 翻译不完整，且 `as any` 破坏类型安全 | 补全 `zh` 翻译；开启 `i18next` 缺失 key 报警 |
| 20 | 无 loading skeleton / 空状态设计 | `Dashboard.tsx`, `Projects.tsx` | 92 / 86 | 只有纯文本 loading，视觉跳变明显 | 增加 Skeleton 组件 + 统一空状态插画 |

---

## 五、风险矩阵与建议优先级

```
影响范围
  高 │ P0-2 CORS/DEBUG    P1-5 SQLite性能    P1-6 Worker隔离
     │ P1-7 XSS风险       P1-8 暴力破解
  中 │ P1-9 日志无限增长  P2-12 datetime废弃 P2-14 计费硬编码
     │ P2-15 依赖上界过松
  低 │ P2-10 stores遗留   P2-11 models遗留   P2-13 Alembic遗留
     └─────────────────────────────────────────────────
         确定性高          确定性中          确定性低
```

**建议修复顺序：**

1. **Week 1（安全+稳定）**：P0-1/2/3 + P1-8/7/9
2. **Week 2（性能）**：P1-4/5/6 + P2-12/15
3. **Week 3（结构）**：P2-10/11/13/14 + 前端架构优化

---

## 六、前端样式优化方向（详细方案见上一轮回复）

用户已选择方向 **C — 保持当前品牌蓝，优化层次感、阴影、圆角、动效**。

下一步动作：
1. 统一 CSS Variables + 抽离 `*.module.css`
2. Dashboard/Projects/SprintDetail 组件视觉升级
3. 增加通用 Modal、Skeleton、ErrorBoundary
4. 移动端响应式适配

---

## 七、附：关键文件路径速查

```
backend/
├── app/
│   ├── config.py          ← P0-1/3, P2-15
│   ├── main.py            ← P1-9
│   ├── database.py        ← P1-4/5/6
│   ├── api/v1/
│   │   ├── auth.py        ← P0-3, P1-8
│   │   └── projects.py    ← P1-7
│   └── services/
│       ├── jira.py        ← P2-12
│       ├── codebase.py    ← P2-12
│       ├── team.py        ← P2-12/14
│       └── analysis.py
├── alembic/               ← P2-13（可删除）
└── Dockerfile / docker-compose.yml ← P0-2

frontend/
├── src/
│   ├── lib/
│   │   └── client.ts      ← P1-18
│   ├── components/
│   │   ├── Layout.tsx     ← P1-16/19
│   │   └── LoginPage.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx  ← P1-16/20
│   │   ├── Projects.tsx   ← P1-16/20
│   │   └── SprintDetail.tsx ← P1-7/16/20
│   └── styles/
│       └── global.css     ← token 体系（已建立但未用透）
```

---

*文档结束。如需逐条修复的 Kanban 任务列表，可继续生成。*
