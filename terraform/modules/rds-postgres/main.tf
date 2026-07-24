resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-postgres"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name        = "${var.name_prefix}-postgres-sg"
  description = "Allow Postgres (5432) from the ECS task security group only"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-postgres-sg" })
}

resource "aws_security_group_rule" "ingress_from_ecs" {
  # count (not for_each/toset) - the ECS tasks SG id in allowed_security_group_ids is
  # only known after apply when both are created in the same run; count only needs the
  # list's length, which is static (S32/D-084).
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.this.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.master_username
  port     = 5432

  # D-092 (S33): real automatic rotation, AWS-managed end to end - no custom rotation
  # Lambda to deploy/maintain (the SAR-template alternative), no `random_password`
  # resource, no manually-maintained combined-DSN secret. AWS creates its own Secrets
  # Manager secret for the master password and rotates it automatically (defaults to
  # every 7 days - the AWS provider doesn't currently expose a way to configure that
  # interval, confirmed via search before choosing this design; 7 days is if anything
  # more conservative than most manual rotation policies, not a compromise). The
  # secret's shape is AWS's own managed JSON (`username`/`password` keys, no combined
  # DSN) - `master_user_secret_arn` output below is consumed via ECS's per-JSON-key
  # `secrets` extraction, not as a ready connection string; see
  # `learning_api.config.Settings`'s component-based DSN builder.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  publicly_accessible    = false

  multi_az                   = var.multi_az
  backup_retention_period    = var.backup_retention_days
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = !var.deletion_protection
  final_snapshot_identifier  = var.deletion_protection ? "${var.name_prefix}-postgres-final" : null
  auto_minor_version_upgrade = true

  tags = var.tags
}
