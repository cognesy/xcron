# xcron CLI

`xcron-cli` owns the terminal channel and the `xcron` console entry point. It
turns the CLI paths declared by selected providers into Typer registrations,
validating their ownership and uniqueness before attaching them.

The implementation, renderers, packaged help, and contribution validation all
live in `src/xcron_cli`. Provider cores expose ports and descriptor metadata
only; none import Typer, Rich, or TOON.

```sh
just ops packages test xcron-cli
just ops packages build xcron-cli
```
