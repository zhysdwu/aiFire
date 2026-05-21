# AI Hotword Generator (TikTok US) MVP

Backend: Django + DRF + MySQL  
Frontend: Vue 3 + Vite

## 环境变量（建议）

- `DJANGO_SECRET_KEY`：Django 密钥（生产环境必须配置）
- `MYSQL_DATABASE` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_HOST` / `MYSQL_PORT`
- `DEEPSEEK_API_KEY`：用于 AI 分析与推荐标题

## Quick Start

Run all services (backend + frontend):

```powershell
powershell -ExecutionPolicy Bypass -File D:\aiFire\start-dev.ps1
```

Stop all services:

```powershell
powershell -ExecutionPolicy Bypass -File D:\aiFire\stop-dev.ps1
```

Restart all services:

```powershell
powershell -ExecutionPolicy Bypass -File D:\aiFire\restart-dev.ps1
```

URLs:

- Frontend: `http://127.0.0.1:5173/`
- Backend API: `http://127.0.0.1:8000/api/phrases/?window=24h&sort=heat`
- Django Admin: `http://127.0.0.1:8000/admin/`

## 每日自动抓取机制

- 项目启动脚本 `D:\aiFire\start-dev.ps1` 会在后端可用后自动执行一次“今日抓取检查”
- 若当天（按系统时区）已经抓取过，则跳过
- 若当天未抓取，则自动执行一次 `run_daily_pipeline`
- 项目运行期间会启动轻量调度器，每 15 分钟检查一次“今天是否已抓取”
- 项目停止时会同时停止该调度器，不会在停服后继续抓取

手动检查命令：

```powershell
D:\aiFire\.venv\Scripts\python.exe D:\aiFire\backend\manage.py ensure_daily_fetch --source official --limit 60 --failover-after-minutes 30
```

手动启动调度器（可选）：

```powershell
D:\aiFire\.venv\Scripts\python.exe D:\aiFire\backend\manage.py run_daily_scheduler --source official --limit 60 --failover-after-minutes 30 --check-interval-minutes 15
```
