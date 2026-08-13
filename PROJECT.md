# Dota 2 AI 赛后复盘分析

## 项目概要
公开 Web 应用，娱乐性质的 Dota 2 比赛赛后复盘工具。输入玩家ID或比赛ID → AI 分析 → MVP/背锅侠/1-5号位评估/关键时间线。支持分享链接。Vue3 前端 + FastAPI 后端，Docker 部署到阿里云 ECS。

## 技术栈
- 前端: Vue 3 + TypeScript + Vite, Inter 字体
- 后端: Python 3.11 FastAPI, uvicorn
- AI: 可切换 OpenAI / DeepSeek / Claude, 通过 openai SDK + anthropic SDK
- 数据源: OpenDota API (免费, 无 key)
- 缓存: SQLite (aiosqlite)
- 部署: Docker Compose (Nginx + 前端 + 后端), 目标阿里云 ECS

## 目录结构
```
work/dota2-analyzer/
├── Makefile              # dev/dev-backend/dev-frontend/install/build
├── dev.sh                # 一键启动前后端
├── docker-compose.yml    # 生产部署编排
├── .env.example          # 环境变量模板
├── nginx/default.conf    # 反向代理
├── backend/
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # pydantic-settings 配置
│   ├── requirements.txt  # fastapi, uvicorn, httpx, openai, anthropic, aiosqlite 等
│   ├── database/db.py    # SQLite 初始化 + 连接
│   ├── models/schemas.py # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── matches.py    # /api/players/{id}, /api/players/{id}/matches, /api/matches/{id}
│   │   ├── analysis.py   # /api/analyze (POST), /api/providers
│   │   └── share.py      # /api/share/{share_id}
│   └── services/
│       ├── opendota.py   # OpenDota API 客户端 (带重试)
│       ├── position_detector.py  # 1-5号位判定 (英雄主位置 > GPM > 辅助装)
│       ├── hero_position.py     # 127英雄主/次要位置映射表 (按hero_id升序)
│       ├── hero_cn.py           # 126英雄中英文名映射
│       └── analyzer.py          # AI分析引擎 (prompt构造+SDK调用+结果组装)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts     # /api 代理到 localhost:8000
    ├── index.html         # Inter 字体引入
    └── src/
        ├── main.ts, App.vue, style.css
        ├── router/index.ts   # /, /analysis/:matchId, /share/:shareId
        ├── api/index.ts      # API 客户端类型定义
        ├── views/
        │   ├── Home.vue      # 首页 (搜玩家/搜比赛, AI模型选择, 比赛列表)
        │   ├── Analysis.vue  # 分析结果页 (MVP/背锅侠, 阵营切换, 位置评估, 时间线)
        │   └── Share.vue     # 分享页 (同Analysis但只读)
        └── components/
            ├── PlayerCard.vue     # 玩家数据卡片
            ├── PositionEval.vue   # 位置评估卡片
            └── Timeline.vue       # 关键事件时间线
```

## 核心功能

### 位置判定 (position_detector.py)
三级仲裁: 英雄主位置 > GPM > 辅助装备
1. 每个玩家取 HERO_PRIMARY 表中的主位置
2. 无冲突直接分配
3. 同位置冲突: 核心位(1-3)GPM高者胜, 辅助位(4-5)辅助得分高者胜
4. 未分配者→次要位置→按GPM填剩余空位
5. 辅助得分: 购买辅助装(wand/glimmer/force等20件) + 真假眼(ward_observer/sentry) + GPM

### AI 分析 (analyzer.py)
- System prompt 定义分析师角色 (毒舌幽默)
- User prompt 包含: 比赛概览 + 分段基准 + 选手数据(位置/英雄/KDA/GPM/补刀/伤害/关键装备)
- 要求 AI 输出 JSON: mvp, scapegoat, position_evals×10(每选手一条), timeline, game_summary
- MVP/背锅侠匹配: 四级 fallback (精确→忽略大小写→子串→英雄名)

### 前端交互
- 首页: 玩家ID搜索(有 localStorage 缓存) 或直接输入比赛ID
- AI 模型可切换 (DeepSeek 默认)
- 分析结果页: 天辉/夜魇双阵营 tab 切换, 每方5个位置评估卡片
- 分享链接: 12位 share_id, 存 SQLite, 可分享
- 响应式: 480px 断点适配手机

## 已知限制
- OpenDota /matches/{id} 不返回 lane_role (无分路数据), 不返回 obs_placed/sen_placed (无插眼数据)
- 插眼通过 purchase_log 中的 ward_observer/ward_sentry 检测
- OpenDota 偶发 522 Cloudflare 超时 (已加重试+友好提示)
- HERO_PRIMARY 部分英雄位置为 role 自动推断, 需手动校准

## 开发命令
```bash
make install    # 创建 venv + pip install + npm install
make dev        # 一键启动 (backend :8000 + frontend :5173)
make dev-backend  # 仅后端
make dev-frontend # 仅前端
make build       # 仅构建前端
```

## 部署
```bash
cp .env.example .env && vim .env   # 填入 API Key
docker-compose up -d               # 默认暴露 8080 端口
```

### 小程序服务器域名
小程序通过 `https://maojike.me/dota-api` 访问后端，上线前需在微信公众平台：

- `request合法域名` 添加 `https://maojike.me`
- `downloadFile合法域名` 添加 `https://maojike.me`（英雄头像走同一域名）

若仍报 `url not in domain list`，先检查这两项，以及是否误上传了 `dist/dev` 构建产物。

## 当前状态 (2026-08-05)
- 前端: UI 已通过 finesse 优化 (tinted neutral palette, 去 AI tell, 响应式)
- 后端: 所有接口正常, 位置判定逻辑完成
- 待办: HERO_PRIMARY/HERO_SECONDARY 中部分英雄位置需手动校准
