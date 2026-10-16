"""Running the algorithm: step, back, play, scrub, keyboard, start node."""

import re

from playwright.sync_api import Page, expect

from conftest import build, click_canvas, step


def test_page_loads_with_sample_graph(app: Page):
    expect(app).to_have_title("Prim's MST Visualizer")
    expect(app.locator("#layer [data-e]")).to_have_count(13)
    expect(app.locator("#start option")).to_have_count(8)
    expect(app.locator("#phase")).to_have_text("Ready")
    expect(app.locator("#status")).to_contain_text("8 nodes, 13 edges")
    expect(app.locator("#api")).to_contain_text("Server connected")
    expect(app.locator("#empty")).to_be_hidden()
    expect(app.locator("#back")).to_be_disabled()
    expect(app.locator("#tot")).to_have_text("0")


def test_stepping_through_sample_builds_mst_of_32(app: Page):
    step(app, 15)
    expect(app.locator("#tot")).to_have_text("32")
    expect(app.locator("#joined")).to_have_text("8/8")
    expect(app.locator("#kept")).to_have_text("7")
    expect(app.locator("#phase")).to_have_text("Finished")
    expect(app.locator("#status")).to_have_text("Done. Every node is connected, with a minimum total weight of 32.")
    expect(app.locator(".eline.mst")).to_have_count(7)
    expect(app.locator(".node.in")).to_have_count(8)
    expect(app.locator("#step")).to_be_disabled()
    expect(app.locator("#log li")).to_have_count(15)
    expect(app.locator("#prog")).to_have_text("Step 15 of 15")
    # Edges inside the tree that were never taken are drawn as skipped.
    expect(app.locator(".eline.ign")).to_have_count(6)


def test_first_step_marks_start_node(app: Page):
    step(app)
    expect(app.locator(".node.in")).to_have_count(1)
    expect(app.locator('[data-n="0"]')).to_have_class(re.compile(r"\bin\b"))
    expect(app.locator("#phase")).to_have_text("Starting")
    expect(app.locator("#log li")).to_have_text(["Start at A: add it to the tree."])


def test_frontier_lists_crossing_edges_cheapest_first(app: Page):
    step(app, 4)  # start, A-B picked, added, frontier from {A, B}
    expect(app.locator("#phase")).to_have_text("Choosing the cheapest edge")
    rows = app.locator("#tb li")
    expect(rows.locator(".who")).to_have_text(["A–G", "B–C", "B–H"])
    expect(rows.locator(".w")).to_have_text(["8", "8", "11"])
    expect(rows.first).to_have_class("pick")
    expect(app.locator(".eline.pick")).to_have_count(1)
    expect(app.locator(".eline.cand")).to_have_count(2)
    expect(app.locator("#status")).to_have_text("3 edges cross out of the tree. The cheapest is A–G, weight 8.")


def test_frontier_empty_between_rounds(app: Page):
    step(app, 3)
    expect(app.locator("#tb")).to_contain_text("Updating after the last edge joined.")


def test_back_steps_and_disables_at_start(app: Page):
    step(app, 5)
    app.locator("#back").click()
    expect(app.locator("#prog")).to_have_text("Step 4 of 15")
    expect(app.locator("#log li")).to_have_count(4)
    for _ in range(4):
        app.locator("#back").click()
    expect(app.locator("#prog")).to_have_text("Step 0 of 15")
    expect(app.locator("#back")).to_be_disabled()
    expect(app.locator("#tot")).to_have_text("0")


def test_scrubber_jumps_to_any_step(app: Page):
    app.locator("#scrub").fill("15")
    expect(app.locator("#tot")).to_have_text("32")
    app.locator("#scrub").fill("7")
    expect(app.locator("#prog")).to_have_text("Step 7 of 15")
    expect(app.locator("#tot")).to_have_text("13")
    app.locator("#scrub").fill("0")
    expect(app.locator("#phase")).to_have_text("Ready")


def test_clicking_timeline_entry_jumps_there(app: Page):
    step(app, 9)
    app.locator('#log li[data-step="2"]').click()
    expect(app.locator("#prog")).to_have_text("Step 3 of 15")
    expect(app.locator("#log li.now")).to_have_text("Added edge A–B and node B. Total = 4.")


def test_play_runs_to_the_end(app: Page):
    app.locator("#spd").fill("10")
    app.get_by_role("button", name="Play").click()
    expect(app.get_by_role("button", name="Pause")).to_be_visible()
    expect(app.locator("#tot")).to_have_text("32", timeout=15000)
    expect(app.get_by_role("button", name="Play")).to_be_visible()
    # Playing again after the end restarts from the beginning.
    app.get_by_role("button", name="Play").click()
    expect(app.locator("#prog")).to_have_text(re.compile(r"Step [1-3] of 15"))
    app.get_by_role("button", name="Pause").click()


def test_pause_stops_progress(app: Page):
    app.locator("#spd").fill("10")
    app.get_by_role("button", name="Play").click()
    expect(app.locator("#prog")).to_have_text(re.compile(r"Step [2-9] of 15"))
    app.get_by_role("button", name="Pause").click()
    held = app.locator("#prog").text_content()
    app.wait_for_timeout(1200)
    expect(app.locator("#prog")).to_have_text(held)


def test_reset_rewinds_but_keeps_graph(app: Page):
    step(app, 6)
    app.get_by_role("button", name="Reset").click()
    expect(app.locator("#prog")).to_have_text("Step 0 of 15")
    expect(app.locator(".node.in")).to_have_count(0)
    expect(app.locator("#layer [data-n]")).to_have_count(8)


def test_changing_start_node_gives_same_total(app: Page):
    step(app, 3)
    app.locator("#start").select_option(label="D")
    expect(app.locator("#prog")).to_have_text("Step 0 of 15")
    step(app, 15)
    expect(app.locator("#log li").first).to_have_text("Start at D: add it to the tree.")
    expect(app.locator("#tot")).to_have_text("32")


def test_keyboard_shortcuts(app: Page):
    app.locator("body").click(position={"x": 5, "y": 5})
    app.keyboard.press("ArrowRight")
    app.keyboard.press("ArrowRight")
    expect(app.locator("#prog")).to_have_text("Step 2 of 15")
    app.keyboard.press("ArrowLeft")
    expect(app.locator("#prog")).to_have_text("Step 1 of 15")
    app.keyboard.press("r")
    expect(app.locator("#prog")).to_have_text("Step 0 of 15")
    app.locator("#spd").fill("10")
    app.locator("body").click(position={"x": 5, "y": 5})
    app.keyboard.press(" ")
    expect(app.get_by_role("button", name="Pause")).to_be_visible()
    app.keyboard.press(" ")
    expect(app.get_by_role("button", name="Play")).to_be_visible()


def test_shortcuts_ignored_while_typing(app: Page):
    app.get_by_role("tab", name="Edge list").click()
    app.locator("#el").press("ArrowRight")
    app.locator("#el").press("r")
    expect(app.locator("#prog")).to_have_text("Step 0 of 15")


def test_disconnected_graph_stops_early(app: Page):
    build(app, "A B 1\nC D 2")
    step(app, 4)
    expect(app.locator("#phase")).to_have_text("Stopped early")
    expect(app.locator("#status")).to_contain_text("graph is disconnected")
    expect(app.locator("#tot")).to_have_text("1")
    expect(app.locator("#joined")).to_have_text("2/4")
    expect(app.locator("#step")).to_be_disabled()


def test_single_node_finishes_immediately(app: Page):
    build(app, "Solo")
    step(app)
    expect(app.locator("#phase")).to_have_text("Finished")
    expect(app.locator("#prog")).to_have_text("Step 1 of 1")


def test_edit_mid_run_resets_trace(app: Page):
    step(app, 5)
    click_canvas(app, 760, 470)
    expect(app.locator("#layer [data-n]")).to_have_count(9)
    expect(app.locator("#prog")).to_have_text("Step 0 of 16")
    expect(app.locator(".node.in")).to_have_count(0)


def test_stepping_does_not_scroll_the_page(app: Page):
    app.evaluate("window.scrollTo(0, 0)")
    step(app, 15)
    assert app.evaluate("window.scrollY") == 0
    # the timeline itself follows the current step
    assert app.evaluate("document.getElementById('log').scrollTop") > 0
