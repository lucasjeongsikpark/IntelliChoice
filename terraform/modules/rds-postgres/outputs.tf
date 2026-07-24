output "endpoint_address" {
  value = aws_db_instance.this.address
}

output "endpoint_port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "master_username" {
  value = aws_db_instance.this.username
}

output "security_group_id" {
  value = aws_security_group.this.id
}

# D-092 (S33): AWS-managed secret (real automatic rotation) - JSON-shaped
# (`username`/`password` keys), not a ready DSN. Consumed via ECS's per-JSON-key
# `secrets` extraction (`<this arn>:username::` / `:password::`), combined with the
# plain (non-secret) endpoint_address/endpoint_port/db_name outputs above.
#
# S34: `one(...)` not `[0]` - found live while investigating a real `terraform plan`
# crash the moment AWS access returned this session. `master_user_secret` is empty in
# the *pre-apply* state (this instance didn't have `manage_master_user_password` turned
# on yet when D-092 was written but never applied) - indexing an empty list with `[0]`
# hard-errors plan/apply outright ("Invalid index... the collection has no elements"),
# rather than resolving to "known after apply" the way a plain computed attribute would.
# `one()` is Terraform's built-in for exactly this "a list that's either empty or has
# one element" shape: it returns `null` when empty instead of erroring, and once this
# secret actually exists post-apply, correctly returns its single element. Not yet
# applied - AWS access only just returned; this fix is unverified against a real apply,
# only confirmed to unblock `terraform plan` (see DECISIONS.md).
output "master_user_secret_arn" {
  value = one(aws_db_instance.this.master_user_secret[*].secret_arn)
}
