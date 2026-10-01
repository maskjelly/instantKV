# Security

Report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/maskjelly/instantKV/security/advisories/new).
Do not put credentials or sensitive memory in a public issue.

This is an early single-node release. Namespace grants are the authorization
boundary; agent labels are not. Use separate scopes for private agents/projects.
The default Docker host port is loopback-only. Use an SSH tunnel or an HTTPS proxy
for remote clients and keep generated credentials private.

Persisted values are not encrypted by instantKV. Protect the host, volumes and
backups. Deletion does not promise secure physical erasure. Retrieved agent memory
is untrusted reference data; it must not override system instructions or authorize
tools. No arbitrary code execution or plugin loading is offered by this server.

Configuration changes and credential rotation require restart. Preserve the data
volume; never use `docker compose down -v` during an ordinary upgrade.
