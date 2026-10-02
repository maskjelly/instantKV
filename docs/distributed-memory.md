# Distributed agent memory: design proposal

Status: **proposal, not implemented**. Updated: 2026-10-02. Audience: builders and
operators. Owners: instantKV maintainers. This document defines a path from the
working [single-server swarm profile](cloud-agents.md) to independent worker nodes.

## Objective

Start agents from a chosen historical memory snapshot. Give several agents the
same starting point, or let each pick a different one. Each agent gets a private
branch and can explore its own direction. While they work, they can submit
findings and follow accepted updates from the shared knowledge base. A final
submission closes the run. Keep sources and disagreements visible throughout.

For example, two agents start from snapshot 3: one investigates a failing build,
the other updates the setup guide. The first publishes a verified fix. The second
receives that update and corrects the guide without waiting for the first run to
end. Their private notes stay private. Historical snapshot 3 remains unchanged.

![Proposed snapshot branches and continuous shared updates](assets/memory-branches.svg)

Current code provides durable records, scoped namespaces, conditional revisions
and atomic handoff capsules. It does not provide snapshot manifests, replication,
change feeds, run-completion jobs, automatic summaries or knowledge quality metrics.

## Proposed ownership and flow

1. **Publish baseline.** The canonical knowledge service publishes an immutable manifest with a
   baseline ID, schema version, record content hashes and source revisions.
2. **Fork a snapshot.** Select any retained, authorized historical baseline.
   Record a branch ID, parent snapshot, agent and task. Several branches can share
   a parent without sharing private writes. Each worker fetches a projection
   into a local KV replica. Private writes land in a separate overlay; they do not
   mutate the baseline or another worker's findings.
3. **Work independently.** Local knowledge, scratch and capsules support compaction
   and network outages. The run records which baseline it used.
4. **Share during the run.** Submit explicit batches of shareable changes with a
   branch ID, monotonically increasing sequence and content digest. Receipt is
   durable before acknowledgement. Retrying an identical batch is idempotent;
   reusing its sequence with different content is a conflict. Private records
   are excluded unless the run explicitly permits export. Completion submits a
   final batch and the last acknowledged sequence so interrupted runs can resume.
5. **Consolidate.** A durable job imports candidates, deduplicates exact content,
   checks provenance and policy, and surfaces disagreements. An optional model
   may propose a summary; acceptance requires validation and source retention.
6. **Publish baseline revision.** Reviewed facts update the canonical knowledge base with conditional
   revisions. A new manifest records the accepted changes. The next swarm starts
   from it. Unfinished or rejected jobs never partially publish a baseline.
7. **Follow accepted updates.** Connected workers follow an authorized change
   feed and apply accepted facts to a separate shared-updates overlay. Their
   pinned parent snapshot and private branch remain intact. Offline workers
   replay from a saved cursor; streams only notify them that committed events
   are available. Peers can see authorized branch status and publication progress.

This is a proposed distributed knowledge workflow with a canonical publisher.
It is not a promise of a multi-writer consensus database. The first replication
step should use export/import and restartable pull sync; choose consensus only
if availability requirements later require automatic leader failover.

## Proposed interchange schema

These are design shapes, not accepted endpoints or the current record format:

| Object | Proposed fields | Invariant |
|---|---|---|
| BaselineManifest | `baseline_id`, `schema_version`, `created_at`, authorized record descriptors `{key, revision, content_hash}`, `manifest_hash` | Immutable; published only after referenced records are available |
| BranchManifest | `branch_id`, `parent_snapshot_id`, `agent_id`, `task`, `created_at`, `sharing_policy`, `last_submitted_sequence`, `shared_feed_cursor` | Parent is pinned; independent private overlay; only authorized historical snapshots can be forked |
| FindingBatch | `branch_id`, `sequence`, `content_hash`, `changes[]`, `source_locators[]`, `base_revisions[]` | Same branch + sequence + digest is idempotent; changed digest conflicts; durable receipt precedes acknowledgement |
| SharedEvent | `event_id`, `sequence`, `scope`, `kind`, `key`, `revision`, `origin_branch`, `published_baseline_id` | Canonical publisher assigns order; durable replay; consumers persist cursor only after applying an event |
| AgentPresence | `agent_id`, `branch_id`, `task`, `state`, `lease_deadline`, `last_published_sequence`, `observed_feed_cursor` | Authorized metadata only; expired lease means stale/unknown, never proof of completion |
| RunCompletion | `run_id`, `branch_id`, `agent_id`, `baseline_id`, `checkpoint_locator`, `last_submitted_sequence`, `delta_hash`, `shareable_changes[]` | Same run ID + digest is idempotent; changed digest is a conflict; completion waits for preceding finding batches |
| KnowledgeCandidate | `candidate_id`, `key`, `content`, `source_locators[]`, `observed_at`, `run_id`, `base_revision`, `content_hash`, `visibility` | Sources, origin and sharing policy survive summarization |
| ConsolidationJob | `job_id`, `run_id`, `branch_id`, `batch_sequence`, `state`, `attempt`, `lease_deadline`, `accepted[]`, `rejected[]`, `conflicts[]`, `published_baseline_id` | Durable state transitions; expired leases are reclaimable |
| PublishedFact | `key`, `revision`, `content`, `source_locators[]`, `origin_runs[]`, `validated_at`, `supersedes[]` | Conflicting content is reviewed; updates use revision checks |

Job states: `received -> importing -> validating -> awaiting_review -> publishing
-> published`. Failures retain their last durable state and retry metadata.
Transport acknowledgements mean receipt or committed publication explicitly;
they must not imply the other. Model output is untrusted candidate content.

## Compaction and conflict policy

Context compaction and knowledge consolidation have different purposes. A
handoff capsule preserves enough context to continue one task. Consolidation
extracts reusable knowledge from findings shared during or after runs. It must preserve original source
locators and cannot replace private capsules silently.

Deduplicate exact content first. A change based on an older baseline revision
becomes a conflict when the canonical value changed. Surface both candidates
with their sources; do not silently apply last-writer-wins. Deletions require
explicit tombstones and authorization. Revoked scopes stop future sync/import;
already downloaded replicas require a separate retention/revocation policy.

## Continuous sync and peer awareness

Findings may enter review during a run as well as at completion. A received
candidate is visible as pending only to authorized reviewers; it is not yet a
shared fact. Acceptance publishes a canonical revision and a durable event.
Workers discover new events through bounded polling or a streaming connection.
Neither an open socket nor a reconnect alone proves that they are up to date.

The canonical event log provides ordered replay, event IDs and revision checks.
Clients tolerate duplicates, save their cursor after applying updates, and retry
after disconnection. An expired replay cursor requires a fresh authorized
snapshot plus events after its watermark. Tombstones carry the same ordering and
permission checks as writes. Publication jobs run independently of subscriptions.
Bounded subscriber queues disconnect slow consumers and let them catch up later.

Keep the parent snapshot immutable. Accepted updates go into a distinct overlay,
so an agent can inspect what changed and choose when to use it. A local finding
based on a superseded revision enters conflict review; sync cannot overwrite it.
Switching the branch's baseline is an explicit rebase with recorded lineage.

Peer awareness means a scoped roster of tasks, branch state and the last update
each agent has observed. Use renewable leases to mark stale peers. Do not expose
private notes, credentials or unreviewed findings through presence. Recheck grants
on subscription and replay, and stop delivery when access is revoked. Agents can
lag while offline; the first version promises resumable convergence, not
instantaneous agreement between every worker.

## Knowledge quality metrics

Track checked facts, source coverage, freshness and unresolved conflicts. Test
recall against a fixed set of tasks and show what changed between baselines.
Record validation dates. More stored text alone doesn't show better knowledge;
the current namespace stats endpoint counts only entries, bytes and revisions.

## Failure boundaries and rollout gates

| Stage | Required evidence before shipping |
|---|---|
| 1. Explicit export/import | Round trip authorized records with hashes, revisions and sources; deny private-scope export |
| 2. Baseline + overlay | Two workers start from one manifest, write independently, and retain the correct base revision |
| 2a. Historical branches | Workers fork the same and different retained snapshots; lineage survives restart; unauthorized or expired snapshots are denied |
| 3. Completion queue | Duplicate/reordered uploads, interrupted transfer, lease expiry and worker restart never double-publish |
| 3a. Incremental findings | A finding is reviewed and published before its run ends; retries and final flush neither drop nor double-publish changes |
| 4. Reviewed consolidation | Conflicting agent findings remain visible; rejected or unsupported summaries do not enter the canonical knowledge base |
| 5. Distributed pull sync | Offline/reconnect, tombstones, revoked grants and partial baselines behave as documented |
| 5a. Connected agents | Disconnect/replay, duplicate events, expired cursors, slow consumers and lease expiry preserve private work and expose stale peers accurately |
| 6. Knowledge quality metrics | Fixed recall evaluation and quality counters show useful improvements rather than only database growth |

Roll out behind an opt-in protocol version on separate data stores. Keep the
single-node HTTP/MCP contract working. Back up the canonical database and keep
the previous immutable manifest before publishing. Roll back by selecting that
manifest and pausing consolidation; never rewrite worker history to hide a merge.

Open decisions: manifest size/pagination, per-team projections, conflict review
ownership, completed-run retention, tombstone lifetime, model validation policy,
historical snapshot retention, event replay windows, rebase policy, presence
visibility, and whether pull-sync availability warrants leader election. Resolve these with
concrete multi-agent workloads before adding a consensus or custom storage layer.
