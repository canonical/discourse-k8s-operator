# Reference

The Discourse charm exposes a layered set of configuration surfaces, integration points, and architectural primitives that govern how the application behaves within a Juju-managed Kubernetes environment -- from operational configuration and action automation through connectivity and external access to the plugin ecosystem and versioning policy.

## Configuration and operations

Every operational decision — from tuning runtime behavior to automating administrative tasks — depends on a clear mapping between the charm's configuration options, its available actions, and the internal architecture that connects them.

* [Actions]
* [Configurations]
* [Charm architecture]

## Connectivity

Integrating Discourse into a broader service mesh requires precise knowledge of the charm's relation interfaces and the mechanisms that control how external traffic reaches the application.

* [Integrations]
* [External access]

## Ecosystem

Plugin availability and versioning policy directly affect feature compatibility across upgrades. Evaluating these constraints before making changes prevents unexpected regressions in production.

* [Plugins]
* [Versioning]

<!--Links-->

[Actions]: actions.md
[Charm architecture]: charm-architecture.md
[Configurations]: configurations.md
[External access]: external-access.md
[Integrations]: integrations.md
[Plugins]: plugins.md
[Versioning]: versioning.md
