use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Record {
    pub value: Vec<u8>,
    pub revision: u64,
    pub written_at_ms: u64,
    pub expires_at_ms: Option<u64>,
    pub(crate) inserted: u64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Usage {
    pub entries: u64,
    pub bytes: u64,
    pub revision: u64,
}

#[derive(Debug, Clone, Copy, Default)]
pub enum Condition {
    #[default]
    Any,
    Absent,
    Revision(u64),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecordInfo {
    pub key: String,
    pub revision: u64,
    pub bytes: usize,
    pub expires_at_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Page {
    pub items: Vec<RecordInfo>,
    pub next_cursor: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Capsule {
    pub goal: String,
    pub summary: String,
    #[serde(default)]
    pub constraints: Vec<String>,
    #[serde(default)]
    pub decisions: Vec<String>,
    #[serde(default)]
    pub open_tasks: Vec<String>,
    pub next_action: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryReference {
    pub namespace: String,
    pub key: String,
    pub revision: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CheckpointRequest {
    pub id: String,
    pub agent_id: String,
    pub session_id: String,
    pub expected_latest_revision: Option<u64>,
    pub capsule: Capsule,
    #[serde(default)]
    pub references: Vec<MemoryReference>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointReceipt {
    pub id: String,
    pub revision: u64,
    pub latest_revision: u64,
    pub locator: String,
    pub is_latest: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReferenceStatus {
    Available,
    Stale,
    Missing,
    Forbidden,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResolvedReference {
    #[serde(flatten)]
    pub reference: MemoryReference,
    pub status: ReferenceStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Restore {
    pub checkpoint_id: String,
    pub revision: u64,
    pub latest_revision: u64,
    pub capsule: Capsule,
    pub references: Vec<ResolvedReference>,
}
