"""Reader regressions in the real app shell; no LLM or Firestore requests."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401


def reader_screenshot(page, name):
    """Opt-in visual review of the real shell, using only fixture answers."""
    directory = os.environ.get("READER_SCREENSHOTS")
    if directory:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path / f"{name}.png"))


def seed_reader(page, direct=False):
    page.route('**/api/topics/favicon?*', lambda route: route.fulfill(content_type='image/svg+xml',
        body='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" rx="5" fill="#526b82"/><path d="M5 6h10v2H5zm0 5h7v2H5z" fill="white"/></svg>'))
    page.evaluate("""direct => {
      const registry = window.App.runRegistry;
      const providers = window.App.modelPrefs.slice(0, 3).map(p => ({
        provider: p.key, modelLabel: p.key + ' test model'
      }));
      const first = providers[0].provider;
      const second = providers[1].provider;
      const source = {id:'S1', title:'First turn source', url:'https://example.invalid/first'};
      const old = {turn_id:'reader-old', question:'What did the first question ask?',
        consensus:'The first consensus.', sources:[source], model_answers:{
          [first]:{answer:'Original from the first turn. [S1]', model_label:'First saved model', sources:[source]},
          [second]:{answer:'Alternative from the first turn.', model_label:'Second saved model'}
        }};
      const ctx = registry.create({runId:'reader-test', question:'What changes in the next question?',
        config:{agentMode:!direct, providers}});
      ctx.historyTurns = direct ? [] : [old];
      ctx.status = 'succeeded'; ctx.phase = 'answers_ready';
      providers.forEach((p, i) => {
        ctx.modelResults[p.provider] = {
          status: i === 2 ? 'error' : 'complete',
          text: i === 2 ? '' : ('## Original answer ' + i + '\\n\\n' + 'A readable paragraph. '.repeat(160)),
          error: i === 2 ? 'This model timed out.' : null, sources:[]
        };
      });
      if (!direct) Object.assign(ctx.consensus, {status:'complete', text:'The current consensus.',
        completedTurn:{turn_id:'reader-current', question:ctx.question, consensus:'The current consensus.'}});
      registry.renderVisible();
    }""", direct)


def seed_insights(page):
    seed_reader(page)
    page.evaluate("""() => {
      const ctx = App.runRegistry.visible();
      const data = {models_compared:['OpenAI','Mistral'], claims:[], differences:[
        {claim:'The reported participant total differs', type:'contradiction', severity:'major',
          positions:[{models:['OpenAI'], stance:'Counts registered participants.', quote:'2,000 registered participants'},
            {models:['Mistral'], stance:'Counts only finishers.', quote:'1,800 finishers'}], verify:'Check the official results and the registration list.'},
        {claim:'The models emphasise different age groups', type:'emphasis',
          positions:[{models:['OpenAI'],stance:'Focuses on adult participants.'},{models:['Mistral'],stance:'Includes youth competitions.'}]}
      ]};
      ctx.consensus.differencesData = data;
      ctx.historyTurns[0].differences_data = data;
      ctx.evidenceSources = [{title:'Official race results',url:'https://example.invalid/results',snippet:'A longer excerpt from the official result list.'}];
      App.runRegistry.renderVisible();
    }""")


@pytest.mark.parametrize('width', [1440, 1920, 2560])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_wide_reader_centering_and_source_cards(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width':width,'height':1080})
        seed_insights(page)
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible();
          ctx.evidenceSources = [
            {title:'Official results · Hannover Triathlon 2026',url:'https://results.example.invalid/race',snippet:'Participant totals, individual results and finishing times by age group.'},
            {title:'Registration and competition distances',url:'https://race.example.invalid/participants',snippet:'The event programme distinguishes registered competitors from finishers.'},
            {title:'Race-day report: a full field at the Maschsee',url:'https://news.example.invalid/sport/triathlon'}];
          App.runRegistry.renderVisible();
        }""")
        page.locator('#consensusSourcesTab').click()
        dialog = page.locator('.answer-reader-dialog')
        chat = page.locator('.container')
        def assert_centered(left):
            dialog.evaluate("el => Promise.all(el.getAnimations().map(animation => animation.finished))")
            bounds = chat.bounding_box()
            expected = (left + dialog.bounding_box()['x']) / 2
            assert abs(bounds['x'] + bounds['width'] / 2 - expected) <= 2
            assert bounds['x'] + bounds['width'] <= dialog.bounding_box()['x'] - 25
        assert_centered(260)
        assert 520 <= dialog.bounding_box()['width'] <= 720
        icons = page.locator('#answerReaderInspector .answer-reader-site-icon img')
        expect(icons).to_have_count(3)
        expect(icons.first).to_be_visible()
        page.wait_for_function("Array.from(document.querySelectorAll('#answerReaderInspector .answer-reader-site-icon img')).every(img => img.complete && img.naturalWidth > 0)")
        reader_screenshot(page, f'finished-sources-{width}-{theme}')
        page.locator('#sidebarToggleInner').click()
        expect(page.locator('.sidebar')).to_have_class(re.compile(r'.*collapsed.*'))
        assert_centered(0)
        page.locator('#answerReaderSections [data-section="differences"]').click()
        reader_screenshot(page, f'finished-differences-{width}-{theme}')
        page.locator('#answerReaderExpand').click()
        page.locator('#answerReaderInspector .diff-card summary').first.click()
        reader_screenshot(page, f'finished-expanded-{width}-{theme}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


def test_single_difference_and_missing_favicon(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width':390,'height':844})
        seed_insights(page)
        page.route('**/api/topics/favicon?*', lambda route: route.fulfill(status=404, body=''))
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible(); ctx.consensus.differencesData.differences.splice(1);
          App.runRegistry.renderVisible();
        }""")
        page.locator('#consensusDifferencesTab').click()
        expect(page.locator('#answerReaderInspector .diff-card')).to_have_attribute('open','')
        page.locator('#answerReaderSections [data-section="sources"]').click()
        expect(page.locator('#answerReaderInspector .answer-reader-site-icon > span')).to_have_text('E')
        expect(page.locator('#answerReaderInspector .answer-reader-site-icon img')).to_have_count(0)
        card = page.locator('#answerReaderInspector .answer-reader-source-card')
        icon = card.locator('.answer-reader-site-icon')
        assert icon.bounding_box()['x'] - card.bounding_box()['x'] >= 12
        expect(card.locator('a')).to_have_attribute('href','https://example.invalid/results')
    finally:
        context.close()


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_detail_panel_survives_resize_and_short_viewports(browser, phase4_server, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        seed_insights(page)
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible();
          ctx.question = 'How do the participant counts differ across competition groups? '.repeat(8);
          ctx.consensus.differencesData.differences[0].claim =
            'Availability of participant totals for each competition before and after the race';
          App.runRegistry.renderVisible();
        }""")
        page.locator('#consensusDifferencesTab').click()
        page.locator('#answerReaderInspector .diff-card summary').first.click()
        for width, height in [(1920, 1080), (1400, 900), (1399, 900), (1100, 768),
                              (1099, 768), (320, 568), (844, 390)]:
            page.set_viewport_size({'width': width, 'height': height})
            dialog = page.locator('.answer-reader-dialog')
            expect(dialog).to_have_attribute('data-modal', str(width < 1400).lower())
            dialog.evaluate("el => Promise.all(el.getAnimations().map(animation => animation.finished))")
            metrics = page.evaluate("""() => {
              const rect = s => document.querySelector(s).getBoundingClientRect();
              const panel = rect('.answer-reader-dialog'), close = rect('#answerReaderClose');
              const root = document.querySelector('#modelAnswerReader');
              const scroll = document.querySelector('#answerReaderScroll');
              return {left: panel.left, right: panel.right, bottom: panel.bottom,
                closeTop: close.top, closeRight: close.right, closeBottom: close.bottom,
                rootOverflow: root.scrollWidth - root.clientWidth,
                contentOverflow: scroll.scrollWidth - scroll.clientWidth,
                scrollHeight: scroll.clientHeight,
                headerBottom: rect('.answer-reader-sections').bottom,
                contentTop: rect('.answer-reader-inspector').top};
            }""")
            assert metrics['left'] >= 0 and metrics['right'] <= width
            assert metrics['bottom'] <= height
            assert 0 <= metrics['closeTop'] < metrics['closeBottom'] <= height
            assert metrics['closeRight'] <= width
            assert metrics['rootOverflow'] <= 1 and metrics['contentOverflow'] <= 1
            assert metrics['contentTop'] >= metrics['headerBottom']
            assert metrics['scrollHeight'] >= min(200, height * .4)
            page.locator('#answerReaderInspector .diff-resolve-btn').first.scroll_into_view_if_needed()
            expect(page.locator('#answerReaderInspector .diff-resolve-btn').first).to_be_in_viewport()
            page.evaluate("""() => {
              document.querySelector('#modelAnswerReader').scrollTop = 0;
              document.querySelector('#answerReaderScroll').scrollTop = 0;
            }""")
            reader_screenshot(page, f'panel-resize-{width}x{height}-{theme}')
        page.locator('#answerReaderClose').click()
        expect(page.locator('#modelAnswerReader')).to_be_hidden()
    finally:
        context.close()


@pytest.mark.parametrize('width', [390, 1024, 1440, 1920])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_expanded_reader_uses_one_content_grid(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width': width, 'height': 900})
        seed_insights(page)
        page.locator('#agentModeAnswersToggle').click()
        if width >= 1400:
            page.locator('#answerReaderExpand').click()
        expect(page.locator('.answer-reader-dialog')).to_have_attribute('data-modal', 'true')
        page.evaluate("""() => {
          document.querySelector('.answer-reader-body').innerHTML =
            '<h2>How should we compare the answers?</h2>' +
            '<p>Start with the question each model actually answered. A useful comparison separates shared evidence from assumptions and shows where the conclusions differ. Read the original responses alongside their sources before choosing an interpretation.</p>' +
            '<h3>What the responses agree on</h3>' +
            '<ul><li><strong>Scope:</strong> Compare the same event, time period and participant groups.</li><li><strong>Evidence:</strong> Check whether each total counts registrations, starters or finishers.</li></ul>' +
            '<h3>Where the answers differ</h3>' +
            '<p>The first response uses the registration list. The second uses results published after the race. Both numbers can be correctly quoted while describing different groups of people.</p>'.repeat(5);
        }""")
        metrics = page.evaluate("""() => {
          const rect = s => document.querySelector(s).getBoundingClientRect();
          const selectors = ['.answer-reader-header', '.answer-reader-context',
            '.answer-reader-sections', '.answer-reader-toolbar', '.answer-reader-body'];
          return {edges: selectors.map(s => rect(s).left),
            bodyWidth: rect('.answer-reader-body').width,
            controlWidth: rect('.answer-reader-header').width,
            overflow: document.querySelector('#answerReaderScroll').scrollWidth -
              document.querySelector('#answerReaderScroll').clientWidth};
        }""")
        assert max(metrics['edges']) - min(metrics['edges']) <= 1
        assert metrics['bodyWidth'] >= metrics['controlWidth'] * .94
        assert metrics['overflow'] <= 1
        reader_screenshot(page, f'expanded-grid-{width}-{theme}')
        for section in ['differences', 'sources']:
            page.locator(f'#answerReaderSections [data-section="{section}"]').click()
            inspector = page.locator('#answerReaderInspector').bounding_box()
            header = page.locator('.answer-reader-header').bounding_box()
            assert abs(inspector['x'] - header['x']) <= 1
            assert inspector['width'] >= header['width'] * .94
        page.locator('#answerReaderClose').click()
        expect(page.locator('#modelAnswerReader')).to_be_hidden()
    finally:
        context.close()


@pytest.mark.parametrize('width,theme', [(390,'light'),(768,'dark'),(1440,'dark')])
def test_differences_and_sources_share_turn_scoped_sidebar(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width':width,'height':960})
        seed_insights(page)
        page.locator('#consensusDifferencesTab').click()
        expect(page.locator('#answerReaderTitle')).to_have_text('Differences')
        cards = page.locator('#answerReaderInspector .diff-card')
        expect(cards).to_have_count(2)
        expect(cards.first).not_to_have_attribute('open','')
        reader_screenshot(page, f'differences-overview-{width}-{theme}')
        cards.first.locator('summary').click()
        expect(cards.first.locator('.diff-resolve-btn')).to_be_visible()
        reader_screenshot(page, f'differences-detail-{width}-{theme}')
        # Projection may rebuild the live cards; the expanded claim stays open.
        page.evaluate('App.runRegistry.renderVisible()')
        expect(page.locator('#answerReaderInspector .diff-card').first).to_have_attribute('open','')
        page.locator('#answerReaderSections [data-section="sources"]').click()
        expect(page.locator('#answerReaderTitle')).to_have_text('Sources')
        expect(page.locator('#answerReaderInspector')).to_contain_text('Official race results')
        expect(page.locator('#answerReaderInspector .consensus-source-snippet')).to_be_hidden()
        page.locator('.answer-reader-source-excerpt summary').click()
        expect(page.locator('#answerReaderInspector .consensus-source-snippet')).to_be_visible()
        reader_screenshot(page, f'sources-sidebar-{width}-{theme}')
        page.keyboard.press('Escape')
        expect(page.locator('#consensusSourcesPanel #consensusSourcesList')).to_have_count(1)
        expect(page.locator('#consensusDifferencesPanel #differencesCards')).to_have_count(1)
        page.locator('.thread-history-turn .consensus-tab').filter(has_text='Review differences').click()
        expect(page.locator('#answerReaderTurn')).to_have_value('turn:reader-old')
        page.locator('#answerReaderSections [data-section="sources"]').click()
        expect(page.locator('#answerReaderInspector')).to_contain_text('First turn source')
        expect(page.locator('#answerReaderInspector')).not_to_contain_text('Official race results')
        page.locator('#answerReaderSections [data-section="answers"]').click()
        expect(page.locator('.answer-reader-body')).to_contain_text('Original from the first turn')
        expect(page.locator('#answerReaderQuestion summary')).to_have_attribute('aria-disabled','true')
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible(); ctx.question = 'A much longer question with extra context. '.repeat(24);
          App.runRegistry.renderVisible(); App.answerReader.openLive();
        }""")
        question = page.locator('#answerReaderQuestion')
        expect(question.locator('summary')).to_have_attribute('aria-disabled','false')
        question.locator('summary').click()
        expect(question).to_have_attribute('open','')
        assert question.bounding_box()['height'] < 300
        question.locator('summary').click()
        expect(question).not_to_have_attribute('open','')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize("width,height", [(390, 844), (768, 1024), (1024, 768), (1440, 960)])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_reader_responsive_comparison_and_return(browser, phase4_server, width, height, theme):
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"localStorage.setItem('theme', '{theme}');")
    try:
        page.set_viewport_size({"width": width, "height": height})
        seed_reader(page)
        opener = page.locator("#agentModeAnswersToggle")
        opener.click()
        reader = page.locator("#modelAnswerReader")
        expect(reader).to_be_visible()
        assert page.evaluate("document.body.classList.contains('dark-mode')") == (theme == "dark")
        assert reader.bounding_box()["width"] <= width
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator(".answer-reader-dialog").get_attribute("data-modal") == str(width < 1400).lower()
        if width >= 1400:
            chat = page.locator(".container").bounding_box()
            assert chat["x"] + chat["width"] <= page.locator(".answer-reader-dialog").bounding_box()["x"]
        if width == 390:
            expect(page.locator("#answerReaderSingle")).to_be_visible()
            expect(page.locator("#answerReaderModels")).to_be_hidden()
        assert page.locator("#answerReaderScroll").bounding_box()["height"] > height * .4
        reader_screenshot(page, f"reader-{width}-{theme}")
        page.locator("#answerReaderCompare").click()
        expect(page.locator(".answer-reader-dialog")).to_have_attribute("data-modal", "true")
        if width <= 768:
            page.locator("#answerReaderSideB").click()
            expect(page.locator('.answer-reader-answer[data-side="a"]')).to_be_hidden()
            expect(page.locator('.answer-reader-answer[data-side="b"]')).to_be_visible()
        else:
            expect(page.locator('.answer-reader-answer[data-side="a"]')).to_be_visible()
            expect(page.locator('.answer-reader-answer[data-side="b"]')).to_be_visible()
        reader_screenshot(page, f"compare-{width}-{theme}")
        page.keyboard.press("Escape")
        expect(reader).to_be_hidden()
        expect(opener).to_be_focused()
    finally:
        context.close()


def test_archived_reader_keeps_turn_sources_during_projection(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        seed_reader(page)
        page.locator(".thread-history-turn .answer-reader-trigger").click()
        expect(page.locator(".answer-reader-body")).to_contain_text("Original from the first turn")
        page.evaluate("""() => {
          const ctx = window.App.runRegistry.visible();
          ctx.modelResults[ctx.config.providers[0].provider].text = 'New live answer';
          window.App.runRegistry.renderVisible();
        }""")
        expect(page.locator("#answerReaderTurn")).to_have_value("turn:reader-old")
        expect(page.locator(".answer-reader-body")).to_contain_text("Original from the first turn")
        expect(page.locator(".answer-reader-sources a")).to_have_attribute("href", "https://example.invalid/first")
        assert page.locator(".thread-history-models").count() == 0
    finally:
        context.close()


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_direct_reader_remains_inline_and_lists_failed_models(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({"width": width, "height": 1000})
        seed_reader(page, direct=True)
        expect(page.locator(".response-section > #modelAnswerReader")).to_be_visible()
        expect(page.locator(".answer-reader-dialog")).not_to_have_attribute("open", "")
        expect(page.locator(".answer-reader-answer")).to_have_count(3)
        expect(page.locator(".answer-reader-body").nth(2)).to_have_text("This model timed out.")
        expect(page.locator('.answer-reader-toolbar')).not_to_be_visible()
        assert page.evaluate("document.querySelector('.response-section').nextElementSibling.matches('.input-section')")
        if width > 1000:
            a, b = [page.locator('.answer-reader-answer').nth(i).bounding_box() for i in (0, 1)]
            assert abs(a['y'] - b['y']) < 2 and b['x'] > a['x'] + a['width']
        assert page.locator('#threadAsk').bounding_box()['y'] < page.locator('#modelAnswerReader').bounding_box()['y']
        expect(page.locator('#answerReaderStatus')).to_contain_text('1 unavailable')
        reader_screenshot(page, f'direct-{width}-{theme}')
        page.evaluate("""() => {
          const ctx = App.runRegistry.create({runId:'direct-six', question:'What makes a useful product launch?',
            config:{agentMode:false, providers:App.modelPrefs.slice(0, 6).map(p => ({provider:p.key, modelLabel:p.key + ' example model'}))}});
          ctx.status = 'succeeded'; ctx.phase = 'answers_ready';
          ctx.config.providers.forEach((p, i) => { ctx.modelResults[p.provider] = {
            status:'complete', text:'A strong launch gives people a clear reason to try the product.\\n\\nStart with a specific audience, demonstrate one useful outcome, and make the first step simple. Measure activation and return visits before expanding the campaign.', sources:[]
          }; });
          App.runRegistry.renderVisible();
        }""")
        expect(page.locator('.answer-reader-answer')).to_have_count(6)
        reader_screenshot(page, f'direct-six-{width}-{theme}')
        page.evaluate('App.answerReader.reset()')
        assert page.evaluate("document.querySelector('.input-section').compareDocumentPosition(document.querySelector('.response-section')) & Node.DOCUMENT_POSITION_FOLLOWING")

        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_reader_custom_pickers_and_dismissal(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"localStorage.setItem('theme', '{theme}');")
    try:
        page.set_viewport_size({"width": width, "height": 844})
        seed_reader(page)
        page.locator("#agentModeAnswersToggle").click()
        if width == 1440:
            page.locator("#answerReaderExpand").click()
        page.locator("#answerReaderTurnPicker").click()
        menu = page.locator("#answerReaderTurnOptions")
        expect(menu).to_be_visible()
        expect(menu).to_contain_text("What did the first question ask?")
        assert menu.bounding_box()["x"] >= 0
        assert menu.bounding_box()["x"] + menu.bounding_box()["width"] <= width
        reader_screenshot(page, f"question-picker-{width}-{theme}")
        menu.get_by_role("option").first.click()
        expect(page.locator(".answer-reader-body")).to_contain_text("Original from the first turn")
        page.locator("#answerReaderQuestion summary").click()
        assert page.locator("#answerReaderQuestion").inner_text().count("What did the first question ask?") == 1
        sources = page.locator('.answer-reader-sources summary')
        expect(sources).to_have_css('list-style-type', 'none')
        sources.click()
        expect(page.locator('.answer-reader-sources a')).to_be_visible()
        reader_screenshot(page, f"sources-{width}-{theme}")
        page.locator("#answerReaderTurnPicker").click()
        page.keyboard.press("End")
        page.keyboard.press("Enter")
        expect(page.locator("#answerReaderTurn")).to_have_value("turn:reader-current")
        expect(page.locator("#answerReaderQuestion")).not_to_have_attribute("open", "")
        page.locator("#answerReaderCompare").click()
        page.locator("#answerReaderBPicker").click()
        reader_screenshot(page, f"model-picker-{width}-{theme}")
        page.keyboard.press("Escape")
        expect(page.locator("#answerReaderBOptions")).to_be_hidden()
        expect(page.locator("#answerReaderBPicker")).to_be_focused()
        expect(page.locator("#modelAnswerReader")).to_be_visible()
        page.locator("#answerReaderBPicker").click()
        page.locator('#answerReaderBOptions [role="option"]').first.click()
        assert page.locator("#answerReaderA").input_value() != page.locator("#answerReaderB").input_value()
        if width == 1440:
            page.mouse.click(5, 400)
        else:
            page.keyboard.press("Escape")
        expect(page.locator("#modelAnswerReader")).to_be_hidden()
        expect(page.locator("#agentModeAnswersToggle")).to_be_focused()
    finally:
        context.close()


@pytest.mark.parametrize('width', [390, 1024, 1440, 1920])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_direct_comparison_shares_chat_shell_and_fits_picker(browser, phase4_server, width, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.set_viewport_size({'width':width, 'height':900})
        page.evaluate('setAgentMode(false, {persist:true})')
        expect(page.locator('.response-section')).not_to_be_visible()
        assert page.locator('.response-section').evaluate('el => el.inert')
        reader_screenshot(page, f'direct-empty-{width}-{theme}')
        seed_reader(page, direct=True)
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible();
          ctx.question = 'How many participants competed in each group at the Hannover triathlon today?';
          ctx.config.providers.forEach(p => {ctx.modelResults[p.provider] = {status:'pending', text:''};});
          ctx.status = 'running';
          App.runRegistry.renderVisible();
        }""")
        expect(page.locator('.is-direct .answer-reader-body[aria-busy="true"] .answer-skeleton')).to_have_count(3)
        expect(page.locator('.is-direct .answer-reader-answer-actions')).to_have_count(0)
        assert not page.locator('body').evaluate("el => el.classList.contains('is-hero')")
        # Compare the actual computed shell with Agent Mode at the same width.
        measure = """() => Object.fromEntries(['.container','#threadAskText','.chat-input-container','#questionInput'].map(selector => {
          const el = document.querySelector(selector), r = el.getBoundingClientRect(), s = getComputedStyle(el);
          return [selector, {x:r.x, width:r.width, font:s.fontSize, background:s.backgroundColor,
            radius:s.borderRadius, padding:s.padding, minHeight:s.minHeight}];
        }))"""
        page.wait_for_timeout(600)
        direct = page.evaluate(measure)
        reader_screenshot(page, f'direct-waiting-{width}-{theme}')
        page.evaluate('exitHeroMode()')
        normal = page.evaluate(measure)
        assert direct == normal
        page.evaluate('enterDirectComparisonView()')
        if width >= 1100:
            page.locator('#sidebarToggleInner').click()
            page.wait_for_timeout(400)
            collapsed_direct = page.evaluate(measure)
            page.evaluate('exitHeroMode()')
            assert page.evaluate(measure) == collapsed_direct
            page.evaluate('enterDirectComparisonView()')
        assert page.locator('.input-section').evaluate("el => getComputedStyle(el).backgroundColor") == 'rgba(0, 0, 0, 0)'
        # Use the actual trigger, including the collapsed mobile composer.
        page.locator('#questionInput').click()
        trigger = page.locator('.chat-input-container .model-picker-display')
        trigger.click()
        menu = page.locator('.chat-input-container .model-picker-menu.is-open')
        expect(menu).to_be_visible()
        def assert_fits():
            r = menu.bounding_box()
            assert r['x'] >= 10 and r['y'] >= 10
            assert r['x'] + r['width'] <= page.viewport_size['width'] - 10
            assert r['y'] + r['height'] <= page.viewport_size['height'] - 10
        assert_fits()
        reader_screenshot(page, f'direct-picker-{width}-{theme}')
        page.set_viewport_size({'width':width, 'height':520})
        page.wait_for_timeout(400)
        assert_fits()
        reader_screenshot(page, f'direct-picker-short-{width}-{theme}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_fresh_agent_mode_session_opens_saved_direct_answers(browser, phase4_server, width, theme):
    import json
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}');localStorage.setItem('agentMode','true');")
    try:
        page.set_viewport_size({'width':width, 'height':900})
        page.route('**/bookmarks/direct-saved', lambda route: route.fulfill(content_type='application/json', body=json.dumps({
            'bookmark': {'id':'direct-saved', 'query':'Which approach should we choose?', 'mode':'Standard',
                'responses':{'OpenAI':'Start with a small pilot and measure the outcome.',
                    'Gemini':'Compare the costs before expanding the pilot.',
                    'Meta':'Define success criteria with the team first.'},
                'model_labels':{'OpenAI':'Saved GPT version', 'Gemini':'Saved Gemini version', 'Meta':'Saved Muse version'},
                'sources':[], 'attachments':[]}})))
        page.route('**/bookmarks/agent-saved', lambda route: route.fulfill(content_type='application/json', body=json.dumps({
            'bookmark': {'id':'agent-saved', 'query':'A normal saved question', 'mode':'Standard',
                'responses':{'OpenAI':'Other model answer', 'consensus':'A normal saved consensus.'},
                'sources':[], 'attachments':[]}})))
        # A saved answer remains visible even if its model is excluded for the next run.
        page.evaluate("document.getElementById(App.modelPrefs.find(p => p.key === 'Meta').responseId).classList.add('excluded')")
        await_open = "id => window.openBookmark(id)"
        page.evaluate(await_open, 'direct-saved')
        expect(page.locator('#modelAnswerReader')).to_be_visible()
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(3)
        expect(page.locator('.answer-reader-body[data-provider="Meta"]')).to_have_text('Define success criteria with the team first.')
        expect(page.locator('#answerReaderTitle')).to_have_text('Direct comparison')
        expect(page.locator('#answerReaderMode')).to_be_hidden()
        assert page.evaluate("localStorage.getItem('agentMode')") == 'true'
        expect(page.locator('#agentModeSwitch')).to_be_checked()
        page.wait_for_timeout(200)
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(3)
        reader_screenshot(page, f'saved-direct-{width}-{theme}')
        page.evaluate(await_open, 'agent-saved')
        expect(page.locator('#modelAnswerReader')).not_to_be_visible()
        expect(page.locator('#consensusAnswerBody')).to_contain_text('A normal saved consensus.')
        page.evaluate(await_open, 'direct-saved')
        expect(page.locator('#modelAnswerReader')).to_be_visible()
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(3)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize('agent_mode', [False, True])
def test_demo_uses_all_balanced_models_and_never_displays_spinner_markup(browser, phase4_server, agent_mode):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('agentMode','{str(agent_mode).lower()}');")
    try:
        page.set_viewport_size({'width':1440, 'height':900})
        cdn_dir = os.environ.get('READER_CDN_DIR')
        if cdn_dir:
            # Optional real CDN libraries for offline visual review; never mock
            # parsing with a permissive identity sanitizer.
            libraries = {phase4_server + f'/static/e2e-{name}.js': str(Path(cdn_dir) / f'{name}.js')
                for name in ('marked', 'purify')}
            def serve_library(route):
                route.fulfill(content_type='application/javascript', path=libraries[route.request.url])
            for url in libraries:
                page.route(url, serve_library)
                page.add_script_tag(url=url)
        page.wait_for_function("typeof window.runDemoFlow === 'function'")
        if agent_mode:
            # Simulate a registry-updated Balanced preset with the newer families.
            page.evaluate("""() => {
              const wanted = ['OpenAI','Gemini','DeepSeek','Kimi','GLM','Meta'];
              CONSENSUS_PRESETS.find(p => p.id === 'balanced').models = Object.fromEntries(
                App.modelPrefs.filter(p => wanted.includes(p.key)).map(p => [p.provider,
                  Array.from(document.getElementById(p.selectId).options).find(o => !o.disabled && o.value).value]));
            }""")
        page.evaluate("""() => {
          App.selectConsensusPreset('fast');
          App.modelPrefs.filter(p => ['Mistral','Anthropic','Grok'].includes(p.key)).forEach(p =>
            App.setModelSelectionState(p, false, {persist:false, animate:false}));
          window.__demoFinished = false;
          window.runDemoFlow().then(() => window.__demoFinished = true);
        }""")
        expect(page.locator('#threadAskText')).to_contain_text('client', timeout=30000)
        if not agent_mode:
            expect(page.locator('#modelAnswerReader')).to_be_visible(timeout=30000)
            expect(page.locator('#answerReaderStatus')).to_have_text('0 of 6 ready')
            expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(6)
            expect(page.locator('.is-direct .answer-reader-body[aria-busy="true"] .answer-skeleton')).to_have_count(6)
            reader_screenshot(page, 'demo-balanced-waiting')
        page.wait_for_function('() => window.__demoFinished === true', timeout=60000)
        result = page.evaluate("""() => App.modelPrefs.filter(p => !document.getElementById(p.responseId).classList.contains('excluded')).map(p => {
          const box = document.getElementById(p.responseId);
          return {provider:p.provider, model:document.getElementById(p.selectId).value,
            text:box.dataset.consensusAnswer, state:box.dataset.responseState};
        })""")
        expected = page.evaluate("CONSENSUS_PRESETS.find(p => p.id === 'balanced').models")
        assert len(result) == 6
        assert {r['provider']:r['model'] for r in result} == expected
        assert all(r['state'] == 'complete' and len(r['text']) > 100 for r in result)
        assert all('<span' not in r['text'] and '<div' not in r['text'] and 'thinking-wrap' not in r['text'] for r in result)
        assert page.evaluate("localStorage.getItem('pref_consensus_preset')") == 'balanced'
        if agent_mode:
            expect(page.locator('#consensusOutput')).to_be_visible(timeout=30000)
            expect(page.locator('#differencesCards .diff-card')).to_have_count(3, timeout=60000)
        else:
            answers = page.locator('.is-direct .answer-reader-body')
            expect(answers).to_have_count(6)
            for answer in answers.all():
                expect(answer).to_be_visible()
                assert '<span' not in answer.inner_text() and '<div' not in answer.inner_text()
            expect(page.locator('#answerReaderStatus')).to_have_text('6 of 6 ready')
            if cdn_dir:
                assert page.locator('.is-direct .answer-reader-body h4').count() > 0
                assert page.locator('.is-direct .answer-reader-body li').count() > 10
                assert page.locator('.is-direct .answer-reader-body ol > li').count() >= 5
                expect(page.locator('.is-direct .answer-reader-body ul ul')).to_have_count(0)

            expect(page.locator('#consensusOutput')).not_to_be_visible()
        assert page.evaluate("localStorage.getItem('agentMode')") == str(agent_mode).lower()
        reader_screenshot(page, f'demo-balanced-{agent_mode}')
    finally:
        context.close()
