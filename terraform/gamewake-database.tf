resource "aws_security_group" "database" {
  name_prefix = "${local.name_prefix}-database-"
  description = "Aurora is reachable only through the HTTPS Data API"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-database" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_subnet_group" "gamewake" {
  name       = "${local.name_prefix}-database"
  subnet_ids = aws_subnet.database[*].id

  tags = { Name = "${local.name_prefix}-database" }
}

resource "aws_rds_cluster" "gamewake" {
  cluster_identifier          = "${local.name_prefix}-gamewake"
  engine                      = "aurora-postgresql"
  engine_version              = var.aurora_engine_version
  engine_mode                 = "provisioned"
  database_name               = var.aurora_database_name
  master_username             = "gamewake_admin"
  manage_master_user_password = true
  enable_http_endpoint        = true
  storage_encrypted           = true
  copy_tags_to_snapshot       = true
  deletion_protection         = var.aurora_deletion_protection
  skip_final_snapshot         = var.aurora_skip_final_snapshot
  final_snapshot_identifier   = var.aurora_skip_final_snapshot ? null : "${local.name_prefix}-gamewake-final"
  backup_retention_period     = 7
  preferred_backup_window     = "04:00-05:00"
  db_subnet_group_name        = aws_db_subnet_group.gamewake.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  enabled_cloudwatch_logs_exports = [
    "postgresql",
  ]

  serverlessv2_scaling_configuration {
    min_capacity             = var.aurora_min_acu
    max_capacity             = var.aurora_max_acu
    seconds_until_auto_pause = var.aurora_auto_pause_seconds
  }

  lifecycle {
    precondition {
      condition     = var.aurora_max_acu >= var.aurora_min_acu
      error_message = "aurora_max_acu deve ser maior ou igual a aurora_min_acu."
    }
  }
}

resource "aws_rds_cluster_instance" "gamewake" {
  identifier         = "${local.name_prefix}-gamewake-1"
  cluster_identifier = aws_rds_cluster.gamewake.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.gamewake.engine
  engine_version     = aws_rds_cluster.gamewake.engine_version
}
