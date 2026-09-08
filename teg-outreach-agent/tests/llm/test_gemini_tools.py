import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY"),
]


async def test_gemini_calls_a_tool():
    from app.llm.gemini_client import GeminiClient

    client = GeminiClient()
    tools = [
        {
            "name": "get_weather",
            "description": "Get the weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ]
    turn = await client.generate_with_tools(
        system="Use the tool when asked about weather.",
        messages=[{"role": "user", "content": "What's the weather in Ahmedabad?"}],
        tools=tools,
    )
    assert turn.tool_calls and turn.tool_calls[0].name == "get_weather"
    assert turn.tool_calls[0].args.get("city")


async def test_gemini_answers_after_tool_result():
    from app.llm.gemini_client import GeminiClient

    client = GeminiClient()
    tools = [
        {
            "name": "get_weather",
            "description": "Get the weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ]
    messages = [
        {"role": "user", "content": "What's the weather in Ahmedabad?"},
        {"role": "assistant", "content": "[called get_weather]"},
        {"role": "tool", "tool_call_id": "c0", "name": "get_weather", "content": "34C and sunny"},
    ]
    turn = await client.generate_with_tools(
        system="Answer the user using the tool result.", messages=messages, tools=tools
    )
    assert turn.text and "34" in turn.text
