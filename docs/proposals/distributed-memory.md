# Distributed agent memory: design proposal

Status: proposal, not implemented. Updated: 2026-10-03.
Audience: builders and operators. Owners: instantKV maintainers.
This design extends the working [single-server swarm](../cloud-agents.md) to independent worker nodes.

## Objective

Each agent starts from a selected historical memory snapshot and gets a private branch.
Agents can choose the same or different snapshots.
They can submit findings during a run and follow accepted shared updates.
A final submission closes the run. Sources and disagreements remain visible.

Two agents start from snapshot 3. One investigates a build failure; the other updates the setup guide.
The first publishes a verified fix. The second receives it before the first run ends.
Private notes remain private, and snapshot 3 remains unchanged.

![Proposed snapshot branches and continuous shared updates](../assets/memory-branches.svg)

Current code provides durable records, namespace grants, conditional writes and atomic checkpoints.
Snapshots, replication, change feeds, completion jobs and automatic summaries remain proposed.

## Proposed ownership and flow

1. **Publish a baseline.** The canonical service publishes an immutable manifest.
   It includes a baseline ID, schema version, record hashes and source revisions.
2. **Create a branch.** A worker selects an authorized retained snapshot and records its parent, agent and task.
   It stores private writes in a separate overlay. Those writes do not change the baseline or sibling branches.
3. **Work locally.** Local records, scratch and checkpoints support context resets and network outages.
4. **Submit findings.** Each batch includes its branch ID, sequence and content digest.
   Acknowledgement follows durable receipt. Identical retries are idempotent; different content at the same sequence conflicts.
   Private records require explicit export permission. The final batch records the last acknowledged sequence.
5. **Review findings.** A durable job deduplicates content, verifies sources and exposes conflicts.
   An optional model can propose a summary; acceptance requires validation and retained sources.
6. **Publish updates.** Accepted facts use conditional revisions and form a new manifest.
   Failed or rejected jobs cannot partially publish a baseline.
7. **Follow updates.** Workers apply accepted facts to a separate shared-updates overlay.
   The parent snapshot and private branch remain unchanged. Offline workers resume from a saved cursor.

The design uses one canonical publisher. It does not promise a multi-writer consensus database.
The first replication stage uses export/import and restartable pull synchronization.
Automatic leader failover needs separate availability requirements.

## Proposed interchange schema

These are design shapes, not accepted endpoints or the current record format:

| Object             | Proposed fields                                                                                                                                             | Invariant                                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| BaselineManifest   | `baseline_id`, `schema_version`, `created_at`, authorized record descriptors `{key, revision, content_hash}`, `manifest_hash`                               | Immutable; published only after referenced records are available                                                  |
| BranchManifest     | `branch_id`, `parent_snapshot_id`, `agent_id`, `task`, `created_at`, `sharing_policy`, `last_submitted_sequence`, `shared_feed_cursor`                      | Parent is pinned; independent private overlay; only authorized historical snapshots can be forked                 |
| FindingBatch       | `branch_id`, `sequence`, `content_hash`, `changes[]`, `source_locators[]`, `base_revisions[]`                                                               | Same branch + sequence + digest is idempotent; changed digest conflicts; durable receipt precedes acknowledgement |
| SharedEvent        | `event_id`, `sequence`, `scope`, `kind`, `key`, `revision`, `origin_branch`, `published_baseline_id`                                                        | Canonical publisher assigns order; durable replay; consumers persist cursor only after applying an event          |
| AgentPresence      | `agent_id`, `branch_id`, `task`, `state`, `lease_deadline`, `last_published_sequence`, `observed_feed_cursor`                                               | Authorized metadata only; expired lease means stale/unknown, never proof of completion                            |
| RunCompletion      | `run_id`, `branch_id`, `agent_id`, `baseline_id`, `checkpoint_locator`, `last_submitted_sequence`, `delta_hash`, `shareable_changes[]`                      | Same run ID + digest is idempotent; changed digest is a conflict; completion waits for preceding finding batches  |
| KnowledgeCandidate | `candidate_id`, `key`, `content`, `source_locators[]`, `observed_at`, `run_id`, `base_revision`, `content_hash`, `visibility`                               | Sources, origin and sharing policy survive summarization                                                          |
| ConsolidationJob   | `job_id`, `run_id`, `branch_id`, `batch_sequence`, `state`, `attempt`, `lease_deadline`, `accepted[]`, `rejected[]`, `conflicts[]`, `published_baseline_id` | Durable state transitions; expired leases are reclaimable                                                         |
| PublishedFact      | `key`, `revision`, `content`, `source_locators[]`, `origin_runs[]`, `validated_at`, `supersedes[]`                                                          | Conflicting content is reviewed; updates use revision checks                                                      |

Job states: `received → importing → validating → awaiting_review → publishing → published`.
Failures retain the last durable state and retry metadata.
An acknowledgement must specify receipt or committed publication. The two meanings are not interchangeable.
Model output remains untrusted candidate content.

## Compaction and conflict policy

Compaction preserves enough context to continue one task.
Consolidation creates reusable knowledge from submitted findings.
It preserves source locators and cannot silently replace private checkpoints.

Exact duplicate content is removed first. A candidate conflicts if its base revision no longer matches the canonical record.
Both candidates and sources remain visible for review.
Deletions require explicit tombstones and authorization.
Revoked grants stop future sync/import; downloaded replicas need a separate retention and revocation policy.

## Continuous sync and peer awareness

Findings can enter review during a run or at completion.
Pending candidates are visible only to authorized reviewers. Acceptance publishes a canonical revision and durable event.
Workers discover events through bounded polling or a stream.
An open or reconnected socket does not prove that a worker is current.

The event log provides ordered replay, event IDs and revision tests.
Clients accept duplicates and save their cursor only after applying an update.
An expired cursor requires a fresh authorized snapshot and events after its watermark.
Tombstones use the same ordering and permission rules as writes.
Publication jobs run independently of subscriptions.
Slow consumers disconnect when their bounded queues fill and resume through replay.

The parent snapshot remains immutable. Accepted updates use a separate overlay.
The agent can inspect changes before using them.
A finding based on a superseded revision enters conflict review. Synchronization cannot overwrite private work.
A baseline change is an explicit rebase with recorded lineage.

Peer status lists permitted tasks, branch state and observed update sequences.
Renewable leases identify stale peers. Presence does not expose private notes, credentials or unreviewed findings.
Subscriptions and replay recheck grants; revoked access stops delivery.
Offline agents can fall behind. The design promises resumable convergence, not immediate agreement.

## Knowledge quality metrics

Quality metrics record verified facts, source coverage, freshness and unresolved conflicts.
A fixed task set measures recall changes between baselines.
More stored text does not establish better knowledge.
Current namespace stats report only entries, bytes and revisions.

## Failure boundaries and rollout gates

| Stage                        | Required evidence before shipping                                                                                                             |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Explicit export/import    | Round trip authorized records with hashes, revisions and sources; deny private-scope export                                                   |
| 2. Baseline + overlay        | Two workers start from one manifest, write independently, and retain the correct base revision                                                |
| 2a. Historical branches      | Workers fork the same and different retained snapshots; lineage survives restart; unauthorized or expired snapshots are denied                |
| 3. Completion queue          | Duplicate/reordered uploads, interrupted transfer, lease expiry and worker restart never double-publish                                       |
| 3a. Incremental findings     | A finding is reviewed and published before its run ends; retries and final flush neither drop nor double-publish changes                      |
| 4. Reviewed consolidation    | Conflicting agent findings remain visible; rejected or unsupported summaries do not enter the canonical knowledge base                        |
| 5. Distributed pull sync     | Offline/reconnect, tombstones, revoked grants and partial baselines behave as documented                                                      |
| 5a. Connected agents         | Disconnect/replay, duplicate events, expired cursors, slow consumers and lease expiry preserve private work and expose stale peers accurately |
| 6. Knowledge quality metrics | Fixed recall evaluation and quality counters show useful improvements rather than only database growth                                        |

Rollout uses an optional protocol version and separate data stores.
The existing single-node HTTP/MCP contract remains available.
Before publication, operators back up the canonical database and retain the previous manifest.
Rollback selects that manifest and pauses consolidation. Worker history remains intact.

Open decisions include manifest size, pagination, team scopes and conflict-review ownership.
Retention policies must cover completed runs, snapshots, tombstones and event replay.
Model validation, rebase policy, peer visibility and leader election also need decisions.
Real multi-agent workloads must guide those choices.
