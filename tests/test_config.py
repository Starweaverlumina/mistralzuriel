"""Tests for lumina.config.loader."""

import os
import tempfile
import pytest
from lumina.config.loader import load_config, LuminaConfig, _coerce, _deep_merge


class TestCoerce:
    def test_bool_true(self):
        assert _coerce("true") is True
        assert _coerce("yes") is True

    def test_bool_false(self):
        assert _coerce("false") is False
        assert _coerce("no") is False

    def test_null(self):
        assert _coerce("null") is None
        assert _coerce("~") is None

    def test_int(self):
        assert _coerce("42") == 42
        assert _coerce("-1") == -1

    def test_float(self):
        assert _coerce("3.14") == pytest.approx(3.14)

    def test_string(self):
        assert _coerce("hello") == "hello"

    def test_quoted_string(self):
        assert _coerce('"hello world"') == "hello world"
        assert _coerce("'single'") == "single"


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 99, "z": 3}}
        result = _deep_merge(base, override)
        assert result["a"] == {"x": 1, "y": 99, "z": 3}

    def test_none_values_not_applied(self):
        base = {"a": "original"}
        override = {"a": None}
        result = _deep_merge(base, override)
        # None values should not override existing values
        assert result["a"] == "original"


class TestLoadConfig:
    def test_defaults_load(self):
        cfg = load_config()
        assert isinstance(cfg, LuminaConfig)
        assert cfg.persona == "Lumina"
        assert cfg.backend.type == "auto"
        assert cfg.memory.max_bytes == 8 * 1024 * 1024 * 1024

    def test_user_config_override(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("lumina:\n  persona: TestBot\n")
            path = f.name
        try:
            cfg = load_config(user_config_path=path)
            assert cfg.persona == "TestBot"
        finally:
            os.unlink(path)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LUMINA_PERSONA", "EnvBot")
        cfg = load_config()
        assert cfg.persona == "EnvBot"

    def test_inline_overrides(self):
        cfg = load_config(overrides={"lumina": {"persona": "InlineBot"}})
        assert cfg.persona == "InlineBot"

    def test_resolved_paths(self):
        cfg = load_config()
        db_path = cfg.resolved_db_path()
        assert "~" not in db_path
        assert db_path.startswith("/")

    def test_backend_config(self):
        cfg = load_config(overrides={
            "backend": {
                "type": "mistral",
                "model_path": "/tmp/model",
            }
        })
        assert cfg.backend.type == "mistral"
        assert cfg.backend.model_path == "/tmp/model"

    def test_reasoning_config(self):
        cfg = load_config()
        assert cfg.reasoning.fractal_shells == 7
        assert cfg.reasoning.bh_max_depth == 7

    def test_tools_config(self):
        cfg = load_config()
        assert cfg.tools.enabled is True
        assert cfg.tools.allow_file_write is False

    def test_missing_user_config_ok(self):
        """Non-existent user config should not raise."""
        cfg = load_config(user_config_path="/nonexistent/path/config.yaml")
        assert isinstance(cfg, LuminaConfig)
