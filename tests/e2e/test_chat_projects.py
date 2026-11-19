"""Projects in the sidebar, in Chromium against the real routes and the
Firestore emulator (the journey harness of test_persisted_journeys.py).

The first project is made where a chat is: its menu's "Move to project"
asks for a name when there is no project yet, and the chat moves in. The
project stays open after a reload, folds to one row, a search finds its
chat by the project's name, and deleting it keeps the chat.
"""
from pathlib import Path

from playwright.sync_api import expect

# The journey harness: its fixtures, imported, are this module's too.
from test_persisted_journeys import journey, journey_server  # noqa: F401


def _open_sidebar(page):
    page.evaluate("() => { const sidebar = document.querySelector('.sidebar');"
                  " if (sidebar?.classList.contains('collapsed')) document.getElementById('toggleSidebarButton').click(); }")


def _stored(j, bookmark_id):
    return j.control('state')['collections']['bookmarks'][bookmark_id]['data']


def test_a_chat_moves_into_a_new_project_that_folds_finds_and_goes(journey):
    j = journey
    j.open()
    first = j.run('Which planets have rings? ' + j.uid)
    second = j.run('How far is Mars? ' + j.uid)
    page = j.page
    _open_sidebar(page)
    shots = Path('test-results')

    # No project yet: the list looks as it always did.
    expect(page.locator('.chat-projects-heading')).to_have_count(0)

    row = page.locator(f'.bookmark[data-id="{first["bookmark"]}"]')
    row.hover()
    row.locator('.bookmark-menu-button').click()
    page.locator('.bookmark-menu-item[data-action="move"]').click()
    # With no project, the picker asks for the first one's name at once.
    field = page.locator('.bookmark-menu-field input')
    expect(field).to_be_focused()
    page.locator('.bookmark-menu').screenshot(path=str(shots / 'projects-picker-first.png'))
    field.fill('Thesis')
    with page.expect_response(lambda r: r.url.endswith('/project') and r.request.method == 'PATCH') as moved:
        field.press('Enter')
    assert moved.value.ok, moved.value.text()

    project = page.locator('.chat-project')
    expect(project).to_have_count(1)
    expect(project.locator('.chat-project-name')).to_have_text('Thesis')
    expect(project.locator('.chat-project-toggle')).to_have_attribute('aria-expanded', 'true')
    assert 'in-project' in (row.get_attribute('class') or '')
    stored = j.control('state')['collections']
    [project_id] = [entry['id'] for entry in stored['chat_state']['projects']['data']['projects']]
    assert stored['bookmarks'][first['bookmark']]['data']['project_id'] == project_id
    assert 'project_id' not in stored['bookmarks'][second['bookmark']]['data']
    # Projects first, the chat under its project, the other one under its date.
    order = page.evaluate("() => [...document.getElementById('bookmarksContainer').children]"
                          ".filter(n => n.offsetParent).map(n => n.dataset.id || n.dataset.projectId || n.textContent.trim())")
    assert order[:3] == ['Projects', project_id, first['bookmark']], order
    assert order.index(second['bookmark']) > order.index('Today'), order
    page.locator('#appSidebar').screenshot(path=str(shots / 'projects-sidebar-open.png'))

    # Open after a reload, with its chat.
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function('() => window.__consensioAuthState?.known && document.querySelector(".chat-project")')
    _open_sidebar(page)
    expect(row).to_be_visible()

    # Folded: one row, the chat out of sight.
    page.locator('.chat-project-toggle').click()
    expect(row).to_be_hidden()
    expect(page.locator('.chat-project-toggle')).to_have_attribute('aria-expanded', 'false')
    page.locator('#appSidebar').screenshot(path=str(shots / 'projects-sidebar-folded.png'))

    # A search by the project's name finds its chat in the folded project.
    page.locator('#bookmarkSearchTrigger').click()
    page.locator('#chatSearch').fill('thesis')
    expect(row).to_be_visible()
    expect(page.locator(f'.bookmark[data-id="{second["bookmark"]}"]')).to_be_hidden()
    page.locator('#chatSearch').press('Escape')
    expect(row).to_be_hidden()

    # The chat menu of a chat in a project: no Pin, a way out instead.
    page.locator('.chat-project-toggle').click()
    row.hover()
    row.locator('.bookmark-menu-button').click()
    expect(page.locator('.bookmark-menu-item[data-action="pin"]')).to_have_count(0)
    expect(page.locator('.bookmark-menu-item[data-action="unproject"]')).to_be_visible()
    page.keyboard.press('Escape')

    # Deleting the project keeps its chat, back under its date.
    project_row = page.locator('.chat-project')
    project_row.hover()
    project_row.locator('.bookmark-menu-button').click()
    page.locator('.bookmark-menu-item[data-action="delete"]').click()
    expect(page.locator('.chat-project')).to_have_count(0)
    expect(row).to_be_visible()
    with page.expect_response(lambda r: '/projects/' in r.url and r.request.method == 'DELETE', timeout=15000) as deleted:
        pass
    assert deleted.value.ok, deleted.value.text()
    stored = j.control('state')['collections']
    assert stored['chat_state']['projects']['data']['projects'] == []
    assert stored['bookmarks'][first['bookmark']]['data'].get('project_id') is None
