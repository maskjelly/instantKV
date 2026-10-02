Hey Sigil, I heard you guys are going all in on local LLMs. I've built instantKV, a small memory layer in Rust that could fit alongside Underdog.

It lets agents save facts, preferences and task checkpoints locally, then find them by topic, time or keywords after a fresh session or restart. One binary, no cloud dependency, with MCP tools, configurable limits and custom metadata. The Rust core can run inside an app too.

The source MVP is working, with Mac benchmarks and Linux ARM64 CI. Native phone integration is what I'd like to work on next.

Would you be open to a quick chat about whether this fits what you're building? I'd like to work with you guys on the memory side.

https://github.com/maskjelly/instantKV
