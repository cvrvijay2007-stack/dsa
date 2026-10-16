"""Saving, opening, updating and deleting graphs (UI + backend together)."""

import httpx
from playwright.sync_api import Page, expect

from conftest import build


def save_as(page: Page, name: str) -> None:
    page.get_by_role("button", name="Save graph").click()
    dlg = page.get_by_role("dialog", name="Save graph")
    expect(dlg).to_be_visible()
    dlg.get_by_label("Name").fill(name)
    dlg.get_by_role("button", name="Save", exact=True).click()
    expect(dlg).to_be_hidden()
    expect(page.locator("#toast")).to_contain_text(f"“{name}”")  # request finished


def open_saved(page: Page):
    page.get_by_role("tab", name="Saved").click()
    return page.locator("#saved")


def test_empty_saved_list(app: Page):
    expect(open_saved(app)).to_contain_text("Nothing saved yet")
    expect(app.locator("#saved-count")).to_have_text("")


def test_save_lists_graph_and_hits_backend(app: Page, server):
    save_as(app, "Sample copy")
    expect(app.locator("#toast")).to_have_text("Saved “Sample copy”.")
    saved = open_saved(app)
    expect(saved.locator("li[data-id]")).to_have_count(1)
    expect(saved).to_contain_text("8 nodes, 13 edges")
    expect(app.locator("#saved-count")).to_have_text("1")
    expect(app.locator("#dirty")).to_have_text("Editing “Sample copy”.")
    rows = httpx.get(f"{server}/api/graphs").json()
    assert [(r["name"], r["node_count"], r["edge_count"]) for r in rows] == [("Sample copy", 8, 13)]


def test_cancel_save_dialog_saves_nothing(app: Page, server):
    app.get_by_role("button", name="Save graph").click()
    dlg = app.get_by_role("dialog", name="Save graph")
    dlg.get_by_label("Name").fill("nope")
    dlg.get_by_role("button", name="Cancel").click()
    expect(dlg).to_be_hidden()
    app.get_by_role("button", name="Save graph").click()
    app.keyboard.press("Escape")
    expect(dlg).to_be_hidden()
    assert httpx.get(f"{server}/api/graphs").json() == []


def test_save_requires_a_name(app: Page, server):
    app.get_by_role("button", name="Save graph").click()
    dlg = app.get_by_role("dialog", name="Save graph")
    dlg.get_by_label("Name").fill("")
    dlg.get_by_role("button", name="Save", exact=True).click()
    expect(dlg).to_be_visible()  # native required validation blocks submit
    dlg.get_by_role("button", name="Cancel").click()
    assert httpx.get(f"{server}/api/graphs").json() == []


def test_save_needs_nodes(app: Page):
    app.get_by_role("button", name="Clear").click()
    app.get_by_role("button", name="Save graph").click()
    expect(app.locator("#toast")).to_have_text("Add at least one node before saving.")
    expect(app.get_by_role("dialog")).to_have_count(0)


def test_open_saved_graph_restores_it(app: Page):
    build(app, "Oslo Bergen 5\nBergen Tromso 2")
    save_as(app, "Norway")
    app.get_by_role("button", name="Sample").click()
    expect(app.locator("#layer [data-n]")).to_have_count(8)
    open_saved(app).get_by_role("button", name="Open Norway").click()
    expect(app.locator("#toast")).to_have_text("Opened “Norway”.")
    expect(app.locator("#layer .nt")).to_have_text(["Oslo", "Bergen", "Tromso"])
    expect(app.locator("#saved li.current")).to_have_count(1)


def test_same_name_updates_new_name_copies(app: Page, server):
    save_as(app, "Mine")
    app.locator("#layer .wbg").first.click()
    app.get_by_label("Edit edge weight").fill("50")
    app.get_by_label("Edit edge weight").press("Enter")
    open_saved(app)
    expect(app.locator("#dirty")).to_have_text("“Mine” has unsaved changes.")
    app.get_by_role("button", name="Save graph").click()
    dlg = app.get_by_role("dialog", name="Save graph")
    expect(dlg.get_by_label("Name")).to_have_value("Mine")
    expect(dlg).to_contain_text("Keep the name to update “Mine”")
    dlg.get_by_role("button", name="Save", exact=True).click()
    expect(app.locator("#toast")).to_have_text("Updated “Mine”.")
    rows = httpx.get(f"{server}/api/graphs").json()
    assert len(rows) == 1
    assert httpx.get(f"{server}/api/graphs/{rows[0]['id']}").json()["edges"][0]["w"] == 50

    save_as(app, "Mine v2")
    assert sorted(r["name"] for r in httpx.get(f"{server}/api/graphs").json()) == ["Mine", "Mine v2"]
    expect(app.locator("#saved-count")).to_have_text("2")


def test_saved_positions_survive_reload(app: Page):
    save_as(app, "Layout")
    before = app.locator('[data-n="3"] .nc').get_attribute("cx")
    app.reload()
    open_saved(app).get_by_role("button", name="Open Layout").click()
    expect(app.locator('[data-n="3"] .nc')).to_have_attribute("cx", before)


def test_delete_asks_first(app: Page, server):
    save_as(app, "Temp")
    saved = open_saved(app)
    saved.get_by_role("button", name="Delete Temp").click()
    dlg = app.get_by_role("dialog", name="Delete saved graph?")
    expect(dlg).to_contain_text("“Temp” will be removed for good.")
    dlg.get_by_role("button", name="Keep it").click()
    expect(saved.locator("li[data-id]")).to_have_count(1)

    saved.get_by_role("button", name="Delete Temp").click()
    dlg.get_by_role("button", name="Delete").click()
    expect(app.locator("#toast")).to_have_text("Deleted.")
    expect(saved).to_contain_text("Nothing saved yet")
    expect(app.locator("#dirty")).to_have_text("")
    assert httpx.get(f"{server}/api/graphs").json() == []
