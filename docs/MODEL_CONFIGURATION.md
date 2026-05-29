# Model Configuration

The harness inherits the model from the parent agent by default. You can override this via environment variable or configuration file.

## Default Behavior

**The harness uses the same model as the parent agent.**

- If Pi uses `mimo-v2.5-pro`, the harness uses `mimo-v2.5-pro`
- If Claude Code uses `claude-sonnet-4.6`, the harness uses `claude-sonnet-4.6`
- If Cursor uses `gpt-5.5`, the harness uses `gpt-5.5`

No configuration needed. The harness automatically inherits the model.

## Override Model

If you want to use a different model than the parent agent:

### Environment Variable

Set `MERCURY_MODEL` to override:

```bash
# Windows
set MERCURY_MODEL=claude-opus-4.7

# Linux/Mac
export MERCURY_MODEL=claude-opus-4.7
```

### Configuration File

Create `.agentic-pi/config.json`:

```json
{
  "model": "claude-opus-4.7",
  "thinking": "xhigh"
}
```

## Current Models (2026)

### Cloud Models (require API keys)

- `claude-opus-4.7` — Claude Opus 4.7 (best for coding & thinking)
- `claude-sonnet-4.6` — Claude Sonnet 4.6 (good balance)
- `gpt-5.5` — GPT-5.5 (latest OpenAI model)
- `gpt-5.4` — GPT-5.4 (good for general tasks)
- `deepseek-v4-pro` — DeepSeek V4 Pro (fast, cheap)
- `deepseek-v3.2` — DeepSeek V3.2 (good for coding)
- `gemini-3.1-pro` — Gemini 3.1 Pro (Google's latest)
- `kimi-k2.6` — Kimi K2.6 (Moonshot AI)
- `minimax-m2.5` — MiniMax M2.5 (good for coding)

### Local Models (no API key needed)

- `ollama/codellama` — CodeLlama via Ollama
- `ollama/deepseek-coder` — DeepSeek Coder via Ollama
- `ollama/llama3` — Llama 3 via Ollama

## API Keys

### Required for Cloud Models

- **Claude**: Get API key from https://anthropic.com
- **GPT**: Get API key from https://openai.com
- **DeepSeek**: Get API key from https://deepseek.com
- **Gemini**: Get API key from https://ai.google.dev
- **Kimi**: Get API key from https://moonshot.cn
- **MiniMax**: Get API key from https://minimaxi.com

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
pi --model claude-opus-4.7
```

### Claude Code

Claude Code automatically uses its configured model. The harness inherits it.

```bash
# Check Claude Code's model
cat ~/.claude/settings.json

# Set Claude Code's model
# Edit ~/.claude/settings.json
{
  "model": "claude-opus-4.7"
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

## Keeping Up-to-Date

The AI model landscape changes fast. To stay current:

1. Check https://www.faros.ai/blog/best-ai-model-for-coding-2026 for latest rankings
2. Check https://www.morphllm.com/best-ai-model-for-coding for benchmarks
3. Update your model configuration as new models are released

The harness will use whatever model you configure. Update your configuration to use the latest models.
