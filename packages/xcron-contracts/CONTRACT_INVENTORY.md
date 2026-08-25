# Contract inventory

<!-- markdownlint-disable MD013 -->

This is the canonical vocabulary shared by the SDK and independently installed
providers. The metadata-only aggregate distribution contains no compatibility
types; providers must not invent a parallel type.

| Product concern | Canonical contract module | Owning distribution |
| --- | --- | --- |
| manifest values and normalization identities | `xcron.contracts.domain` | contracts + manifest/scheduler providers |
| invocation options and settings | `xcron.contracts.domain` | contracts + SDK host |
| workspace/home/path values and errors | `xcron.contracts.domain` / `.results` | workspace provider |
| manifest documents, hashes, validation values and errors | `xcron.contracts.domain` / `.results` | manifest provider |
| typed create/update requests and job results | `xcron.contracts.requests` / `.results` | jobs provider + SDK |
| scheduler plans, results, and ports | `xcron.contracts.results` / `.ports` | scheduler provider |
| log and metrics values and ports | `xcron.contracts.results` / `.ports` | logs/metrics providers |
| hook values, errors, and ports | `xcron.contracts.results` / `.ports` | agent-hooks provider |

The contracts wheel installs without YAML, native scheduler, configuration,
logging, or terminal dependencies. Its types are the implementation return and
request types today, which lets a provider be selected or replaced without
changing an SDK caller's vocabulary.
