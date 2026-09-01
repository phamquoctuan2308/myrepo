import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_codex_hook_config_uses_supported_top_level_schema():
    config = json.loads((REPO_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    assert set(config) <= {"description", "hooks"}
    assert "hooks" in config


def test_codex_hooks_define_cross_platform_command_handlers():
    config = json.loads((REPO_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    for event_name in ("UserPromptSubmit", "Stop"):
        handler = config["hooks"][event_name][0]["hooks"][0]

        assert handler["type"] == "command"
        assert "git rev-parse --show-toplevel" in handler["command"]
        assert "git rev-parse --show-toplevel" in handler["commandWindows"]
        assert "--tool=codex" in handler["command"]
        assert "log_hook.ps1" in handler["commandWindows"]
        assert "_pyrun.cmd" not in handler["commandWindows"]
        assert "-Tool codex" in handler["commandWindows"]


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher test")
def test_windows_python_launcher_uses_repository_venv_from_subdirectory(tmp_path):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "py.cmd").write_text("@exit /b 112\n", encoding="utf-8")

    launcher = REPO_ROOT / "scripts" / "_pyrun.cmd"
    command = f'call "{launcher}" -c "print(\'PYRUN_OK\')"'
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        command,
        cwd=REPO_ROOT / "Frontend",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
        shell=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PYRUN_OK"


def test_codex_prompt_is_normalized_and_appended_to_jsonl(tmp_path):
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "codex-session",
        "turn_id": "codex-turn",
        "transcript_path": "transcripts/codex.jsonl",
        "prompt": "x" * 1200,
    }
    env = os.environ.copy()
    env["AI_LOG_DIR"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "log_hook.py"), "--tool=codex"],
        cwd=REPO_ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"continue": True}
    lines = (tmp_path / "session.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "codex"
    assert entry["event"] == "UserPromptSubmit"
    assert entry["session_id"] == "codex-session"
    assert entry["turn_id"] == "codex-turn"
    assert entry["transcript_path"] == "transcripts/codex.jsonl"
    assert entry["prompt"] == "x" * 1000


def test_codex_prompt_from_subdirectory_uses_repository_root_log_dir(tmp_path):
    repo = tmp_path / "repo"
    nested = repo / "Frontend"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.test/team/project.git"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "codex-session",
        "prompt": "prompt from a nested working directory",
    }
    env = os.environ.copy()
    env.pop("AI_LOG_DIR", None)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "log_hook.py"), "--tool=codex"],
        cwd=nested,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / ".ai-log" / "session.jsonl").is_file()
    assert not (nested / ".ai-log" / "session.jsonl").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows hook command test")
def test_windows_codex_hook_commands_log_prompt_and_stop_from_subdirectory(tmp_path):
    config = json.loads((REPO_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    env = os.environ.copy()
    env["AI_LOG_DIR"] = str(tmp_path)

    payloads = {
        "UserPromptSubmit": {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "cli-session",
            "turn_id": "cli-turn",
            "transcript_path": "transcripts/cli.jsonl",
            "prompt": "Codex CLI prompt",
        },
        "Stop": {
            "hook_event_name": "Stop",
            "session_id": "ide-session",
            "turn_id": "ide-turn",
            "transcript_path": "transcripts/ide.jsonl",
        },
    }

    for event_name, payload in payloads.items():
        command = config["hooks"][event_name][0]["hooks"][0]["commandWindows"]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT / "Frontend",
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=env,
            shell=True,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"continue": True}

    entries = [
        json.loads(line)
        for line in (tmp_path / "session.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [(entry["tool"], entry["event"]) for entry in entries] == [
        ("codex", "UserPromptSubmit"),
        ("codex", "Stop"),
    ]


@pytest.mark.skipif(os.name != "nt", reason="Codex notify uses PowerShell on Windows")
def test_codex_notify_logs_each_input_message_once(tmp_path):
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "notify-thread",
        "turn-id": "notify-turn",
        "cwd": str(REPO_ROOT),
        "input-messages": ["prompt one", "prompt tiếng Việt"],
        "last-assistant-message": "done",
    }
    env = os.environ.copy()
    env["AI_LOG_DIR"] = str(tmp_path)
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(REPO_ROOT / "scripts" / "log_codex_notify.ps1"),
        json.dumps(payload),
    ]

    first = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env=env,
    )
    second = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env=env,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    entries = [
        json.loads(line)
        for line in (tmp_path / "session.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [entry["prompt"] for entry in entries] == ["prompt one", "prompt tiếng Việt"]
    assert all(entry["tool"] == "codex" for entry in entries)
    assert all(entry["event"] == "UserPromptSubmit" for entry in entries)
    assert all(entry["session_id"] == "notify-thread" for entry in entries)
    assert all(entry["turn_id"] == "notify-turn" for entry in entries)
    assert all(entry["source"] == "notify" for entry in entries)


@pytest.mark.skipif(os.name != "nt", reason="Codex notify installer uses PowerShell")
def test_codex_notify_installer_preserves_config_and_adds_top_level_command(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'model = "gpt-test"\n\n[projects."f:\\\\p-132"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    notify_script = REPO_ROOT / "scripts" / "log_codex_notify.ps1"

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / "install_codex_notify.ps1"),
            "-ConfigPath",
            str(config_path),
            "-NotifyScriptPath",
            str(notify_script),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    updated = config_path.read_text(encoding="utf-8")
    escaped_notify_script = str(notify_script).replace("\\", "\\\\")
    assert updated.startswith('notify = ["powershell.exe"')
    assert f'"-File", "{escaped_notify_script}"]' in updated
    assert 'model = "gpt-test"' in updated
    assert '[projects."f:\\\\p-132"]' in updated
    assert config_path.with_suffix(".toml.ai-log.bak").is_file()
