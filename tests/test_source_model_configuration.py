"""Source judge selection is Admin-owned and frozen before background execution."""
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.core import config as cfg
from app.api.routers import admin
from app.services import source_verification as sv


@pytest.fixture(autouse=True)
def restore_config():
    state = cfg._capture_runtime_config()
    yield
    cfg._restore_runtime_config(state)


def payload():
    return admin.normalize_models_document({
        **{provider: cfg.get_ordered_models(provider) for provider in cfg.PROVIDERS},
        'premium': list(cfg.PREMIUM_MODELS),
        'defaults': dict(cfg.FREE_DEFAULT_MODEL_BY_PROVIDER),
        'preset_models': cfg.get_consensus_preset_models(),
        'consensus': list(cfg.ALLOWED_CONSENSUS_MODELS),
    })


def test_default_is_gemini_and_env_does_not_override_admin(monkeypatch):
    monkeypatch.setenv('SOURCE_VERIFICATION_MODEL', 'openai/old-model')
    cfg.apply_source_verification_model()
    assert sv.Limits.configured().model == 'google/gemini-3.5-flash-lite'
    cfg.apply_source_verification_model('openai/gpt-5-mini')
    assert sv.Limits.configured().model == 'openai/gpt-5-mini'


def test_metadata_and_dependencies_use_real_openrouter_ids():
    data = payload()
    data['source_verification_model'] = 'google/gemini-3.5-flash-lite'
    meta = admin._admin_meta(data)
    assert {'id': cfg.DEFAULT_SOURCE_VERIFICATION_MODEL, 'label': 'Gemini 3.5 Flash Lite'} in meta['source_verification_models']
    assert meta['source_verification_default'] == cfg.DEFAULT_SOURCE_VERIFICATION_MODEL
    assert all('/' in item['id'] for item in meta['source_verification_models'])
    assert 'Source verification' in meta['dependencies']['gemini']['gemini-3.5-flash-lite']


@pytest.mark.parametrize('invalid', ['', None, {}, 'Gemini', 'gemini-3.5-flash-lite', 'evil/model', 'google/gemini-3.5-flash-lite:online'])
def test_invalid_explicit_admin_choice_is_rejected_before_write(monkeypatch, invalid):
    data = payload()
    data['source_verification_model'] = invalid
    monkeypatch.setattr(admin, '_require_admin', lambda *_: None)
    write = Mock()
    monkeypatch.setattr(admin, '_persist_and_activate_models', write)
    with pytest.raises(HTTPException) as error:
        admin.update_models(Mock(), data)
    assert error.value.status_code == 400
    write.assert_not_called()


def test_admin_save_persists_choice_and_legacy_tab_preserves_active_choice(monkeypatch):
    cfg.apply_source_verification_model('openai/gpt-5-mini')
    data = payload()
    data.pop('source_verification_model')
    monkeypatch.setattr(admin, '_require_admin', lambda *_: None)
    monkeypatch.setattr(admin, 'db_firestore', Mock())
    write = Mock()
    monkeypatch.setattr(admin, '_persist_and_activate_models', write)
    admin.update_models(Mock(), data)
    assert write.call_args.args[1]['source_verification_model'] == 'openai/gpt-5-mini'
    data['source_verification_model'] = cfg.DEFAULT_SOURCE_VERIFICATION_MODEL
    admin.update_models(Mock(), data)
    assert write.call_args.args[1]['source_verification_model'] == cfg.DEFAULT_SOURCE_VERIFICATION_MODEL


@pytest.mark.parametrize('supplied', [None, 'bad/model', 'openai/gpt-5-mini'])
def test_database_load_defaults_and_backfills_missing_or_invalid_choice(monkeypatch, supplied):
    data = payload()
    data.pop('source_verification_model')
    if supplied is not None:
        data['source_verification_model'] = supplied
    document = Mock()
    document.get.return_value = Mock(exists=True, to_dict=lambda: data)
    database = Mock()
    database.collection.return_value.document.return_value = document
    monkeypatch.setattr('app.core.security.db_firestore', database)
    cfg.load_models_from_db(strict=True)
    expected = supplied if supplied == 'openai/gpt-5-mini' else cfg.DEFAULT_SOURCE_VERIFICATION_MODEL
    assert cfg.get_source_verification_model() == expected
    patches = [call.args[0] for call in document.set.call_args_list]
    if supplied != expected:
        assert any(patch.get('source_verification_model') == expected for patch in patches)
    assert all(call.kwargs['merge'] is True for call in document.set.call_args_list)


def test_read_only_get_defaults_without_writing(monkeypatch):
    document = Mock()
    document.get.return_value = Mock(exists=True, to_dict=lambda: {})
    database = Mock()
    database.collection.return_value.document.return_value = document
    monkeypatch.setattr(admin, 'db_firestore', database)
    monkeypatch.setattr(admin, '_require_admin', lambda *_: None)
    assert admin.get_models(Mock())['source_verification_model'] == cfg.DEFAULT_SOURCE_VERIFICATION_MODEL
    document.set.assert_not_called()


def test_runtime_reload_rolls_back_source_choice_when_later_activation_fails(monkeypatch):
    cfg.apply_source_verification_model('openai/gpt-5-mini')
    data = payload()
    data['source_verification_model'] = cfg.DEFAULT_SOURCE_VERIFICATION_MODEL
    document = Mock()
    document.get.return_value = Mock(exists=True, to_dict=lambda: data)
    database = Mock()
    database.collection.return_value.document.return_value = document
    monkeypatch.setattr('app.core.security.db_firestore', database)
    monkeypatch.setattr(cfg, 'apply_watch_models', Mock(side_effect=ValueError('fail')))
    with pytest.raises(ValueError):
        cfg.load_models_from_db(strict=True)
    assert cfg.get_source_verification_model() == 'openai/gpt-5-mini'
