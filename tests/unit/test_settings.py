"""Unit tests for ICECODE settings and configuration."""
import os
import pytest
from pathlib import Path


class TestICECodeSettings:
    def test_default_port(self):
        from icecode.config.settings import ICECodeSettings
        s = ICECodeSettings()
        assert s.host_api_port == 13210

    def test_default_home_dir(self):
        from icecode.config.settings import ICECodeSettings
        s = ICECodeSettings()
        assert ".icecode" in str(s.home_dir)

    def test_db_path_set_automatically(self):
        from icecode.config.settings import ICECodeSettings
        s = ICECodeSettings()
        assert s.db_path is not None
        assert s.db_path.suffix == ".db"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("HOST_API_PORT", "9999")
        from importlib import reload
        import icecode.config.settings as mod
        reload(mod)
        s = mod.ICECodeSettings()
        assert s.host_api_port == 9999
        reload(mod)

    def test_api_keys_redacted_in_dict(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
        from icecode.config.settings import ICECodeSettings
        s = ICECodeSettings()
        d = s.to_dict()
        assert d.get("anthropic_api_key") == "***"

    def test_feature_flags_defaults(self):
        from icecode.config.settings import ICECodeSettings
        s = ICECodeSettings()
        assert s.enable_self_learning is True
        assert s.enable_goals is True
        assert s.enable_kanban is True
        assert s.enable_voice is False

    def test_version_is_2(self):
        import icecode
        assert icecode.__version__ == "2.0.0"


class TestSettingsDirectoriesCreated:
    def test_home_dirs_created(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from icecode.config.settings import ICECodeSettings
        s = ICECodeSettings()
        assert s.home_dir.exists()
        assert (s.home_dir / "data").exists()
        assert (s.home_dir / "skills").exists()
        assert (s.home_dir / "logs").exists()
