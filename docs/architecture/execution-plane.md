# Execution Plane

The execution plane runs agent engineering workloads on AKS.

Workspaces should be isolated and ephemeral where practical.

Typical capabilities include:

- Git checkout
- Java/Quarkus tooling
- Python tooling
- Node/Angular tooling
- Helm
- kubectl
- tests
- static analysis
- CI-related tooling

The control plane should not directly execute arbitrary repository commands.
