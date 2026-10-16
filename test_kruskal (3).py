"""Kruskal's algorithm mode and switching between algorithms."""

import re

from playwright.sync_api import Page, expect

from conftest import build, step


def use_kruskal(page: Page) -> None:
    page.get_by_role("radio", name="Kruskal's").click()
    expect(page.locator("#prog")).to_have_text("Step 0 of 17")


def test_prim_is_default(app: Page):
    expect(app.get_by_role("radio", name="Prim's")).to_have_attribute("aria-checked", "true")
    expect(app.get_by_role("radio", name="Kruskal's")).to_have_attribute("aria-checked", "false")
    expect(app.locator("#start-wrap")).to_be_visible()


def test_switching_updates_copy_and_controls(app: Page):
    use_kruskal(app)
    expect(app).to_have_title("Kruskal's MST Visualizer")
    expect(app.get_by_role("radio", name="Kruskal's")).to_have_attribute("aria-checked", "true")
    expect(app.locator("#algo-desc")).to_contain_text("from cheapest to most expensive")
    expect(app.locator("#start-wrap")).to_be_hidden()
    expect(app.locator("#leg-cand")).to_be_hidden()
    expect(app.locator("#leg-pick")).to_have_text("Edge being checked")
    expect(app.locator("#queue-title")).to_have_text("Edge queue")
    expect(app.locator("#joined-label")).to_have_text("Trees left")
    expect(app.locator("#joined")).to_have_text("8")
    expect(app.locator("#status")).to_have_text("8 nodes, 13 edges. Press play or step to begin.")


def test_kruskal_full_run_on_sample(app: Page):
    use_kruskal(app)
    step(app, 17)
    expect(app.locator("#tot")).to_have_text("32")
    expect(app.locator("#joined")).to_have_text("1")
    expect(app.locator("#kept")).to_have_text("7")
    expect(app.locator("#phase")).to_have_text("Finished")
    expect(app.locator(".eline.mst")).to_have_count(7)
    expect(app.locator(".eline.ign")).to_have_count(1)  # only C-D was checked and skipped
    expect(app.locator("#step")).to_be_disabled()
    expect(app.locator("#log li").last).to_have_text("Kept A–G. Total = 32. All nodes connected. MST complete.")


def test_sort_step_shows_whole_queue(app: Page):
    use_kruskal(app)
    step(app)
    expect(app.locator("#phase")).to_have_text("Sorting edges")
    expect(app.locator("#status")).to_contain_text("Sort all 13 edges")
    rows = app.locator("#tb li")
    expect(rows.locator(".w")).to_have_text(["1", "2", "4", "4", "6", "7", "7", "8"])
    expect(rows.last).to_have_text("and 5 more")
    expect(app.locator(".eline.cand")).to_have_count(0)  # queue isn't drawn as frontier


def test_consider_then_keep(app: Page):
    use_kruskal(app)
    step(app, 2)
    expect(app.locator("#phase")).to_have_text("Checking the next edge")
    expect(app.locator("#status")).to_have_text("Next cheapest edge is F–G, weight 1. F and G are in different trees.")
    expect(app.locator("#tb li").first).to_have_class("pick")
    expect(app.locator(".eline.pick")).to_have_count(1)
    step(app)
    expect(app.locator("#phase")).to_have_text("Edge kept")
    expect(app.locator(".node.in")).to_have_count(2)
    expect(app.locator("#joined")).to_have_text("7")
    expect(app.locator("#tb li .who").first).to_have_text("C–H")


def test_skip_cycle_edge(app: Page):
    use_kruskal(app)
    step(app, 13)
    expect(app.locator("#phase")).to_have_text("Edge skipped")
    expect(app.locator("#status")).to_have_text("Skipped C–D. It would close a cycle, since C and D are already in one tree.")
    expect(app.locator('[data-e="4"] .eline')).to_have_class(re.compile(r"\bign\b"))


def test_kruskal_disconnected_builds_forest(app: Page):
    use_kruskal(app)
    build(app, "A B 3\nC D 1\nE")
    step(app, 6)
    expect(app.locator("#phase")).to_have_text("Stopped early")
    expect(app.locator("#status")).to_contain_text("disconnected into 3 pieces")
    expect(app.locator("#tot")).to_have_text("4")  # both pieces, unlike Prim
    expect(app.locator("#joined")).to_have_text("3")


def test_both_algorithms_agree_on_random_graphs(app: Page):
    for size in ("6", "15", "25"):
        app.get_by_label("Random graph node count").fill(size)
        app.get_by_role("button", name="Random").click()
        totals = []
        for algo in ("Prim's", "Kruskal's"):
            app.get_by_role("radio", name=algo).click()
            expect(app.locator("#prog")).to_have_text(re.compile(r"Step 0 of \d+"))
            last = app.locator("#scrub").get_attribute("max")
            app.locator("#scrub").fill(last)
            expect(app.locator("#phase")).to_have_text("Finished")
            totals.append(app.locator("#tot").text_content())
        assert totals[0] == totals[1], (size, totals)
        app.get_by_role("radio", name="Prim's").click()


def test_switch_mid_run_restarts(app: Page):
    step(app, 5)
    use_kruskal(app)
    expect(app.locator(".node.in")).to_have_count(0)
    expect(app.locator("#log")).to_contain_text("Steps appear here")


def test_choice_persists_across_reload(app: Page):
    use_kruskal(app)
    app.reload()
    expect(app.get_by_role("radio", name="Kruskal's")).to_have_attribute("aria-checked", "true")
    expect(app.locator("#prog")).to_have_text("Step 0 of 17")


def test_arrow_keys_switch_algorithm_without_stepping(app: Page):
    app.get_by_role("radio", name="Prim's").focus()
    app.keyboard.press("ArrowRight")
    expect(app.get_by_role("radio", name="Kruskal's")).to_be_focused()
    expect(app.get_by_role("radio", name="Kruskal's")).to_have_attribute("aria-checked", "true")
    expect(app.locator("#prog")).to_have_text("Step 0 of 17")
    app.keyboard.press("ArrowLeft")
    expect(app.get_by_role("radio", name="Prim's")).to_have_attribute("aria-checked", "true")
    expect(app.locator("#prog")).to_have_text("Step 0 of 15")


def test_sends_algorithm_to_backend(app: Page):
    with app.expect_request("**/api/mst") as req:
        app.get_by_role("radio", name="Kruskal's").click()
    assert req.value.post_data_json["algorithm"] == "kruskal"
