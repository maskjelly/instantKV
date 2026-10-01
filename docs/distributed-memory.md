# Distributed agent memory: design proposal

Status: **proposal, not implemented**. Date: 2026-10-01. Audience: builders and
operators. Owners: instantKV maintainers. This document defines a path from the
working [single-server swarm profile](cloud-agents.md) to independent worker nodes.

## Objective

The goal is to give each agent a copy of shared knowledge and its own local
working memory. When a run ends, it submits the findings it wants to share. A
consolidation service checks those findings before adding them to the next
baseline. Keep the original sources and disagreements visible so the team can
review what changed.

Current code provides durable records, scoped namespaces, conditional revisions
and atomic handoff capsules. It does not provide snapshot manifests, replication,
change feeds, run-completion jobs, automatic summaries or knowledge quality metrics.

## Proposed ownership and flow

1. **Publish baseline.** The canonical knowledge service publishes an immutable manifest with a
   baseline ID, schema version, record content hashes and source revisions.
2. **Seed workers.** Each worker fetches an authorized projection of that manifest
   into a local KV replica. Private writes land in a separate overlay; they do not
   mutate the baseline or another worker's findings.
3. **Work independently.** Local knowledge, scratch and capsules support compaction
   and network outages. The run records which baseline it used.
4. **Finish durably.** The runtime submits a completion envelope and an explicit
   set of shareable changes. Retries use the same run ID and content digest.
   Private records are excluded unless the run explicitly permits export.
5. **Consolidate.** A durable job imports candidates, deduplicates exact content,
   checks provenance and policy, and surfaces disagreements. An optional model
   may propose a summary; acceptance requires validation and source retention.
6. **Publish baseline revision.** Reviewed facts update the canonical knowledge base with conditional
   revisions. A new manifest records the accepted changes. The next swarm starts
   from it. Unfinished or rejected jobs never partially publish a baseline.

This is a proposed distributed knowledge workflow with a canonical publisher.
It is not a promise of a multi-writer consensus database. The first replication
step should use export/import and restartable pull sync; choose consensus only
if availability requirements later require automatic leader failover.

## Proposed interchange schema

These are design shapes, not accepted endpoints or the current record format:

| Object | Proposed fields | Invariant |
|---|---|---|
| BaselineManifest | `baseline_id`, `schema_version`, `created_at`, authorized record descriptors `{key, revision, content_hash}`, `manifest_hash` | Immutable; published only after referenced records are available |
| RunCompletion | `run_id`, `agent_id`, `baseline_id`, `checkpoint_locator`, `delta_hash`, `shareable_changes[]` | Same run ID + digest is idempotent; changed digest is a conflict |
| KnowledgeCandidate | `candidate_id`, `key`, `content`, `source_locators[]`, `observed_at`, `run_id`, `base_revision`, `content_hash`, `visibility` | Sources, origin and sharing policy survive summarization |
| ConsolidationJob | `job_id`, `run_id`, `state`, `attempt`, `lease_deadline`, `accepted[]`, `rejected[]`, `conflicts[]`, `published_baseline_id` | Durable state transitions; expired leases are reclaimable |
| PublishedFact | `key`, `revision`, `content`, `source_locators[]`, `origin_runs[]`, `validated_at`, `supersedes[]` | Conflicting content is reviewed; updates use revision checks |

Job states: `received -> importing -> validating -> awaiting_review -> publishing
-> published`. Failures retain their last durable state and retry metadata.
Transport acknowledgements mean receipt or committed publication explicitly;
they must not imply the other. Model output is untrusted candidate content.

## Compaction and conflict policy

Context compaction and knowledge consolidation have different purposes. A
handoff capsule preserves enough context to continue one task. Consolidation
extracts reusable knowledge from finished runs. It must preserve original source
locators and cannot replace private capsules silently.

Deduplicate exact content first. A change based on an older baseline revision
becomes a conflict when the canonical value changed. Surface both candidates
with their sources; do not silently apply last-writer-wins. Deletions require
explicit tombstones and authorization. Revoked scopes stop future sync/import;
already downloaded replicas require a separate retention/revocation policy.

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
| 3. Completion queue | Duplicate/reordered uploads, interrupted transfer, lease expiry and worker restart never double-publish |
| 4. Reviewed consolidation | Conflicting agent findings remain visible; rejected or unsupported summaries do not enter the canonical knowledge base |
| 5. Distributed pull sync | Offline/reconnect, tombstones, revoked grants and partial baselines behave as documented |
| 6. Knowledge quality metrics | Fixed recall evaluation and quality counters show useful improvements rather than only database growth |

Roll out behind an opt-in protocol version on separate data stores. Keep the
single-node HTTP/MCP contract working. Back up the canonical database and keep
the previous immutable manifest before publishing. Roll back by selecting that
manifest and pausing consolidation; never rewrite worker history to hide a merge.

Open decisions: manifest size/pagination, per-team projections, conflict review
ownership, completed-run retention, tombstone lifetime, model validation policy,
and whether pull-sync availability warrants leader election. Resolve these with
concrete multi-agent workloads before adding a consensus or custom storage layer.
