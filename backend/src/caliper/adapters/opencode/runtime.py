import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class OpenCodeRuntime:
    """Own the local OpenCode server and keep its writable profile on tmpfs."""

    def __init__(
        self,
        executable: str = "opencode",
        data_home: Path | None = None,
        config_home: Path | None = None,
        base_url: str = "http://127.0.0.1:4096",
    ):
        self.executable = executable
        self.data_home = data_home or Path(
            os.environ.get("XDG_DATA_HOME", "/run/caliper-opencode/data")
        )
        self.config_home = config_home or Path(
            os.environ.get("XDG_CONFIG_HOME", "/run/caliper-opencode/config")
        )
        self.base_url = base_url.rstrip("/")
        self.profile_path = self.data_home / "opencode" / "auth.json"
        self._process: asyncio.subprocess.Process | None = None
        self.profile_error = False

    @property
    def available(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def write_profile(self, payload: bytes) -> None:
        try:
            profile = json.loads(payload)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("Invalid OpenCode authentication profile") from error
        if not isinstance(profile, dict):
            raise TypeError("Invalid OpenCode authentication profile")
        if len(payload) > 1024 * 1024:
            raise ValueError("OpenCode authentication profile is too large")
        self.profile_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".auth-", dir=self.profile_path.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.profile_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.profile_error = False

    def read_profile(self) -> bytes:
        try:
            payload = self.profile_path.read_bytes()
        except FileNotFoundError:
            return b"{}"
        if len(payload) > 1024 * 1024:
            raise ValueError("OpenCode authentication profile is too large")
        try:
            profile = json.loads(payload)
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("Invalid OpenCode authentication profile") from error
        if not isinstance(profile, dict):
            raise TypeError("Invalid OpenCode authentication profile")
        return payload

    async def reload_profile(self, payload: bytes) -> bool:
        await self.stop()
        self.write_profile(payload)
        return await self.start()

    async def start(self) -> bool:
        if shutil.which(self.executable) is None:
            logger.info("OpenCode CLI is unavailable; provider management is disabled")
            return False
        self.data_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.config_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["XDG_DATA_HOME"] = str(self.data_home)
        environment["XDG_CONFIG_HOME"] = str(self.config_home)
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.executable,
                "serve",
                "--hostname",
                "127.0.0.1",
                "--port",
                "4096",
                cwd="/tmp",
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            logger.info("OpenCode CLI is unavailable; provider management is disabled")
            self._process = None
            return False

        async with httpx.AsyncClient(timeout=2) as client:
            for _ in range(30):
                if not self.available:
                    self._process = None
                    return False
                try:
                    response = await client.get(f"{self.base_url}/global/health")
                    if response.status_code == 200 and response.json().get("healthy") is True:
                        return True
                except (httpx.HTTPError, ValueError):
                    pass
                await asyncio.sleep(0.5)
        await self.stop()
        logger.error("OpenCode server did not become ready")
        return False

    async def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=5)
