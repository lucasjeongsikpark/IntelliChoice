resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-mysql"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name        = "${var.name_prefix}-mysql-sg"
  description = "Allow MySQL (3306) from the ECS task security group only"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-mysql-sg" })
}

resource "aws_security_group_rule" "ingress_from_ecs" {
  # count (not for_each/toset) - the ECS tasks SG id in allowed_security_group_ids is
  # only known after apply when both are created in the same run; count only needs the
  # list's length, which is static (S32/D-084).
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  security_group_id        = aws_security_group.this.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
}

resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-mysql"
  engine         = "mysql"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.master_username
  password = random_password.master.result
  port     = 3306

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  publicly_accessible    = false

  multi_az                   = var.multi_az
  backup_retention_period    = var.backup_retention_days
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = !var.deletion_protection
  final_snapshot_identifier  = var.deletion_protection ? "${var.name_prefix}-mysql-final" : null
  auto_minor_version_upgrade = true

  tags = var.tags
}

# LEARNING_MYSQL_URL / CHAT_MYSQL_URL's expected shape (mysql+aiomysql://user:pass@host:3306) -
# no database name suffix, matching Settings.mysql_url's local-dev default, since
# MySQLProfileAdapter selects the database itself (D-083).
resource "aws_secretsmanager_secret" "mysql_url" {
  name = "${var.name_prefix}/mysql/mysql-url"
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "mysql_url" {
  secret_id     = aws_secretsmanager_secret.mysql_url.id
  secret_string = "mysql+aiomysql://${var.master_username}:${random_password.master.result}@${aws_db_instance.this.address}:3306"
}
