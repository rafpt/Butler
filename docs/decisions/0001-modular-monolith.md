# ADR 0001: Start as a policy-gated modular monolith

- Status: accepted
- Date: 2026-06-29

## Decision

Butler will start as one Python process and one SQLite database with dependency boundaries between
domain, services, policies, adapters, and interfaces.

## Consequences

- Local development, backup, and debugging remain simple.
- Domain tests need no model, API, or network.
- Integrations can evolve independently behind ports.
- Cross-module imports must flow inward; interfaces and integrations may depend on services, but
  core code must not depend on them.
