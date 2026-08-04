# Domain

The domain layer holds normalized models, identifiers, and diffing structures
shared by actions and services.

Current v1 model decisions:

- every project manifest must define `project.id`
- fully-qualified job identity is derived as `<project.id>.<job.id>`
- artifact identity is a scheduler-friendly derivative of that qualified id
- `schedule.cron` and `schedule.every` are both part of the public model
- `schedule.every` is intentionally constrained to a simple portable duration
  string such as `10m`, `2h`, or `1d`

The next validation task is responsible for enforcing these rules at load time.
