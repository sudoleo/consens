"""Mobile reading navigation in the real shell, using isolated fixture answers."""
import re

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _json, _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import reader_screenshot, seed_insights
from test_agent_chat_frontend import CATALOG


def seed_long_answer(page):
    paragraph = ('Viele Rennradfahrer leben in der Region rund um Monaco. '
                 'Die Strecken führen über La Turbie, Èze und Menton. '
                 'An der Küste und in der Stadt sollte man wegen des Verkehrs vorsichtig sein.')
    seed_insights(page, consensus='\n\n'.join([paragraph] * 18))
    to_top(page)


def to_top(page):
    """An opened chat holds its newest question in place until the reader
    scrolls (chat-scroll.js interrupt); scroll to the top as a reader does."""
    page.evaluate("() => { window.dispatchEvent(new WheelEvent('wheel', {deltaY: -1})); window.scrollTo(0, 0); }")
    page.wait_for_function("() => scrollY === 0")


def with_agent_access(page):
    """Every signed-in account has Agent (users.py); its start screen is the
    hero. Without access an account starts in Compare."""
    page.route('**/user_status', lambda route: _json(route, {'tier': 'free', 'is_pro': False, 'agent_access': True}))
    page.route('**/agent/models', lambda route: _json(route, CATALOG))


# The composer is the raised field (--field = --well, Apple-Audit G8).
COMPOSER_SURFACE = {'light': 'rgb(255, 255, 255)', 'dark': 'rgb(38, 40, 43)'}

# iPhone Safari (iOS 26; WebKit LocalFrameView::fixedContainerEdges) paints
# the strips behind its status bar and bottom bar: it hit-tests the middle of
# each edge 4px in, ignoring pointer-events, and walks up to the first fixed or
# sticky box about as wide as the viewport. A box that is not also about as
# tall gives the opaque background met on the way (boxes over 10px tall).
# Without one Safari measures pixels and keeps the result; a viewport-sized
# box or a sidebar keeps the colour from before, so a theme switch left the
# old colour (white under the dark app). Only a page colour counts as fixed.
SAFARI_BAR_COLOURS = """() => {
  const style = document.createElement('style');
  style.textContent = '*,*::before,*::after{pointer-events:auto!important}';
  document.head.append(style);
  try {
    const w = document.documentElement.clientWidth, h = innerHeight;
    const read = y => {
      const colours = new Set();
      for (let el = document.elementFromPoint(w / 2, y); el; el = el.parentElement) {
        const cs = getComputedStyle(el), box = el.getBoundingClientRect();
        if (cs.visibility === 'hidden' || Number(cs.opacity) < 0.05) continue;
        const wide = box.width >= 0.9 * (w - 8), tall = box.height >= 0.9 * (h - 8);
        if (wide && box.height > 10 && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') colours.add(cs.backgroundColor);
        if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
        if (tall) return 'kept from before (' + el.className + ')';
        if (!wide) continue;
        return colours.size === 1 ? [...colours][0] : [...colours].join(' + ') || 'measured by Safari';
      }
      return 'no fixed box';
    };
    return {top: read(4), bottom: read(innerHeight - 5), page: getComputedStyle(document.body).backgroundColor};
  } finally {
    style.remove();
  }
}"""


@pytest.mark.parametrize('width,theme', [(320, 'light'), (390, 'dark'), (768, 'light'), (1099, 'dark')])
def test_mobile_islands_float_over_the_thread_and_yield_while_reading(browser, phase4_server, width, theme):
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
        # No bar: the menu and the actions are bare glyphs, as on the
        # desktop (Apple-Audit G17); the strip between them belongs to the
        # thread.
        expect(header).to_have_css('background-color', 'rgba(0, 0, 0, 0)')
        islands = page.locator('#toggleSidebarButton, #mobileConversationActions')
        for island in islands.all():
            expect(island).to_have_css('background-color', 'rgba(0, 0, 0, 0)')
            expect(island).to_have_css('box-shadow', 'none')
        expect(menu).to_have_css('border-top-left-radius', '50%')
        expect(page.locator('#mobileConversationActions')).to_have_css('border-top-left-radius', '999px')
        expect(header.locator('.brand-float')).to_be_hidden()
        expect(header.locator('#mobileNewRunButton')).to_be_visible()
        expect(header.locator('#mobileNewRunButton')).to_have_css('background-color', 'rgba(0, 0, 0, 0)')
        assert header.locator('#mobileNewRunButton svg').bounding_box()['width']>=20
        # Share moved into the ... menu; New chat, Watch and the menu stay.
        expect(header.locator('#consensusShareButton')).to_be_hidden()
        expect(header.locator('#consensusWatchButton')).to_be_visible()
        toggle = header.locator('.consensus-actions-toggle')
        expect(toggle).to_be_visible()
        expect(toggle).to_have_attribute('aria-label', 'Share, copy and cite')
        expect(toggle.locator('.more-toggle-icon')).to_be_visible()
        expect(toggle.locator('.quote-toggle-icon')).to_be_hidden()
        expect(page.locator('#runProvenance .consensus-footer-actions')).to_have_count(0)
        assert page.evaluate('() => !document.querySelector(".app-mobile-header").contains(document.elementFromPoint(innerWidth / 2 - 30, 28))')
        buttons=header.locator('button:visible').all()
        bounds=[button.bounding_box() for button in buttons]
        assert len(bounds)==4
        assert all(box['width']>=44 and box['height']>=44 for box in bounds)
        assert all(a['x']+a['width']<=b['x']+.5 for a,b in zip(bounds,bounds[1:]))
        assert bounds[-1]['x']+bounds[-1]['width']<=width
        # From the top, the thread starts below the islands.
        to_top(page)
        assert page.locator('.thread-history-turn').first.bounding_box()['y'] >= header.bounding_box()['height']
        # The collapsed composer is a pill of the same material.
        page.wait_for_function("() => document.body.classList.contains('composer-collapsed') && !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        composer = page.locator('.chat-input-container')
        expect(composer).to_have_css('border-top-left-radius', '25px')
        expect(composer).to_have_css('background-color', COMPOSER_SURFACE[theme])
        assert composer.bounding_box()['height'] <= 52

        fade = "() => getComputedStyle(document.querySelector('.app-mobile-header'), '::before').opacity"
        assert page.evaluate(fade) == '0'
        page.evaluate('window.scrollTo(0, 900)')
        expect(header).to_be_hidden()
        page.evaluate('window.scrollBy(0, -100)')
        expect(menu).to_be_visible()
        page.wait_for_function('() => Math.abs(document.querySelector(".app-mobile-header").getBoundingClientRect().top) < 1')
        page.wait_for_function(f"() => ({fade})() === '1'")
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


@pytest.mark.parametrize('width,theme', [(320, 'light'), (390, 'dark'), (640, 'light'), (1099, 'dark')])
def test_guest_navigation_fits_and_auth_dialogs_open(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        header = page.locator('.app-mobile-header')
        menu = page.locator('#toggleSidebarButton')
        switch = page.locator('#viewSwitch')
        auth = page.locator('#authTopActions')
        login = page.locator('#authTopLoginBtn')
        signup = page.locator('#authTopSignupBtn')
        expect(menu).to_be_visible()
        expect(page.locator('#mobileSidebarViews #viewSwitch')).to_have_count(1)
        expect(switch).not_to_be_in_viewport()
        expect(auth).to_be_visible()
        expect(login).to_be_visible()
        expect(signup).to_be_visible()
        expect(page.locator('#mobileNewRunButton')).to_be_hidden()
        expect(header.locator('#consensusFooterActions')).to_be_hidden()
        bounds = [item.bounding_box() for item in [menu, login, signup]]
        assert bounds[0]['x'] + bounds[0]['width'] <= bounds[1]['x']
        assert bounds[1]['x'] + bounds[1]['width'] <= bounds[2]['x']
        assert bounds[2]['x'] + bounds[2]['width'] <= width
        assert all(item['y'] >= 0 and item['y'] + item['height'] <= header.bounding_box()['height'] for item in bounds)
        assert all(item['height'] >= 44 and item['width'] >= 44 for item in bounds)
        reader_screenshot(page, f'mobile-header-guest-{width}')
        # A guest opens no saved chat and, since 2026-10-25, runs no
        # Consensus demo: no answer actions join the auth buttons here.
        signup.click()
        expect(page.locator('#loginModal')).to_be_visible()
        expect(page.locator('#loginForm')).to_have_attribute('data-mode', 'register')
        page.keyboard.press('Escape')
        expect(signup).to_be_focused()
        login.click()
        expect(page.locator('#loginModal')).to_be_visible()
        expect(page.locator('#loginForm')).to_have_attribute('data-mode', 'login')
        page.keyboard.press('Escape')
        expect(login).to_be_focused()
        page.evaluate("() => window.__switchE2EUser('account-a')")
        expect(auth).to_be_hidden()
        expect(page.locator('#mobileNewRunButton')).to_be_visible()
        page.evaluate('() => window.__switchE2EUser(null)')
        expect(signup).to_be_visible()
        expect(page.locator('#mobileNewRunButton')).to_be_hidden()
    finally:
        context.close()


@pytest.mark.parametrize('new_chat', [False, True])
def test_watch_navigation_uses_the_same_mobile_surface(browser, phase4_server, new_chat):
    context, page = _real_firebase_page(browser, phase4_server,
        initial_uid='account-a' if new_chat else None, path='/app/watches')
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        header = page.locator('.app-mobile-header')
        expect(page.locator('#watchDashboard')).to_be_visible()
        # The page cancels exactly the body's 6px phone sides: it starts at
        # the left edge and never scrolls sideways (a11y audit P8).
        assert page.evaluate("document.getElementById('watchDashboard').getBoundingClientRect().left") == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        expect(page.locator('#mobileSidebarViews #viewSwitch')).to_have_count(1)
        expect(page.locator('#viewSwitch')).not_to_be_in_viewport()
        expect(page.locator('#toggleSidebarButton')).to_be_visible()
        page.evaluate("""() => {
          const text=document.createElement('p'); text.textContent='A watched question. '.repeat(300);
          document.getElementById('watchDashBody').append(text);
          window.scrollTo(0, 500);
        }""")
        # Watches scroll the document like every page (F14).
        expect(header).to_be_hidden()
        page.evaluate('window.scrollBy(0, -80)')
        expect(header).to_be_visible()
        if new_chat:
            page.locator('#mobileNewRunButton').click()
            expect(page.locator('#questionInput')).to_be_focused()
        else:
            page.locator('#toggleSidebarButton').click()
            expect(page.locator('#mobileSidebarViews #viewSwitch')).to_be_visible()
            page.wait_for_function('() => document.getElementById("appSidebar").getBoundingClientRect().left >= -.5')
            reader_screenshot(page, 'mobile-topbar-sidebar-watches')
            # The drawer shows Watches as a row, the Chat half of the switch
            # is gone there: back to chat is New chat, as in every chat app.
            expect(page.locator('#viewSwitchWatches')).to_have_class(re.compile(r'\bis-active\b'))
            expect(page.locator('#mobileSidebarViews #viewSwitchConsensus')).to_be_hidden()
            page.locator('#newRunButton').click()
        expect(page.locator('#watchDashboard')).to_be_hidden()
        expect(page.locator('#toggleSidebarButton')).to_be_visible()
    finally:
        context.close()


@pytest.mark.parametrize('width', [390, 1440])
def test_watches_take_the_place_of_an_open_chat(browser, phase4_server, width):
    # In a chat shell.css shows the column as flex: Watches hung below the
    # answer, and on the phone the menu's Watches seemed to do nothing.
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        seed_long_answer(page)
        expect(page.locator('body')).not_to_have_class(re.compile(r'\bis-hero\b'))
        page.evaluate('window.scrollTo(0, 600)')
        if width < 1100:
            # Reading down hides the menu island; a little way back shows it.
            page.evaluate('window.scrollBy(0, -80)')
            expect(page.locator('.app-mobile-header')).to_be_visible()
            page.locator('#toggleSidebarButton').click()
            page.locator('#mobileSidebarViews #viewSwitchWatches').click()
        else:
            page.evaluate('window.openWatchDashboard()')
        expect(page.locator('#watchDashboard')).to_be_visible()
        expect(page.locator('.container')).to_be_hidden()
        page.wait_for_function("() => document.getElementById('watchDashboard').getBoundingClientRect().top <= 0")
        page.go_back()
        expect(page.locator('#watchDashboard')).to_be_hidden()
        expect(page.locator('.container')).to_be_visible()
    finally:
        context.close()


def test_open_mobile_sidebar_survives_the_keyboard_resize(browser, phase4_server):
    # Chrome on Android resizes the layout viewport when the keyboard opens
    # (interactive-widget=resizes-content); typing in the chat search must not
    # snap the sidebar shut. Only crossing the overlay/push breakpoint resets it.
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        sidebar = page.locator('#appSidebar')
        page.locator('#toggleSidebarButton').click()
        expect(sidebar).to_have_class(re.compile(r'\bactive\b'))
        page.set_viewport_size({'width': 390, 'height': 420})
        page.wait_for_timeout(100)
        expect(sidebar).to_have_class(re.compile(r'\bactive\b'))
        page.set_viewport_size({'width': 844, 'height': 390})
        page.wait_for_timeout(100)
        expect(sidebar).to_have_class(re.compile(r'\bactive\b'))
        page.set_viewport_size({'width': 1440, 'height': 900})
        expect(sidebar).not_to_have_class(re.compile(r'\bactive\b'))
    finally:
        context.close()


def test_touch_fields_are_large_enough_that_ios_does_not_zoom(browser, phase4_server):
    # iOS Safari zooms into any focused field below 16px and stays zoomed.
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True)
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        assert page.evaluate("matchMedia('(hover: none) and (pointer: coarse)').matches")
        sizes = page.evaluate("""() => ['#chatSearch', '#questionInput', '#feedbackForm textarea', '#feedbackForm input[type=email]']
          .map(selector => document.querySelector(selector)).filter(Boolean)
          .map(el => parseFloat(getComputedStyle(el).fontSize))""")
        assert len(sizes) >= 2 and min(sizes) >= 16, sizes
    finally:
        context.close()
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': 1280, 'height': 820})
        # A mouse keeps the compact sidebar search.
        assert page.evaluate("parseFloat(getComputedStyle(document.getElementById('chatSearch')).fontSize)") < 16
    finally:
        context.close()


def test_menu_island_carries_the_watches_hint_until_watches_opens(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('theme','light');localStorage.setItem('consensio.watchViewSwitchHint.seen.v1','true')")
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        dot = "() => getComputedStyle(document.getElementById('toggleSidebarButton'), '::after').content"
        assert page.evaluate(dot) == 'none'
        page.evaluate("document.getElementById('viewSwitchWatches').classList.add('has-watch-pulse')")
        assert page.evaluate(dot) != 'none'
        assert page.evaluate("getComputedStyle(document.getElementById('toggleSidebarButton'), '::after').backgroundColor") \
            == 'rgb(33, 120, 99)'
        page.locator('#toggleSidebarButton').click()
        expect(page.locator('#mobileSidebarViews #viewSwitchWatches')).to_be_visible()
        assert page.evaluate("getComputedStyle(document.getElementById('viewSwitchWatches'), '::after').content") != 'none'
        # Popovers of the islands sit above the fade but never above the
        # open sidebar that covers the islands.
        page.evaluate("""() => { const probe = document.createElement('span');
          probe.className = 'watch-feature-nudge'; probe.id = 'nudgeProbe'; probe.textContent = 'Keep this answer current';
          document.body.append(probe); }""")
        expect(page.locator('#nudgeProbe')).to_be_hidden()
        page.evaluate("document.getElementById('nudgeProbe').remove()")
        reader_screenshot(page, 'mobile-sidebar-watches-hint')
        page.locator('#viewSwitchWatches').click()
        expect(page.locator('#watchDashboard')).to_be_visible()
        assert page.evaluate(dot) == 'none'
    finally:
        context.close()


@pytest.mark.parametrize('width', [390, 1440])
def test_one_line_thread_composer_is_a_pill(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        composer = page.locator('.chat-input-container')
        # The start screen keeps its box.
        expect(composer).to_have_css('border-top-left-radius', '20px')
        seed_long_answer(page)
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        expect(composer).to_have_css('border-top-left-radius', '25px')
        page.wait_for_function("() => !document.getAnimations().some(animation => animation.playState === 'running')")
        box = composer.bounding_box()
        attach = page.locator('#attachTrigger').bounding_box()
        # Its ends are concentric with (+): the same 7px all round.
        assert abs((attach['x'] - box['x']) - (attach['y'] - box['y'])) <= 1
        assert box['height'] <= 52
        reader_screenshot(page, f'thread-composer-pill-{width}')
        if width >= 1100:
            page.locator('#questionInput').fill('first line\nsecond line\nthird line')
            expect(composer).to_have_class(re.compile(r'\bis-multiline\b'))
            expect(composer).to_have_css('border-top-left-radius', '20px')
        else:
            page.locator('#questionInput').click()
            expect(page.locator('body')).not_to_have_class(re.compile(r'\bcomposer-collapsed\b'))
            page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
            expect(composer).to_have_css('border-top-left-radius', '20px')
    finally:
        context.close()


def test_desktop_sidebar_controls_keep_their_original_layout(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': 1440, 'height': 900})
        expect(page.locator('.app-mobile-header')).to_have_css('display', 'contents')
        expect(page.locator('#mobileNewRunButton')).to_be_hidden()
        expect(page.locator('#runProvenance #consensusFooterActions')).to_have_count(1)
        expect(page.locator('#toggleSidebarButton')).to_be_hidden()
        page.locator('#sidebarToggleInner').click()
        expect(page.locator('#toggleSidebarButton')).to_be_visible()
        expect(page.locator('.app-nav-float')).to_have_css('position', 'fixed')
        page.locator('#toggleSidebarButton').click()
        expect(page.locator('#sidebarToggleInner')).to_be_visible()
    finally:
        context.close()


def test_mobile_actions_keep_dialogs_focus_and_new_chat_behavior(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, before_goto=with_agent_access)
    try:
        page.set_viewport_size({'width':390,'height':820})
        seed_insights(page)
        header=page.locator('.app-mobile-header')
        cite=header.locator('.consensus-actions-toggle')
        menu=page.locator('#consensusActionsMenuGlobal')
        expect(header.locator('#consensusShareButton')).to_be_hidden()
        # Share lives in the ... menu and opens the same dialog; focus comes
        # back to the toggle the way it went.
        cite.click()
        share_item=menu.get_by_role('menuitem', name='Share publicly')
        expect(share_item).to_be_visible()
        assert menu.get_by_role('menuitem').all()[0].text_content().strip() == 'Share publicly'
        share_item.click()
        expect(menu).to_be_hidden()
        expect(page.locator('#shareModal')).to_be_visible()
        expect(page.locator('#shareModal')).to_have_class(re.compile('is-share-dialog'))
        page.keyboard.press('Escape')
        expect(cite).to_be_focused()
        watch=header.locator('#consensusWatchButton')
        watch.click()
        expect(page.locator('#shareModal')).to_be_visible()
        expect(page.locator('#shareModal')).to_have_class(re.compile('is-watch-dialog'))
        page.keyboard.press('Escape')
        expect(watch).to_be_focused()
        cite.click()
        expect(menu).to_be_visible()
        assert menu.bounding_box()['y']>=cite.bounding_box()['y']+cite.bounding_box()['height']
        assert menu.bounding_box()['x']+menu.bounding_box()['width']<=390
        # The menu opens over the fade beneath the islands, not under it.
        assert share_item.evaluate('el => {const r=el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}')
        reader_screenshot(page,'mobile-topbar-cite')
        page.keyboard.press('Escape')
        expect(menu).to_be_hidden()
        expect(cite).to_be_focused()
        page.evaluate('window.__mobileActions=document.getElementById("consensusFooterActions")')
        page.set_viewport_size({'width':1440,'height':900})
        footer_share=page.locator('#runProvenance #consensusShareButton')
        expect(footer_share).to_be_visible()
        # The footer keeps its own Share and "Cite"; the menu does not repeat it.
        desktop_cite=page.locator('#runProvenance .consensus-actions-toggle')
        expect(desktop_cite).to_have_attribute('aria-label', 'Citation and copy options')
        desktop_cite.click()
        expect(menu).to_be_visible()
        expect(share_item).to_be_hidden()
        page.keyboard.press('Escape')
        page.set_viewport_size({'width':390,'height':820})
        expect(cite).to_be_visible()
        assert page.evaluate('__mobileActions===document.getElementById("consensusFooterActions")')
        page.evaluate('window.__previousMobileRun=App.runRegistry.visible()')
        header.locator('#mobileNewRunButton').click()
        expect(page.locator('body')).to_have_class(re.compile(r'\bis-hero\b'))
        expect(page.locator('#questionInput')).to_have_value('')
        expect(page.locator('#questionInput')).to_be_focused()
        expect(header.locator('#consensusFooterActions')).to_be_hidden()
        assert page.evaluate('App.runRegistry.visible() === null')
        page.wait_for_function('() => {const r=document.querySelector(".chat-input-container").getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth+1;}')
        page.wait_for_function('() => [document.querySelector(".container"),document.querySelector(".input-section")].every(el => !el.getAnimations().some(animation => animation.playState === "running"))')
        reader_screenshot(page,'mobile-topbar-new-chat')
    finally:
        context.close()


# Safari on iOS keeps the layout viewport under the keyboard and only shrinks
# and pans the visual viewport. Chromium cannot open a virtual keyboard, so
# the test stands in a visual viewport that reports what Safari reports.
FAKE_VISUAL_VIEWPORT = """(() => {
  const viewport = new EventTarget();
  Object.assign(viewport, {offsetTop: 0, offsetLeft: 0, pageTop: 0, pageLeft: 0, scale: 1, width: 390, height: 820});
  Object.defineProperty(window, 'visualViewport', {configurable: true, get: () => viewport});
  window.__keyboard = (height, offsetTop = 0, event = 'resize') => {
    viewport.height = height; viewport.offsetTop = offsetTop;
    viewport.dispatchEvent(new Event(event));
  };
})();"""


def test_mobile_composer_hangs_from_the_keyboard_edge(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True, init_script=FAKE_VISUAL_VIEWPORT)
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        seed_long_answer(page)
        settle = "() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')"
        page.wait_for_function(settle)
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 820) <= 1")

        page.locator('#questionInput').tap()
        expect(page.locator('#questionInput')).to_be_focused()
        page.evaluate('() => window.__keyboard(420)')
        expect(page.locator('body')).to_have_class(re.compile(r'\bkeyboard-open\b'))
        page.wait_for_function(settle)
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 420) <= 1")
        # Every line above the keyboard belongs to the answer: the note waits.
        expect(page.locator('.input-section .app-footer')).to_be_hidden()
        # Expanded, it is still the phone's one row: (+), models, Send.
        rows = [page.locator(sel).bounding_box() for sel in ('#attachTrigger', '.composer-models .model-picker-display:visible', '.chat-input-container > .input-actions-container')]
        centers = [box['y'] + box['height'] / 2 for box in rows]
        assert max(centers) - min(centers) <= 1
        reader_screenshot(page, 'mobile-composer-keyboard')

        # Safari pans the visual viewport within the layout viewport.
        page.evaluate("() => window.__keyboard(420, 140, 'scroll')")
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 560) <= 1")

        # Pinch zoom also shrinks the visual viewport; that is no keyboard.
        page.evaluate("() => { visualViewport.scale = 2; window.__keyboard(410, 0); }")
        expect(page.locator('body')).not_to_have_class(re.compile(r'\bkeyboard-open\b'))
        page.evaluate("() => { visualViewport.scale = 1; window.__keyboard(420, 0); }")
        expect(page.locator('body')).to_have_class(re.compile(r'\bkeyboard-open\b'))

        # Keyboard closed: back on the bottom edge, the note returns.
        page.evaluate('() => { document.activeElement.blur(); window.__keyboard(820, 0); }')
        expect(page.locator('body')).not_to_have_class(re.compile(r'\bkeyboard-open\b'))
        page.wait_for_function(settle)
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 820) <= 1")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--keyboard-edge')") == ''
    finally:
        context.close()


def test_mobile_composer_rises_with_a_known_keyboard_before_safari_reports_it(browser, phase4_server):
    """F9: Safari reports the keyboard once it stands. A height this device
    reported before moves the composer up with the keyboard at the tap and
    down with it when the field is left; the report only corrects."""
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True, init_script=FAKE_VISUAL_VIEWPORT)
    try:
        page.set_viewport_size({'width': 390, 'height': 820})
        seed_long_answer(page)
        settle = "() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')"
        page.wait_for_function(settle)
        bottom = "() => Math.round(document.querySelector('.input-section').getBoundingClientRect().bottom)"
        # The first opening is measured (no prediction yet) and remembered.
        page.locator('#questionInput').tap()
        page.evaluate('() => window.__keyboard(420)')
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 420) <= 1")
        page.evaluate('() => { document.activeElement.blur(); window.__keyboard(820, 0); }')
        page.wait_for_function("() => !document.body.classList.contains('keyboard-open')")
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 820) <= 1")
        # Second tap: up at once, gliding, before the viewport says anything.
        page.locator('#questionInput').tap()
        expect(page.locator('body')).to_have_class(re.compile(r'\bkeyboard-open\b'))
        expect(page.locator('body')).to_have_class(re.compile(r'\bkeyboard-moving\b'))
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 420) <= 1")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--keyboard-lift')") == ''
        # Safari's late report changes nothing that is already right.
        page.evaluate('() => window.__keyboard(420)')
        page.wait_for_timeout(100)
        assert abs(page.evaluate(bottom) - 420) <= 1
        # Leaving the field: down with the keyboard, not after its report.
        page.evaluate('() => document.activeElement.blur()')
        expect(page.locator('body')).not_to_have_class(re.compile(r'\bkeyboard-open\b'))
        page.wait_for_function("() => Math.abs(document.querySelector('.input-section').getBoundingClientRect().bottom - 820) <= 1")
        page.evaluate('() => window.__keyboard(820, 0)')
        # A keyboard that never comes (hardware keyboard): back down after a moment.
        page.locator('#questionInput').tap()
        expect(page.locator('body')).to_have_class(re.compile(r'\bkeyboard-open\b'))
        page.wait_for_function("() => !document.body.classList.contains('keyboard-open')", timeout=3000)
    finally:
        context.close()


@pytest.mark.parametrize('width', [320, 375, 390])
def test_mobile_header_names_the_product_on_the_start_screen(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, before_goto=with_agent_access)
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        header = page.locator('.app-mobile-header')
        brand = header.locator('.brand-float')
        expect(page.locator('body')).to_have_class(re.compile(r'\bis-hero\b'))
        expect(brand).to_be_visible()
        expect(brand.locator('.brand-float-title')).to_be_visible()
        # Nothing scrolls beneath the islands on an empty start screen, so
        # there is no fade; one icon ink for menu and new chat.
        expect(header).not_to_have_class(re.compile(r'\bis-scrolled\b'))
        expect(header).to_have_css('border-bottom-color', 'rgba(0, 0, 0, 0)')
        assert header.locator('#mobileNewRunButton').evaluate('el => getComputedStyle(el).color') == \
            header.locator('#toggleSidebarButton').evaluate('el => getComputedStyle(el).color')
        menu, new_chat = (header.locator(sel).bounding_box() for sel in ('#toggleSidebarButton', '#mobileNewRunButton'))
        mark = brand.bounding_box()
        assert menu['x'] + menu['width'] <= mark['x'] and mark['x'] + mark['width'] <= new_chat['x']
        assert mark['height'] >= 44
        reader_screenshot(page, f'mobile-header-start-{width}')

        seed_long_answer(page)
        expect(brand).to_be_hidden()
        page.evaluate('window.scrollTo(0, 200)')
        expect(header).to_have_class(re.compile(r'\bis-scrolled\b'))
        page.evaluate('window.scrollTo(0, 0)')
        expect(header).not_to_have_class(re.compile(r'\bis-scrolled\b'))
    finally:
        context.close()


@pytest.mark.parametrize('width', [320, 390])
def test_guest_start_header_keeps_the_mark_beside_the_auth_buttons(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None)
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        brand = page.locator('.app-mobile-header .brand-float')
        expect(page.locator('#authTopLoginBtn')).to_be_visible()
        expect(brand).to_be_visible()
        title = brand.locator('.brand-float-title')
        if width < 360:
            expect(title).to_be_hidden()
        else:
            expect(title).to_be_visible()
        mark = brand.bounding_box()
        assert mark['x'] + mark['width'] <= page.locator('#authTopLoginBtn').bounding_box()['x']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize('width,theme', [(320, 'light'), (390, 'dark')])
def test_iphone_safari_finds_the_page_colour_at_both_bars(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')", before_goto=with_agent_access)
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        expect(page.locator('body')).to_have_class(re.compile(r'\bis-hero\b'))
        # Start screen: the header's edge strip on top; below, the bottom
        # strip over the letter clouds (which fill the viewport).
        page.wait_for_function("() => App.letterClouds.state().active"
            " && getComputedStyle(document.querySelector('.letter-clouds')).opacity === '1'")
        bars = page.evaluate(SAFARI_BAR_COLOURS)
        assert bars['top'] == bars['page'] and bars['bottom'] == bars['page'], bars

        # Thread: the same strip on top, the fixed composer below.
        seed_long_answer(page)
        page.wait_for_function("() => document.body.classList.contains('composer-collapsed')"
            " && !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        bars = page.evaluate(SAFARI_BAR_COLOURS)
        assert bars['top'] == bars['page'] and bars['bottom'] == bars['page'], bars
    finally:
        context.close()

    # Watches fill the viewport too; the bottom strip lies above them.
    context, page = _real_firebase_page(browser, phase4_server, path='/app/watches',
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width': width, 'height': 820})
        expect(page.locator('#watchDashboard')).to_be_visible()
        expect(page.locator('.app-mobile-header')).to_be_visible()
        bars = page.evaluate(SAFARI_BAR_COLOURS)
        assert bars['top'] == bars['page'] and bars['bottom'] == bars['page'], bars
    finally:
        context.close()
