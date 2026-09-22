"""Regression test: worker must handle UTF-8 (e.g. Chinese) paths over stdio.

Electron writes commands as UTF-8, but the Windows console default is GBK,
which previously corrupted non-ASCII characters in audioPath and produced a
confusing FileNotFoundError with mojibake. This test runs the worker with a
deliberately missing Chinese-named file and asserts the error message echoes
the path back intact.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parent.parent / "worker.py"
CHINESE_NAME = "test/\u98ce\u7b5d\u7ebf\u7684\u53e6\u4e00\u7aef-\u4e0d\u5b58\u5728.wav"  # Chinese filename


def run_worker(audio_path: str, extra_env: dict[str, str] | None = None) -> tuple[int, dict]:
    command = {
        "type": "transcribe",
        "taskId": "utf8-regression",
        "audioPath": audio_path,
        "modelPath": "unused/model.safetensors",
        "configPath": "unused/config.json",
        "device": "cpu",
        "outputDir": str(Path(os.environ.get("TEMP", ".")) / "muscriptor-utf8-test"),
        "ffmpegPath": "unused/ffmpeg.exe",
    }
    env = dict(os.environ)
    # The worker must cope even WITHOUT these being set by the launcher.
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, "-u", str(WORKER)],
        input=json.dumps(command, ensure_ascii=False).encode("utf-8") + b"\n",
        capture_output=True,
        env=env,
        timeout=120,
    )
    events = [
        json.loads(line)
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip().startswith("{")
    ]
    assert events, f"no JSON events emitted; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    return proc.returncode, events[-1]


def test_chinese_path_survives_stdio_roundtrip() -> None:
    missing = str(Path.cwd() / CHINESE_NAME)
    code, event = run_worker(missing)
    assert code == 1
    assert event["type"] == "error"
    assert CHINESE_NAME.replace("/", os.sep) in event["message"], repr(event["message"])


def test_chinese_path_with_utf8_env_from_electron() -> None:
    missing = str(Path.cwd() / CHINESE_NAME)
    code, event = run_worker(missing, {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    assert code == 1
    assert event["type"] == "error"
    assert CHINESE_NAME.replace("/", os.sep) in event["message"], repr(event["message"])


if __name__ == "__main__":
    test_chinese_path_survives_stdio_roundtrip()
    print("PASS: without UTF-8 env (worker reconfigures stdio itself)")
    test_chinese_path_with_utf8_env_from_electron()
    print("PASS: with PYTHONUTF8/PYTHONIOENCODING set by Electron")
