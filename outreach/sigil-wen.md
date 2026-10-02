Hey Sigil, I heard you guys are going all in on local LLMs. I've been working on instantKV, a local-first memory layer in Rust that could fit alongside what you're building.

It lets agents save preferences, facts and task checkpoints on their own machine, then find memory by topic, time or keywords after a fresh session or restart. One binary, no cloud calls or separate database, with simple MCP tools, configurable limits and custom metadata. The Rust core can be embedded directly. Apple Silicon is tested today; native phone integration is what I'd like to work on next.

Would you be open to a quick chat about whether this could fit Underdog? I'd love to work with you guys on the memory side.

https://github.com/maskjelly/instantKV
