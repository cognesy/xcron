set positional-arguments := true

default:
    @just --list --list-submodules

# Invoke an operation capability. Omitting command opens its safe command menu.
ops capability command="default" *args:
    @just --justfile ops/{{ capability }}/justfile {{ command }} {{ args }}

list:
    @just --justfile ops/control/justfile list

validate:
    @just --justfile ops/control/justfile validate

check:
    @just --justfile ops/control/justfile aggregate check

test:
    @just --justfile ops/control/justfile aggregate test
