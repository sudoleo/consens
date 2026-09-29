from app.services import publisher_config


class Snap:
    def __init__(self, data):
        self.data = data

    @property
    def exists(self):
        return self.data is not None

    def to_dict(self):
        return dict(self.data or {})


class Ref:
    def __init__(self, store, key):
        self.store = store
        self.key = key

    def get(self):
        return Snap(self.store.get(self.key))

    def set(self, data, merge=False):
        if merge and self.key in self.store:
            self.store[self.key].update(data)
        else:
            self.store[self.key] = dict(data)


class Collection:
    def __init__(self, store):
        self.store = store

    def document(self, key):
        return Ref(self.store, key)


class Db:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        assert name == "app_config"
        return Collection(self.store)


def test_default_publisher_configuration_is_persisted_and_free_pinned():
    db = Db()

    config = publisher_config.get_config(db=db)

    assert config["enabled"] is True
    assert config["weekly_watch_enabled"] is True
    assert config["max_active_publisher_watches"] == 12
    assert db.store["scheduled_consensus_publisher"]["topic_brief"] == (
        publisher_config.DEFAULT_TOPIC_BRIEF
    )
    assert publisher_config.public_config(config)["watch_model_tier"] == "free"
    assert publisher_config.public_config(config)["excluded_providers"] == []


def test_public_config_reports_the_real_provider_plan_instead_of_an_exclusion():
    """R32: the Admin UI shows the server-side providers of both runs."""
    import app.core.config as cfg
    from app.services import api_consensus_runner

    public = publisher_config.public_config(publisher_config.normalize_config({}))
    plan = api_consensus_runner.build_server_model_plan(deep_think=False, is_pro=True)
    assert public["initial_run_providers"] == [
        cfg.provider_label(provider) for provider in cfg.PROVIDERS if provider in plan["providers"]
    ]
    assert public["watch_providers"] == [
        cfg.provider_label(provider)
        for provider in cfg.PROVIDERS if cfg.get_watch_models("free").get(provider)
    ]
    assert public["excluded_providers"] == []

    original = cfg.get_watch_models("free")
    try:
        cfg.WATCH_MODELS_BY_TIER["free"].pop(next(iter(original)))
        changed = publisher_config.public_config(publisher_config.normalize_config({}))
        assert changed["watch_providers"] != public["watch_providers"]
    finally:
        cfg.WATCH_MODELS_BY_TIER["free"].clear()
        cfg.WATCH_MODELS_BY_TIER["free"].update(original)


def test_admin_publisher_ui_makes_no_static_provider_exclusion_promise():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    template = (root / "templates" / "admin.html").read_text(encoding="utf-8")
    script = (root / "static" / "js" / "admin.js").read_text(encoding="utf-8")
    assert "DeepSeek excluded" not in template + script
    assert "DeepSeek is excluded" not in template
    assert 'id="publisherProviderPlan"' in template
    assert "config.initial_run_providers" in script
    assert "config.watch_providers" in script


def test_saved_publisher_configuration_is_normalized():
    db = Db()
    data = {
        **publisher_config.DEFAULT_CONFIG,
        "enabled": False,
        "watch_weekday": "Friday",
        "watch_time": "14:30",
        "watch_timezone": "Europe/Berlin",
    }

    saved = publisher_config.save_config(data, updated_by="admin-1", db=db)

    assert saved["enabled"] is False
    assert saved["watch_weekday"] == "friday"
    assert db.store["scheduled_consensus_publisher"]["updated_by"] == "admin-1"


def test_superseded_default_topic_briefs_migrate_to_the_disagreement_strategy():
    for superseded in publisher_config.SUPERSEDED_TOPIC_BRIEFS:
        config = publisher_config.normalize_config({
            **publisher_config.DEFAULT_CONFIG,
            "topic_brief": superseded,
        })

        assert config["topic_brief"] == publisher_config.DEFAULT_TOPIC_BRIEF

    assert "still answer differently" in publisher_config.DEFAULT_TOPIC_BRIEF
    # The event is the trigger, but the question has to survive it.
    assert "fresh product event" in publisher_config.DEFAULT_TOPIC_BRIEF
    assert "stand on its own" in publisher_config.DEFAULT_TOPIC_BRIEF


def test_hand_edited_topic_brief_is_never_overwritten():
    config = publisher_config.normalize_config({
        **publisher_config.DEFAULT_CONFIG,
        "topic_brief": "My own brief.",
    })

    assert config["topic_brief"] == "My own brief."
