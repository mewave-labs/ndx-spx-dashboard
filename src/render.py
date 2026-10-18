# -*- coding: utf-8 -*-
"""用纯 SVG 渲染两个分析图（无前端图表库、离线可用）。

* ``render_livermore_svg``：纳指100 价格 + MA20/60/200 + 趋势背景 + 关键点；
* ``render_fund_returns_svg``：多基金 5 年累计收益曲线。

数据由 mewave 的 ``/api/charts/*`` 提供；本模块只负责画图。
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Iterable, Sequence

import math
import requests

W, H = 1120, 440
ML, MR, MT, MB = 66, 190, 34, 42
PW, PH = W - ML - MR, H - MT - MB

BG = "#0f1115"
GRID = "#242b37"
TEXT = "#93a0b4"
FG = "#e7eaf0"
CLOSE = "#e7eaf0"
MA20 = "#5aa9ff"
MA60 = "#ffb454"
MA200 = "#b98bff"
UP = "#3ddc97"
DOWN = "#ff6b6b"
FUND_COLORS = ("#3ddc97", "#ffb454", "#5aa9ff", "#b98bff", "#ff6b6b", "#66d9ef")
STATE_FILL = {
    "uptrend": "#22c55e",
    "retreat": "#eab308",
    "retreat2nd": "#f97316",
    "downtrend": "#ef4444",
    "recover": "#3b82f6",
    "recover2nd": "#a855f7",
    "range": "#93a0b4",
}
STATE_LABEL = {
    "uptrend": "上升",
    "retreat": "回撤",
    "retreat2nd": "二次回撤",
    "downtrend": "下降",
    "recover": "修复",
    "recover2nd": "二次修复",
    "range": "震荡",
}
YEAR_COLORS = {
    2021: "#f59e0b",
    2022: "#f472b6",
    2023: "#34d399",
    2024: "#fb923c",
    2025: "#a78bfa",
    2026: "#60a5fa",
}

ENV_BASE = "USFUNDS_API_BASE"
DEFAULT_BASE = "http://127.0.0.1:8000"


def api_base() -> str:
    return os.environ.get(ENV_BASE, DEFAULT_BASE).rstrip("/")


def fetch_json(path: str, params: dict[str, Any] | None = None, timeout: float = 240.0) -> dict:
    resp = requests.get(f"{api_base()}{path}", params=params, timeout=(3.0, timeout))
    if resp.status_code != 200:
        detail = ""
        try:
            detail = str(resp.json().get("detail") or "")
        except Exception:  # noqa: BLE001
            detail = resp.text[:120]
        raise RuntimeError(f"mewave {resp.status_code}: {detail}")
    payload = resp.json()
    if not isinstance(payload, dict):
        raise RuntimeError("mewave 返回不是对象")
    return payload


def _esc(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _finite(values: Iterable[float | None]) -> list[float]:
    return [float(v) for v in values if v is not None and v == v]


def _svg_start(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
        f'role="img" aria-label="{_esc(title)}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<text x="{ML}" y="20" fill="{FG}" font-size="13" font-family="Segoe UI, Microsoft YaHei, sans-serif">'
        f"{_esc(title)}</text>",
    ]


def _y_ticks(values: list[float], count: int = 5) -> list[float]:
    lo, hi = min(values), max(values)
    if hi <= lo:
        hi = lo + 1
    return [lo + (hi - lo) * i / (count - 1) for i in range(count)]


def _line_path(values: Sequence[float | None], x_at, y_at) -> str:
    parts: list[str] = []
    started = False
    for i, value in enumerate(values):
        if value is None:
            started = False
            continue
        cmd = "L" if started else "M"
        parts.append(f"{cmd}{x_at(i):.2f},{y_at(float(value)):.2f}")
        started = True
    return " ".join(parts)


def _text(x: float, y: float, value: str, *, fill: str = TEXT, size: int = 11,
          anchor: str = "start", weight: str = "normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
        f'text-anchor="{anchor}" font-weight="{weight}" '
        f'font-family="Segoe UI, Microsoft YaHei, sans-serif">{_esc(value)}</text>'
    )


def placeholder_svg(message: str, title: str = "图表") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%">'
        f'<rect width="{W}" height="{H}" fill="{BG}"/>'
        + _text(ML, H // 2, f"{title}：数据不可用", fill=DOWN, size=16)
        + _text(ML, H // 2 + 26, message[:120], fill=TEXT, size=12)
        + "</svg>"
    )


def render_livermore_svg(data: dict) -> str:
    dates = [str(d) for d in data.get("dates") or []]
    closes = data.get("close") or []
    ma20 = data.get("ma20") or []
    ma60 = data.get("ma60") or []
    ma200 = data.get("ma200") or []
    states = data.get("states") or []
    signals = data.get("signals") or []
    if not dates or not closes:
        return placeholder_svg("没有可用的纳指历史数据", "利弗莫尔模型")

    values = _finite([*closes, *ma20, *ma60, *ma200])
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.04 or 1.0
    lo, hi = lo - pad, hi + pad
    n = len(dates)

    def x_at(i: int) -> float:
        return ML + (i / (n - 1) * PW if n > 1 else 0)

    def y_at(v: float) -> float:
        return MT + PH - (v - lo) / (hi - lo) * PH

    svg = _svg_start(f"纳斯达克100 · 利弗莫尔六状态机（{data.get('model', '')}）")

    # 二级状态用斜线纹理，和一级状态区分开
    svg.append("<defs>")
    for key in ("retreat", "retreat2nd", "recover", "recover2nd"):
        color = STATE_FILL[key]
        svg.append(
            f'<pattern id="st-{key}" width="8" height="8" patternUnits="userSpaceOnUse">'
            f'<rect width="8" height="8" fill="{color}" opacity="0.16"/>'
            f'<path d="M0,8 L8,0" stroke="{color}" stroke-width="1.2" opacity="0.55"/>'
            f"</pattern>"
        )
    svg.append("</defs>")

    # 状态背景
    if states:
        start = 0
        current_state = states[0]
        for i in range(1, n + 1):
            if i == n or states[i] != current_state:
                x0 = x_at(max(0, start - 0.5))
                x1 = x_at(min(n - 1, i - 0.5))
                color = STATE_FILL.get(current_state, TEXT)
                if current_state in ("retreat", "retreat2nd", "recover", "recover2nd"):
                    fill = f"url(#st-{current_state})"
                    opacity = "1"
                else:
                    fill = color
                    opacity = "0.18" if current_state in ("uptrend", "downtrend") else "0.05"
                svg.append(
                    f'<rect x="{x0:.1f}" y="{MT}" width="{max(0.0, x1 - x0):.1f}" '
                    f'height="{PH}" fill="{fill}" opacity="{opacity}"/>'
                )
                if current_state != "range":
                    svg.append(
                        f'<rect x="{x0:.1f}" y="{MT}" width="{max(0.0, x1 - x0):.1f}" '
                        f'height="3" fill="{color}" opacity="0.95"/>'
                    )
                if i < n:
                    start, current_state = i, states[i]

    # 网格与 Y 轴
    for tick in _y_ticks([lo, hi], 5):
        y = y_at(tick)
        svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML + PW}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(_text(ML - 8, y + 4, f"{tick:,.0f}", anchor="end"))

    # X 轴
    for i in (0, n // 4, n // 2, 3 * n // 4, n - 1):
        if 0 <= i < n:
            svg.append(_text(x_at(i), H - 18, dates[i][:7], anchor="middle", size=10))

    # 均线
    for values_line, color, width in ((ma200, MA200, 1.6), (ma60, MA60, 1.1), (ma20, MA20, 1.1)):
        path = _line_path(values_line, x_at, y_at)
        if path:
            svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}"/>')

    # 收盘价
    close_path = _line_path(closes, x_at, y_at)
    svg.append(f'<path d="{close_path}" fill="none" stroke="{CLOSE}" stroke-width="2"/>')

    # 关键点标记
    for signal in signals:
        idx = signal.get("index")
        price = signal.get("price")
        if idx is None or price is None or not (0 <= int(idx) < n):
            continue
        x, y = x_at(int(idx)), y_at(float(price))
        if signal.get("type") == "buy":
            svg.append(
                f'<path d="M{x:.1f},{y - 9:.1f} L{x - 6:.1f},{y + 2:.1f} L{x + 6:.1f},{y + 2:.1f} Z" fill="{UP}"/>'
            )
        else:
            svg.append(
                f'<path d="M{x:.1f},{y + 9:.1f} L{x - 6:.1f},{y - 2:.1f} L{x + 6:.1f},{y - 2:.1f} Z" fill="{DOWN}"/>'
            )

    # 图例
    lx = ML + PW + 16
    legend = (("收盘", CLOSE), ("MA20", MA20), ("MA60", MA60), ("MA200", MA200))
    for row, (label, color) in enumerate(legend):
        y = MT + 16 + row * 20
        svg.append(f'<line x1="{lx}" y1="{y}" x2="{lx + 20}" y2="{y}" stroke="{color}" stroke-width="2"/>')
        svg.append(_text(lx + 26, y + 4, label))

    current = data.get("current") or {}
    state_cn = STATE_LABEL.get(str(current.get("trend")), "未知")
    last_transition = current.get("last_transition") or {}
    last_cn = STATE_LABEL.get(str(last_transition.get("state")), "—")
    info = [
        f"状态：{state_cn}",
        f"模型仓位：{'持有' if current.get('position') == 'long' else '空仓'}",
        f"切换频率：{float(data.get('frequency') or 0):.1f} 次/年",
        f"最新：{float(current.get('close') or 0):,.0f}",
        f"MA200：{float(current.get('ma200') or 0):,.0f}" if current.get("ma200") else "MA200：—",
        f"最近切换：{last_transition.get('date', '—')} {last_cn}" if last_transition else "最近切换：—",
    ]
    for row, text in enumerate(info):
        svg.append(_text(lx, MT + 112 + row * 19, text, fill=FG if row == 0 else TEXT, size=11))

    svg.append("</svg>")
    return "".join(svg)


def _date_ordinal(value: str) -> int:
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return 0


def render_seasonality_svg(data: dict) -> str:
    years = data.get("years") or []
    if not years:
        return placeholder_svg("所选年份没有纳指数据", "年度走势对比")
    start_year = int(data.get("start_year") or years[0]["year"])
    end_year = int(data.get("end_year") or years[-1]["year"])

    values = [v for item in years for v in (item.get("returns") or [])]
    step = 0.10
    lo = math.floor(min(values + [0.0]) / step) * step
    hi = math.ceil(max(values + [0.0]) / step) * step
    if hi <= lo:
        hi = lo + step

    def x_at_day(day: str) -> float:
        doy = date.fromisoformat(day).timetuple().tm_yday
        return ML + (doy - 1) / 364.0 * PW

    def y_at(value: float) -> float:
        return MT + PH - (value - lo) / (hi - lo) * PH

    svg = _svg_start(f"纳斯达克100 · 年度走势对比（{start_year}–{end_year}）")

    # 月份网格
    for month in range(1, 13):
        day = date(2021, month, 1).isoformat()
        x = x_at_day(day)
        svg.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT + PH}" stroke="{GRID}" stroke-width="1" opacity="0.7"/>')
        anchor = "start" if month == 1 else "end" if month == 12 else "middle"
        svg.append(_text(x, H - 18, f"{month}月", anchor=anchor, size=10))

    tick = lo
    while tick <= hi + 1e-9:
        y = y_at(tick)
        svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML + PW}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(_text(ML - 8, y + 4, f"{tick:+.0%}" if abs(tick) > 1e-9 else "0%", anchor="end"))
        tick += step

    zero_y = y_at(0.0)
    svg.append(
        f'<line x1="{ML}" y1="{zero_y:.1f}" x2="{ML + PW}" y2="{zero_y:.1f}" '
        f'stroke="{TEXT}" stroke-width="1" stroke-dasharray="4 4" opacity="0.7"/>'
    )

    for item in years:
        year = int(item["year"])
        color = YEAR_COLORS.get(year, FUND_COLORS[year % len(FUND_COLORS)])
        points = [(x_at_day(d), y_at(float(v))) for d, v in zip(item["dates"], item["returns"])]
        if not points:
            continue
        path = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)
        width = 2.2 if year == end_year else 1.7
        svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" opacity="0.95"/>')
        lx, ly = points[-1]
        svg.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" fill="{color}"/>')

        gx = ML + PW + 16
        gy = MT + 15 + (year - start_year) * 38
        svg.append(f'<line x1="{gx}" y1="{gy}" x2="{gx + 18}" y2="{gy}" stroke="{color}" stroke-width="2"/>')
        svg.append(_text(gx + 24, gy + 4, str(year), fill=FG, size=11))
        svg.append(
            _text(
                gx + 24,
                gy + 19,
                f"{float(item.get('final_return') or 0):+.1%}",
                fill=color,
                size=11,
                weight="600",
            )
        )

    svg.append("</svg>")
    return "".join(svg)


def render_fund_returns_svg(data: dict) -> str:
    series = data.get("series") or []
    rolling = data.get("mode") == "rolling"
    title = "任意时点买入并持有 5 年的收益（滚动窗口）" if rolling else "5 年累计收益对比"
    if not series:
        return placeholder_svg("没有满 5 年历史的基金序列", title)

    all_dates = sorted({d for s in series for d in (s.get("dates") or [])})
    if len(all_dates) < 2:
        return placeholder_svg("净值日期不足", "5 年累计收益")
    ords = [_date_ordinal(d) for d in all_dates]
    o_min, o_max = min(ords), max(ords)
    span = max(1, o_max - o_min)

    values = [v for s in series for v in (s.get("returns") or []) if v is not None]
    step = 0.25
    raw_min = min(values + [0.0])
    raw_max = max(values + [0.0])
    lo = math.floor(raw_min / step) * step
    hi = math.ceil(raw_max / step) * step
    if hi <= lo:
        hi = lo + step

    def x_at_ord(ordinal: int) -> float:
        return ML + (ordinal - o_min) / span * PW

    def y_at(v: float) -> float:
        return MT + PH - (v - lo) / (hi - lo) * PH

    svg = _svg_start(title)

    tick = lo
    while tick <= hi + 1e-9:
        y = y_at(tick)
        svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML + PW}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(_text(ML - 8, y + 4, f"{tick:+.0%}" if abs(tick) > 1e-9 else "0%", anchor="end"))
        tick += step

    zero_y = y_at(0.0)
    svg.append(
        f'<line x1="{ML}" y1="{zero_y:.1f}" x2="{ML + PW}" y2="{zero_y:.1f}" '
        f'stroke="{TEXT}" stroke-width="1" stroke-dasharray="4 4" opacity="0.6"/>'
    )

    for i in (0, len(all_dates) // 4, len(all_dates) // 2, 3 * len(all_dates) // 4, len(all_dates) - 1):
        if 0 <= i < len(all_dates):
            svg.append(_text(x_at_ord(ords[i]), H - 18, all_dates[i][:7], anchor="middle", size=10))

    for idx, item in enumerate(series):
        color = FUND_COLORS[idx % len(FUND_COLORS)]
        points = [
            (x_at_ord(_date_ordinal(day)), y_at(float(value)))
            for day, value in zip(item.get("dates") or [], item.get("returns") or [])
            if value is not None
        ]
        if not points:
            continue
        step = max(1, len(points) // 420)
        sampled = points[::step]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        path = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in sampled)
        svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8"/>')

        lx = ML + PW + 16
        ly = MT + 16 + idx * 42
        svg.append(f'<line x1="{lx}" y1="{ly}" x2="{lx + 18}" y2="{ly}" stroke="{color}" stroke-width="2"/>')
        name = str(item.get("name") or item.get("code"))
        svg.append(_text(lx + 24, ly + 4, name[:16], fill=FG, size=11))
        if rolling:
            detail = (
                f"{item.get('code')} {float(item.get('final_return') or 0):+.1%}"
                f" / 均{float(item.get('avg_return') or 0):+.1%}"
            )
        else:
            detail = f"{item.get('code')}  {float(item.get('final_return') or 0):+.1%}"
        svg.append(_text(lx + 24, ly + 19, detail, fill=color, size=11, weight="600"))

    svg.append(
        _text(
            ML,
            H - 4,
            f"区间 {data.get('start_date', '')} ~ {data.get('end_date', '')}（横轴=持有到期日）",
            size=10,
        )
    )
    svg.append("</svg>")
    return "".join(svg)
