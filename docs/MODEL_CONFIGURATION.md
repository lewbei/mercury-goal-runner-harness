# Model Configuration

The harness inherits the model from the parent agent by default. You can override this via environment variable or configuration file.

## Default Behavior

**The harness uses the same model as the parent agent.**

- If Pi uses `mimo-v2.5-pro`, the harness uses `mimo-v2.5-pro`
- If Claude Code uses `claude-sonnet-4`, the harness uses `claude-sonnet-4`
- If Cursor uses `gpt-4o`, the harness uses `gpt-4o`

No configuration needed. The harness automatically inherits the model.

## Override Model

If you want to use a different model than the parent agent:

### Environment Variable

Set `MERCURY_MODEL` to override:

```bash
# Windows
set MERCURY_MODEL=inception/mercury-2

# Linux/Mac
export MERCURY_MODEL=inception/mercury-2
```

### Configuration File

Create `.agentic-pi/config.json`:

```json
{
  "model": "inception/mercury-2",
  "thinking": "xhigh"
}
```

## Supported Models

### Cloud Models (require API keys)

- `inception/mercury-2` — Mercury model (fast, good for coding)
- `deepseek/deepseek-v4-flash` — DeepSeek Flash (fast, cheap)
- `anthropic/claude-sonnet-4` — Claude Sonnet (good for complex tasks)
- `openai/gpt-4o` — GPT-4o (good for general tasks)
- `mimo-v2.5-pro` — MiMo (Xiaomi's model)

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
- **MiMo**: Get API key from https://xiaomi.com

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

Pi automatically uses its configured model. The harness inherits it.

```bash
# Check Pi's model
pi --model

# Set Pi's model
pi --model mimo-v2.5-pro
```

### Claude Code

Claude Code automatically uses its configured model. The harness inherits it.

```bash
# Check Claude Code's model
cat ~/.claude/settings.json

# Set Claude Code's model
# Edit ~/.claude/settings.json
{
  "model": "claude-sonnet-4"
}
```

### Cursor

Cursor automatically uses its configured model. The harness inherits it.

### Codex

Codex automatically uses its configured model. The harness inherits it.

## Summary

- **Default**: Harness inherits model from parent agent
- **Override**: Set `MERCURY_MODEL` environment variable
- **Local**: Use Ollama for local models (no API key)
- **Cloud**: Use cloud models (require API key)

The harness automatically uses whatever model the parent agent is using. No configuration needed unless you want to override.
