set positional-arguments := true

mod version 'ops/version/justfile'

default:
    @just --list --list-submodules

# Invoke an operation capability through the validated operations router.
# No arguments and `list` are safe discovery routes. Omitting the command for a
# valid capability opens its local safe command menu.
ops *args:
    @just --justfile ops/justfile route {{ args }}

list:
    @just --justfile ops/control/justfile list

validate:
    @just --justfile ops/control/justfile validate

check:
    @just --justfile ops/control/justfile aggregate check

test:
    @just --justfile ops/control/justfile aggregate test
