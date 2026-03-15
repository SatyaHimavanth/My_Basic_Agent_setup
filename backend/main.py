from langchain_core.messages import BaseMessage

from agents.research_agent.agent import create_research_agent


def _print_last_message(node_name: str, payload: dict) -> bool:
    messages = payload.get("messages")
    if not messages:
        return False

    last_message = messages[-1]
    if isinstance(last_message, BaseMessage):
        print(f"\n[{node_name}]")
        last_message.pretty_print()
        return True

    return False


def print_stream_update(chunk: dict) -> None:
    for node_name, payload in chunk.items():
        if isinstance(payload, dict) and _print_last_message(node_name, payload):
            continue

        if payload is None:
            print(f"[{node_name}] completed")
            continue

        if isinstance(payload, dict):
            print(f"[{node_name}] {list(payload.keys())}")
            continue

        print(f"[{node_name}] {payload}")


if __name__ == "__main__":
    agent = create_research_agent()
    messages = {
        "messages": [
            {
                "role": "user",
                "content": "Can you findout about todays war details and build me a small report.",
            }
        ]
    }
    config = {"configurable": {"thread_id": "thread_1"}}
    for chunk in agent.stream(input=messages, config=config, stream_mode="updates"):
        print_stream_update(chunk)
