# -*- coding: utf-8 -*-
"""构建纳指/标普研究静态页。

数据来源：本机 mewave（默认 http://127.0.0.1:8000）。
输出：dist/index.html —— 单文件，所有图表/数据/悬停内容内嵌，可离线打开。

用法::

    python -m src.build
    python -m src.build --api-base http://127.0.0.1:8000 --observed-at 2026-10-18T17:00:00+08:00

本仓库只依赖 mewave 的只读 API，不 import 四个现有仓库的源码。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.render import (
    render_fund_returns_svg,
    render_livermore_svg,
    render_seasonality_svg,
)

ROOT = Path(__file__).resolve().parents[1]
GROUP_LABEL = {
    "ndx": "纳指100",
    "ndx_tech": "纳指科技",
    "sp500": "标普500",
    "other": "其他",
}
WANTED_GROUPS = ("ndx", "ndx_tech", "sp500")


def fetch_json(base: str, path: str, params: dict | None = None, timeout: float = 180.0) -> dict:
    url = base.rstrip("/") + path
    try:
        resp = requests.get(url, params=params, timeout=(3.0, timeout))
    except requests.RequestException as exc:
        raise RuntimeError(f"请求失败 {url}: {exc}") from exc
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = resp.text[:160]
        raise RuntimeError(f"mewave {resp.status_code} {path}: {detail}")
    payload = resp.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} 返回不是 JSON 对象")
    return payload


def build_market_board(snapshot: dict) -> dict:
    """把 mewave 快照裁成公开看板，不携带任何账户/持仓字段。"""
    funds = []
    unknown = []
    for raw in snapshot.get("funds") or []:
        item = dict(raw)
        group = str(item.get("group") or "other")
        if group not in WANTED_GROUPS:
            unknown.append(str(item.get("code") or ""))
            continue
        item["group_label"] = GROUP_LABEL.get(group, group)
        item["is_holding"] = False
        funds.append(item)

    warnings = list(snapshot.get("warnings") or [])
    if unknown:
        warnings.append(
            f"{len(unknown)} 只标的不属于纳指/标普分组，已隐藏：{', '.join(unknown[:6])}"
        )
    return {
        "source": snapshot.get("source") or "mewave",
        "observed_at": snapshot.get("observed_at") or "",
        "policy_version": "public-static-v1",
        "indices": list(snapshot.get("indices") or []),
        "funds": funds,
        "warnings": warnings,
    }


def svg_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64," + encoded


def _safe_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def build(
    *,
    api_base: str,
    out_dir: Path,
    observed_at: str | None = None,
    snapshot_file: Path | None = None,
    season_start: int = 2021,
    season_end: int = 2026,
    fund_codes: str = "513100,513500",
) -> Path:
    if observed_at is None:
        observed_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

    if snapshot_file is not None:
        snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    else:
        snapshot = fetch_json(
            api_base,
            "/api/funds/snapshot",
            {"observed_at": observed_at},
        )

    board = build_market_board(snapshot)
    ndx = fetch_json(api_base, "/api/charts/ndx-livermore")
    season = fetch_json(
        api_base,
        "/api/charts/ndx-seasonality",
        {"start_year": season_start, "end_year": season_end},
    )
    funds = fetch_json(
        api_base,
        "/api/charts/fund-returns",
        {"codes": fund_codes, "years": 5, "mode": "rolling5y"},
    )

    transitions = list(ndx.get("transitions") or [])[-12:]
    transitions.reverse()
    images = {
        "ndx": svg_data_uri(render_livermore_svg(ndx)),
        "season": svg_data_uri(render_seasonality_svg(season)),
        "funds": svg_data_uri(render_fund_returns_svg(funds)),
    }
    static_data = {"ndx": ndx, "season": season, "funds": funds}

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("index.html").render(
        board_json=_safe_json(board),
        ndx_states=transitions,
        ndx_current=ndx.get("current") or {},
        ndx_frequency=float(ndx.get("frequency") or 0),
        ndx_model=str(ndx.get("model") or ""),
        static_mode=True,
        ndx_svg=images["ndx"],
        season_svg=images["season"],
        fund_svg=images["funds"],
        static_data_json=_safe_json(static_data),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成纳指/标普研究静态页")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default=str(ROOT / "dist"))
    parser.add_argument("--observed-at", default=None)
    parser.add_argument("--snapshot", default=None, help="可选：离线快照 JSON")
    parser.add_argument("--season-start", type=int, default=2021)
    parser.add_argument("--season-end", type=int, default=2026)
    parser.add_argument("--fund-codes", default="513100,513500")
    args = parser.parse_args(argv)

    try:
        output = build(
            api_base=args.api_base,
            out_dir=Path(args.out),
            observed_at=args.observed_at,
            snapshot_file=Path(args.snapshot) if args.snapshot else None,
            season_start=args.season_start,
            season_end=args.season_end,
            fund_codes=args.fund_codes,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"构建失败：{exc}", file=sys.stderr)
        return 1
    print(f"已生成 {output} ({output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
