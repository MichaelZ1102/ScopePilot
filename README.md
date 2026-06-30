# ScopePilot 🚀

> **AI-powered Sprint Requirement Analysis Platform**  
> 从 Jira Sprint 到代码影响、API 测试、Figma 设计分析的全链路智能分析平台

---

## ✨ 功能一览

| 模块 | 功能 | 
|------|------|
| 📊 **Dashboard** | Sprint 概览、完成率、Ticket 状态分布 |
| 📁 **Projects** | 项目创建 + Jira 配置 + Sprint 导入 |
| 🔍 **AI 分析** | 自动解析 Jira Ticket → 需求理解、核心逻辑、影响范围 |
| 📂 **Codebase** | GitHub/本地仓库扫描 + Code Impact 影响分析 |
| 🧪 **API 测试** | OpenAPI/Swagger 导入 → AI 生成测试场景 → 导出 Postman |
| 🎨 **Figma** | 设计稿链接分析 → 自动生成后端影响报告 |
| 👥 **团队** | 多成员管理、套餐计费、报告分享（密码保护 + 过期） |

## 🏗️ 技术栈

```
Backend:    Python 3.11+ / FastAPI / SQLite
Frontend:   React 19 / TypeScript / Vite / react-i18next / TanStack Query
AI:         OpenCode Go / Groq / StepFun / OpenAI-compatible APIs
CLI:        Python Typer / Jira API / Git
Deploy:     Docker / docker-compose
```

## 🚀 快速启动

### 前置条件

- Python 3.11+
- Node.js 18+

### 1️⃣ 安装依赖

```bash
# 后端
cd backend
pip install -e .

# 前端
cd ../frontend
npm install
```

### 2️⃣ 配置环境变量

创建根目录 `.env`（Docker 部署使用）或 `backend/.env`（仅本地后端开发使用）。`SECRET_KEY` 必须设置；Jira 和 AI provider 按需要配置：

```env
# 必填：生产部署时设置一个随机密钥
SECRET_KEY=your-random-secret-key-here
COOKIE_SECURE=false
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000

# Jira（拉取 Sprint 时需要）
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your_jira_token
JIRA_PROJECT_KEY=PROJ

# AI provider（AI 分析/API 测试计划等增强功能需要）
# 支持：opencode / groq / stepfun / openai
AI_PROVIDER=stepfun
AI_API_KEY=your-ai-api-key
AI_MODEL=step-3.7-flash
AI_BASE_URL=https://api.stepfun.com/step_plan/v1
```

GitHub 仓库访问 Token 在 Codebase 页面按代码源填写；Figma Token 在 Figma 分析页面填写，不需要全局环境变量。

### 3️⃣ 构建前端

```bash
cd frontend
npm run build
```

### 4️⃣ 启动服务

```bash
# 方式一：Docker（推荐生产）
docker compose up --build

# 方式二：一键启动（开发）
scripts\dev\start.bat dev    # Windows
# 或
./scripts/dev/start.sh dev   # Linux/Mac

# 方式三：手动
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5️⃣ 打开浏览器

➡️ **http://localhost:8000**

| 账号 | 密码 | 角色 |
|------|------|------|
| `demo@test.com` | `demo123` | 管理员（已注册） |

> 或点登录页的「注册」创建新账号。

## 🔐 安全特性

- **HttpOnly Cookie** — JWT 存储在 HttpOnly Cookie 中，XSS 无法窃取
- **Token 加密** — Jira/GitHub API Token 使用 Fernet 对称加密存储
- **Token 黑名单** — 登出后 token 被加入持久化黑名单，重启不丢失
- **Secret Key 校验** — 使用默认 secret_key 时启动失败，强制设置
- **Workspace 隔离** — 所有数据访问强制检查 workspace_id
- **CORS 可配置** — 通过 `CORS_ORIGINS` 环境变量控制

## 📖 用户手册

详细操作指南 → [`docs/user-manual.md`](docs/user-manual.md)

## 🧪 测试

```bash
cd backend
python -m pytest tests/ -v
```

测试覆盖：**auth（密码/JWT/黑名单）** · **database（CRUD/ID）** · **workspace 隔离** · **API 路由** · **Figma 分析** · **Codebase 扫描** · **Team/计费** · **E2E**

## 🐳 Docker 部署

```bash
# 构建并启动
docker compose up --build -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

环境变量通过 `docker-compose.yml` 或 `.env` 文件传入。

## 📁 项目结构

```
ScopePilot/
├── Dockerfile                  # 多阶段 Docker 构建
├── docker-compose.yml          # Docker 编排
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 路由模块
│   │   │   ├── auth.py         # 认证注册登录（HttpOnly Cookie）
│   │   │   ├── projects.py     # 项目管理
│   │   │   ├── sprints.py      # Sprint/Ticket
│   │   │   ├── analysis.py     # AI 分析（异步）
│   │   │   ├── codebase.py     # 代码仓库
│   │   │   ├── api_tests.py    # API 测试计划
│   │   │   ├── figma.py        # Figma 设计分析
│   │   │   ├── reports.py      # 报告导出
│   │   │   └── team.py         # 团队/计费
│   │   ├── database.py         # SQLite 持久化层（SqliteStore）
│   │   ├── encryption.py       # 敏感数据加密
│   │   ├── adapters.py         # CLI ↔ Backend 适配层
│   │   ├── config.py           # 配置（secret_key 校验）
│   │   ├── schemas/            # Pydantic 数据模型
│   │   ├── services/           # 业务逻辑
│   │   └── main.py             # 入口 + 日志配置
│   ├── tests/                  # 测试套件
│   │   ├── test_auth.py        # 认证安全测试
│   │   ├── test_database.py    # 持久化层测试
│   │   ├── test_workspace_isolation.py  # 隔离性测试
│   │   ├── ...                 # API/Figma/Codebase 测试
│   │   └── conftest.py         # 测试夹具（DB 隔离）
│   └── scripts/dev/            # 开发工具脚本
├── frontend/                   # React 前端
│   └── src/
│       ├── lib/
│       │   ├── client.ts       # Axios 实例（withCredentials）
│       │   ├── auth.ts         # 认证 API
│       │   ├── projects.ts     # 项目 API
│       │   ├── sprints.ts      # Sprint API
│       │   ├── codebase.ts     # 代码源 API
│       │   ├── api-tests.ts    # API 测试 API
│       │   ├── figma.ts        # Figma API
│       │   ├── team.ts         # 团队 API
│       │   ├── hooks.ts        # TanStack Query hooks
│       │   ├── types.ts        # 类型定义
│       │   └── i18n.ts         # 中英文国际化
│       ├── styles/global.css   # 设计 Token / CSS 变量
│       └── pages/              # 页面组件
├── src/                        # CLI 命令行工具
│   └── scopepilot/
│       ├── analyzer.py         # AI 分析引擎
│       ├── jira_client.py      # Jira API 客户端
│       └── main.py             # CLI 入口
└── docs/                       # 文档
```

## 🔧 API 文档

启动服务后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 当前限制

- 当前持久化层以本地 SQLite + 进程内缓存为主，适合单实例部署；多实例部署前需要迁移到共享数据库并收口缓存一致性。
- 后台分析任务已从请求线程移出，但进度推送仍以轮询为主，尚未接入 WebSocket 或任务队列。
- 前端仍有部分页面使用 inline style 和浏览器 `alert`，后续可继续迁移到统一组件、通知系统和 TanStack Query。
- 报告导出与共享已可用，但 PDF/Jira 等高级导出能力仍依赖后续实现和环境配置。

---

## 📜 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| 0.6.0 | 2026-06 | **优化大修**: 41 项修复（P0:10, P1:18, P2:13）|
| 0.5.0 | 2026-06 | Phase 0-5 全功能 + 测试 + SQLite 持久化 |

### 0.6.0 优化清单

| 等级 | 数量 | 内容 |
|------|------|------|
| 🔴 P0 | 10 | 运行时崩溃修复 + 安全漏洞（方法名不存在、logout 空壳、workspace 隔离、ID off-by-one、O(n²) 持久化、AI 异步、secret_key 校验、token 加密存储） |
| 🟡 P1 | 18 | 架构拆分+日志+代码质量（死代码清理、ID 双重记账、billing 持久化、依赖修正、batch 匹配、AC 提取、CORS 可配置、HttpOnly Cookie、分析路径统一） |
| 🟢 P2 | 13 | 结构+前端+测试（Dockerfile、Schema 去重、api.ts 拆分、CSS Token、react-query、测试覆盖） |

## 📄 License

MIT

---

## 🔜 下一步做什么

项目已从功能开发阶段进入 **稳定优化阶段**。以下是为您推荐的下一步方向：

### 🥇 短期（1-2 天）

1. **运行测试确认回归** — 执行 `cd backend && python -m pytest tests/ -v` 验证所有修改未破坏现有功能
2. **生产部署** — 设置 `SECRET_KEY` 环境变量，用 `docker compose up --build -d` 部署
3. **接入真实 Jira** — 创建 Project → 配置 Jira 连接 → 导入 Sprint 验证全链路

### 🥈 中期（1-2 周）

4. **前端迁移到 TanStack Query** — 将现有 `useEffect + fetch` 页面逐步迁移到 `lib/hooks.ts` 中的 `useQuery`/`useMutation`，获得缓存/重试/loading 状态
5. **CSS 逐步替换** — 将 inline `style={{...}}` 替换为 `global.css` 中的 `.card`/`.btn` 类
6. **补全 i18n 翻译** — 在 `i18n.ts` 中补充剩余页面中的硬编码中文文本
7. **观察 CI 回归** — 推送后查看 GitHub Actions 的 backend/frontend 结果并修复失败项

### 🥉 长期（1-3 月）

8. **PostgreSQL 迁移** — 将 SqliteStore 替换为 SQLAlchemy + PostgreSQL，支持多实例部署
9. **WebSocket 实时分析** — AI 分析改为 WebSocket 推送进度，替代当前轮询
10. **多用户 RBAC** — 实现基于角色的访问控制（admin/member/viewer）
11. **插件系统** — 将代码源/Figma/API 测试等模块插件化，支持第三方扩展

---

> 💡 **建议**：先跑测试确认回归，然后用 Docker 部署验证全链路。接下来最值得投入的是 **TanStack Query 迁移** — 能显著提升前端用户体验，有现成的 `hooks.ts` 可用。
