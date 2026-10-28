import pytest

from sandbank.cli import main
from sandbank.runner.keyguard import (
    ForbiddenKeyError,
    assert_no_api_keys,
    assert_safe_argv,
    present_keys,
    scrubbed_env,
)


def test_clean_env_passes() -> None:
    assert_no_api_keys({"PATH": "/bin"})
    assert present_keys({}) == []


@pytest.mark.parametrize("key", ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"])
def test_each_key_refused(key: str) -> None:
    with pytest.raises(ForbiddenKeyError, match=key):
        assert_no_api_keys({key: "x"})


def test_empty_value_not_counted() -> None:
    assert present_keys({"ANTHROPIC_API_KEY": ""}) == []


def test_bare_flag_refused() -> None:
    with pytest.raises(ForbiddenKeyError):
        assert_safe_argv(["claude", "-p", "hi", "--bare"])
    assert_safe_argv(["claude", "-p", "hi"])


def test_scrubbed_env() -> None:
    assert scrubbed_env({"ANTHROPIC_API_KEY": "x", "A": "1"}) == {"A": "1"}


def test_cli_refuses_with_key_on_claude_code_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert main(["demo", "--backend", "claude-code"]) == 2


def test_demo_stub_passes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert main(["demo", "--stub", "--results", str(tmp_path)]) == 0
