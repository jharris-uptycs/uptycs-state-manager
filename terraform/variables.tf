variable "iam_role_name" {
  type    = string
  default = "AmazonSSMRoleForInstancesQuickSetup"
}

# Define the key pair name to use for each instance
variable "key_pair_name" {
  type    = string
  default = "root-us-east-1"
}

variable "instance_profile" {
  type    = string
  default = "AmazonSSMRoleForInstancesQuickSetup"
}

# Define the instance type to teuse for each instance
variable "instance_type" {
  type    = string
  default = "t2.micro"
}

variable "create_instance" {
  type    = string
}
# The tag key name and value that should be applied to an instance if state manager is to manage it
variable "UptycsEc2TargetTagKeyName" {
  type = string
}
variable "UptycsEc2TargetTagKeyValue" {
  type = string
}
# Location where the manifest.json file is located.   This file is used by the uptycs-sm-package.tf
variable "path_to_manifest" {
  type    = string
  default = "../s3-bucket/manifest.json"
}

#The name of the distributor package as it appears in the console
variable "package_name" {
  type    = string
  default = "UptycsAgent"
}

#The name of the bucket where the the zip files and manifest.json file are located
variable "s3_bucket_name" {
  type = string
}
#The action to take when state manager runs the automation doc (Do not modify)
variable "Action" {
  type    = string
  default = "Install"
}
#The additional arguments to apply  (Do not modify)
variable "AdditionalArgs" {
  type    = string
  default = "{}"
}

# Define the regions in which to create the resources
variable "aws_region" {
  type = string
}


