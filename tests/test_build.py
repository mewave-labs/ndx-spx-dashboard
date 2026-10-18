# -*- coding: utf-8 -*-

from src.build import build_market_board, svg_data_uri


def test_board_keeps_market_groups_and_drops_other():
    snapshot = {
        "source": "mewave",
        "observed_at": "2026-10-18T17:00:00+08:00",
        "indices": [{"name": "纳斯达克100"}],
        "warnings": [],
        "funds": [
            {"code": "513100", "group": "ndx", "name": "纳指ETF"},
            {"code": "513650", "group": "sp500", "name": "标普500ETF"},
            {"code": "999999", "group": "other", "name": "其他"},
        ],
    }
    board = build_market_board(snapshot)
    assert [f["code"] for f in board["funds"]] == ["513100", "513650"]
    assert board["funds"][0]["group_label"] == "纳指100"
    assert board["funds"][0]["is_holding"] is False
    assert any("不属于纳指/标普分组" in w for w in board["warnings"])
    assert "holdings" not in board


def test_svg_data_uri_is_embeddable():
    uri = svg_data_uri("<svg/>")
    assert uri.startswith("data:image/svg+xml;base64,")
