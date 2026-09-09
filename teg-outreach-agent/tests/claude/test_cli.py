"""Unit tests for the `claude` CLI subprocess wrapper.

The spawner is injected, so these drive a fake child process and assert on the
event stream and on individual CLI flags — never on the whole argv array, which
would break on harmless reordering.
"""
import asyncio

import pytest

from app.claude.cli import ClaudeCli, ClaudeError, ClaudeProgress, ClaudeResult

pytestmark = pytest.mark.asyncio


class _FakeStream:
    """Minimal asyncio.StreamReader stand-in driven by a list of byte lines."""

    def __init__(self, lines: list[bytes] | None = None) -> None:
        self._lines = list(lines or [])

    async def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        return b""  # EOF

    async def read(self) -> bytes:
        out = b"".join(self._lines)
        self._lines = []
        return out


class _FakeChild:
    def __init__(self, *, stdout_lines: list[bytes], stderr: bytes = b"", returncode: int = 0):
        self.stdout = _FakeStream(stdout_lines)
        self.stderr = _FakeStream([stderr] if stderr else [])
        self.returncode = returncode
        self.killed = False

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        self.killed = True


def _spawner(child: _FakeChild, captured: dict):
    async def spawn(program, *args, **kwargs):
        captured["program"] = program
        captured["args"] = list(args)
        captured["kwargs"] = kwargs
        return child

    return spawn


def _flag(args: list[str], flag: str):
    """Value immediately after `flag`, or None. Robust to argv reordering."""
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def _line(obj: str) -> bytes:
    return (obj + "\n").encode()


async def test_run_yields_progress_then_result():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"stream_event","event":{"type":"content_block_delta",'
              '"delta":{"type":"text_delta","text":"hel"}}}'),
        _line('{"type":"stream_event","event":{"type":"content_block_delta",'
              '"delta":{"type":"text_delta","text":"lo"}}}'),
        _line('{"type":"result","structured_output":{"ok":true},'
              '"total_cost_usd":0.01,"session_id":"sess_1","stop_reason":"tool_use"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="claude-sonnet-5", system_prompt="sys", user_prompt="user",
        json_schema={"type": "object"}, cwd="/tmp",
    )]

    assert events == [
        ClaudeProgress(chars_streamed=3),
        ClaudeProgress(chars_streamed=5),
        ClaudeResult(data={"ok": True}, cost_usd=0.01, session_id="sess_1"),
    ]


async def test_run_counts_websearch_and_webfetch_tool_calls():
    child = _FakeChild(stdout_lines=[
        _line('{"type":"stream_event","event":{"type":"content_block_start",'
              '"content_block":{"type":"tool_use","name":"WebSearch"}}}'),
        _line('{"type":"stream_event","event":{"type":"content_block_delta",'
              '"delta":{"type":"text_delta","text":"..."}}}'),
        _line('{"type":"stream_event","event":{"type":"content_block_start",'
              '"content_block":{"type":"tool_use","name":"WebFetch"}}}'),
        # a non-counted tool_use (e.g. Skill) must not inflate the count
        _line('{"type":"stream_event","event":{"type":"content_block_start",'
              '"content_block":{"type":"tool_use","name":"Skill"}}}'),
        _line('{"type":"stream_event","event":{"type":"content_block_start",'
              '"content_block":{"type":"tool_use","name":"WebSearch"}}}'),
        _line('{"type":"result","structured_output":{"ok":true},'
              '"total_cost_usd":0.03,"session_id":"sess_2","stop_reason":"tool_use"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, {}))

    events = [e async for e in cli.run(
        model="claude-sonnet-5", system_prompt="sys", user_prompt="user",
        json_schema={"type": "object"}, cwd="/tmp",
    )]

    result = events[-1]
    assert isinstance(result, ClaudeResult)
    assert result.tool_calls == 3  # 2x WebSearch + 1x WebFetch, not the Skill call


async def test_run_passes_the_flags_that_matter():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{},"session_id":"s"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    _ = [e async for e in cli.run(
        model="claude-sonnet-5", system_prompt="sys", user_prompt="the prompt",
        json_schema={"type": "object"}, cwd="/work",
    )]

    args = captured["args"]
    assert captured["program"] == "claude"
    assert _flag(args, "-p") == "the prompt"
    assert _flag(args, "--model") == "claude-sonnet-5"
    assert _flag(args, "--append-system-prompt") == "sys"
    assert _flag(args, "--output-format") == "stream-json"
    assert _flag(args, "--permission-mode") == "dontAsk"
    assert _flag(args, "--json-schema") == '{"type": "object"}'
    assert "--include-partial-messages" in args
    assert "--verbose" in args
    # Prospect text reaches this prompt, so the default run grants NO tools:
    # an injection attempt can only produce bad text, never tool execution.
    assert _flag(args, "--tools") == ""
    assert captured["kwargs"]["cwd"] == "/work"


async def test_run_can_grant_a_narrow_tool_list():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{},"session_id":"s"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    _ = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        tools=["WebSearch", "WebFetch"],
    )]

    args = captured["args"]
    idx = args.index("--tools")
    assert args[idx + 1:idx + 3] == ["WebSearch", "WebFetch"]


async def test_allowed_tools_are_passed_separately_from_tools():
    """`--tools` makes a tool available; `--allowed-tools` pre-approves it.

    Under `--permission-mode dontAsk` an available-but-unapproved tool is
    denied at call time, so both flags are needed for a tool that must run.
    """
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{},"session_id":"s"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    _ = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        tools=["WebSearch", "WebFetch"], allowed_tools=["WebSearch", "WebFetch"],
    )]

    args = captured["args"]
    ti = args.index("--tools")
    assert args[ti + 1:ti + 3] == ["WebSearch", "WebFetch"]
    ai = args.index("--allowed-tools")
    assert args[ai + 1:ai + 3] == ["WebSearch", "WebFetch"]


async def test_no_allowed_tools_flag_when_none_are_requested():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{},"session_id":"s"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    _ = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert "--allowed-tools" not in captured["args"]


async def test_run_errors_when_result_has_no_structured_output():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":null,"stop_reason":"max_tokens"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert len(events) == 1
    assert isinstance(events[0], ClaudeError)
    assert "max_tokens" in events[0].message


async def test_run_errors_on_nonzero_exit_without_a_result():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[], stderr=b"not logged in", returncode=1)
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert events == [ClaudeError(message="claude exited with code 1: not logged in")]


async def test_run_errors_when_the_binary_is_missing():
    async def spawn(*a, **k):
        raise FileNotFoundError("claude")

    cli = ClaudeCli(spawn=spawn)
    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert len(events) == 1
    assert isinstance(events[0], ClaudeError)
    assert "not installed" in events[0].message


async def test_run_ignores_non_json_and_unrelated_lines():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        b"warning: something\n",
        _line('{"type":"system","subtype":"init"}'),
        _line('{"type":"result","structured_output":{"ok":1},"session_id":"s"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert events == [ClaudeResult(data={"ok": 1}, cost_usd=None, session_id="s")]


async def test_run_kills_the_child_on_timeout():
    captured: dict = {}

    class _HangingStream:
        async def readline(self):
            await asyncio.sleep(10)
            return b""

        async def read(self):
            return b""

    child = _FakeChild(stdout_lines=[])
    child.stdout = _HangingStream()
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        timeout_s=0.05,
    )]

    assert len(events) == 1
    assert isinstance(events[0], ClaudeError)
    assert "timed out" in events[0].message.lower()
    assert child.killed


async def test_generate_returns_the_structured_payload():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{"company":"TRT"},'
              '"total_cost_usd":0.5,"session_id":"s9"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    result = await cli.generate(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )

    assert result.data == {"company": "TRT"}
    assert result.cost_usd == 0.5


async def test_generate_forwards_resume_to_run():
    """Regression test: generate() silently dropped `resume` until a real
    `scripts/run_verification.py --all` run against the live KB surfaced
    the bug — app/verify/claude_verifier.py is the first real caller of
    resume=, and it calls generate(), not run(), directly."""
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{"ok":true},"session_id":"s2"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    await cli.generate(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        resume="sess_1",
    )

    assert _flag(captured["args"], "--resume") == "sess_1"


async def test_generate_raises_on_error():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[], stderr=b"boom", returncode=2)
    cli = ClaudeCli(spawn=_spawner(child, captured))

    with pytest.raises(RuntimeError, match="boom"):
        await cli.generate(
            model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        )


async def test_auth_status_parses_the_cli_json():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        b'{"loggedIn":true,"email":"a@b.com","subscriptionType":"pro"}'
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    status = await cli.auth_status(cwd="/tmp")

    assert status == {"logged_in": True, "email": "a@b.com", "subscription_type": "pro"}
    assert captured["args"][:3] == ["auth", "status", "--json"]


async def test_auth_status_returns_none_on_garbage():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[b"not json"])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    assert await cli.auth_status(cwd="/tmp") is None


def _sequence_spawner(children: list[_FakeChild], captured: dict):
    """A spawner that hands out a fresh child per call, for retry tests."""
    captured["spawns"] = 0

    async def spawn(program, *args, **kwargs):
        child = children[min(captured["spawns"], len(children) - 1)]
        captured["spawns"] += 1
        captured["args"] = list(args)
        return child

    return spawn


async def test_run_salvages_json_the_model_wrote_as_plain_text():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":null,"stop_reason":"stop_sequence",'
              '"result":"```json\\n{\\"reply\\":\\"hi\\"}\\n```","session_id":"s"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert isinstance(events[0], ClaudeResult)
    assert events[0].data == {"reply": "hi"}


async def test_missing_structured_output_is_marked_retryable():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":null,"stop_reason":"stop_sequence",'
              '"result":"sorry, I cannot"}'),
    ])
    cli = ClaudeCli(spawn=_spawner(child, captured))

    events = [e async for e in cli.run(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )]

    assert isinstance(events[0], ClaudeError)
    assert events[0].retryable


async def test_generate_retries_once_when_structured_output_is_missing():
    captured: dict = {}
    first = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":null,"stop_reason":"stop_sequence",'
              '"result":"plain prose, no json"}'),
    ])
    second = _FakeChild(stdout_lines=[
        _line('{"type":"result","structured_output":{"reply":"ok"},"session_id":"s2"}'),
    ])
    cli = ClaudeCli(spawn=_sequence_spawner([first, second], captured))

    result = await cli.generate(
        model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
    )

    assert result.data == {"reply": "ok"}
    assert captured["spawns"] == 2


async def test_generate_gives_up_after_the_retry():
    captured: dict = {}
    bad = [
        _FakeChild(stdout_lines=[
            _line('{"type":"result","structured_output":null,'
                  '"stop_reason":"stop_sequence","result":"nope"}'),
        ])
        for _ in range(3)
    ]
    cli = ClaudeCli(spawn=_sequence_spawner(bad, captured))

    with pytest.raises(RuntimeError, match="stop_sequence"):
        await cli.generate(
            model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        )

    assert captured["spawns"] == 2


async def test_generate_does_not_retry_a_hard_failure():
    captured: dict = {}
    child = _FakeChild(stdout_lines=[], stderr=b"not logged in", returncode=1)
    cli = ClaudeCli(spawn=_sequence_spawner([child], captured))

    with pytest.raises(RuntimeError, match="not logged in"):
        await cli.generate(
            model="m", system_prompt="s", user_prompt="u", json_schema={}, cwd="/tmp",
        )

    assert captured["spawns"] == 1
