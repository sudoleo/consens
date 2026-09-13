"""Mobile reading navigation in the real shell, using isolated fixture answers."""
import re

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import reader_screenshot, seed_insights


def seed_long_answer(page):
    seed_insights(page)
    page.evaluate("""() => {
      const ctx = App.runRegistry.visible();
      const paragraph = 'Viele Rennradfahrer leben in der Region rund um Monaco. '
        + 'Die Strecken führen über La Turbie, Èze und Menton. '
        + 'An der Küste und in der Stadt sollte man wegen des Verkehrs vorsichtig sein.';
      ctx.consensus.text = Array.from({length:18}, () => paragraph).join('\\n\\n');
      ctx.consensus.completedTurn.consensus = ctx.consensus.text;
      App.runRegistry.renderVisible();
      window.scrollTo(0, 0);
    }""")


@pytest.mark.parametrize('width,theme', [(320, 'light'), (390, 'dark'), (768, 'light'), (1099, 'dark')])
def test_mobile_menu_has_opaque_header_and_yields_while_reading(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        seed_long_answer(page)
        header = page.locator('.app-mobile-header')
        menu = page.get_by_role('button', name='Open sidebar', exact=True)
        expect(menu).to_be_visible()
        expect(menu).to_have_attribute('aria-controls', 'appSidebar')
        assert menu.bounding_box()['width'] >= 44
        assert menu.bounding_box()['height'] >= 44
        assert header.bounding_box()['height'] == 56
        expect(header).to_have_css('background-color', 'rgb(25, 26, 28)' if theme == 'dark' else 'rgb(250, 250, 250)')
        expect(header.locator('.brand-float-title')).to_be_visible()
        assert page.locator('.thread-history-turn').first.bounding_box()['y'] >= header.bounding_box()['height']

        page.evaluate('window.scrollTo(0, 900)')
        expect(header).to_be_hidden()
        page.evaluate('window.scrollBy(0, -100)')
        expect(menu).to_be_visible()
        page.wait_for_function('() => Math.abs(document.querySelector(".app-mobile-header").getBoundingClientRect().top) < 1')
        assert menu.evaluate('el => {const r=el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        reader_screenshot(page, f'mobile-header-reading-{width}-{theme}')

        menu.click()
        expect(page.locator('#appSidebar')).to_have_class(re.compile(r'\bactive\b'))
        expect(header).to_be_hidden()
        expect(page.locator('#sidebarToggleInner')).to_be_visible()
        page.locator('#sidebarToggleInner').click()
        expect(menu).to_be_visible()
        expect(menu).to_be_focused()
        expect(page.locator('#appSidebar')).to_have_attribute('inert', '')

        page.emulate_media(reduced_motion='reduce')
        page.evaluate('window.scrollBy(0, 100)')
        expect(header).to_be_hidden()
        page.keyboard.press('Tab')
        expect(menu).to_be_visible()
        assert float(header.evaluate('el => getComputedStyle(el).transitionDuration.split(",")[0].replace("s", "")')) < .01
    finally:
        context.close()


@pytest.mark.parametrize('width', [320, 640])
def test_guest_navigation_fits_and_login_still_opens(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None)
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        header = page.locator('.app-mobile-header')
        menu = page.locator('#toggleSidebarButton')
        switch = page.locator('#viewSwitch')
        auth = page.locator('#authTopActions')
        expect(menu).to_be_visible()
        expect(switch).to_be_visible()
        expect(auth).to_be_visible()
        bounds = [item.bounding_box() for item in [menu, switch, auth]]
        assert bounds[0]['x'] + bounds[0]['width'] <= bounds[1]['x']
        assert bounds[1]['x'] + bounds[1]['width'] <= bounds[2]['x']
        assert bounds[2]['x'] + bounds[2]['width'] <= width
        assert all(item['y'] >= 0 and item['y'] + item['height'] <= header.bounding_box()['height'] for item in bounds)
        reader_screenshot(page, f'mobile-header-guest-{width}')
        page.locator('#authTopLoginBtn').click()
        expect(page.locator('#loginModal')).to_be_visible()
    finally:
        context.close()


def test_watch_navigation_uses_the_same_mobile_surface(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, path='/app/watches')
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        header = page.locator('.app-mobile-header')
        expect(page.locator('#watchDashboard')).to_be_visible()
        expect(page.locator('#viewSwitch')).to_be_visible()
        expect(page.locator('#toggleSidebarButton')).to_be_hidden()
        page.evaluate("""() => {
          const text=document.createElement('p'); text.textContent='A watched question. '.repeat(300);
          document.getElementById('watchDashBody').append(text);
          document.getElementById('watchDashboard').scrollTop=500;
        }""")
        expect(header).to_be_hidden()
        page.locator('#watchDashboard').evaluate('el => el.scrollTop -= 80')
        expect(header).to_be_visible()
        page.locator('#viewSwitchConsensus').click()
        expect(page.locator('#watchDashboard')).to_be_hidden()
        expect(page.locator('#toggleSidebarButton')).to_be_visible()
    finally:
        context.close()


def test_desktop_sidebar_controls_keep_their_original_layout(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': 1440, 'height': 900})
        expect(page.locator('.app-mobile-header')).to_have_css('display', 'contents')
        expect(page.locator('#toggleSidebarButton')).to_be_hidden()
        page.locator('#sidebarToggleInner').click()
        expect(page.locator('#toggleSidebarButton')).to_be_visible()
        expect(page.locator('.app-nav-float')).to_have_css('position', 'fixed')
        page.locator('#toggleSidebarButton').click()
        expect(page.locator('#sidebarToggleInner')).to_be_visible()
    finally:
        context.close()
