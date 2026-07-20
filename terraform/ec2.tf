data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

locals {
  user_data = templatefile("${path.module}/user-data.sh.tpl", {
    aws_region                            = var.aws_region
    palworld_port                         = var.palworld_port
    palworld_rest_api_port                = var.palworld_rest_api_port
    palworld_rest_api_username            = var.palworld_rest_api_username
    palworld_server_name_b64              = base64encode(var.palworld_server_name)
    palworld_server_description_b64       = base64encode(var.palworld_server_description)
    palworld_max_players                  = var.palworld_max_players
    palworld_exp_rate                     = var.palworld_exp_rate
    palworld_collection_drop_rate         = var.palworld_collection_drop_rate
    palworld_spawn_rate                   = var.palworld_spawn_rate
    palworld_death_penalty                = var.palworld_death_penalty
    palworld_pal_damage_attack_rate       = var.palworld_pal_damage_attack_rate
    palworld_pal_damage_defense_rate      = var.palworld_pal_damage_defense_rate
    palworld_player_damage_attack_rate    = var.palworld_player_damage_attack_rate
    palworld_player_damage_defense_rate   = var.palworld_player_damage_defense_rate
    palworld_pal_stamina_decrease_rate    = var.palworld_pal_stamina_decrease_rate
    palworld_player_stamina_decrease_rate = var.palworld_player_stamina_decrease_rate
    palworld_item_weight_rate             = var.palworld_item_weight_rate
    autostop_check_minutes                = var.autostop_check_minutes
    autostop_idle_minutes                 = var.autostop_idle_minutes
    healthcheck_timeout_minutes           = var.healthcheck_timeout_minutes
    local_backup_retention_days           = var.local_backup_retention_days
    server_password_parameter_name        = aws_ssm_parameter.server_password.name
    admin_password_parameter_name         = aws_ssm_parameter.admin_password.name
    palworld_config_parameter_name        = aws_ssm_parameter.palworld_config.name
    discord_webhook_parameter_name        = aws_ssm_parameter.discord_webhook_url.name
    server_status_parameter_name          = aws_ssm_parameter.server_status.name
    s3_backup_uri                         = local.s3_backup_uri
    stop_after_initial_bootstrap          = var.stop_after_initial_bootstrap
    common_script_b64                     = filebase64("${path.module}/../server/palworld-common.sh")
    render_settings_script_b64            = filebase64("${path.module}/../server/render_settings.py")
    install_script_b64                    = filebase64("${path.module}/../server/install-palworld.sh")
    configure_script_b64                  = filebase64("${path.module}/../server/configure-palworld.sh")
    start_script_b64                      = filebase64("${path.module}/../server/start-palworld.sh")
    stop_script_b64                       = filebase64("${path.module}/../server/stop-palworld.sh")
    backup_script_b64                     = filebase64("${path.module}/../server/backup-palworld.sh")
    autostop_script_b64                   = filebase64("${path.module}/../server/autostop.sh")
    notify_script_b64                     = filebase64("${path.module}/../server/notify-discord.sh")
    healthcheck_script_b64                = filebase64("${path.module}/../server/healthcheck.sh")
    palworld_service_b64                  = filebase64("${path.module}/../server/palworld.service")
    notify_service_b64                    = filebase64("${path.module}/../server/palworld-notify.service")
    autostop_service_b64                  = filebase64("${path.module}/../server/palworld-autostop.service")
    autostop_timer_b64                    = filebase64("${path.module}/../server/palworld-autostop.timer")
    backup_service_b64                    = filebase64("${path.module}/../server/palworld-backup.service")
    backup_timer_b64                      = filebase64("${path.module}/../server/palworld-backup.timer")
  })
}

resource "aws_instance" "palworld" {
  ami                         = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type               = var.instance_type
  availability_zone           = aws_subnet.public.availability_zone
  subnet_id                   = aws_subnet.public.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.palworld.id]
  iam_instance_profile        = aws_iam_instance_profile.palworld.name
  key_name                    = var.enable_ssh ? var.ssh_key_name : null

  instance_initiated_shutdown_behavior = "stop"
  disable_api_termination              = var.enable_termination_protection
  monitoring                           = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gib
    encrypted             = true
    delete_on_termination = var.root_volume_delete_on_termination

    tags = merge(local.common_tags, { Name = "${local.name_prefix}-root" })
  }

  user_data_base64            = base64gzip(local.user_data)
  user_data_replace_on_change = false

  tags = { Name = "${local.name_prefix}-server" }

  lifecycle {
    ignore_changes = [ami]

    precondition {
      condition     = ceil(length(base64gzip(local.user_data)) * 3 / 4) <= 16384
      error_message = "O user-data gzip excedeu o limite EC2 de 16 KiB; mova assets para armazenamento externo."
    }
  }

  depends_on = [
    aws_iam_role_policy.ec2_runtime,
    aws_iam_role_policy_attachment.ec2_ssm_core,
    aws_route_table_association.public,
  ]
}
