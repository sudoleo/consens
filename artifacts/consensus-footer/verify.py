"""Offline browser QA with real footer markup, bundled CSS and action/status renderers."""
import json
from pathlib import Path
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
soup = BeautifulSoup((ROOT / 'templates/index.html').read_text(encoding='utf-8'), 'html.parser')
main = soup.select_one('.consensus-main')
main.select_one('#consensusAnswerBody').append(BeautifulSoup('<p>Für deinen Ablauf ist genau diese Abfolge sinnvoller als die übliche schnelle Oldschool-Route. <a class="src-ref" data-source-number="1" href="#src-1">4, 5, 6</a></p>', 'html.parser'))
for selector in ['#runProvenance', '#consensusDifferencesTab', '#agentModeAnswersRow', '#consensusSourcesTab']:
    del main.select_one(selector)['hidden']
for selector, value in [('#consensusDifferencesTabCount','1'),('#consensusAnswersTabCount','6'),('#consensusSourcesTabCount','12'),('#runProvenanceFacts','6 models · 65 s'),('#runReplayCost','· uses 1 run')]:
    main.select_one(selector).string = value
manifest = json.loads((ROOT / 'static/dist/manifest.json').read_text())
html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="' + manifest['styles']['app'] + '"></head><body><main style="max-width:900px;margin:32px auto;padding:0 6px"><div id="consensusResponse" class="consensus-box is-synthesizing">' + str(main) + '</div></main><script>window.App={modelPrefs:[],consensusBodyEl:()=>document.getElementById("consensusAnswerBody")};</script><script src="/static/js/consensus-anchor.js"></script><script src="/static/js/source-verification.js"></script><script src="/static/js/consensus-actions.js"></script></body></html>'
results = []
html = html.replace('</body>', '<div hidden>' + str(soup.select_one('#consensusHighlightsSelect')) + '</div>' + '<script src="/static/js/consensus-insights.js"></script></body>')
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(request):
        url = urlparse(request.request.url)
        if url.hostname != 'footer.local': return request.abort()
        if url.path == '/': return request.fulfill(body=html, content_type='text/html')
        file = ROOT / unquote(url.path).lstrip('/')
        if file.is_file() and file.resolve().is_relative_to(ROOT): return request.fulfill(path=str(file))
        request.abort()
    page.route('**/*', route)
    page.goto('http://footer.local/')
    page.evaluate('''() => {
      window.renderConsensusInsights({agreement:{score:72},claims:[],differences:[]},6);
      document.getElementById('consensusVerdict').hidden=true;
    }''')
    # Same Watch markup as watch.js, without starting the dashboard/network module.
    page.evaluate('''() => {
      const watch = document.createElement('span'); watch.className='watch-feature-anchor';
      watch.innerHTML='<button class="consensus-share-pill" type="button"><svg class="share-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg><span>Watch</span></button>';
      document.querySelector('.consensus-actions-wrapper').before(watch);
    }''')
    for theme in ['light', 'dark']:
      for width in [320, 360, 390, 520, 640, 641, 768, 1024, 1440]:
        page.set_viewport_size({'width':width,'height':900})
        page.evaluate('(dark) => document.body.classList.toggle("dark-mode",dark)', theme == 'dark')
        for state in ['unavailable','pending','issues','none']:
          page.evaluate('''state => {
            const tab=document.getElementById('consensusSourcesTab'); tab.hidden=state==='none';
            const snapshot = state==='none' ? null : {status:state==='pending'?'pending':'partial',scope:{pairs:4,checked_pairs:state==='issues'?2:0,processed_pairs:state==='pending'?0:4}, findings:[]};
            window.App.sourceVerification.renderCurrent(snapshot);
          }''', state)
          metrics = page.evaluate('''() => {
            const footer=document.getElementById('runProvenance');
            const box=el=>{const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,w:r.width,h:r.height};};
            return {width:footer.clientWidth,overflow:footer.scrollWidth-footer.clientWidth,
              tabs:Array.from(document.querySelectorAll('#consensusFooterTabs .consensus-tab:not([hidden])'),box),
              actions:box(document.getElementById('consensusFooterActions')),facts:box(document.querySelector('.consensus-footer-facts')),
              source:box(document.querySelector('.consensus-footer-source-status'))};
          }''')
          assert metrics['overflow'] <= 1, (width,state,metrics)
          assert len({round(tab['y']) for tab in metrics['tabs']}) == 1, (width,state,metrics)
          assert all(tab['h'] >= 44 for tab in metrics['tabs']), metrics
          if width <= 640:
            assert metrics['actions']['right'] <= metrics['facts']['x'] + 1, metrics
          if state != 'none':
            assert metrics['source']['y'] >= max(tab['bottom'] for tab in metrics['tabs']), metrics
          else:
            assert metrics['source']['h'] == 0, metrics
          if width in [390,1440] and state=='unavailable':
            page.mouse.move(0,0)
            page.screenshot(path=str(OUT/f'{theme}-{width}.png'))
          results.append({'theme':theme,'viewport':width,'state':state,**metrics})
        # The real Cite menu still anchors to the moved toolbar.
        page.locator('.consensus-actions-toggle').click()
        for verdict in ['full', 'summary', 'off']:
          page.evaluate('''mode => {
            document.getElementById('consensusVerdict').hidden=false;
            document.body.classList.toggle('agreement-score-hidden',mode==='summary');
            document.body.classList.toggle('agreement-verdict-hidden',mode==='off');
          }''', verdict)
          assert page.locator('#runProvenance').evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
          if verdict != 'off':
            assert page.locator('#consensusVerdict').evaluate('(el)=>el.getBoundingClientRect().bottom<=document.getElementById("consensusFooterTabs").getBoundingClientRect().top+1')
        page.evaluate('''() => {
          document.getElementById('consensusVerdict').hidden=true;
          document.body.classList.remove('agreement-score-hidden','agreement-verdict-hidden');
        }''')
        assert page.locator('.consensus-actions-menu').is_visible()
        page.locator('.consensus-actions-toggle').click()
    # Real setting changes must also filter existing and late-arriving source links.
    page.evaluate("""() => {
      const sample=document.createElement('p'); sample.id='source-filter-sample';
      for (const state of ['supported','contradicted','issue','unknown','pending']) {
        const a=document.createElement('a');a.href='#src-1';a.className='src-ref';
        a.dataset.sourceCheck=state;a.textContent=state;sample.append(a);
      }
      document.body.append(sample);
    }""")
    for mode, neutral in [('all', []), ('concerns', ['supported','pending']), ('critical', ['supported','issue','unknown','pending']), ('contradictions', ['supported','issue','unknown','pending']), ('none', ['supported','contradicted','issue','unknown','pending'])]:
      page.evaluate('(mode)=>{const el=document.getElementById("consensusHighlightsSelect");el.value=mode;el.dispatchEvent(new Event("change"));}',mode)
      for state in neutral:
        assert page.locator('#source-filter-sample [data-source-check="'+state+'"]').evaluate('(el)=>getComputedStyle(el).backgroundColor==="rgba(0, 0, 0, 0)" && getComputedStyle(el).textDecorationLine==="none"')
      if mode=='concerns':
        assert page.locator('#source-filter-sample [data-source-check="contradicted"]').evaluate('(el)=>getComputedStyle(el).backgroundColor!=="rgba(0, 0, 0, 0)"')
        page.evaluate("""() => {
          const late=document.createElement('a'); late.className='src-ref';late.dataset.sourceCheck='supported';late.id='late-check';late.textContent='late';document.body.append(late);
        }""")
        assert page.locator('#late-check').evaluate('(el)=>getComputedStyle(el).backgroundColor==="rgba(0, 0, 0, 0)"')
    assert not errors, errors
    browser.close()
(OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(f'PASS: {len(results)} footer layouts; independent status, aligned tabs, no overflow; Cite menu and source highlight filters.')
