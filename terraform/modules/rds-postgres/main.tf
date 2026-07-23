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

resource "random_password" "master" {
  length  = 32
  special = false # simplifies embedding in a DSN URI without percent-encoding
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
  password = random_password.master.result
  port     = 5432

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

# Full connection-string secret (asyncpg-driver DSN, matching Settings.database_url's
# expected shape) - the app reads one combined URL, not separate host/user/pass fields,
# so ECS's `secrets` task-def block injects this one value directly into
# LEARNING_DATABASE_URL / CHAT_DATABASE_URL (both apps share this one instance, same as
# local dev - packages/db has no per-app schema separation today).
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.name_prefix}/postgres/database-url"
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql+asyncpg://${var.master_username}:${random_password.master.result}@${aws_db_instance.this.address}:5432/${var.db_name}"
}
