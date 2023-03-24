# Set the region where the Association and the distributor package will be created
aws_region = "us-east-1"

# The tag key name and value that should be applied to an instance if state manager is to manage it
UptycsEc2TargetTagKeyName  = "UPTYCS-AGENT"
UptycsEc2TargetTagKeyValue = "TRUE"

#The name of the bucket where the the zip files and manifest.json file are located
s3_bucket_name = "uptycs-dist-qjrzwm"

create_instance = "true"