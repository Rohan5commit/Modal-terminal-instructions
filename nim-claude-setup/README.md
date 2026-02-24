# Claude Code + NVIDIA NIM local proxy setup

This folder contains the setup files used to run Claude Code CLI through a local proxy that forwards to NVIDIA NIM.

## Files

- `server.py`: Anthropic-compatible local proxy server.
- `nim-claude-proxy`: helper script to start/stop/status/log the proxy.
- `claude-nim.zsh`: zsh bridge/wrapper functions for `claude`, primary/secondary aliases, and custom selector commands.
- `settings.example.json`: example `~/.claude/settings.json` env block.
- `nim-claude-local.env.example`: local-only hidden env file template for secrets.

## Current model mapping

- Primary: `qwen/qwen3-coder-480b-a35b-instruct`
- Secondary: `qwen/qwen2.5-coder-32b-instruct`

Custom aliases exposed by proxy:

- `qwen3-coder-480b-primary`
- `qwen25-coder-32b-secondary`

## Quick usage

1. Create local-only hidden env file:

```bash
cp ./nim-claude-setup/nim-claude-local.env.example ~/.nim-claude-local.env
chmod 600 ~/.nim-claude-local.env
```

2. Source the zsh bridge functions:

```bash
source ./nim-claude-setup/claude-nim.zsh
```

3. Choose default model:

```bash
nim-model primary
# or
nim-model secondary
```

4. Run Claude with default model routing:

```bash
claude
```

5. Override for one command:

```bash
claude --primary
claude --secondary
```

## Notes

- This package intentionally does **not** include real API keys.
- Keep your NVIDIA key only in `~/.nim-claude-local.env` (hidden local file).
- Claude's built-in `/model` list entries (Default/Sonnet/Opus/Haiku) are UI-provided by Claude CLI and are not removed by proxy config.
