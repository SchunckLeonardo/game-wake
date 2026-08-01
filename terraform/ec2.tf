data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

locals {
  gamewake_runtime_user_data_variables = {
    aws_region                    = var.aws_region
    common_script_b64             = filebase64("${path.module}/../server/palworld-common.sh")
    render_settings_script_b64    = filebase64("${path.module}/../server/render_settings.py")
    install_script_b64            = filebase64("${path.module}/../server/install-palworld.sh")
    configure_script_b64          = filebase64("${path.module}/../server/configure-palworld.sh")
    start_script_b64              = filebase64("${path.module}/../server/start-palworld.sh")
    stop_script_b64               = filebase64("${path.module}/../server/stop-palworld.sh")
    palworld_service_b64          = filebase64("${path.module}/../server/palworld.service")
    gamewake_operation_script_b64 = filebase64("${path.module}/../server/gamewake-operation.sh")
  }
}
