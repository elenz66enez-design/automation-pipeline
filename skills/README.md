# Skills Index — Rabbi Goldsteyn Automation

Shortcut reference to skills available in `~/.claude/skills/`.
Invoke any skill via: `/skill-name` in Claude Code.

**Total skills installed: ~1284** (including 33 claude-flow skills + 99 agents)

---

## Claude Flow (Ruflo) — NEW ✓

Multi-agent swarm orchestration by ruvnet. Installed via `npx claude-flow@alpha init --only-claude --full`.

| Skill | What it does |
|-------|-------------|
| `claude-flow-swarm` | Launch multi-agent swarm for complex tasks |
| `claude-flow-memory` | Persistent memory across sessions |
| `claude-flow-help` | claude-flow command reference |
| `sparc:orchestrator` | SPARC orchestrator — routes to specialized agents |
| `sparc:coder` | SPARC coding agent |
| `sparc:architect` | SPARC architecture agent |
| `sparc:tdd` | SPARC TDD cycle |
| `sparc:researcher` | SPARC research agent |
| `sparc:debugger` | SPARC debug agent |
| `sparc:reviewer` | SPARC code review agent |
| `sparc-methodology` | Full SPARC dev methodology |
| `swarm-orchestration` | Swarm coordination patterns |
| `swarm-advanced` | Advanced swarm topologies |
| `agentdb-memory-patterns` | Persistent agent memory (AgentDB) |
| `agentdb-vector-search` | Semantic search over memory |
| `agentdb-learning` | 9 reinforcement learning algorithms |
| `pair-programming` | Driver/navigator AI pair programming |
| `skill-builder` | Create new custom skills |
| `github:swarm-pr` | Swarm-based PR management |
| `github:release-swarm` | Automated release coordination |
| `automation:smart-agents` | Smart agent spawning |
| `automation:self-healing` | Self-healing workflow automation |
| `monitoring:swarm-monitor` | Real-time swarm monitoring |
| `optimization:parallel-execute` | Parallel execution optimization |

**Daemon commands (run in terminal):**
```bash
npx claude-flow@alpha daemon start    # Start background workers
npx claude-flow@alpha memory init     # Init memory database
npx claude-flow@alpha swarm init      # Init a swarm
```

---

## Agent Orchestration / Dispatch

| Skill | Trigger |
|-------|---------|
| `dispatching-parallel-agents` | 2+ independent tasks → run concurrently |
| `parallel-agents` | General parallel agent work |
| `agent-orchestrator` | Route tasks to specialized agents |
| `agent-orchestration-multi-agent-optimize` | Optimize multi-agent setups |

**Most useful:** `/dispatching-parallel-agents` — dispatch multiple Claude subagents in parallel for independent subtasks (e.g. fix 3 bugs at once, research 3 topics at once)

---

## Computer Use

| Skill | Trigger |
|-------|---------|
| `computer-use-agents` | Browser/desktop automation via Claude vision |

**Most useful:** `/computer-use-agents` — automate browser tasks (used for n8n setup)

---

## n8n / Workflow Automation

| Skill | Trigger |
|-------|---------|
| `n8n-workflow-patterns` | n8n workflow design patterns |
| `n8n-node-configuration` | Configure specific n8n nodes |
| `n8n-code-javascript` | Write JS code in n8n Code nodes |
| `n8n-expression-syntax` | n8n expression syntax help |
| `n8n-validation-expert` | Validate n8n workflows |
| `n8n-mcp-tools-expert` | n8n MCP integration |
| `make-automation` | Make.com (Integromat) workflows |
| `workflow-automation` | Generic workflow automation |

---

## Instagram / Social

| Skill | Trigger |
|-------|---------|
| `instagram-automation` | Instagram automation patterns |
| `instagram` | Instagram API / general |

---

## General Purpose

| Skill | Trigger |
|-------|---------|
| `deep-research` | Research a topic thoroughly |
| `plan-writing` | Write implementation plans |
| `claude-code-expert` | Claude Code tips + patterns |
| `commit` | Git commit helper |
| `pr-writer` | Write PRs |

---

## How to Invoke

```
/dispatching-parallel-agents    # dispatch skill
/computer-use-agents            # computer use skill
/n8n-workflow-patterns          # n8n skill
```

Or reference by description in a prompt — Claude will auto-invoke the right skill.
