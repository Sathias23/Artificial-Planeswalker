#!/usr/bin/env python3
"""Manual test script for agent functionality.

This script provides a simple way to test the agent with a manual prompt.
Requires OPENROUTER_API_KEY to be set in environment.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from src.agent import create_agent, run_agent_with_retry

# Load environment variables from .env file
load_dotenv()


async def main() -> None:
    """Run a simple test of the agent."""
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("Please set it in your .env file or export it")
        sys.exit(1)

    print("Creating agent...")
    agent = create_agent()

    print("\nAgent created successfully!")
    print("Testing basic response...")

    # Simple test prompt
    prompt = "What is 2+2? Answer with just the number."
    print(f"\nPrompt: {prompt}")

    try:
        response = await run_agent_with_retry(agent, prompt)
        print(f"Response: {response}")
        print("\n✓ Agent test successful!")
    except Exception as e:
        print(f"\n✗ Agent test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
