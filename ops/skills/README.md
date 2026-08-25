# Agent assets

This capability owns repository-side discovery and smoke checks for the product
skills in `resources/skills/`. The skills remain product assets; this package
only provides an executable maintenance surface around them.

```sh
just ops skills
just ops skills list
just ops skills smoke
just ops skills check
```

Use `check` after changing a packaged skill or authored CLI help. It lists the
real skill entry points and runs the focused help/CLI tests.
