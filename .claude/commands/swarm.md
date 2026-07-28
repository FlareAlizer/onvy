---
description: Explicitly orchestrate a ruflo swarm for a parallelizable task
argument-hint: "<task> [--topology hierarchical|mesh]"
---
Orchestrate via the `ruflo-orchestration` skill: $ARGUMENTS.
Pick topology (hierarchical for delivery, mesh for open research). In ONE message: MCP swarm_init + spawn ALL agents via Task tool with self-contained briefs. Wait for results (no status polling). Merge outputs into a single report and store durable findings in memory.
