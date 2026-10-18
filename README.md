# ndx-spx-dashboard

纳指100 / 标普500 市场研究静态看板。

- 数据、图表、悬停内容全部内嵌在 `dist/index.html`；
- 可离线双击打开，也可直接托管到 GitHub Pages；
- 本仓库不 import `mewave` / `winklet` / `mewealth` / `lorelet` 的源码；
- **构建时**只读取本机 mewave 的只读 API。

## 本地构建

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m src.build
```

默认读取 `http://127.0.0.1:8000`。先确保 mewave 在运行。

指定时间/地址：

```powershell
.\.venv\Scripts\python.exe -m src.build `
  --api-base http://127.0.0.1:8000 `
  --observed-at 2026-10-18T17:00:00+08:00
```

输出：

```text
dist/index.html
```

## 本地展示

```powershell
.\.venv\Scripts\python.exe serve.py --port 8780
```

打开 `http://127.0.0.1:8780/`。

## GitHub Pages

`dist/index.html` 是提交到仓库的产物。仓库 Settings → Pages → source 选择
`GitHub Actions` 即可；`.github/workflows/pages.yml` 会部署 `dist/`。

访问地址：

```text
https://<用户名>.github.io/ndx-spx-dashboard/
```

## 定时构建并推送

`scripts/update-and-push.ps1` 会：

1. 调 mewave 构建 `dist/index.html`；
2. 有变化时 `git add/commit`；
3. `git push origin main`。

手动运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-and-push.ps1
```

Windows 任务计划程序可以设为每天/每周运行；前提是本机 mewave 正在运行。

## 数据依赖

构建时：

```text
mewave /api/funds/snapshot
mewave /api/charts/ndx-livermore
mewave /api/charts/ndx-seasonality
mewave /api/charts/fund-returns
```

成品：

```text
dist/index.html  ← 无运行时依赖
```

`winklet` / `lorelet` 不参与本仓库运行。后续如果纯计算下沉到 winklet，
可以把本仓库的取数/渲染与 winklet 计算包对接。

## 边界

- 不包含账户、持仓、成本、加仓金额；
- 静态快照的年份滑块/基金勾选是冻结的，Tab 和悬停可用；
- 市场数据再分发请遵守数据源条款。
