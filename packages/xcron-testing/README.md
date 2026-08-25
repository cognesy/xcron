# xcron testing

`xcron-testing` is the reusable provider conformance kit. It verifies that a
provider structurally implements a runtime-checkable contract port and scans
every workspace package root for package-boundary violations. It has no
dependency on a concrete xcron provider or terminal library.

```sh
just ops packages test xcron-testing
just ops packages build xcron-testing
```
