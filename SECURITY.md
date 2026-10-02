# Security

Report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/maskjelly/instantKV/security/advisories/new).
Do not put credentials or sensitive memory in a public issue.

The service uses one node. Namespace grants define API access boundaries; agent labels do not.
Use separate namespaces for private agents or projects.
The Docker host port is loopback-only by default.
For remote clients, use an SSH tunnel or HTTPS proxy.
Keep generated credentials private.

instantKV does not encrypt stored values or securely erase deleted disk pages.
Protect the host, volumes and backups.
Treat retrieved memory as untrusted reference data.
Never let it override system instructions or authorize tools.
The server does not execute uploaded code or plugins.

Configuration changes and credential rotation require a restart.
Keep the data volume during upgrades. Never use `docker compose down -v` for an ordinary upgrade.

Before an MVP upgrade, make an offline backup.
Older writers do not maintain the MVP indexes. To downgrade, restore the pre-upgrade backup.
