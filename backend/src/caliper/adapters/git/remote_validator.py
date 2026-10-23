import base64
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


class GitRemoteValidator:
    def __init__(self, timeout_seconds: int = 20):
        self.timeout_seconds = timeout_seconds

    def validate(self, url: str, username: str, token: bytes) -> bool:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or not token
        ):
            return False

        authorization = base64.b64encode(username.encode() + b":" + token).decode("ascii")
        safe_environment = {
            "PATH": os.environ.get("PATH", ""),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TRACE": "0",
            "GIT_CURL_VERBOSE": "0",
            "LC_ALL": "C",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "http.extraheader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {authorization}",
            "GIT_CONFIG_KEY_1": "http.followRedirects",
            "GIT_CONFIG_VALUE_1": "false",
        }
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
            if name in os.environ:
                safe_environment[name] = os.environ[name]

        try:
            with tempfile.TemporaryDirectory(prefix="caliper-git-validate-") as temp_dir:
                empty_config = Path(temp_dir) / "gitconfig"
                empty_config.touch(mode=0o600)
                safe_environment["HOME"] = temp_dir
                safe_environment["GIT_CONFIG_GLOBAL"] = str(empty_config)
                result = subprocess.run(
                    ["git", "ls-remote", "--heads", url],
                    cwd=temp_dir,
                    env=safe_environment,
                    check=False,
                    timeout=self.timeout_seconds,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
