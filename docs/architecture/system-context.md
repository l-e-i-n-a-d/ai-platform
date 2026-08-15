# System Context

The AI Engineering Platform sits between engineers and the organization's engineering systems.

```text
Engineers
   |
   v
AI Engineering Platform          runs locally on the engineer's machine in V1
   |
   +--> Jira
   +--> Confluence
   +--> GitHub
   +--> AI Model Providers
   |
   +--> Local Executor           containerised workspaces on the same machine
```

The platform coordinates engineering workflows but does not replace Jira, Confluence or GitHub.
