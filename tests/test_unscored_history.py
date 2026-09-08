"""Missing agreement measurements must not erase completed checks or changes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.routers.share import _build_watch_drift_view
from app.api.routers.topics import _topic_history_view
from app.services import share_snapshots, watch_service
from app.services.history_view import build_history_view
from test_watch_feature import FakeDb, share


def point(score, day=0, **extra):
    return dict(ts=datetime(2026, 9, 8, tzinfo=timezone.utc) + timedelta(days=day),
                agreement_score=score, changed=False, severity='minor', **extra)


def test_completed_unscored_watch_remains_visible_and_changed():
    db = FakeDb()
    sid = 'A' * 16
    db.stores['shares'][sid] = share()
    db.stores['watches']['w1'] = {'status': 'active', 'current_run_id': 'new-run'}
    claimed = {'share_id': sid, 'current_run_id': 'new-run', 'last_agreement_score': 70, 'interval': 'weekly'}
    result = {'consensus': 'The recommendation changed.', 'agreement_score': None,
              'changed': True, 'severity': 'major', 'change_summary': 'New recommendation.',
              'differences_data': {'agreement': {'score': None, 'coverage_status': 'insufficient'}},
              'included_models': ['OpenAI', 'Gemini'], 'consensus_model': 'OpenAI'}
    with patch.object(share_snapshots, 'invalidate_share_cache'):
        saved = watch_service.complete_watch_run('w1', claimed, result, now=point(None, 1)['ts'], db=db)
    assert saved['event_type'] == 'watch.changed'
    assert saved['agreement_score'] is None
    persisted = db.stores[f'shares/{sid}/watch_history']['new-run']
    query_db = MagicMock()
    query = query_db.collection.return_value.document.return_value.collection.return_value
    query.order_by.return_value.limit.return_value.stream.return_value = [
        SimpleNamespace(id='new-run', to_dict=lambda: persisted),
        SimpleNamespace(id='old-run', to_dict=lambda: point(70)),
    ]
    points = share_snapshots.list_watch_history(sid, db=query_db)
    assert [p['run_id'] for p in points] == ['old-run', 'new-run']
    drift = _build_watch_drift_view(points, 'new-run')
    assert drift['label'] == 'Changed since last check'
    assert drift['summary'] == 'New recommendation.'
    assert drift['score_delta'] is None


def test_history_keeps_unscored_events_and_maps_but_breaks_the_chart_line():
    points = [point(70), point(None, 1), point(80, 2), point(None, 3)]
    points[-1].update(changed=True, severity='major', opinion_map={
        'models': [], 'dimensions': [{'label': 'New finding', 'positions': []}],
    })
    view = build_history_view(points)
    assert len(view['points']) == 4
    assert view['latest_score'] is None
    assert view['points'][1]['y'] is None
    assert view['path'].count('M') == 2
    assert 'L' not in view['path']
    assert 'None' not in view['path']
    assert len(view['events']) == 1
    assert view['position_map']['dimensions'][0]['label'] == 'New finding'
    assert build_history_view([point(None)])['path'] == ''


def test_topic_history_retains_unscored_selected_version_without_future_runs():
    runs = [dict(point(score, i), id=f'run-{i}', observed_at=point(score, i)['ts'],
                 version=i + 1, change_type='major' if i == 1 else 'stable')
            for i, score in enumerate([70, None, 80])]
    view = _topic_history_view(runs, selected_version=2)
    assert [p['run_id'] for p in view['points']] == ['run-0', 'run-1']
    assert view['latest_score'] is None
    assert view['events'][0]['run_id'] == 'run-1'
