# `xcron inspect`

Inspect one managed job in depth.

This command is the detailed companion to `status`: it shows normalized desired fields, deployed artifact/log locations, and backend-native detail for one job.

Use `--fields backend,job,status,desired.command,deployed.artifact_path` to narrow the response and `--full` to disable snippet truncation.
