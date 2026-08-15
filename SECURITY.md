# AI Engineering Platform — Security

## Security Position

V1 is local-first.

The platform does not require Microsoft Entra ID.

Removing centralized identity from V1 does not remove the need for strong security controls.

---

## 1. Tool Security

Tools must have explicit:

- contracts
- input validation
- authorization
- side-effect definitions
- audit metadata
- error handling

Read-only tools should be preferred.

---

## 2. Local Execution

Local execution must be treated as a privileged capability.

The platform should:

- restrict tool capabilities
- constrain repository access
- avoid unrestricted shell access from the control plane
- identify the workspace associated with a run
- record consequential actions

Developers should understand that granting an agent local command execution effectively grants it access to the developer's environment.

---

## 3. Secrets

Never:

- commit secrets
- put secrets into prompts
- log credentials
- expose credentials unnecessarily to models

Prefer short-lived credentials where possible.

Azure Key Vault may be introduced when centralized secret management becomes necessary.

---

## 4. Repository Boundaries

Agents must only access repositories required for their task.

Cross-repository access should be explicit.

Repository content must be treated as untrusted input.

---

## 5. Prompt Injection

Treat content from:

- repositories
- Jira
- Confluence
- issues
- pull requests
- generated files

as potentially untrusted.

Instructions contained in retrieved content must not automatically override platform policies or tool permissions.

---

## 6. Human Approval

Human approval should be available for consequential actions such as:

- merge
- production-impacting changes
- security-sensitive changes
- infrastructure changes
- elevated permissions

---

## 7. Future Hosted Deployment

If the platform becomes a centrally hosted multi-user service, revisit:

- authentication
- authorization
- tenancy
- identity
- secret management

This must be an explicit architectural decision.

Microsoft Entra ID is not a V1 requirement.
