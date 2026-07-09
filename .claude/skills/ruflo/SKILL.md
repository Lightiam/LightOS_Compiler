---
name: ruflo
description: >
  Ruflo agent meta-harness for Claude Code. Use when the user wants to install,
  set up, or use Ruflo — e.g. "add ruflo", "set up the ruflo swarm", "spawn a
  ruflo agent swarm", "route this with ruflo", or asks to coordinate a multi-agent
  system with shared memory and swarm topologies on top of Claude Code. Ruflo is an
  execution layer that turns Claude Code into a collaborative multi-agent system
  ("Agent = Model + Harness") with 100+ specialized agents, vector memory, swarm
  coordination, and multi-provider routing.
---

# Skill: Ruflo Agent Meta-Harness

Ruflo (https://github.com/ruvnet/ruflo) is an execution layer that transforms
Claude Code into a collaborative multi-agent system. The model writes code; Ruflo
supplies the infrastructure — tools, memory, loops, sandboxes, and controls — so
agents can work together. Its guiding principle is **"Agent = Model + Harness."**

Use this skill to install Ruflo, register it as an MCP server, and drive its
agents/swarms from Claude Code.

## When to use

Invoke this skill when the user wants to:

- Install or bootstrap Ruflo (`npx ruflo init`, plugins, or MCP).
- Coordinate a multi-agent **swarm** (hierarchical/queen-led or mesh consensus).
- Use persistent **vector memory** (AgentDB / HNSW) across sessions.
- Route tasks across multiple providers (Claude, GPT, Gemini, Cohere, Ollama).
- Enable self-learning (SONA patterns) or background workers (audit, test-gen).

## Installation

Pick the path that matches what the user wants. Prefer **Path A (plugins)** for a
lightweight, in-editor setup and **Path B (CLI)** for full production capabilities.
Always confirm before running install commands that modify the user's environment.

### Path A — Claude Code Plugins (lightweight)

Run these as Claude Code slash commands:

```
/plugin marketplace add ruvnet/ruflo
/plugin install ruflo-core@ruflo
/plugin install ruflo-swarm@ruflo
/plugin install ruflo-rag-memory@ruflo
```

### Path B — Full CLI Install

POSIX shells (macOS/Linux/WSL):

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/ruvnet/ruflo@main/scripts/install.sh | bash
```

All platforms (interactive wizard, or quick default):

```bash
npx ruflo@latest init wizard
# Or quickly:
npx ruflo@latest init
```

### MCP Server Registration

Register Ruflo as an MCP server so its ~210 tools are callable from Claude Code:

```bash
claude mcp add ruflo -- npx ruflo@latest mcp start
```

## Key capabilities

- **100+ specialized agents** for coding, testing, security, docs, and architecture.
- **Swarm coordination** with hierarchical (queen-led) and adaptive/mesh topologies.
- **Self-learning** via SONA patterns and trajectory-based optimization.
- **Vector memory** — AgentDB with HNSW indexing for sub-millisecond retrieval.
- **Background workers** — auto-triggered auditing, optimization, and test generation.
- **Multi-provider routing** across Claude, GPT, Gemini, Cohere, and Ollama.
- **Zero-trust federation** for secure cross-machine / cross-org agent collaboration.
- **AIDefence security** — prompt-injection blocking and PII detection.

## Typical workflow

After `npx ruflo init`, Ruflo runs in the background while you use Claude Code
normally. It automatically:

1. Routes incoming tasks to the appropriate agents.
2. Stores outcomes in persistent vector memory.
3. Learns successful patterns via SONA.
4. Coordinates multi-agent swarms transparently.
5. Federates work across machines securely.

No manual orchestration is required for the default flow.

## Web interfaces

- **flo.ruv.io** — multi-model chat with built-in MCP tool calling (Claude, Qwen,
  Gemini, OpenAI).
- **goal.ruv.io** — Goal-Oriented Action Planning (GOAP) UI that turns plain-English
  objectives into executable agent plans.

## Documentation

- Repository: https://github.com/ruvnet/ruflo
- User Guide: `docs/USERGUIDE.md` (in the ruflo repo)
- MetaHarness Guide: `docs/metaharness-user-guide.md`

License: MIT.
