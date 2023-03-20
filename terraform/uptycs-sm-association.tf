# This Terraform resource creates an AWS SSM association that installs or updates the Uptycs
# agent on EC2 instances based on a specific tag key-value pair.

resource "aws_ssm_association" "UptycsSSMAssociation" {
  association_name    = "Uptycs-Agent-Install"
  name                = "AWS-ConfigureAWSPackage"
  schedule_expression = "cron(0 0 */1 * * ? *)"
  compliance_severity = "MEDIUM"
  parameters = {
    action              = var.Action
    additionalArguments = var.AdditionalArgs
    installationType    = "Uninstall and reinstall"
    name                = var.package_name
  }
  targets {
    key = "tag:${var.UptycsEc2TargetTagKeyName}"
    values = [
      var.UptycsEc2TargetTagKeyValue
    ]
  }
}

