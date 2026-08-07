<h1 align="center" style="border-bottom: none">
    <div>
        <a href="https://a2e.example.com/?utm_medium=github&utm_content=header_img&utm_campaign=a2e-client">
            <picture>
                <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/a2e-ai/a2e-assets/refs/heads/main/logos/A2E/a2e.svg">
                <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/a2e-ai/a2e-assets/refs/heads/main/logos/A2E/a2e-white.svg">
                <img alt="A2E logo" src="https://raw.githubusercontent.com/a2e-ai/a2e-assets/refs/heads/main/logos/A2E/a2e.svg" width="100" />
            </picture>
        </a>
        <br>
        a2e-otel
    </div>
</h1>

<p align="center">
    <a href="https://pypi.org/project/a2e-otel/">
        <img src="https://img.shields.io/pypi/v/a2e-otel" alt="PyPI Version">
    </a>
    <a href="https://a2e-server.readthedocs.io/projects/otel/en/latest/index.html">
        <img src="https://img.shields.io/badge/docs-blue?logo=readthedocs&logoColor=white" alt="Documentation">
    </a>
    <img referrerpolicy="no-referrer-when-downgrade" src="https://static.scarf.sh/a.png?x-pxid=8e8e8b34-7900-43fa-a38f-1f070bd48c64&page=packages/a2e-otel/README.md" />
</p>

Provides a lightweight wrapper around OpenTelemetry primitives with A2E-aware defaults. A2E OTEL also gives you access to tracing decorators for common GenAI patterns.

## Features

`a2e-otel` simplifies OpenTelemetry configuration for A2E users by providing:

- **A2E-aware defaults** for common OpenTelemetry primitives
- **Automatic configuration** from environment variables
- **Drop-in replacements** for OTel classes with enhanced functionality
- **Simplified tracing setup** with the `register()` function
- **Tracing decorators** for GenAI patterns

## Key Benefits

- **Zero Code Changes**: Enable `auto_instrument=True` to automatically instrument AI libraries
- **Production Ready**: Built-in batching and authentication
- **A2E Integration**: Seamless integration with A2E Cloud and self-hosted instances
- **OpenTelemetry Compatible**: Works with existing OpenTelemetry infrastructure

These defaults are aware of environment variables you may have set to configure A2E:

- `A2E_COLLECTOR_ENDPOINT`
- `A2E_PROJECT_NAME`
- `A2E_CLIENT_HEADERS`
- `A2E_API_KEY`
- `A2E_GRPC_PORT`

## Installation

Install via `pip`:

```shell
pip install a2e-otel
```

## Quick Start

**Recommended**: Enable automatic instrumentation to trace your AI libraries with zero code changes:

```python
from a2e.otel import register

# Recommended: Automatic instrumentation + production settings
tracer_provider = register(
    auto_instrument=True,  # Auto-trace OpenAI, LangChain, LlamaIndex, etc.
    batch=True,           # Production-ready batching
    project_name="my-app" # Organize your traces
)
```

That's it! All `openinference-*` AI libraries are now automatically traced and sent to A2E.

**Note**: `auto_instrument=True` only works if the corresponding OpenInference instrumentation libraries are installed. For example, to automatically trace OpenAI calls, you need `openinference-instrumentation-openai` installed:

```bash
pip install openinference-instrumentation-openai
pip install openinference-instrumentation-langchain  # For LangChain
pip install openinference-instrumentation-llama-index  # For LlamaIndex
```

See the [OpenInference repository](https://github.com/a2e-ai/openinference) for the complete list of available instrumentation packages.

### Authentication

```bash
export A2E_API_KEY="your-api-key"
```

```python
# Or pass directly to register()
tracer_provider = register(api_key="your-api-key")
```

### Endpoint Configuration

Configure where to send your traces:

**Environment Variables** (Recommended):

```bash
export A2E_COLLECTOR_ENDPOINT="https://app.a2e.example.com/s/your-space"
export A2E_PROJECT_NAME="my-project"
```

**Direct Configuration**:

```python
tracer_provider = register(
    endpoint="http://localhost:6006/v1/traces",  # HTTP endpoint
    protocol="grpc"  # Or force gRPC protocol
)
```

## Usage Examples

### Simple Setup

```python
from a2e.otel import register

# Basic setup - sends to localhost
tracer_provider = register(auto_instrument=True)
```

### Production Configuration

```python
tracer_provider = register(
    project_name="my-production-app",
    auto_instrument=True,      # Auto-trace AI/ML libraries
    batch=True,               # Background batching for performance
    api_key="your-api-key",   # Authentication
    endpoint="https://app.a2e.example.com/s/your-space"
)
```

### Manual Configuration

For advanced use cases, use A2E OTEL components directly:

```python
from a2e.otel import TracerProvider, BatchSpanProcessor, HTTPSpanExporter

tracer_provider = TracerProvider()
exporter = HTTPSpanExporter(endpoint="http://localhost:6006/v1/traces")
processor = BatchSpanProcessor(span_exporter=exporter)
tracer_provider.add_span_processor(processor)
```

### Using Decorators

```python
from a2e.otel import register

tracer_provider = register()

# Get a tracer for manual instrumentation
tracer = tracer_provider.get_tracer(__name__)

@tracer.chain
def process_data(data):
    return data + " processed"

@tracer.tool
def weather(location):
    return "sunny"
```

## Environment Variables

| Variable                     | Description          | Example                                      |
| ---------------------------- | -------------------- | -------------------------------------------- |
| `A2E_COLLECTOR_ENDPOINT` | Where to send traces | `https://app.a2e.example.com/s/your-space` |
| `A2E_PROJECT_NAME`       | Project name         | `my-llm-app`                                 |
| `A2E_API_KEY`            | Authentication key   | `your-api-key`                               |
| `A2E_CLIENT_HEADERS`     | Custom headers       | `Authorization=Bearer token`                 |
| `A2E_GRPC_PORT`          | gRPC port override   | `4317`                                       |

## Coding Agent Skill

The A2E repo includes a [a2e-tracing skill](https://github.com/a2e-ai/a2e/tree/main/.agents/skills/a2e-tracing) that teaches coding agents (Claude Code, Cursor, etc.) how to instrument LLM applications with OpenInference tracing. Install it with:

```bash
npx skills add a2e-ai/a2e --skill a2e-tracing
```

## Documentation

- **[Full Documentation](https://a2e-server.readthedocs.io/projects/otel/en/latest/index.html)** - Complete API reference and guides
- **[A2E Docs](https://example.com/docs/a2e)** - Detailed tracing examples and patterns
- **[OpenInference](https://github.com/a2e-ai/openinference)** - Auto-instrumentation libraries for frameworks

## Community

Join our community to connect with thousands of AI builders:

- 🌍 Join our [Slack community](https://example.com/slack/shared_invite/zt-3r07iavnk-ammtATWSlF0pSrd1DsMW7g).
- 💡 Ask questions and provide feedback in the _#a2e-support_ channel.
- 🌟 Leave a star on our [GitHub](https://github.com/a2e-ai/a2e).
- 🐞 Report bugs with [GitHub Issues](https://github.com/a2e-ai/a2e/issues).
- 𝕏 Follow us on [𝕏](https://twitter.com/ArizeA2E).
- 🗺️ Check out our [roadmap](https://github.com/orgs/a2e-ai/projects/45) to see where we're heading next.
