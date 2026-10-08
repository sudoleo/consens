"""The app sidebar's width follows a drag on its right edge (sidebar-resize.js).

Real mouse input in Chromium: the handle sits on the edge, everything beside
the sidebar (reading column, toggle, fixed footer) follows, the width is
remembered across a reload, and the narrow overlay sidebar keeps its own width.
"""

from playwright.sync_api import expect


def _geometry(page):
    return page.evaluate(
        """() => {
          const box = el => document.querySelector(el).getBoundingClientRect();
          const sidebar = box('.sidebar'), container = box('.container');
          const handle = document.getElementById('sidebarResizer');
          return {
            sidebar: sidebar.width,
            handleLeft: handle.getBoundingClientRect().left,
            handleWidth: handle.getBoundingClientRect().width,
            handleShown: getComputedStyle(handle).display !== 'none',
            // Reading column centred in the canvas beside the sidebar.
            gapLeft: container.left - sidebar.right,
            gapRight: document.documentElement.clientWidth - container.right,
            toggleRight: box('#sidebarToggleInner').right,
            settingsRight: box('.sidebar-settings').right,
            valuenow: Number(handle.getAttribute('aria-valuenow')),
            stored: localStorage.getItem('sidebar_width'),
          };
        }"""
    )


def _open_sidebar(page):
    if page.evaluate("() => document.querySelector('.sidebar').classList.contains('collapsed')"):
        page.locator(".app-nav-float .sidebar-toggle").click()
    page.wait_for_function("() => getComputedStyle(document.getElementById('sidebarResizer')).display !== 'none'")
    # Let the open transition settle before measuring.
    page.wait_for_timeout(400)


def _drag(page, dx):
    handle = page.locator("#sidebarResizer").bounding_box()
    x, y = handle["x"] + handle["width"] / 2, handle["y"] + 300
    page.mouse.move(x, y)
    page.mouse.down()
    # Several steps, like a real hand: every move is applied at once.
    for step in range(1, 6):
        page.mouse.move(x + dx * step / 5, y)
    assert page.evaluate("() => document.body.classList.contains('is-resizing-sidebar')")
    page.mouse.up()


def test_dragging_the_edge_resizes_the_sidebar_and_everything_beside_it(app_page, get_console_errors):
    page = app_page
    _open_sidebar(page)
    before = _geometry(page)
    assert before["sidebar"] == 260 and before["handleShown"]
    assert before["handleLeft"] < 260 < before["handleLeft"] + before["handleWidth"]
    expect(page.locator("#sidebarResizer")).to_have_attribute("role", "separator")

    # The column's offset from the canvas centre before the drag (a reserved
    # scrollbar gutter makes it slightly asymmetric); it must stay the same.
    skew = before["gapLeft"] - before["gapRight"]
    _drag(page, 120)
    after = _geometry(page)
    assert after["sidebar"] == 380 and after["valuenow"] == 380 and after["stored"] == "380"
    assert not page.evaluate("() => document.body.classList.contains('is-resizing-sidebar')")
    # The column stays centred beside the wider sidebar; the toggle and the
    # footer follow the edge.
    page.wait_for_timeout(400)
    after = _geometry(page)
    assert abs((after["gapLeft"] - after["gapRight"]) - skew) <= 2
    assert 380 - 20 <= after["toggleRight"] <= 380
    assert 380 - 20 <= after["settingsRight"] <= 380

    # Remembered across a reload, already on the first paint.
    page.reload(wait_until="domcontentloaded")
    assert page.evaluate("() => document.querySelector('.sidebar').getBoundingClientRect().width") == 380

    # Limits: never wider than 480 px (40 % of a 1440 px window is more),
    # never narrower than 200 px.
    _open_sidebar(page)
    _drag(page, 600)
    assert _geometry(page)["sidebar"] == 480
    _drag(page, -800)
    assert _geometry(page)["sidebar"] == 200

    # Double-click restores the default and forgets the stored width.
    page.locator("#sidebarResizer").dblclick()
    reset = _geometry(page)
    assert reset["sidebar"] == 260 and reset["stored"] is None
    assert get_console_errors() == []


def test_keyboard_resizing_and_collapsed_or_narrow_sidebars(app_page):
    page = app_page
    _open_sidebar(page)
    handle = page.locator("#sidebarResizer")
    handle.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Shift+ArrowRight")
    assert _geometry(page)["sidebar"] == 310
    page.keyboard.press("ArrowLeft")
    assert _geometry(page)["sidebar"] == 300
    page.keyboard.press("End")
    assert _geometry(page)["sidebar"] == 480
    page.keyboard.press("Home")
    assert _geometry(page)["sidebar"] == 200
    page.keyboard.press("ArrowRight")
    assert _geometry(page)["stored"] == "210"

    # A collapsed sidebar has no handle.
    page.locator("#sidebarToggleInner").click()
    page.wait_for_function("() => document.querySelector('.sidebar').classList.contains('collapsed')")
    expect(handle).to_be_hidden()
    page.locator(".app-nav-float .sidebar-toggle").click()
    expect(handle).to_be_visible()
    assert _geometry(page)["sidebar"] == 210

    # A smaller window caps the chosen width without forgetting it; the
    # narrow overlay sidebar keeps its own width and has no handle.
    handle.focus()
    page.keyboard.press("End")
    assert _geometry(page)["stored"] == "480"
    page.set_viewport_size({"width": 1150, "height": 900})
    page.wait_for_timeout(300)
    assert _geometry(page)["sidebar"] == 460  # 40 % of 1150
    assert _geometry(page)["stored"] == "480"
    page.set_viewport_size({"width": 1000, "height": 900})
    page.wait_for_timeout(300)
    assert not _geometry(page)["handleShown"]
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(300)
    _open_sidebar(page)
    assert _geometry(page)["sidebar"] == 480
