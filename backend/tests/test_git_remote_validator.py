import base64
import subprocess
from types import SimpleNamespace

from caliper.adapters.git.remote_validator import GitRemoteValidator


def test_token_is_sent_only_in_process_environment_and_redirects_are_disabled(monkeypatch):
    token = b"unit-test-token"

    def fake_run(command, **kwargs):
        assert token.decode() not in repr(command)
        assert kwargs["env"]["GIT_CONFIG_VALUE_0"] == (
            "Authorization: Basic " + base64.b64encode(b"x-access-token:" + token).decode("ascii")
        )
        assert kwargs["env"]["GIT_CONFIG_VALUE_1"] == "false"
        assert kwargs["timeout"] == 20
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("caliper.adapters.git.remote_validator.subprocess.run", fake_run)
    assert GitRemoteValidator().validate(
        "https://example.test/org/repo.git", "x-access-token", token
    )


def test_validator_rejects_embedded_url_password_and_handles_timeout(monkeypatch):
    validator = GitRemoteValidator(timeout_seconds=2)
    assert not validator.validate("https://user:secret@example.test/repo", "user", b"token")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("caliper.adapters.git.remote_validator.subprocess.run", timeout)
    assert not validator.validate("https://example.test/repo", "user", b"token")
