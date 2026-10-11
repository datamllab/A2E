"""Simulated User Agent for multi-turn evaluation.

Provides a FastAPI server that simulates a user in multi-turn conversations
with an AI agent, compatible with the OpenClaw Safety Bench framework.

Usage:
    # Start the server
    python -m benchmark.simulated_user --port 9090

    # Or with environment variables
    USER_AGENT_MODEL_ID=your-model \\
    USER_AGENT_BASE_URL=https://your-api-endpoint/v1 \\
    USER_AGENT_API_KEY=your-key \\
    python -m benchmark.simulated_user --port 9090
"""

__version__ = "0.1.0"