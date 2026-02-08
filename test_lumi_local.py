#!/usr/bin/env python3
"""
Local test script for Lumi onboarding flow.
Run with: uv run python test_lumi_local.py
"""

import asyncio
import os

# Ensure we use the local DB path
os.environ.setdefault("SHORT_TERM_MEMORY_DB_PATH", "short_term_memory/memory.db")

from ai_companion.modules.lumi.flow_handler import get_flow_handler
from ai_companion.modules.lumi.state import delete_user_state

TEST_PHONE = "919999999999"


async def test_conversation():
    """Simulate a conversation with Lumi."""

    # Clear any existing state for test phone
    delete_user_state(TEST_PHONE)
    print("=" * 60)
    print("LUMI ONBOARDING FLOW TEST")
    print("=" * 60)

    handler = get_flow_handler()

    # Test messages to simulate a conversation
    test_messages = [
        "Hello",  # Should get welcome + intro
        "I'm 28 years old, male",  # Demographics
        "I've been feeling anxious and stressed at work lately",  # Story
        "No, I'm new to this",  # Therapy history
        "Just therapy for now",  # Care preference
        "No",  # Medication
        "anxiety, stress, burnout",  # Concerns
        "English",  # Language
        "warm and nurturing",  # Therapist style
        "woman",  # Gender preference
        "single",  # Relationship status
        "15/05/1995",  # DOB
        "Mumbai",  # City
    ]

    for i, msg in enumerate(test_messages):
        print(f"\n{'='*40}")
        print(f"USER [{i+1}]: {msg}")
        print("-" * 40)

        try:
            response = await handler.handle_message(
                phone_number=TEST_PHONE,
                message_text=msg,
            )

            print(f"STAGE: {response.new_state.stage if response.new_state else 'N/A'}")
            print(f"LUMI:")
            for m in response.messages:
                print(f"  {m[:200]}..." if len(m) > 200 else f"  {m}")

            if response.buttons:
                print(f"BUTTONS: {[b['title'] for b in response.buttons]}")

            if response.is_handoff:
                print(f"[HANDOFF]: {response.handoff_reason}")
                break

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            break

        # Small delay between messages
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


async def interactive_test():
    """Interactive test mode - type messages to Lumi."""

    # Clear any existing state
    delete_user_state(TEST_PHONE)
    print("=" * 60)
    print("LUMI INTERACTIVE TEST")
    print("Type 'quit' to exit, 'reset' to start over")
    print("=" * 60)

    handler = get_flow_handler()

    while True:
        try:
            user_input = input("\nYOU: ").strip()

            if user_input.lower() == 'quit':
                break
            elif user_input.lower() == 'reset':
                delete_user_state(TEST_PHONE)
                handler = get_flow_handler()
                print("[State reset]")
                continue
            elif not user_input:
                continue

            response = await handler.handle_message(
                phone_number=TEST_PHONE,
                message_text=user_input,
            )

            print(f"\n[Stage: {response.new_state.stage if response.new_state else 'N/A'}]")
            print("LUMI:", end=" ")
            for m in response.messages:
                print(m)

            if response.buttons:
                print(f"[Options: {', '.join(b['title'] for b in response.buttons)}]")

            if response.is_handoff:
                print(f"[HANDED OFF: {response.handoff_reason}]")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    print("\nGoodbye!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive_test())
    else:
        asyncio.run(test_conversation())
