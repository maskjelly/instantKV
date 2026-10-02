// Synthetic fixtures shared by live storage, recorder and integrity checks.
export const topics = ["preferences", "project", "decisions", "tasks"];
export const eventBase = 1790985600000; // 2026-10-03 00:00 UTC; synthetic event clock.
export const namespace = "demo_memories";
export const defaultContent =
  "Prefer Rust for local tools. Keep source references with each decision.";
export const memoryKey = (session, index) =>
  "run/" + session.id + "/memory/" + String(index).padStart(6, "0");
export const sessionTag = (session, tag) =>
  "run-" + session.id + (tag ? "-" + tag : "");
export function memoryInput(session, index) {
  return {
    content: (
      session.content +
      " entry-" +
      String(index).padStart(6, "0")
    ).padEnd(session.valueBytes, " context retained"),
    topic: topics[index % topics.length],
    tags: [
      sessionTag(session),
      sessionTag(session, index % 2 ? "offline" : "local"),
    ].sort(),
    occurred_at_ms: eventBase + index * 60000,
    metadata: {
      record_id: index,
      source: "synthetic",
      device: "local-agent",
      kind: "fixture",
    },
  };
}
export function expectedMemory(session, index) {
  return { _instantkv_memory: 1, ...memoryInput(session, index) };
}
