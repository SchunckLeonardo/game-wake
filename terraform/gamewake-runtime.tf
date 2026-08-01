locals {
  gamewake_runtime_user_data = templatefile(
    "${path.module}/user-data.sh.tpl",
    local.gamewake_runtime_user_data_variables,
  )
}

data "aws_iam_policy_document" "gamewake_runtime_data" {
  statement {
    sid     = "ReadOwnWorldConfiguration"
    effect  = "Allow"
    actions = ["ssm:GetParameter"]
    resources = [
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.parameter_path}/gamewake/worlds/*",
    ]
  }

  statement {
    sid    = "WorldDataObjects"
    effect = "Allow"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.world_data.arn}/*"]
  }

  statement {
    sid       = "ListWorldData"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.world_data.arn]
  }

  statement {
    sid    = "UseWorldDataKey"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.world_data.arn]
  }
}

resource "aws_iam_role_policy" "gamewake_runtime_data" {
  name   = "${local.name_prefix}-world-data"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.gamewake_runtime_data.json
}

resource "aws_launch_template" "gamewake_runtime" {
  name_prefix = "${local.name_prefix}-runtime-"
  description = "Disposable GameWake game server runtime"

  image_id      = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type = var.instance_type
  key_name      = var.enable_ssh ? var.ssh_key_name : null

  instance_initiated_shutdown_behavior = "terminate"
  update_default_version               = true
  user_data                            = base64gzip(local.gamewake_runtime_user_data)

  iam_instance_profile {
    name = aws_iam_instance_profile.palworld.name
  }

  network_interfaces {
    associate_public_ip_address = true
    delete_on_termination       = true
    device_index                = 0
    security_groups             = [aws_security_group.palworld.id]
    subnet_id                   = aws_subnet.public.id
  }

  block_device_mappings {
    device_name = "/dev/sda1"

    ebs {
      delete_on_termination = true
      encrypted             = true
      volume_size           = var.root_volume_size_gib
      volume_type           = "gp3"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  monitoring {
    enabled = false
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(local.common_tags, { GameWakeManaged = "true" })
  }

  lifecycle {
    create_before_destroy = true

    precondition {
      condition     = ceil(length(base64gzip(local.gamewake_runtime_user_data)) * 3 / 4) <= 16384
      error_message = "O user-data GameWake excedeu o limite EC2 de 16 KiB."
    }
  }

  depends_on = [
    aws_iam_role_policy.gamewake_runtime_data,
    aws_iam_role_policy_attachment.ec2_ssm_core,
    aws_route_table_association.public,
  ]
}
