"""Errors, security, theming, accessibility and responsive layout."""

import re

import httpx
from playwright.sync_api import Page, expect

from conftest import build, step


def test_server_offline_is_reported(app: Page):
    app.route("**/api/**", lambda route: route.abort())
    app.get_by_role("button", name="Sample").click()
    expect(app.locator("#toast")).to_have_text("Can't reach the server. Check that it's running, then try again.")
    expect(app.locator("#api")).to_contain_text("Server offline")
    app.unroute("**/api/**")
    app.get_by_role("button", name="Sample").click()
    expect(app.locator("#api")).to_contain_text("Server connected")


def test_trace_failure_shows_error_and_recovers(app: Page):
    app.route("**/api/mst", lambda r: r.fulfill(status=500, json={"detail": "Trace failed on the server."}))
    app.locator("#start").select_option(label="C")  # forces a new trace
    step(app)
    expect(app.locator("#toast")).to_have_text("Trace failed on the server.")
    expect(app.locator("#prog")).to_have_text("")
    app.unroute("**/api/mst")
    step(app)
    expect(app.locator("#prog")).to_have_text("Step 1 of 15")


def test_validation_error_message_is_readable(app: Page):
    app.route("**/api/parse", lambda r: r.fulfill(status=422, json={"detail": [{"msg": "Value error, bad input"}]}))
    build(app, "A B 1")
    expect(app.locator("#toast")).to_have_text("bad input")


def test_labels_are_escaped(app: Page, server):
    """Hostile labels from the edge list or the database render as text."""
    # ">" separates names in the edge list, so markup there can only be partial tags.
    build(app, '<b "q"&lt 2\n<i B 3')
    expect(app.locator("#layer .nt")).to_have_text(["<b", '"q"&lt', "<i", "B"])
    expect(app.locator("#start option")).to_have_text(["<b", '"q"&lt', "<i", "B"])
    assert app.locator("#layer b, #layer i, #start b").count() == 0

    payload = "<svg onload=__p=1>"
    nodes = [{"x": 100, "y": 100, "label": payload}, {"x": 300, "y": 200, "label": "ok"}]
    httpx.post(f"{server}/api/graphs", json={"name": payload, "nodes": nodes, "edges": [{"a": 0, "b": 1, "w": 2}]})
    app.reload()
    app.get_by_role("tab", name="Saved").click()
    expect(app.locator("#saved .load b")).to_have_text(payload)
    app.get_by_role("button", name=f"Open {payload}").click()
    step(app, 3)
    expect(app.locator("#log li").first).to_have_text(f"Start at {payload}: add it to the tree.")
    assert app.evaluate("typeof window.__p") == "undefined"
    assert app.locator("#layer svg, #log svg, #saved svg, #tb svg").count() == 0


def test_theme_toggle_persists(app: Page):
    html = app.locator("html")
    was_dark = "dark" in (html.get_attribute("class") or "")
    app.locator("#theme").click()
    assert ("dark" in (html.get_attribute("class") or "")) != was_dark
    app.reload()
    assert ("dark" in (html.get_attribute("class") or "")) != was_dark
    label = app.locator("#theme").get_attribute("aria-label")
    assert label == ("Switch to dark theme" if was_dark else "Switch to light theme")


def test_dark_theme_changes_palette(app: Page):
    app.emulate_media(color_scheme="light")
    app.evaluate("localStorage.removeItem('theme')")
    app.reload()
    light_bg = app.evaluate("getComputedStyle(document.body).backgroundColor")
    app.locator("#theme").click()
    dark_bg = app.evaluate("getComputedStyle(document.body).backgroundColor")
    assert light_bg == "rgb(232, 237, 239)" and dark_bg == "rgb(15, 21, 29)"


def test_tabs_support_arrow_keys(app: Page):
    steps_tab = app.get_by_role("tab", name="Steps")
    steps_tab.focus()
    app.keyboard.press("ArrowRight")
    expect(app.get_by_role("tab", name="Edge list")).to_have_attribute("aria-selected", "true")
    expect(app.locator("#pane-list")).to_be_visible()
    expect(app.locator("#pane-steps")).to_be_hidden()
    app.keyboard.press("ArrowLeft")
    app.keyboard.press("ArrowLeft")
    expect(app.get_by_role("tab", name="Saved")).to_be_focused()


def test_every_control_has_an_accessible_name(app: Page):
    unnamed = app.evaluate(
        """() => [...document.querySelectorAll('button, input, select, textarea')]
            .filter(el => el.offsetParent !== null)
            .filter(el => !(el.getAttribute('aria-label') || el.labels?.length || el.textContent.trim()))
            .map(el => el.outerHTML.slice(0, 80))"""
    )
    assert unnamed == []


def test_mobile_layout_has_no_horizontal_scroll(page: Page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto("/")
    expect(page.locator("#layer [data-n]")).to_have_count(8)
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    box = page.locator("#svg").bounding_box()
    assert box["width"] > 300
    page.locator("#step").click()
    expect(page.locator("#prog")).to_have_text("Step 1 of 15")


def test_reduced_motion_disables_animation(page: Page):
    page.emulate_media(reduced_motion="reduce")
    page.goto("/")
    page.locator("#step").click()
    page.locator("#step").click()
    anim = page.evaluate("getComputedStyle(document.querySelector('.eline.pick')).animationName")
    assert anim == "none"


def test_api_docs_reachable(page: Page):
    page.goto("/docs")
    expect(page.get_by_text("MST Visualizer API")).to_be_visible()


def test_works_without_internet(page: Page):
    """Everything but web fonts is served locally; the app must work fully offline."""
    page.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort("internetdisconnected"))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("/")
    expect(page.locator("#layer [data-n]")).to_have_count(8)
    page.set_viewport_size({"width": 1280, "height": 900})
    assert page.evaluate("getComputedStyle(document.querySelector('main')).display") == "grid"
    assert page.evaluate("getComputedStyle(document.querySelector('main')).gridTemplateColumns").endswith("380px")
    page.locator("#step").click()
    expect(page.locator("#prog")).to_have_text("Step 1 of 15")
    assert errors == []
