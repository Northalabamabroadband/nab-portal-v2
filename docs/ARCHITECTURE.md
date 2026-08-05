# Architecture

NAB Portal v2 is organized as a modular monolith for the first production milestones.

This keeps deployment manageable while enforcing clear boundaries between:

- authentication
- customers
- billing
- TAUC
- UISP
- NOC
- GIS
- field operations
- inventory
- notifications
- analytics
- automation
- audit and security

The architecture can later split high-load modules into independent services without rewriting the public API.
