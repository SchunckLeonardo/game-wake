locals {
  gamewake_runtime_image_source_hash = sha256(join(":", [
    filesha256("${path.module}/../server/install-palworld.sh"),
    data.aws_ssm_parameter.ubuntu_ami.value,
  ]))
  gamewake_runtime_image_version = format(
    "1.%d.%d",
    parseint(substr(local.gamewake_runtime_image_source_hash, 0, 4), 16),
    parseint(substr(local.gamewake_runtime_image_source_hash, 4, 4), 16),
  )
  gamewake_runtime_image_id = one([
    for ami in aws_imagebuilder_image.gamewake_runtime.output_resources[0].amis : ami.image
    if ami.region == var.aws_region
  ])
}

resource "aws_iam_role" "image_builder" {
  name               = "${local.name_prefix}-image-builder"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "image_builder" {
  role       = aws_iam_role.image_builder.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/EC2InstanceProfileForImageBuilder"
}

resource "aws_iam_role_policy_attachment" "image_builder_ssm" {
  role       = aws_iam_role.image_builder.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "image_builder" {
  name = "${local.name_prefix}-image-builder"
  role = aws_iam_role.image_builder.name
}

resource "aws_security_group" "image_builder" {
  name_prefix = "${local.name_prefix}-image-builder-"
  description = "Outbound-only access for disposable GameWake runtime image builds"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-image-builder" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_egress_rule" "image_builder" {
  security_group_id = aws_security_group.image_builder.id
  description       = "Ubuntu packages, AWS CLI, SSM and SteamCMD during the image build"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_imagebuilder_component" "gamewake_runtime" {
  name        = "${local.name_prefix}-palworld-runtime"
  description = "Preinstalls the GameWake Palworld runtime outside the player wake path"
  platform    = "Linux"
  version     = local.gamewake_runtime_image_version

  data = yamlencode({
    name          = "GameWake Palworld runtime"
    description   = "Install operating system dependencies, SteamCMD and Palworld once"
    schemaVersion = "1.0"
    phases = [
      {
        name = "build"
        steps = [
          {
            name   = "InstallGameWakeRuntime"
            action = "ExecuteBash"
            inputs = {
              commands = [
                "printf '%s' '${filebase64("${path.module}/../server/install-palworld.sh")}' | base64 --decode > /tmp/install-palworld.sh",
                "chmod 0755 /tmp/install-palworld.sh",
                "/tmp/install-palworld.sh",
                "install -d -o root -g root -m 0755 /opt/gamewake",
                "printf '%s\\n' '${local.gamewake_runtime_image_source_hash}' > /opt/gamewake/image-ready",
                "chmod 0644 /opt/gamewake/image-ready",
                "rm -f /tmp/install-palworld.sh",
              ]
            }
          }
        ]
      },
      {
        name = "validate"
        steps = [
          {
            name   = "ValidateGameWakeRuntime"
            action = "ExecuteBash"
            inputs = {
              commands = [
                "test -x /opt/palworld/PalServer.sh",
                "test -x /usr/games/steamcmd || command -v steamcmd",
                "test -x /usr/local/bin/aws",
                "test -s /opt/gamewake/image-ready",
              ]
            }
          }
        ]
      },
    ]
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_imagebuilder_image_recipe" "gamewake_runtime" {
  name         = "${local.name_prefix}-palworld-runtime"
  description  = "Versioned GameWake AMI with Palworld ready before a player wakes a World"
  parent_image = data.aws_ssm_parameter.ubuntu_ami.value
  version      = local.gamewake_runtime_image_version

  component {
    component_arn = aws_imagebuilder_component.gamewake_runtime.arn
  }

  block_device_mapping {
    device_name = "/dev/sda1"

    ebs {
      delete_on_termination = "true"
      encrypted             = "true"
      volume_size           = var.root_volume_size_gib
      volume_type           = "gp3"
    }
  }

  systems_manager_agent {
    uninstall_after_build = false
  }

  ami_tags = merge(local.common_tags, {
    GameWakeManaged = "true"
    Purpose         = "GameWakeRuntimeImage"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_imagebuilder_infrastructure_configuration" "gamewake_runtime" {
  name                          = "${local.name_prefix}-runtime-image"
  description                   = "Disposable builder for the GameWake Palworld runtime AMI"
  instance_profile_name         = aws_iam_instance_profile.image_builder.name
  instance_types                = [var.runtime_image_builder_instance_type]
  security_group_ids            = [aws_security_group.image_builder.id]
  subnet_id                     = aws_subnet.public.id
  terminate_instance_on_failure = true
  resource_tags = merge(local.common_tags, {
    GameWakeManaged = "true"
    Purpose         = "GameWakeRuntimeImageBuild"
  })

  instance_metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.image_builder,
    aws_iam_role_policy_attachment.image_builder_ssm,
    aws_route_table_association.public,
  ]
}

resource "aws_imagebuilder_image" "gamewake_runtime" {
  image_recipe_arn                 = aws_imagebuilder_image_recipe.gamewake_runtime.arn
  infrastructure_configuration_arn = aws_imagebuilder_infrastructure_configuration.gamewake_runtime.arn
  enhanced_image_metadata_enabled  = true

  image_tests_configuration {
    image_tests_enabled = true
    timeout_minutes     = 60
  }

  timeouts {
    create = "90m"
  }

  lifecycle {
    create_before_destroy = true
  }
}
