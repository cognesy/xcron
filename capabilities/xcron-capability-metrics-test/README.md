# Test metrics capability

This package is a deterministic alternate `metrics` provider used only by the
installed-wheel verification lane. It demonstrates explicit provider selection
without adding a test implementation to xcron's default aggregate.

```sh
just ops packages test xcron-capability-metrics-test
just ops packages build xcron-capability-metrics-test
```
