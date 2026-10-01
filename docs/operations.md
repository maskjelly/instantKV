# Operating one node

## Docker setup and health

`./scripts/quickstart.sh` builds the image, initializes a new volume once, starts
with health checks, and runs `doctor`. Existing config/data are never overwritten.
The process is UID 10001, capabilities are dropped, the root filesystem is read
only, and `/tmp` is a small disposable mount. Host access is loopback-only.

```sh
docker compose ps
docker compose logs --tail 50 instantkv
./scripts/kv.sh doctor
./scripts/kv.sh stats knowledge
```

`/healthz` reports a running service after startup config, credentials and database
validation; it does not probe disk writes on every check. `/metrics` requires a
stats grant and exports aggregate request/failure counters. Detailed latency,
expiry-lag and storage-health metrics are planned.

## Remote access

Prefer loopback plus an SSH tunnel for a personal server. Example VPS port 8095:

```sh
INSTANTKV_PORT=8095 ./scripts/quickstart.sh
ssh -N -L 8080:127.0.0.1:8095 your-vps
```

For external multi-user deployment, terminate TLS at your reverse proxy and keep
scoped API tokens enabled. Do not expose disabled-auth mode beyond loopback.
Credentials never belong in repository config or request query strings.

## Offline backup and restore

Stop the only process using the data file before copying it. The helper briefly
stops the Compose service, copies all state, and restarts it:

```sh
./scripts/backup.sh /absolute/private/instantkv-backup
```

The backup contains config, credentials and the database: keep it private and
protect it with your existing encrypted backup system. If the helper fails, inspect
and remove the partial backup before retrying. It refuses an existing destination.
An online snapshot/export API is not implemented.

The backup is `state.tar`, retaining ownership metadata rather than assigning
all files to the host's copy user. This uses Docker's documented
[tar-stream copy mode](https://docs.docker.com/reference/cli/docker/container/cp/).

Verify a known checkpoint in a separate temporary volume:

```sh
./scripts/restore-drill.sh /absolute/private/instantkv-backup YOUR_SAVED_CHECKPOINT
# Swarm: specify the private checkpoint namespace.
./scripts/restore-drill.sh /absolute/private/instantkv-backup alpha-first-handoff alpha_checkpoints
```

The helper extracts into a new volume, sets ownership for UID 10001, starts an
isolated loopback-only container, checks health, restores the checkpoint, and
removes its temporary container/volume. The archive and live instance are retained.
The optional third argument selects a checkpoint namespace; it defaults to
`checkpoints` for the single-agent profile.
A missing or unreadable checkpoint fails the drill. Use the same binary version;
keep the original backup until verification passes. Never open one data file with
two processes.

## Retention and upgrades

Knowledge has no default expiry. Delete deliberately; scratch expires and can
evict within quota. Old checkpoints can be pruned with `delete-checkpoint ID`;
the latest per session is protected. Final-session retirement is future work.
A namespace's quota includes its checkpoint pointer and bundle records.

Back up, build a reviewed commit, then `docker compose up -d --wait`. Check
`doctor`, recall known data and restore a known capsule. Config loads on startup;
credential rotation needs a restart. Storage format is versioned; incompatible
namespace mode/purpose/removal changes are rejected instead of silently losing data.

On HTTP timeouts, a submitted write may still commit. Inspect the revision or
retry the exact checkpoint ID and payload. On storage errors no success response
is sent; resolve disk/permission problems before retrying. Process-restart recovery
is tested; broad disk-full, power-loss and kill-during-commit fault testing remains
on the roadmap.
