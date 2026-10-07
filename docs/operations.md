# Operating one node

## Local agent lifecycle

For one agent harness, configure `instantkv mcp-local --dir /absolute/path/memory`.
The harness starts the process when it connects. The process opens a loopback
HTTP listener and closes it when the MCP input stream ends. The data directory
stays on disk. Restart the harness with the same directory to use its records.
You do not need a separate background daemon for this mode.

One data directory has one active database owner. Do not point two running
`mcp-local` processes, or `instantkv start` and `mcp-local`, at the same
directory. For concurrent harnesses, run one `instantkv start` service and
connect each harness through `instantkv mcp`. See [Connect an agent](agents.md).

For the default local profile, stop the harness before a backup. Copy the whole
memory directory to a private location, including `instantkv.toml` and
`.instantkv/credentials.env`. If `storage.data_dir` points outside that
directory, back up that path too. Start the harness and fetch one known memory
to check the copy did not interrupt normal use. Test restores in an isolated
directory with the same binary version. Protect credentials and backup copies.

If tools do not connect, check the absolute binary and data paths, the harness
MCP status, and stderr from its MCP process. If the database is busy, stop the
other owner or use the shared server mode. If a write fails, check free disk
space and permissions before retrying. The local MCP process does not restart a
crashed harness; the harness controls its lifecycle.

## Docker setup and health

`./scripts/quickstart.sh` builds an image, initializes a new volume and starts the service with health checks.
It then runs `doctor`. Existing configuration and data remain unchanged.
For the source MVP, set `INSTANTKV_BUILD_SOURCE=source-build` during setup.

The container uses UID 10001, dropped capabilities and a read-only root filesystem.
A small `/tmp` mount holds temporary files.
Only clients on the host can connect directly.

```sh
docker compose ps
docker compose logs --tail 50 instantkv
./scripts/kv.sh doctor
./scripts/kv.sh stats knowledge
```

`/healthz` reports a running service after startup validation.
It does not test disk writes on each request.
`/metrics` requires a stats grant and reports aggregate requests and failures.
Detailed latency, expiry-lag and storage-health metrics are planned.

## Remote access

Prefer loopback plus an SSH tunnel for a personal server. Example VPS port 8095:

```sh
INSTANTKV_PORT=8095 ./scripts/quickstart.sh
ssh -N -L 8080:127.0.0.1:8095 your-vps
```

For remote clients, terminate TLS at your reverse proxy.
Keep scoped API tokens enabled.
Keep disabled authentication restricted to loopback.
Never store credentials in repository configuration or request URLs.

## Offline backup and restore

Stop the only process using the data file before copying it. The helper briefly
stops the Compose service, copies all state, and restarts it:

```sh
./scripts/backup.sh /absolute/private/instantkv-backup
```

The backup contains configuration, credentials and the database.

Keep it private and protect it with your encrypted backup system.
If the helper fails, inspect the partial backup before retrying.

The helper refuses an existing destination. Online snapshots and export are planned.

The `state.tar` archive preserves file ownership metadata.
It uses Docker's [tar-stream copy mode](https://docs.docker.com/reference/cli/docker/container/cp/).

Verify a known checkpoint in a separate temporary volume:

```sh
./scripts/restore-drill.sh /absolute/private/instantkv-backup YOUR_SAVED_CHECKPOINT
# Swarm: specify the private checkpoint namespace.
./scripts/restore-drill.sh /absolute/private/instantkv-backup alpha-first-handoff alpha_checkpoints
```

The restore helper creates a temporary volume and assigns UID 10001 ownership.
It starts an isolated loopback container, verifies health and restores the checkpoint.
It then removes the temporary container and volume.
The backup and live instance remain.
The optional third argument selects the checkpoint namespace; its default is `checkpoints`.

A missing or unreadable checkpoint fails the test.
Use the same binary version as the backup.
Keep the backup until verification succeeds.
Never open one data file with two processes.

## Retention and upgrades

Knowledge has no default expiry. Scratch expires and can evict records within its quota.
`delete-checkpoint ID` removes an old checkpoint. The latest checkpoint for each session is protected.
Final-session retirement is planned. Quotas count checkpoint bundles and pointers.

1. Save an offline backup.
2. Build the reviewed source commit.
3. Run `docker compose up -d --wait`.
4. Run `doctor`.
5. Retrieve a known record.
6. Restore a known checkpoint.

Configuration loads at startup. Credential rotation requires a restart.
The server rejects incompatible namespace changes instead of silently discarding data.
Older binaries do not maintain the MVP memory indexes.
To downgrade from the MVP, restore the backup made before the upgrade.

A submitted write can commit after an HTTP timeout.
Inspect its revision, or retry the same checkpoint ID and payload.

Storage errors do not return success. Resolve disk or permission failures before retrying.
Process-restart recovery is tested.
Disk-full, power-loss and kill-during-commit tests remain planned.
