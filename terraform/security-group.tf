resource "aws_security_group" "palworld" {
  name_prefix = "${local.name_prefix}-"
  description = "Palworld UDP only; REST, RCON and SSH remain closed by default"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "palworld_udp" {
  security_group_id = aws_security_group.palworld.id
  description       = "Palworld dedicated server"
  ip_protocol       = "udp"
  from_port         = var.palworld_port
  to_port           = var.palworld_port
  cidr_ipv4         = var.palworld_allowed_cidr
}

resource "aws_vpc_security_group_ingress_rule" "temporary_ssh" {
  count = var.enable_ssh ? 1 : 0

  security_group_id = aws_security_group.palworld.id
  description       = "Temporary restricted SSH; prefer Session Manager"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.ssh_allowed_cidr

  lifecycle {
    precondition {
      condition     = var.ssh_allowed_cidr != null && var.ssh_key_name != null
      error_message = "enable_ssh=true exige ssh_allowed_cidr restrito e ssh_key_name."
    }
  }
}

resource "aws_vpc_security_group_egress_rule" "all_ipv4" {
  security_group_id = aws_security_group.palworld.id
  description       = "Updates, SteamCMD, SSM, Parameter Store and Discord webhook"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

