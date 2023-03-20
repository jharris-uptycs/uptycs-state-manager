

# Create a new VPC
resource "aws_vpc" "uptycs-demo-vpc" {
  count = var.create_instance ? 1 : 0
  cidr_block = "10.0.0.0/16"
}

# Create an internet gateway
resource "aws_internet_gateway" "uptycs-demo-igw" {
  count = var.create_instance ? 1 : 0
  vpc_id = aws_vpc.uptycs-demo-vpc[count.index].id

}

# Create a new subnet
resource "aws_subnet" "uptycs-demo-subnet" {
  count = var.create_instance ? 1 : 0
  vpc_id     = aws_vpc.uptycs-demo-vpc[count.index].id
  cidr_block = "10.0.1.0/24"
}

resource "aws_route_table_association" "a" {
  count = var.create_instance ? 1 : 0
  subnet_id      = aws_subnet.uptycs-demo-subnet[count.index].id
  route_table_id = aws_route_table.uptycs-demo-rt[count.index].id
}


# Allocate an Elastic IP address for the NAT gateway
resource "aws_eip" "uptycs-demo-eip" {
  count = var.create_instance ? 1 : 0
  vpc = true
}

# Create a route table
resource "aws_route_table" "uptycs-demo-rt" {
  count = var.create_instance ? 1 : 0
  vpc_id = aws_vpc.uptycs-demo-vpc[count.index].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.uptycs-demo-igw[count.index].id
  }
}


# Create a security group
resource "aws_security_group" "uptycs-demo-sg" {
  count = var.create_instance ? 1 : 0
  name_prefix = "example-sg"
  vpc_id      = aws_vpc.uptycs-demo-vpc[count.index].id
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["1.1.1.1/32"]
  }
  egress {
    description = "Allow All Egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "uptycs-demo-vpc-ep-sg" {
  count = var.create_instance ? 1 : 0
  name_prefix = "example-sg"
  vpc_id      = aws_vpc.uptycs-demo-vpc[count.index].id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "Allow All Egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}

# Create an EC2 instance


## Create an EC2 instance
resource "aws_instance" "uptycs_al2_x86" {
  count = var.create_instance ? 1 : 0
  depends_on                  = [aws_ssm_document.distributor]
  associate_public_ip_address = true
  ami                         = data.aws_ami.uptycs_al2_x86.id
  instance_type               = var.instance_type
  key_name                    = var.key_pair_name
  subnet_id                   = aws_subnet.uptycs-demo-subnet[count.index].id
  vpc_security_group_ids      = [aws_security_group.uptycs-demo-sg[count.index].id]
  iam_instance_profile        = var.iam_role_name

  tags = {
    Name         = "uptycs_al2_x86_${count.index}"
    UPTYCS-AGENT = "TRUE"
  }
}

resource "aws_instance" "uptycs_ubuntu_x86" {
  count = var.create_instance ? 1 : 0
  depends_on                  = [aws_ssm_document.distributor]
  associate_public_ip_address = true
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = var.key_pair_name
  subnet_id                   = aws_subnet.uptycs-demo-subnet[count.index].id
  vpc_security_group_ids      = [aws_security_group.uptycs-demo-sg[count.index].id]
  iam_instance_profile        = var.iam_role_name

  tags = {
    Name         = "uptycs_ubuntu_${count.index}"
    UPTYCS-AGENT = "TRUE"
  }
}
data "aws_ami" "ubuntu" {

  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"]
}


#
## Retrieve the AMI for the region
data "aws_ami" "uptycs_al2_x86" {
  most_recent = true

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  owners = ["amazon"]
}
