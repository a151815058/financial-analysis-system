"""REQ_013：/admin 排程執行狀況頁面（獨立於 /dashboard）。"""

from __future__ import annotations


def test_admin_route_serves_html(client):
    response = client.get("/admin")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "排程執行狀況" in response.text


def test_admin_static_asset_is_served(client):
    js = client.get("/static/admin.js")
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]


def test_admin_page_does_not_require_api_key(client):
    # 頁面本身不需要驗證；驗證發生在頁面內對 /api/v1/admin/* 端點的呼叫
    response = client.get("/admin")
    assert response.status_code == 200
