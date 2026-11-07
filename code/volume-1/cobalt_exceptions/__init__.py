"""Cobalt Freight's exception-management application: the package the project chapters extend.

Layers, each importing only the ones below it:

- cli: the entry points (`cobalt investigate`, `cobalt decide`, ...).
- agents: Microsoft Agent Framework adapters (the workflow, the agent, its tools, provider,
  middleware and telemetry). services: the case lifecycle and the approval gate. Neither
  imports the other.
- systems: Cobalt's systems of record, as stand-ins behind the clients a real system would have.
- domain: contracts, the procedure's rules, the lifecycle and the approval policy. No framework.
"""
