# xcron contracts

`xcron-contracts` is the provider-neutral vocabulary for the capability
workspace. It contains immutable value models, strict SDK request models,
runtime-checkable ports, and channel contribution descriptors. It does not
read manifests, environments, or scheduler state, and it imports no provider.

The temporary root distribution retains its current public imports while
providers migrate one at a time. New providers must depend on this package,
not another provider's private types.

`CONTRACT_INVENTORY.md` records the legacy public surfaces and their target
modules. Keeping that mapping with the package makes an extraction reviewable
without reopening the architecture plan.

```sh
just ops packages test xcron-contracts
just ops packages build xcron-contracts
```
