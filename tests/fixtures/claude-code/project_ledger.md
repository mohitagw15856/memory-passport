---
name: project-ledger
description: Ledger rewrite at /projects/ledger; Rust workspace; cut-over Q4 2026
metadata:
  node_type: memory
  type: project
  modified: 2026-09-01T10:00:00.000Z
---

Ledger rewrite lives at `/projects/ledger`. It is a Rust workspace with three crates.
Target cut-over is the end of Q4 2026.

- Chose Postgres logical replication over a Kafka outbox.
