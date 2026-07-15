from __future__ import annotations


def test_dashboard_route_serves_html(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "各公司各季度財務分析與股價預測系統" in response.text


def test_dashboard_static_assets_are_served(client):
    css = client.get("/static/dashboard.css")
    js = client.get("/static/dashboard.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert "javascript" in js.headers["content-type"]


def test_dashboard_does_not_require_api_key(client):
    # 頁面本身（HTML/CSS/JS）不需要驗證；驗證發生在頁面內對 API 端點的呼叫
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_root_redirects_to_dashboard(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/dashboard"
