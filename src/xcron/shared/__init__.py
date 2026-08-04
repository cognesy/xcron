"""Strict leaf utilities every xcron module may depend on.

`libs/shared/` is not a capability and holds no decision of its own. It carries
logging configuration and the structlog wiring that six owners need, plus the
packaged logging resource that configuration reads. Nothing here may run a
workflow, persist capability state, import a capability, or reach for a service
locator. Adding a module here is a recorded architectural decision, not a
convenience.
"""
