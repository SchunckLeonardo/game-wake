resource "aws_s3_bucket" "backups" {
  count = var.enable_s3_backup ? 1 : 0

  bucket        = local.s3_backup_bucket_name
  force_destroy = false

  tags = { Name = "${local.name_prefix}-backups" }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  count = var.enable_s3_backup ? 1 : 0

  bucket                  = aws_s3_bucket.backups[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  count = var.enable_s3_backup ? 1 : 0

  bucket = aws_s3_bucket.backups[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  count = var.enable_s3_backup ? 1 : 0

  bucket = aws_s3_bucket.backups[0].id
  versioning_configuration {
    status = var.s3_backup_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  count = var.enable_s3_backup ? 1 : 0

  bucket = aws_s3_bucket.backups[0].id

  rule {
    id     = "expire-old-backups"
    status = "Enabled"

    filter {
      prefix = "saves/"
    }

    expiration {
      days = var.s3_backup_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.s3_backup_retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.backups]
}
