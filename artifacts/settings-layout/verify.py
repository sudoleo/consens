"""Offline layout check using the real Settings markup, built CSS and controller."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / 'static/dist/manifest.json').read_text())
soup = BeautifulSoup((ROOT / 'templates/index.html').read_text(encoding='utf-8'), 'html.parser')
modal = soup.select_one('#systemPromptModal')
modal.select_one('#helpModal').decompose()
markup = re.sub(r'{[%{].*?[%}]}', '', str(modal))
html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="' + manifest['styles']['app'] + '"></head><body><button id="editSystemPromptBtn">Settings</button>' + markup + '<script src="/static/app-ui.js"></script></body></html>'
html = html.replace('</body>', '<script src="/static/js/consensus-anchor.js"></script><script src="/static/js/consensus-insights.js"></script></body>')
results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(request):
        url = urlparse(request.request.url)
        if url.hostname != 'settings.local':
            return request.abort()
        if url.path == '/':
            return request.fulfill(body=html, content_type='text/html')
        file = ROOT / unquote(url.path).lstrip('/')
        if file.is_file() and file.resolve().is_relative_to(ROOT):
            return request.fulfill(path=str(file))
        request.abort()
    page.route('**/*', route)
    page.goto('http://settings.local/')
    page.evaluate('window.App.settingsTabs.setTabAvailable("accountSettingsSection", true)')
    for theme in ['light', 'dark']:
        page.evaluate('(dark) => document.body.classList.toggle("dark-mode", dark)', theme == 'dark')
        for width, height in [(320,568), (390,844), (520,740), (699,800), (700,800), (768,1024), (1024,600), (1440,900), (1920,1080), (844,390), (390,360)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('openSettingsModal()')
            assert page.locator('#settingsTabMemory').evaluate('(el) => {const r=el.getBoundingClientRect(),n=el.parentElement.getBoundingClientRect(); return r.left >= n.left && r.right <= n.right;}')
            for panel in ['Memory', 'Behavior', 'Runs', 'Display', 'Connections', 'Account']:
                page.locator('#settingsTab' + panel).click()
                if panel == 'Display':
                    for mode in ['all', 'contradictions', 'critical', 'none', 'concerns']:
                        page.locator('#consensusHighlightsSelect').select_option(mode)
                        assert page.locator('.settings-body').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
                        assert page.locator('#consensusHighlightsSelect').evaluate('(el)=>{const c=document.createElement("canvas").getContext("2d"),s=getComputedStyle(el);c.font=s.font;return c.measureText(el.selectedOptions[0].text).width+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)<=el.clientWidth+1;}')
                        assert page.locator('#consensusHighlightsSelect').evaluate('(el) => {const r=el.getBoundingClientRect(),p=el.closest(".settings-group").getBoundingClientRect();return r.left >= p.left && r.right <= p.right;}')
                if panel == 'Connections':
                    page.locator('#apiSettingsArea').evaluate('(el) => el.style.display="block"')
                    page.locator('#openrouterKey').fill('sk-or-' + 'a' * 160)
                metrics = page.evaluate('''() => {
                    const box = el => {const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom};};
                    const modal=document.querySelector('.settings-modal-content'), body=document.querySelector('.settings-body'), nav=document.querySelector('.settings-nav');
                    const panel=document.querySelector('.settings-category:not([hidden])');
                    return {modal:box(modal),close:box(document.querySelector('#closeSystemPromptModal')),body:box(body),overflow:body.scrollWidth-body.clientWidth,panelOverflow:panel.scrollWidth-panel.clientWidth, orientation:nav.getAttribute('aria-orientation'),columns:getComputedStyle(document.querySelector('.settings-memory-fields')).gridTemplateColumns};
                }''')
                assert metrics['overflow'] <= 1, (theme,width,height,panel,metrics)
                assert metrics['panelOverflow'] <= 1, (theme,width,height,panel,metrics)
                assert metrics['modal']['x'] >= 0 and metrics['modal']['right'] <= width, metrics
                assert metrics['modal']['y'] >= 0 and metrics['modal']['bottom'] <= height + 1, metrics
                assert metrics['close']['bottom'] <= height and metrics['body']['h'] > 60, metrics
                assert metrics['orientation'] == ('horizontal' if width < 700 else 'vertical'), metrics
                page.locator('.settings-body').evaluate('(el) => el.scrollTop=el.scrollHeight')
                assert page.locator('#closeSystemPromptModal').is_visible()
                page.locator('.settings-body').evaluate('(el) => el.scrollTop=0')
                if (width,height) in [(390,844),(1440,900),(844,390)] and panel in ['Memory','Display','Connections']:
                    page.screenshot(path=str(OUT / f'{theme}-{width}-{height}-{panel.lower()}.png'))
                results.append({'theme':theme,'viewport':[width,height],'panel':panel,**metrics})
            page.locator('#settingsTabAccount').focus()
            page.keyboard.press('Home')
            assert page.locator('#settingsTabMemory').get_attribute('aria-selected') == 'true'
            page.keyboard.press('End')
            assert page.locator('#settingsTabAccount').get_attribute('aria-selected') == 'true'
            page.evaluate('window.App.settingsTabs.setTabAvailable("accountSettingsSection", false)')
            assert page.locator('#settingsTabMemory').get_attribute('aria-selected') == 'true'
            page.evaluate('window.App.settingsTabs.setTabAvailable("accountSettingsSection", true)')
            page.locator('#settingsTabAccount').click()
            page.locator('#closeSystemPromptModal').click()
            assert not page.locator('#systemPromptModal').is_visible()
    assert not errors, errors
    browser.close()
(OUT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(f'PASS: {len(results)} panel/theme/viewport combinations; keyboard, auth-tab fallback, close; no JS errors.')
