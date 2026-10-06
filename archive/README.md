# Retired code

This code is retained for historical evidence. It is outside the supported product and website deployment.

`browser-demo/` contains the retired coordinator, recorder and isolated Compose setup.
The current Worker returns HTTP 410 for demo API requests; this archive does not restore that integration.
[Historical architecture](../docs/history/live-demo.md).

Run archive regression checks from the repository root:

```sh
node --test archive/browser-demo/gateway.test.mjs archive/browser-demo/replay-data.test.mjs
```

Reproduction requires a release binary and a new output directory outside this repository:

```sh
INSTANTKV_BIN=/absolute/path/to/instantkv node archive/browser-demo/record.mjs /tmp/new-instantkv-recordings
```

The recorder refuses repository output and existing directories. Never replace a published report with a new run.
Old report hashes describe the original recorder revision; source changes here do not rewrite those reports.
