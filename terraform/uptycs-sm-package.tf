

locals {
  manifest = jsondecode(file(var.path_to_manifest))
}



resource "aws_ssm_document" "distributor" {
  name          = var.package_name
  document_type = "Package"
  content       = file(var.path_to_manifest)
  version_name  = local.manifest["version"]
  attachments_source {
    key = "SourceUrl"

    #    values = [ "../ssm-distributor-sources/s3-bucket/uptycs/" ]
    values = ["s3://${var.s3_bucket_name}/uptycs/"]

  }
}