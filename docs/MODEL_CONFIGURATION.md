# Model Configuration

The harness supports configurable models. You can set the model via environment variable or configuration file.

## Environment Variable

Set `MERCURY_MODEL` to override the default model:

```bash
# Windows
set MERCURY_MODEL=inception/mercury-2

# Linux/Mac
export MERCURY_MODEL=inception/mercury-2
```

## Configuration File

Create `.agentic-pi/config.json` with your model configuration:

```json
{
  "model": "inception/mercury-2",
  "thinking": "xhigh",
  "max_model_calls": 3
}
```

## Supported Models

### Cloud Models (require API keys)

- `inception/mercury-2` — Mercury model (fast, good for coding)
- `deepseek/deepseek-v4-flash` — DeepSeek Flash (fast, cheap)
- `anthropic/claude-sonnet-4` — Claude Sonnet (good for complex tasks)
- `openai/gpt-4o` — GPT-4o (good for general tasks)

### Local Models (no API key needed)

- `ollama/codellama` — CodeLlama via Ollama
- `ollama/deepseek-coder` — DeepSeek Coder via Ollama
- `ollama/llama3` — Llama 3 via Ollama

## API Keys

### Required for Cloud Models

- **Mercury**: Get API key from https://inception.xyz
- **DeepSeek**: Get API key from https://deepseek.com
- **Anthropic**: Get API key from https://anthropic.com
- **OpenAI**: Get API key from https://openai.com

### Not Required for Local Models

Local models (Ollama) don't need API keys. Install Ollama and pull the model:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull codellama
ollama pull deepseek-coder
ollama pull llama3
```

## Agent-Specific Configuration

### Pi

```bash
# Set model in Pi CLI
pi --model inception/mercury-2
# or
pi --model deepseek/deepseek-v4-flash
```

### Claude Code

```bash
# Set model in Claude Code settings
# ~/.claude/settings.json
{
  "model": "inception/mercury-2"
}
```

### Cursor

```
# Set model in Cursor settings
# Cursor Settings > Model > Custom Model
```

### Codex

```bash
# Set model in Codex settings
# ~/.codex/settings.json
{
  "model": "inception/mercury-2"
}
```

## Default Model

If no model is configured, the harness uses `deepseek/deepseek-v4-flash` by default.

To change the default, set `MERCURY_MODEL` environment variable or update `.agentic-pi/config.json`.
