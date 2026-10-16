"""Editing the graph: canvas gestures, weights, edge list, generators."""

import re

from playwright.sync_api import Page, expect

from conftest import build, canvas_point, click_canvas, click_node, node_center


def clear(page: Page) -> None:
    page.get_by_role("button", name="Clear").click()
    expect(page.locator("#layer [data-n]")).to_have_count(0)


def test_clear_shows_empty_state(app: Page):
    clear(app)
    expect(app.locator("#empty")).to_be_visible()
    expect(app.locator("#empty")).to_contain_text("Click anywhere to place a node")
    expect(app.locator("#phase")).to_have_text("No graph yet")
    expect(app.get_by_role("button", name="Play")).to_be_disabled()
    expect(app.locator("#step")).to_be_disabled()
    expect(app.locator("#start")).to_be_disabled()


def test_click_canvas_adds_nodes(app: Page):
    clear(app)
    click_canvas(app, 200, 200)
    click_canvas(app, 500, 300)
    expect(app.locator("#layer [data-n]")).to_have_count(2)
    expect(app.locator("#layer .nt")).to_have_text(["A", "B"])
    expect(app.locator("#empty")).to_be_hidden()
    app.get_by_role("tab", name="Edge list").click()
    expect(app.locator("#el")).to_have_value("A\nB")
    cx = float(app.locator('[data-n="1"] .nc').get_attribute("cx"))
    assert abs(cx - 500) < 2


def test_click_two_nodes_connects_with_typed_weight(app: Page):
    clear(app)
    click_canvas(app, 200, 200)
    click_canvas(app, 500, 300)
    app.locator("#w").fill("42")
    click_node(app, 0)
    expect(app.locator('[data-n="0"]')).to_have_class(re.compile(r"\bsel\b"))
    app.wait_for_timeout(450)  # avoid a double-click
    click_node(app, 1)
    expect(app.locator("#layer [data-e]")).to_have_count(1)
    expect(app.locator("#layer .wt")).to_have_text("42")
    expect(app.locator(".node.sel")).to_have_count(0)
    app.get_by_role("tab", name="Edge list").click()
    expect(app.locator("#el")).to_have_value("A B 42")


def test_random_weight_when_field_blank(app: Page):
    clear(app)
    click_canvas(app, 200, 200)
    click_canvas(app, 500, 300)
    click_node(app, 0)
    app.wait_for_timeout(450)
    click_node(app, 1)
    w = int(app.locator("#layer .wt").text_content())
    assert 1 <= w <= 20


def test_connecting_already_linked_nodes_warns(app: Page):
    click_node(app, 0)
    app.wait_for_timeout(450)
    click_node(app, 1)  # A-B exists in the sample
    expect(app.locator("#toast")).to_have_text("A and B are already connected.")
    expect(app.locator("#layer [data-e]")).to_have_count(13)


def test_clicking_same_node_twice_slowly_deselects(app: Page):
    click_node(app, 2)
    expect(app.locator(".node.sel")).to_have_count(1)
    app.wait_for_timeout(450)
    click_node(app, 2)
    expect(app.locator(".node.sel")).to_have_count(0)


def test_escape_and_empty_click_cancel_selection(app: Page):
    click_node(app, 2)
    app.keyboard.press("Escape")
    expect(app.locator(".node.sel")).to_have_count(0)
    app.wait_for_timeout(450)
    click_node(app, 2)
    click_canvas(app, 760, 470)  # empty space cancels instead of adding
    expect(app.locator(".node.sel")).to_have_count(0)
    expect(app.locator("#layer [data-n]")).to_have_count(8)


def test_edit_weight_inline(app: Page):
    app.locator("#layer .wbg").first.click()
    editor = app.get_by_label("Edit edge weight")
    expect(editor).to_be_visible()
    expect(editor).to_have_value("4")
    editor.fill("3")
    editor.press("Enter")
    expect(editor).to_be_hidden()
    expect(app.locator("#layer .wt").first).to_have_text("3")
    app.locator("#step").click()
    for _ in range(14):
        app.locator("#step").click()
    expect(app.locator("#tot")).to_have_text("31")


def test_edit_weight_escape_and_invalid(app: Page):
    wbg = app.locator("#layer .wbg").first
    wbg.click()
    editor = app.get_by_label("Edit edge weight")
    editor.fill("99")
    editor.press("Escape")
    expect(app.locator("#layer .wt").first).to_have_text("4")
    wbg.click()
    editor.fill("0")
    editor.press("Enter")
    expect(app.locator("#toast")).to_have_text("Weights must be whole numbers from 1 to 9999.")
    expect(app.locator("#layer .wt").first).to_have_text("4")


def test_drag_moves_node_without_resetting_run(app: Page):
    app.locator("#step").click()
    app.locator("#step").click()
    x, y = node_center(app, 3)
    app.mouse.move(x, y)
    app.mouse.down()
    tx, ty = canvas_point(app, 650, 470)
    app.mouse.move(tx, ty, steps=8)
    app.mouse.up()
    c = app.locator('[data-n="3"] .nc')
    assert abs(float(c.get_attribute("cx")) - 650) < 2
    assert abs(float(c.get_attribute("cy")) - 470) < 2
    line = app.locator('[data-e="4"] .eline')  # C-D follows the node
    assert line.get_attribute("x2") == c.get_attribute("cx")
    expect(app.locator("#prog")).to_have_text("Step 2 of 15")


def test_drag_clamps_to_canvas(app: Page):
    x, y = node_center(app, 0)
    app.mouse.move(x, y)
    app.mouse.down()
    box = app.locator("#svg").bounding_box()
    app.mouse.move(box["x"] - 100, box["y"] - 100, steps=5)
    app.mouse.up()
    c = app.locator('[data-n="0"] .nc')
    assert float(c.get_attribute("cx")) == 24 and float(c.get_attribute("cy")) == 24


def test_double_click_node_deletes_it_and_its_edges(app: Page):
    x, y = node_center(app, 7)  # H has 6 edges
    app.mouse.dblclick(x, y)
    expect(app.locator("#layer [data-n]")).to_have_count(7)
    expect(app.locator("#layer [data-e]")).to_have_count(7)
    expect(app.locator("#start option")).to_have_count(7)


def test_double_click_edge_deletes_it(app: Page):
    a = node_center(app, 0)
    b = node_center(app, 6)  # A-G
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + (b[1] - a[1]) * 0.2)
    app.mouse.dblclick(*mid)
    expect(app.locator("#layer [data-e]")).to_have_count(12)
    app.get_by_role("tab", name="Edge list").click()
    expect(app.locator("#el")).not_to_contain_text("A G 8")


def test_build_from_edge_list_with_names(app: Page):
    build(app, "Paris Lyon 4\nLyon Nice 3\nParis Nice 9\nBrest")
    expect(app.locator("#toast")).to_have_text("Built a graph with 4 nodes and 3 edges.")
    expect(app.locator("#layer .nt")).to_have_text(["Paris", "Lyon", "Nice", "Brest"])
    expect(app.locator("#start option")).to_have_text(["Paris", "Lyon", "Nice", "Brest"])


def test_build_rejects_empty_list(app: Page):
    build(app, "   \n  ")
    expect(app.locator("#toast")).to_have_class(re.compile("err"))
    expect(app.locator("#toast")).to_have_text("No edges found. Write one edge per line, like 'A B 4'.")
    expect(app.locator("#layer [data-n]")).to_have_count(8)


def test_edge_list_round_trips_canvas_edits(app: Page):
    app.get_by_role("tab", name="Edge list").click()
    text = app.locator("#el").input_value()
    assert text.splitlines()[0] == "A B 4" and len(text.splitlines()) == 13
    app.get_by_role("button", name="Build graph from list").click()
    expect(app.locator("#layer [data-e]")).to_have_count(13)


def test_random_graph_respects_size(app: Page):
    app.get_by_label("Random graph node count").fill("12")
    app.get_by_role("button", name="Random").click()
    expect(app.locator("#layer [data-n]")).to_have_count(12)
    app.get_by_label("Random graph node count").fill("99")
    app.get_by_role("button", name="Random").click()
    expect(app.locator("#layer [data-n]")).to_have_count(30)
    expect(app.get_by_label("Random graph node count")).to_have_value("30")
    # random graphs are always connected: 1 start step + 29 x (frontier, add)
    expect(app.locator("#prog")).to_have_text("Step 0 of 59")
    app.locator("#scrub").fill("59")
    expect(app.locator("#phase")).to_have_text("Finished")


def test_sample_restores_default(app: Page):
    clear(app)
    app.get_by_role("button", name="Sample").click()
    expect(app.locator("#layer [data-n]")).to_have_count(8)
    expect(app.locator("#layer [data-e]")).to_have_count(13)
