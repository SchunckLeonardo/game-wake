resource "aws_kms_key" "world_data" {
  description             = "GameWake World states, backups and exports"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "world_data" {
  name          = "alias/${local.name_prefix}-world-data"
  target_key_id = aws_kms_key.world_data.key_id
}

resource "aws_s3_bucket" "world_data" {
  bucket        = local.world_data_bucket_name
  force_destroy = false

  tags = { Name = "${local.name_prefix}-world-data" }
}

resource "aws_s3_bucket_public_access_block" "world_data" {
  bucket = aws_s3_bucket.world_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "world_data" {
  bucket = aws_s3_bucket.world_data.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "world_data" {
  bucket = aws_s3_bucket.world_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "world_data" {
  bucket = aws_s3_bucket.world_data.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.world_data.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "world_data" {
  bucket = aws_s3_bucket.world_data.id

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "expire-export-manifests"
    status = "Enabled"

    filter {
      prefix = "exports/"
    }

    expiration {
      days = 2
    }

    noncurrent_version_expiration {
      noncurrent_days = 2
    }
  }

  depends_on = [aws_s3_bucket_versioning.world_data]
}

data "aws_iam_policy_document" "world_data_bucket" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    actions = [
      "s3:*",
    ]
    resources = [
      aws_s3_bucket.world_data.arn,
      "${aws_s3_bucket.world_data.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "world_data" {
  bucket = aws_s3_bucket.world_data.id
  policy = data.aws_iam_policy_document.world_data_bucket.json
}
