# ScopePilot 用户操作手册

> AI驱动的Sprint需求分析平台 — 从需求到代码的全链路分析

---

## 目录

1. [快速开始](#1-快速开始)
2. [项目管理](#2-项目管理)
3. [Sprint & Ticket 分析](#3-sprint--ticket-分析)
4. [Codebase 代码仓库分析](#4-codebase-代码仓库分析)
5. [API 测试计划](#5-api-测试计划)
6. [Figma 设计分析](#6-figma-设计分析)
7. [团队 & 计费](#7-团队--计费)
8. [常见问题](#8-常见问题)

---

## 1. 快速开始

### 1.1 启动系统

```bash
cd F:\personal-space\Project\ScopePilot

# 生产模式（推荐）
.\scripts\start.bat prod

# 开发模式（前后端分开）
.\scripts\start.bat dev
```

访问 **http://localhost:8000**

### 1.2 注册与登录

| 步骤 | 操作 |
|------|------|
| 1 | 打开 http://localhost:8000，看到登录页 |
| 2 | 点 **「没有账号？点击注册」** |
| 3 | 填写：邮箱、密码、姓名 |
| 4 | 注册后自动登录，进入 Dashboard |

> **内置测试账号**：`demo@test.com` / `demo123`（已注册可直接登录）

---

## 2. 项目管理

### 2.1 创建项目

**页面**: 左侧导航 → **📁 Projects**

1. 点 **「创建项目」**
2. 填写：
   - **项目名称** — 如 "Sprint 7 开发"
   - **描述** — 项目简介
3. 点 **「保存」**

### 2.2 连接 Jira

创建项目后，进入项目详情页：

1. 在 **Jira 配置** 区域点 **「配置 Jira」**
2. 填写 Jira 连接信息：
   - **Jira URL** — 例如 `https://your-domain.atlassian.net`
   - **邮箱** — Jira 账号邮箱
   - **API Token** — [生成 Jira API Token](https://id.atlassian.com/manage-profile/security/api-tokens)
3. 点 **「保存配置」**

### 2.3 导入 Sprint

配置 Jira 后：

1. 点 **「导入 Sprint」**
2. 系统自动拉取该项目的所有 Sprint 列表
3. 选择一个 Sprint 点 **「导入」**
4. 导入成功后跳转到 Sprint 详情页

---

## 3. Sprint & Ticket 分析

### 3.1 查看 Sprint 概览

**页面**: 左侧导航 → **📊 Dashboard**

Dashboard 显示所有 Sprint 的统计卡片：
- 总 Ticket 数
- 完成率
- 各状态分布（To Do / In Progress / Done）

点任意卡片进入 Sprint 详情。

### 3.2 Sprint 详情

**页面**: 点击 Sprint 卡片

| 区域 | 说明 |
|------|------|
| **Ticket 列表** | 当前 Sprint 的所有 Ticket，显示概要、状态、优先级 |
| **AI 分析** | 每个 Ticket 的 AI 分析结果（点击 **「分析」** 生成） |
| **Code Impact** | 代码影响分析（需要先配置代码源） |
| **导出报告** | 导出 Markdown/Postman 格式报告 |

### 3.3 AI 分析

在 Sprint 详情页：

1. 点任意 Ticket 旁的 **「分析」** 按钮
2. AI 引擎自动分析 Jira 描述 + 评论，生成：
   - **需求理解** — 把自然语言需求提炼为结构化描述
   - **核心逻辑** — Backend/API/DB 三层变化
   - **关联检查** — 涉及的具体代码模块
   - **影响范围** — 对其他功能的影响
3. 分析结果保存在 Ticket 中，可随时查看

---

## 4. Codebase 代码仓库分析

### 4.1 添加代码源

**页面**: 左侧导航 → **📂 Codebase**

支持两种代码源：

| 类型 | 说明 | 配置 |
|------|------|------|
| **GitHub** | 云端仓库 | 仓库URL + Token |
| **Local** | 本地目录 | 本地路径，点 **「扫描本地」** |

**添加 GitHub 仓库**：
1. 输入仓库 URL（如 `https://github.com/user/repo`）
2. 输入 GitHub Token（[生成 Token](https://github.com/settings/tokens)）
3. 点 **「添加」**
4. 自动开始扫描

**扫描本地仓库**：
1. 在项目目录运行 `scopepilot scan-local /path/to/repo`
2. 或者在 Codebase 页面点 **「扫描本地」**

### 4.2 Code Impact 分析

当 Sprint 有 AI 分析结果 + 代码源时：

1. 进入 Sprint 详情页
2. 在 **Code Impact** 面板点 **「分析影响」**
3. 系统自动将 AI 分析的关键词与代码仓库匹配：
   - 找出受影响的文件/模块
   - 列出函数和类级别的影响
   - 按影响程度排序（高/中/低）
4. 每个 Tracked Change 显示：
   - 影响的文件名和行号
   - 变更类型（新增/修改/删除）
   - 影响原因（关键词匹配说明）

---

## 5. API 测试计划

### 5.1 导入 OpenAPI/Swagger 规范

**页面**: 左侧导航 → **🧪 API Tests**

1. 点 **「导入 OpenAPI」**
2. 输入 OpenAPI JSON/YAML 内容（或 URL）
3. 系统自动解析所有 API 端点、参数和响应模型

### 5.2 生成测试计划

1. 在 API Test 详情页点 **「生成测试计划」**
2. AI 分析每个 API 端点，生成测试场景：
   - **正常流程** — 200 响应测试
   - **异常流程** — 400/401/404 测试
   - **边界条件** — 参数边界值测试
3. 每个场景包含：请求方法、路径、参数、期望状态码、期望响应

### 5.3 导出测试计划

支持两种导出格式：

| 格式 | 用途 | 导出操作 |
|------|------|----------|
| **Markdown** | 文档/评审 | 点 **「导出 Markdown」** |
| **Postman** | 直接导入 Postman 运行 | 点 **「导出 Postman」** |

Postman 导出的 JSON 文件可直接在 Postman 中 **Import → Upload Files**。

---

## 6. Figma 设计分析

### 6.1 分析 Figma 设计稿

**页面**: 左侧导航 → **🎨 Figma**

1. 点 **「分析 Figma 设计」**
2. 输入 Figma 文件链接（格式：`https://www.figma.com/file/xxx/...`）
3. 点 **「分析」**
4. 系统自动解析设计稿结构，生成：

### 6.2 分析报告内容

| 项目 | 说明 |
|------|------|
| **核心页面流** | 主要页面和它们之间的关系 |
| **独立组件** | 可复用的 UI 组件 |
| **设计 Token** | 颜色、字体、间距等设计规范 |
| **后端影响** | 需要新增或修改的 API/数据库/基础设施 |

### 6.3 后端影响报告

Figma 分析的后端影响部分告诉你这个设计稿上线需要做什么：
- **需要新增的 API** — 哪些接口还不存在
- **需要修改的 Schema** — 数据模型变化
- **数据存储影响** — 新增/修改的数据库表
- **基础设施需求** — 缓存/CDN/存储等
- **建议优先级** — 按影响度排序

---

## 7. 团队 & 计费

### 7.1 查看套餐

**页面**: 左侧导航 → **⚙️ Settings → 计费**

| 套餐 | 价格 | 成员 | 项目 | 分析/月 | 适用场景 |
|------|------|------|------|---------|---------|
| **Free** | 免费 | 2人 | 3个 | 10次 | 个人试用 |
| **Pro** | $29/月 | 10人 | 20个 | 100次 | 小团队 |
| **Enterprise** | $99/月 | 不限 | 不限 | 9999次 | 企业级 |

### 7.2 升级套餐

1. 在 Settings → 计费页点 **「升级」**
2. 选择目标套餐
3. 确认后升级（当前为模拟支付）

### 7.3 管理团队成员

1. 在 Settings → 团队页点 **「添加成员」**
2. 输入对方邮箱
3. 选择角色（admin / member / viewer）
4. 点 **「添加」**

### 7.4 分享报告

1. 在任一 Sprint 详情页点 **「分享」**
2. 设置：
   - **分享链接** — 自动生成唯一链接
   - **过期时间** — 链接有效期
   - **密码保护** — 可选
3. 点 **「创建分享」**
4. 将链接发给团队或客户

---

## 8. 常见问题

### 环境变量配置

在 `backend/.env` 中配置：

| 变量 | 用途 | 是否必须 |
|------|------|---------|
| `JIRA_EMAIL` | Jira 登录邮箱 | 使用 Jira 时必需 |
| `JIRA_API_TOKEN` | Jira API Token | 使用 Jira 时必需 |
| `GITHUB_TOKEN` | GitHub API Token | 扫描 GitHub 仓库时必需 |
| `OPENAI_API_KEY` | 增强 AI 分析质量 | 可选（不配则用规则分析） |
| `FIGMA_TOKEN` | Figma API Token | 分析 Figma 设计时必需 |

### 一键重置

```bash
cd backend && python scripts/clean_db.py
# 清除所有数据，回到初始状态
```

### 系统架构

```
浏览器 ──→ FastAPI (后端) ──→ SQLite (数据持久化)
              │
              ├── Jira API ──→ 拉取 Sprint/Ticket
              ├── GitHub API ──→ 仓库扫描
              ├── OpenAI API ──→ AI 分析（可选）
              └── Figma API ──→ 设计分析
```

---

> 版本 0.5.0 | 最后更新 2026-06-26
