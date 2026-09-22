---
name: Ledger rewrite
description: Ongoing project to replace the double-entry ledger service with an event-sourced one.
sources: [claude-code, chatgpt]
aliases: [ledger-v2]
updated: "2026-09-18"
kind: area
---

## Status

- [stated] Target: cut over by end of Q4 2026.
- [observed] Repository is a Rust workspace with three crates. <!-- src: claude-code, 2026-09-18 -->

## Decisions

- [stated] Chose Postgres logical replication over a Kafka outbox to limit new infrastructure.
- [inferred] The team is small, probably three to four engineers, based on PR author counts.
