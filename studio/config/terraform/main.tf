# Provider configuration
provider "aws" {
  region = var.aws_region
}

terraform {
  backend "s3" {
    bucket = "subscr-optinist-for-cloud-tfstate"
    key    = "terraform.tfstate"
    region = "ap-northeast-1"
  }
}

# Variables
variable "aws_region" {
  description = "AWS region to deploy resources"
  default     = ""
}
variable "availability_zone" {
  description = "Availability zone for the subnet"
  default     = ""
}

# Database configuration
variable "mysql_root_password" {
  description = "MySQL/MariaDB root password"
  type        = string
  default     = ""
}

variable "mysql_database" {
  description = "MySQL/MariaDB database name"
  type        = string
  default     = ""
}

variable "mysql_user" {
  description = "MySQL/MariaDB user"
  type        = string
  default     = ""
}

variable "mysql_password" {
  description = "MySQL/MariaDB password"
  type        = string
  default     = ""
}

variable "optinist_org_name" {
  description = "Name for initial organization"
  type        = string
}

variable "optinist_admin_name" {
  description = "Name for initial admin user"
  type        = string
}

variable "optinist_admin_email" {
  description = "Email for initial admin user"
  type        = string
}

variable "optinist_admin_uid" {
  description = "Firebase UID for initial admin user"
  type        = string
}

variable "optinist_secret_key" {
  description = "Secret key for OptiNiSt"
  type        = string
  sensitive   = true
}

variable "firebase_config_json" {
  description = "Firebase web configuration JSON"
  type        = string
  sensitive   = true
}

variable "firebase_private_json" {
  description = "Firebase service account private key JSON"
  type        = string
  sensitive   = true
}

variable "git_repo" {
  description = "Git repository"
  type        = string
}

variable "git_branch" {
  description = "Git branch to checkout"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL for OptiNiSt Docker image"
  type        = string
}

variable "asg_min_size" {
  description = "Minimum number of instances in ASG"
  type        = number
  default     = 1
}

variable "asg_max_size" {
  description = "Maximum number of instances in ASG"
  type        = number
  default     = 1
}

variable "asg_desired_capacity" {
  description = "Desired number of instances in ASG"
  type        = number
  default     = 1
}

# Data sources
data "aws_caller_identity" "current" {}

# ==============
# Key generation
# ==============
variable "key_name" {
  description = "Name of the SSH key pair"
  type        = string
}

# Generate random suffix for key pair name
resource "random_id" "key_suffix" {
  byte_length = 4
}

# Generate a unique key pair name
locals {
  key_name = var.key_name != "" ? var.key_name : "subscr-optinist-cloud-${random_id.key_suffix.hex}"
}

# Generate SSH key pair
resource "tls_private_key" "subscr_optinist_cloud_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

# Create AWS key pair
resource "aws_key_pair" "subscr_optinist_cloud_key_pair" {
  key_name   = local.key_name
  public_key = tls_private_key.subscr_optinist_cloud_key.public_key_openssh  # Fixed reference

  tags = {
    Name = "subscr-optinist-cloud-key"
  }
}

# Save private key to local file
resource "local_file" "private_key" {
  content         = tls_private_key.subscr_optinist_cloud_key.private_key_pem  # Fixed reference
  filename        = "${path.module}/subscr-optinist-cloud-private-key.pem"
  file_permission = "0400"
}


# =============
# VPC & Network
# =============
resource "aws_vpc" "main" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "subscr-optinist-cloud-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "subscr-optinist-cloud-igw"
  }
}

# Public Subnets
resource "aws_subnet" "public1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.1.0.0/20"
  availability_zone = "ap-northeast-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "subscr-optinist-cloud-subnet-public1-ap-northeast-1a"
  }
}

resource "aws_subnet" "public2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.1.16.0/20"
  availability_zone = "ap-northeast-1c"
  map_public_ip_on_launch = true

  tags = {
    Name = "subscr-optinist-cloud-subnet-public2-ap-northeast-1c"
  }
}

# Private Subnets
resource "aws_subnet" "private1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.1.128.0/20"
  availability_zone = "ap-northeast-1a"

  tags = {
    Name = "subscr-optinist-cloud-subnet-private1-ap-northeast-1a"
  }
}

resource "aws_subnet" "private2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.1.144.0/20"
  availability_zone = "ap-northeast-1c"

  tags = {
    Name = "subscr-optinist-cloud-subnet-private2-ap-northeast-1c"
  }
}

# ============
# NAT Instance
# ============
resource "aws_instance" "nat" {
  ami                    = data.aws_ami.nat_instance.id
  instance_type          = "t3a.nano"
  subnet_id              = aws_subnet.public1.id
  vpc_security_group_ids = [aws_security_group.nat_instance.id]
  source_dest_check      = false

  iam_instance_profile   = aws_iam_instance_profile.nat_instance.name

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              echo 1 > /proc/sys/net/ipv4/ip_forward
              iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
              EOF

  tags = {
    Name = "subscr-optinist-nat-instance"
  }
}

# Elastic IP for NAT Instance
resource "aws_eip" "nat_instance" {
  domain = "vpc"
  instance = aws_instance.nat.id

  tags = {
    Name = "subscr-optinist-nat-instance-eip"
  }
}

# NAT Instance
data "aws_ami" "nat_instance" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn-ami-vpc-nat-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_network_interface" "nat" {
  depends_on = [aws_instance.nat]

  filter {
    name   = "attachment.instance-id"
    values = [aws_instance.nat.id]
  }

  filter {
    name   = "attachment.device-index"
    values = ["0"]
  }
}

# ============
# Route Tables
# ============
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "subscr-optinist-cloud-rtb-public"
  }
}

resource "aws_route_table" "private1" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    network_interface_id = data.aws_network_interface.nat.id
  }

  tags = {
    Name = "subscr-optinist-cloud-rtb-private1-ap-northeast-1a"
  }
}

resource "aws_route_table" "private2" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    network_interface_id = data.aws_network_interface.nat.id
  }

  tags = {
    Name = "subscr-optinist-cloud-rtb-private2-ap-northeast-1c"
  }
}

# Route Table Associations
resource "aws_route_table_association" "public1" {
  subnet_id      = aws_subnet.public1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public2" {
  subnet_id      = aws_subnet.public2.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private1" {
  subnet_id      = aws_subnet.private1.id
  route_table_id = aws_route_table.private1.id
}

resource "aws_route_table_association" "private2" {
  subnet_id      = aws_subnet.private2.id
  route_table_id = aws_route_table.private2.id
}

resource "aws_vpc_endpoint_route_table_association" "private1_s3" {
  route_table_id  = aws_route_table.private1.id
  vpc_endpoint_id = aws_vpc_endpoint.s3.id
}

resource "aws_vpc_endpoint_route_table_association" "private2_s3" {
  route_table_id  = aws_route_table.private2.id
  vpc_endpoint_id = aws_vpc_endpoint.s3.id
}

# S3 VPC Endpoint
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.ap-northeast-1.s3"

  tags = {
    Name = "subscr-optinist-cloud-vpce-s3"
  }
}

# ===
# RDS
# ===
resource "aws_db_subnet_group" "main" {
  name       = "subscr-optinist-rds-subnet-group"
  subnet_ids = [
    aws_subnet.private1.id,
    aws_subnet.private2.id,
    aws_subnet.public1.id,
    aws_subnet.public2.id
  ]

  tags = {
    Name = "subscr-optinist-rds-subnet-group"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier              = "subscr-optinist-cloud-rds"
  allocated_storage       = 20
  storage_type            = "gp3"
  engine                  = "mysql"
  engine_version          = "8.0"
  instance_class          = "db.t4g.micro"
  parameter_group_name    = "default.mysql8.0"
  db_name                 = var.mysql_database
  username                = var.mysql_user
  password                = var.mysql_password
  skip_final_snapshot     = true
  final_snapshot_identifier = "${var.mysql_database}-final-snapshot"
  backup_retention_period = 7
  monitoring_interval     = 60
  monitoring_role_arn     = aws_iam_role.rds_monitoring.arn
  publicly_accessible     = false
  enabled_cloudwatch_logs_exports = ["error", "general", "slowquery"]
  network_type            = "IPV4"
  port                    = 3306
  vpc_security_group_ids  = [aws_security_group.rds.id]
  db_subnet_group_name    = aws_db_subnet_group.main.name
  multi_az                = false
  storage_encrypted       = true

  tags = {
    Name = "subscr-optinist-cloud-rds"
  }
}


# ===============
# EFS File System
# ===============
resource "aws_efs_file_system" "snmk" {
  creation_token = "subscr-optinist-cloud-snmk-volume"

  performance_mode = "generalPurpose"
  throughput_mode = "bursting"

  tags = {
    Name = "subscr-optinist-cloud-snmk-volume"
  }
}

# EFS Mount Targets
resource "aws_efs_mount_target" "private1" {
  file_system_id  = aws_efs_file_system.snmk.id
  subnet_id       = aws_subnet.private1.id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_mount_target" "private2" {
  file_system_id  = aws_efs_file_system.snmk.id
  subnet_id       = aws_subnet.private2.id
  security_groups = [aws_security_group.efs.id]
}

# EFS Access Point
resource "aws_efs_access_point" "snmk" {
  file_system_id = aws_efs_file_system.snmk.id

  root_directory {
    path = "/"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "subscr-optinist-cloud-efs-ap"
  }
}

# =================================
# S3 bucket for application storage
# =================================

locals {
  bucket_suffix = formatdate("YYYY-MM-DD", timestamp())
}

resource "aws_s3_bucket" "app_storage" {
  bucket = "subscr-optinist-app-storage-${local.bucket_suffix}"
  force_destroy = true

  tags = {
    Name        = "Subscr OptiNiSt Application Storage"
    Environment = "Production"
  }
}

resource "aws_s3_bucket" "user_data" {
  bucket = "subscr-optinist-user-data-${local.bucket_suffix}"
  force_destroy = true

  tags = {
    Name        = "Subscr OptiNiSt User Data Storage"
    Environment = "Production"
  }
}

resource "aws_s3_bucket_versioning" "app_storage" {
  bucket = aws_s3_bucket.app_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "user_data" {
  bucket = aws_s3_bucket.user_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Block all public access to S3
resource "aws_s3_bucket_public_access_block" "app_storage" {
  bucket = aws_s3_bucket.app_storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "user_data" {
  bucket = aws_s3_bucket.user_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# =========================
# Application Load Balancer
# =========================
resource "aws_lb" "main" {
  name               = "subscr-optinist-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id, aws_security_group.ecs.id]
  subnets           = [aws_subnet.public1.id, aws_subnet.public2.id]

  enable_deletion_protection = false
  idle_timeout              = 60

  # Enable access logs for detailed monitoring
  access_logs {
    bucket  = aws_s3_bucket.app_storage.id
    prefix  = "alb-logs"
    enabled = true
  }

  depends_on = [
    aws_s3_bucket_policy.app_storage
  ]

  tags = {
    Name = "subscr-optinist-load-balancer"
  }
}

# Load Balancer Listener
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ==================
# Auto Scaling Group
# ==================
resource "aws_autoscaling_group" "main" {
  name                = "subscr-optinist-asg"
  vpc_zone_identifier = [aws_subnet.private1.id, aws_subnet.private2.id]
  target_group_arns   = [aws_lb_target_group.app.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 180
  default_cooldown = 300

  min_size         = var.asg_min_size
  max_size         = var.asg_max_size
  desired_capacity = var.asg_desired_capacity

  launch_template {
    id      = aws_launch_template.ecs.id
    version = "$Latest"
  }

  force_delete = true
  termination_policies = ["OldestInstance"]
  wait_for_capacity_timeout = "0"

  # Enable instance scale-in protection
  protect_from_scale_in = false

  # Enable detailed monitoring
  enabled_metrics = [
    "GroupMinSize",
    "GroupMaxSize",
    "GroupDesiredCapacity",
    "GroupInServiceInstances",
    "GroupTotalInstances",
    "GroupPendingInstances",
    "GroupStandbyInstances",
    "GroupTerminatingInstances"
  ]

  tag {
    key                 = "Name"
    value               = "subscr-optinist-asg-instance"
    propagate_at_launch = true
  }

  tag {
    key                 = "Type"
    value               = "ASG-ECS"
    propagate_at_launch = true
  }

  tag {
    key                 = "LaunchTemplateVersion"
    value               = aws_launch_template.ecs.latest_version
    propagate_at_launch = true
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      instance_warmup = 300
      min_healthy_percentage = 0
    }
  }

  lifecycle {
    ignore_changes = [desired_capacity]
  }

  timeouts {
    delete = "30m"
  }

  # Lifecycle hooks for logging
  initial_lifecycle_hook {
    name                 = "subscr-optinist-launch-hook"
    default_result       = "CONTINUE"
    heartbeat_timeout    = 300
    lifecycle_transition = "autoscaling:EC2_INSTANCE_LAUNCHING"
  }

  initial_lifecycle_hook {
    name                 = "subscr-optinist-terminate-hook"
    default_result       = "CONTINUE"
    heartbeat_timeout    = 300
    lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"
  }
}

# Auto Scaling Policies
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "subscr-optinist-scale-up"
  scaling_adjustment     = 1
  adjustment_type        = "ChangeInCapacity"
  cooldown              = 300
  autoscaling_group_name = aws_autoscaling_group.main.name
}

resource "aws_autoscaling_policy" "scale_down" {
  name                   = "subscr-optinist-scale-down"
  scaling_adjustment     = -1
  adjustment_type        = "ChangeInCapacity"
  cooldown              = 300
  autoscaling_group_name = aws_autoscaling_group.main.name
}

# Target Group for ALB
resource "aws_lb_target_group" "app" {
  name        = "subscr-optinist-target-group"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 5
    interval            = 60
    matcher            = "200"
    path               = "/health"
    port               = "traffic-port"
    protocol           = "HTTP"
    timeout            = 30
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "subscr-optinist-cloud-target-group"
  }
}

# ===========
# ECS Cluster
# ===========
resource "aws_ecs_cluster" "main" {
  name = "subscr-optinist-cloud-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  service_connect_defaults {
    namespace = aws_service_discovery_private_dns_namespace.main.arn
  }

  tags = {
    Name = "subscr-optinist-cloud-cluster"
  }
}

# Service Discovery
resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "subscr.optinist.local"
  vpc         = aws_vpc.main.id
}

# ECS Capacity Provider
resource "aws_ecs_capacity_provider" "main" {
  name = "subscr-optinist-capacity-provider"

  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.main.arn
    managed_termination_protection = "DISABLED"

    managed_scaling {
      maximum_scaling_step_size = 1
      minimum_scaling_step_size = 1
      status                    = "DISABLED"
      target_capacity           = 100
      instance_warmup_period    = 300
    }
  }

  tags = {
    Name = "subscr-optinist-capacity-provider"
  }
}

# ECS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = [aws_ecs_capacity_provider.main.name]

  default_capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.main.name
    weight           = 1
    base            = 0
  }

  depends_on = [
    aws_ecs_capacity_provider.main,
    aws_autoscaling_group.main
  ]

  lifecycle {
    prevent_destroy = false
    ignore_changes = [capacity_providers]
  }
}

# ===============
# Security groups
# ===============
resource "aws_security_group" "ecs" {
  name        = "subscr-ecs-optinist-cloud-security-group"
  description = "Created by Terraform for ECS"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "subscr-optinist-cloud-sg-ecs"
  }
}

resource "aws_security_group_rule" "ecs_ingress_all" {
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  ipv6_cidr_blocks  = ["::/0"]
  security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "ecs_ingress_http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  ipv6_cidr_blocks  = ["::/0"]
  security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "ecs_ingress_app" {
  type              = "ingress"
  from_port         = 8000
  to_port           = 8009
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  ipv6_cidr_blocks  = ["::/0"]
  security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "ecs_ingress_dynamic_ports" {
  type                     = "ingress"
  from_port                = 32768
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "ecs_ingress_nfs" {
  type              = "ingress"
  from_port         = 2049
  to_port           = 2049
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "ecs_ingress_mysql" {
  type              = "ingress"
  from_port         = 3306
  to_port           = 3306
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "ecs_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  ipv6_cidr_blocks  = ["::/0"]
  security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group" "alb" {
  name        = "subscr-optinist-alb-security-group"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port        = 80
    to_port          = 80
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  ingress {
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  ingress {
    from_port        = 8000
    to_port          = 8000
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "subscr-optinist-alb-sg"
  }
}

resource "aws_security_group_rule" "ecs_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.ecs.id
  description              = "ALB health checks"
}

resource "aws_security_group_rule" "alb_to_ecs_dynamic" {
  type                     = "egress"
  from_port                = 32768
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ecs.id
  security_group_id        = aws_security_group.alb.id
  description              = "ALB to ECS dynamic ports"
}

resource "aws_security_group_rule" "alb_to_ecs" {
  type                     = "egress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ecs.id
  security_group_id        = aws_security_group.alb.id
  description              = "Health check to ECS targets"
}

resource "aws_security_group" "rds" {
  name        = "subscr-optinist-rds-security-group"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "subscr-optinist-cloud-sg-rds"
  }
}

resource "aws_security_group" "efs" {
  name        = "subscr-optinist-cloud-efs-sg"
  description = "Security group for EFS mount targets"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  tags = {
    Name = "subscr-optinist-cloud-efs-sg"
  }
}

resource "aws_security_group" "nat_instance" {
  name        = "subscr-nat-instance-sg"
  description = "Security group for NAT Instance"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "subscr-optinist-nat-instance-sg"
  }
}

resource "aws_security_group" "batch" {
  name        = "subscr-optinist-batch-sg"
  description = "Security group for AWS Batch compute environments"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port = 2049
    to_port   = 2049
    protocol  = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  # Same rules as ECS for RDS access
  egress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    security_groups = [aws_security_group.rds.id]
  }

  # Internet access for ECR/S3
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "subscr-optinist-batch-sg"
  }
}

resource "aws_security_group_rule" "rds_from_batch" {
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.batch.id
  security_group_id        = aws_security_group.rds.id
  description              = "MySQL access from Batch instances"
}

# ====================
# IAM ROLES & POLICIES
# ====================

# ECS Task Execution Role (for ECS agent to pull images, etc.)
# --------------------------------------------------------------
resource "aws_iam_role" "ecs_task_execution" {
  name = "subscr-optinist-cloud-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "batch_service_additional" {
  name = "subscr-batch-service-additional"
  role = aws_iam_role.batch_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeImages",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs",
          "ec2:DeleteLaunchTemplate",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeLaunchTemplateVersions",
          "ecs:DeleteCluster",
          "ecs:ListClusters",
          "ecs:DescribeClusters"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "time_sleep" "batch_role_propagation" {
  depends_on = [
    aws_iam_role_policy_attachment.batch_service_role,
    aws_iam_role_policy_attachment.batch_service_ecs
  ]
  create_duration = "20s"
}


# ECS Task Role (for containers to call AWS services)
# ------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name = "subscr-optinist-cloud-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Attach standard policies to ECS Task Role
resource "aws_iam_role_policy_attachment" "ecs_task_efs" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonElasticFileSystemClientFullAccess"
}

resource "aws_iam_role_policy_attachment" "ecs_task_cloudwatch" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_iam_role_policy_attachment" "ecs_task_ecr" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}
resource "aws_iam_role_policy_attachment" "ecs_instance_ecr" {
  role       = aws_iam_role.ecs_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
}

# Custom policy for ECS Exec (SSM)
resource "aws_iam_role_policy" "ecs_task_ssm_exec" {
  name = "subscr-ecs-task-ssm-exec"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECS Instance Role (for EC2 instances running ECS tasks)
# -------------------------------------------------------
resource "aws_iam_role" "ecs_instance_role" {
  name = "subscr-optinist-ecs-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ecs_instance_profile" {
  name = "subscr-optinist-ecs-instance-profile"
  role = aws_iam_role.ecs_instance_role.name
}

# Standard policy attachments for ECS instances
resource "aws_iam_role_policy_attachment" "ecs_instance_role_policy" {
  role       = aws_iam_role.ecs_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "ecs_instance_cloudwatch_agent" {
  role       = aws_iam_role.ecs_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy_attachment" "ecs_instance_ssm" {
  role       = aws_iam_role.ecs_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Custom policies for ECS instances
resource "aws_iam_role_policy" "ecs_instance_enhanced_monitoring" {
  name = "subscr-ecs-instance-enhanced-monitoring"
  role = aws_iam_role.ecs_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "logs:PutLogEvents",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "autoscaling:Describe*",
          "autoscaling:CompleteLifecycleAction",
          "autoscaling:RecordLifecycleActionHeartbeat",
          "ec2:DescribeVolumes",
          "ec2:DescribeNetworkInterfaces",
          "ecs:ListTasks",
          "ecs:DescribeTasks"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_instance_ssm_complex" {
  name = "subscr-ecs-instance-ssm-complex"
  role = aws_iam_role.ecs_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:UpdateInstanceInformation"
        ]
        Resource = "*"
      }
    ]
  })
}

# NAT Instance Role (for NAT gateway instances)
# -----------------------------------------------
resource "aws_iam_role" "nat_instance" {
  name = "subscr-nat-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "nat_instance" {
  name = "subscr-nat-instance-profile"
  role = aws_iam_role.nat_instance.name
}

# RDS monitoring role
# -------------------
resource "aws_iam_role" "rds_monitoring" {
  name = "subscr-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}


# S3 policy for application storage
# ---------------------------------
resource "aws_s3_bucket_policy" "app_storage" {
  bucket = aws_s3_bucket.app_storage.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowECSTaskAccess"
        Effect    = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task.arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.app_storage.arn,
          "${aws_s3_bucket.app_storage.arn}/*"
        ]
      },
      {
        Sid    = "AllowALBLogsAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::582318560864:root" # ALB service account for ap-northeast-1
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.app_storage.arn}/alb-logs/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
      },
      {
        Sid    = "AllowLogsDeliveryAccess"
        Effect = "Allow"
        Principal = {
          Service = "delivery.logs.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.app_storage.arn}/alb-logs/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Sid    = "AllowALBGetBucketAcl"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::582318560864:root"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.app_storage.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_s3" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Cloudwatch
# ----------
resource "aws_iam_role_policy" "ecs_task_execution_cloudwatch" {
  name = "subscr-cloudwatch-logs"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# Cloudwatch agent monitoring of ECS
resource "aws_iam_role_policy" "ecs_instance_detailed_monitoring" {
  name = "subscr-ecs-instance-detailed-monitoring"
  role = aws_iam_role.ecs_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ec2:DescribeVolumes",
          "ec2:DescribeNetworkInterfaces",
          "logs:PutLogEvents",
          "logs:CreateLogGroup",
          "logs:CreateLogStream"
        ]
        Resource = "*"
      }
    ]
  })
}

# Batch Service
# -------------
resource "aws_iam_role" "batch_service" {
  name = "subscr-optinist-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "batch.amazonaws.com"
        }
      }
    ]
  })
}
# Batch Job Execution Role
resource "aws_iam_role" "batch_job" {
  name = "subscr-optinist-batch-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "subscr-optinist-batch-job-role"
  }
}

resource "aws_iam_role_policy_attachment" "batch_service_role" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_iam_role_policy_attachment" "batch_service_ecs" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonECS_FullAccess"
}

resource "aws_iam_role_policy_attachment" "batch_job_execution" {
  role       = aws_iam_role.batch_job.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_batch" {
  name = "subscr-ecs-task-batch-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "batch:SubmitJob",
          "batch:DescribeJobs",
          "batch:ListJobs",
          "batch:CancelJob"
        ]
        Resource = "*"
      }
    ]
  })
}

# Batch Spot Fleet Role
resource "aws_iam_role" "batch_spot_fleet" {
  name = "subscr-optinist-batch-spot-fleet-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "spotfleet.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_spot_fleet" {
  role       = aws_iam_role.batch_spot_fleet.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

resource "aws_iam_role_policy" "batch_job_s3" {
  name = "subscr-batch-job-s3-access"
  role = aws_iam_role.batch_job.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.app_storage.arn,
          "${aws_s3_bucket.app_storage.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_ecr_access" {
  name = "subscr-ecs-task-ecr-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}


# ===================
# AWS Batch resources
# ===================

resource "aws_batch_job_queue" "free_tier" {
  name     = "subscr-optinist-free-queue"
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.free_tier.arn
  }

  depends_on = [aws_batch_compute_environment.free_tier]

  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_batch_job_queue" "paid_tier" {
  name     = "subscr-optinist-paid-queue"
  state    = "ENABLED"
  priority = 10  # Higher priority than free tier
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.paid_tier.arn
  }

  depends_on = [aws_batch_compute_environment.paid_tier]

  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_batch_compute_environment" "free_tier" {
  type                    = "MANAGED"
  state                   = "ENABLED"
  service_role           = aws_iam_role.batch_service.arn
  depends_on = [time_sleep.batch_role_propagation]

  compute_resources {
    type                = "EC2"
    min_vcpus          = 0
    max_vcpus          = 5
    desired_vcpus      = 0
    instance_type      = ["m5.large", "m5.xlarge"]

    subnets            = [aws_subnet.private1.id, aws_subnet.private2.id]
    security_group_ids = [aws_security_group.batch.id]

    instance_role = aws_iam_instance_profile.ecs_instance_profile.arn

    tags = {
      Name = "subscr-optinist-batch-free"
    }
  }
}

resource "aws_batch_compute_environment" "paid_tier" {
  type                    = "MANAGED"
  state                   = "ENABLED"
  service_role           = aws_iam_role.batch_service.arn
  depends_on = [time_sleep.batch_role_propagation]

  compute_resources {
    type                = "EC2"
    min_vcpus          = 0
    max_vcpus          = 10
    desired_vcpus      = 0
    instance_type      = ["optimal"]

    # Same network setup as ECS
    subnets            = [aws_subnet.private1.id, aws_subnet.private2.id]
    security_group_ids = [aws_security_group.batch.id]

    instance_role = aws_iam_instance_profile.ecs_instance_profile.arn

    tags = {
      Name = "subscr-optinist-batch-paid"
    }
  }
}

# ==================================================
# CloudWatch Log Groups for comprehensive monitoring
# ==================================================
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/subscr-optinist-cloud-taskdef"
  retention_in_days = 7

  tags = {
    Name = "subscr-optinist-cloud-logs"
  }
}

resource "aws_cloudwatch_log_group" "autoscaling" {
  name              = "/aws/autoscaling/subscr-optinist"
  retention_in_days = 14

  tags = {
    Name = "subscr-optinist-autoscaling-logs"
  }
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/application/subscr-optinist"
  retention_in_days = 14

  tags = {
    Name = "subscr-optinist-application-logs"
  }
}

resource "aws_cloudwatch_log_group" "batch" {
  name              = "/aws/batch/job"
  retention_in_days = 14

  tags = {
    Name = "subscr-optinist-batch-logs"
  }
  depends_on = [
    aws_batch_job_queue.free_tier,
    aws_batch_job_queue.paid_tier,
    aws_batch_compute_environment.free_tier,
    aws_batch_compute_environment.paid_tier
  ]
  lifecycle {
    ignore_changes = [name]
    prevent_destroy = true
  }
}

resource "aws_cloudwatch_log_metric_filter" "user_cpu_usage" {
  name           = "user-cpu-usage"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  pattern        = "[timestamp, level, user_id, cpu_usage]"

  metric_transformation {
    name      = "UserCPUUsage"
    namespace = "OptiNiSt/Application"
    value     = "$cpu_usage"
  }
}


# CloudWatch Dashboard for monitoring
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "subscr-optinist-monitoring"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.main.name, "ClusterName", aws_ecs_cluster.main.name],
            ["AWS/ECS", "MemoryUtilization", "ServiceName", aws_ecs_service.main.name, "ClusterName", aws_ecs_cluster.main.name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "ap-northeast-1"
          title   = "ECS Service Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/AutoScaling", "GroupDesiredCapacity", "AutoScalingGroupName", aws_autoscaling_group.main.name],
            ["AWS/AutoScaling", "GroupInServiceInstances", "AutoScalingGroupName", aws_autoscaling_group.main.name],
            ["AWS/AutoScaling", "GroupTotalInstances", "AutoScalingGroupName", aws_autoscaling_group.main.name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "ap-northeast-1"
          title   = "Auto Scaling Group Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.main.arn_suffix],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.main.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_2XX_Count", "LoadBalancer", aws_lb.main.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", aws_lb.main.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.main.arn_suffix]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "ap-northeast-1"
          title   = "Load Balancer Metrics"
          period  = 300
        }
      }
    ]
  })
}


# ======================================
# Launch Template for Auto Scaling Group
# ======================================

# Get the latest ECS-optimized AMI
data "aws_ami" "ecs_optimized" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_launch_template" "ecs" {
  name_prefix   = "subscr-optinist-ecs-"
  image_id      = data.aws_ami.ecs_optimized.id
  instance_type = "t3.large"
  key_name      = aws_key_pair.subscr_optinist_cloud_key_pair.key_name

  vpc_security_group_ids = [aws_security_group.ecs.id]

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_instance_profile.name
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 30
      volume_type = "gp3"
      encrypted   = true
    }
  }

  monitoring {
    enabled = true
  }

user_data = base64encode(<<-EOF
    #!/bin/bash
    set -e
    exec > /var/log/ecs-setup.log 2>&1

    echo "$(date): Starting ECS setup with OptiNiSt configuration"

    # ECS Configuration
    echo ECS_CLUSTER=${aws_ecs_cluster.main.name} >> /etc/ecs/ecs.config
    echo ECS_ENABLE_CONTAINER_METADATA=true >> /etc/ecs/ecs.config
    echo ECS_ENABLE_TASK_IAM_ROLE=true >> /etc/ecs/ecs.config

    # Install packages
    yum update -y
    yum install -y amazon-ssm-agent mysql amazon-efs-utils nc mysql-client git docker amazon-cloudwatch-agent

    # Start SSM agent
    if ! systemctl is-active --quiet amazon-ssm-agent; then
        systemctl enable amazon-ssm-agent
        systemctl start amazon-ssm-agent
    fi

    # Create CloudWatch agent config
    cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'CW_CONFIG'
    {
        "metrics": {
            "namespace": "CWAgent",
            "metrics_collected": {
                "mem": {
                    "measurement": [
                        "mem_used_percent"
                    ]
                },
                "cpu": {
                    "measurement": [
                        "cpu_usage_idle",
                        "cpu_usage_iowait"
                    ],
                    "totalcpu": true
                }
            }
        }
    }
    CW_CONFIG

    # Start CloudWatch agent
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
        -a fetch-config -m ec2 -s \
        -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

    # Start Docker (using same safe approach)
    if ! systemctl is-active --quiet docker; then
        systemctl enable docker || echo "$(date): Docker enable failed"
        systemctl start docker || echo "$(date): Docker start failed"
    fi
    for user in ec2-user ssm-user; do
      if id "$user" &>/dev/null; then
          usermod -a -G docker "$user" && echo "$(date): Added $user to docker group"
          break
      fi
    done

    # Clone and build OptiNiSt
    echo "$(date): Cloning OptiNiSt repository"
    cd /opt
        git clone -b ${var.git_branch} ${var.git_repo} optinist-for-cloud || {
        echo "$(date): ERROR: Git clone failed!"
        exit 1
    }
    if [ ! -d "optinist-for-cloud" ]; then
        echo "$(date): ERROR: Repository directory not created"
        exit 1
    fi
    cd optinist-for-cloud

    # Create Firebase configuration files on the host
    echo "$(date): Creating Firebase configuration files"
    mkdir -p /opt/optinist-for-cloud/studio/config/auth

    # Create firebase_config.json
    cat > /opt/optinist-for-cloud/studio/config/auth/firebase_config.json << 'FIREBASE_CONFIG'
    ${var.firebase_config_json}
    FIREBASE_CONFIG

    # Create firebase_private.json
    cat > /opt/optinist-for-cloud/studio/config/auth/firebase_private.json << 'FIREBASE_PRIVATE'
    ${var.firebase_private_json}
    FIREBASE_PRIVATE

    # Set proper permissions
    chmod 644 /opt/optinist-for-cloud/studio/config/auth/firebase_*.json

    # Add AWS Batch plugins to Dockerfile
    echo "$(date): Adding AWS Batch plugins to Dockerfile"
    # Build the Docker image
    echo "$(date): Building OptiNiSt Docker image"
    if [ ! -f "studio/config/docker/Dockerfile" ]; then
        echo "ERROR: Dockerfile not found in repository"
        ls -la
        exit 1
    fi

    # ECR login and pull pre-built image
    echo "$(date): Logging into ECR and pulling pre-built image"
    aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin ${split("/", var.ecr_repository_url)[0]}
    echo "$(date): Pulling OptiNiSt Docker image from ECR"
    docker pull "${var.ecr_repository_url}:latest" || {
        echo "ERROR: Docker pull failed!"
        exit 1
    }

    # EFS setup
    mkdir -p /mnt/efs
    echo "${aws_efs_file_system.snmk.id}.efs.ap-northeast-1.amazonaws.com:/ /mnt/efs efs tls,_netdev" >> /etc/fstab
    mount -a || echo "EFS will retry"

    # Test DB connection (non-blocking)
    nc -z ${replace(aws_db_instance.main.endpoint, ":3306", "")} 3306 && echo "DB accessible" || echo "DB will be available"
    EOF
  )
  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "subscr-optinist-ecs-instance"
      Type = "ECS"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============
# Setup scripts
# =============

resource "null_resource" "build_and_deploy" {
  depends_on = [aws_lb.main, aws_ecs_service.main]

  triggers = {
    alb_dns = aws_lb.main.dns_name
    # Force rebuild when git branch changes
    git_branch = var.git_branch
    # Force rebuild when ECR repo changes
    ecr_repo = var.ecr_repository_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "=== Starting automated build and deploy ==="
      echo "ALB DNS: ${aws_lb.main.dns_name}"

      # Create frontend config with ALB DNS
      echo "Creating frontend .env.production..."
      cat > ../../../frontend/.env.production << 'ENV_EOF'
REACT_APP_SERVER_HOST=${aws_lb.main.dns_name}
REACT_APP_SERVER_PORT=80
REACT_APP_SERVER_PROTO=http
REACT_APP_EXPDB_METADATA_EDITABLE=true
ENV_EOF

      echo "Frontend configuration created:"
      cat ../../../frontend/.env.production

      # Build and push image
      echo "Building and pushing Docker image..."
      chmod +x ecr_build_push.sh
      ./ecr_build_push.sh

      echo "Waiting for ECR image to be available..."
      sleep 60

      echo "✅ Build and push completed successfully"

    EOT
  }
}

resource "null_resource" "deploy_to_ecs" {
  depends_on = [null_resource.build_and_deploy]

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "=== Starting ECS deployment ==="

      # Force ECS deployment
      echo "Forcing ECS service deployment..."
      aws ecs update-service \
        --cluster ${aws_ecs_cluster.main.name} \
        --service ${aws_ecs_service.main.name} \
        --force-new-deployment \
        --region ${var.aws_region}

      echo "Waiting for ECS service to stabilize..."
            # Check if service is already running first
            SERVICE_STATUS=$(aws ecs describe-services \
              --cluster ${aws_ecs_cluster.main.name} \
              --services ${aws_ecs_service.main.name} \
              --region ${var.aws_region} \
              --query 'services[0].status' --output text)

            if [ "$SERVICE_STATUS" = "ACTIVE" ]; then
              echo "Service is already active, checking running count..."
              RUNNING_COUNT=$(aws ecs describe-services \
                --cluster ${aws_ecs_cluster.main.name} \
                --services ${aws_ecs_service.main.name} \
                --region ${var.aws_region} \
                --query 'services[0].runningCount' --output text)

              if [ "$RUNNING_COUNT" -gt "0" ]; then
                echo "Service already has $RUNNING_COUNT running tasks"
              else
                echo "Waiting for service to stabilize..."
                timeout 1800 aws ecs wait services-stable \
                  --cluster ${aws_ecs_cluster.main.name} \
                  --services ${aws_ecs_service.main.name} \
                  --region ${var.aws_region} \
                  --cli-read-timeout 1800 \
                  --cli-connect-timeout 120 || echo "Warning: Service stabilization timed out, but continuing..."
              fi
            else
              echo "Service not active, waiting..."
              timeout 1800 aws ecs wait services-stable \
                --cluster ${aws_ecs_cluster.main.name} \
                --services ${aws_ecs_service.main.name} \
                --region ${var.aws_region} \
                --cli-read-timeout 1800 \
                --cli-connect-timeout 120 || echo "Warning: Service stabilization timed out, but continuing..."
            fi

      echo "=== DEPLOYMENT COMPLETE ==="
      echo "✅ Application is ready at: http://${aws_lb.main.dns_name}"
      echo "✅ Health check: http://${aws_lb.main.dns_name}/health"
    EOT
  }
}

# ========================================
resource "local_file" "app_setup_script" {
  content = <<-EOF
#!/usr/bin/env bash
set -e

LOGFILE="/var/log/app-setup.log"
exec > $LOGFILE 2>&1

echo "$(date): Starting application setup script"

# Function for retries
retry_command() {
    local max_attempts=$1
    local delay=$2
    local command="$${@:3}"

    for i in $$(seq 1 $max_attempts); do
        echo "$$(date): Attempting: $$command (attempt $$i/$$max_attempts)"
        if eval "$$command"; then
            echo "$$(date): Success: $$command"
            return 0
        else
            echo "$$(date): Failed attempt $$I/$$max_attempts"
            [ $$i -lt $max_attempts ] && sleep $$delay
        fi
    done

    echo "$$(date): ERROR: Command failed after $$max_attempts attempts: $$command"
    return 1
}

# Wait for ECS agent to be ready
echo "$(date): Waiting for ECS agent to be ready"
retry_command 10 30 "curl -s http://localhost:51678/v1/metadata >/dev/null"

# Create config files
echo "$(date): Creating configuration files"
mkdir -p /opt/optinist/optinist-for-cloud/studio/config/auth

# Create .env file
cat > /opt/optinist/optinist-for-cloud/studio/config/.env << 'CONFIG_ENV'
SECRET_KEY='${var.optinist_secret_key}'
USE_FIREBASE_TOKEN=True
MYSQL_SERVER=${aws_db_instance.main.endpoint}
MYSQL_DATABASE=${var.mysql_database}
MYSQL_USER=${var.mysql_user}
MYSQL_PASSWORD=${var.mysql_password}
S3_DEFAULT_BUCKET_NAME=${aws_s3_bucket.app_storage.id}
CONFIG_ENV

# Create Firebase config files
cat > /opt/optinist/optinist-for-cloud/studio/config/auth/firebase_config.json << 'FIREBASE_CONFIG'
${var.firebase_config_json}
FIREBASE_CONFIG

cat > /opt/optinist/optinist-for-cloud/studio/config/auth/firebase_private.json << 'FIREBASE_PRIVATE'
${var.firebase_private_json}
FIREBASE_PRIVATE

# Database initialization
echo "$(date): Starting database initialization"
retry_command 30 10 "nc -z ${replace(aws_db_instance.main.endpoint, ":3306", "")} 3306"

echo "$(date): Application setup completed successfully"
EOF

  filename = "${path.module}/app_setup.sh"
}

# SSM document to run setup script
resource "aws_ssm_document" "app_setup" {
  name          = "subscr-optinist-app-setup"
  document_type = "Command"
  document_format = "YAML"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Application setup for OptiNiSt instances"
    parameters = {}
    mainSteps = [
      {
        action = "aws:downloadContent"
        name   = "downloadSetupScript"
        inputs = {
          sourceType = "S3"
          sourceInfo = jsonencode({
            path = "https://s3.amazonaws.com/${aws_s3_bucket.app_storage.id}/scripts/app_setup.sh"
          })
          destinationPath = "/tmp"
        }
      },
      {
        action = "aws:runShellScript"
        name   = "runSetupScript"
        inputs = {
          timeoutSeconds = "3600"
          runCommand = [
            "chmod +x /tmp/app_setup.sh",
            "/tmp/app_setup.sh"
          ]
        }
      }
    ]
  })
}

resource "aws_ssm_association" "app_setup" {
  name = aws_ssm_document.app_setup.name

  targets {
    key    = "tag:aws:autoscaling:groupName"
    values = [aws_autoscaling_group.main.name]
  }

  schedule_expression = "rate(30 minutes)"
  max_concurrency    = "1"
  max_errors         = "0"

  compliance_severity = "HIGH"
}


# ===================
# ECS Task Definition
# ===================
resource "aws_ecs_task_definition" "app" {
  family                   = "subscr-optinist-cloud-taskdef"
  requires_compatibilities = ["EC2"]
  network_mode            = "bridge"
  cpu                     = 2048
  memory                  = 6144
  task_role_arn          = aws_iam_role.ecs_task.arn
  execution_role_arn     = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([
    {
      name                  = "subscr-optinist-cloud-container"
      image                 = "${var.ecr_repository_url}:latest"
      cpu                   = 1536
      memory                = 5120
      memoryReservation     = 3072
      essential             = true
      workingDirectory      = "/app"
      entryPoint            = ["/bin/sh", "-c"]
      command               = ["./cloud-startup.sh"]

      portMappings = [
        {
          name           = "subscr-optinist-cloud-container-port-8000"
          containerPort  = 8000
          hostPort       = 8000
          protocol       = "tcp"
        }
      ]

      environment = [
        {
          name  = "CLOUDWATCH_LOG_GROUP"
          value = "/ecs/subscr-optinist-cloud-taskdef"
        },
        {
          name  = "PYTHONPATH"
          value = "/app/"
        },
        {
          name  = "TZ"
          value = "Asia/Tokyo"
        },
        {
          name  = "DB_HOST"
          value = split(":", aws_db_instance.main.endpoint)[0]
        },
        {
          name  = "DB_PORT"
          value = split(":", aws_db_instance.main.endpoint)[1]
        },
        {
          name  = "DB_USER"
          value = var.mysql_user
        },
        {
          name  = "DB_NAME"
          value = var.mysql_database
        },
        {
          name  = "DB_PASSWORD"
          value = var.mysql_password
        },
        {
          name  = "BACKEND_HOST"
          value = "0.0.0.0"
        },
        {
          name  = "BACKEND_PORT"
          value = "8000"
        },
        {
          name  = "INITIAL_FIREBASE_UID"
          value = var.optinist_admin_uid
        },
        {
          name  = "INITIAL_USER_NAME"
          value = var.optinist_admin_name
        },
        {
          name  = "INITIAL_USER_EMAIL"
          value = var.optinist_admin_email
        },
        {
          name  = "SECRET_KEY"
          value = var.optinist_secret_key
        },
        {
          name = "S3_DEFAULT_BUCKET_NAME"
          value = aws_s3_bucket.app_storage.id
        },
        {
          name  = "USE_AWS_BATCH"
          value = "true"
        },
        {
          name = "AWS_BATCH_S3_BUCKET_NAME"
          value = aws_s3_bucket.app_storage.id
        },
        {
          name = "AWS_DEFAULT_PROVIDER"
          value = "S3"
        },
        {
          name  = "AWS_BATCH_JOB_ROLE"
          value = aws_iam_role.ecs_task.arn
        },
        {
          name  = "AWS_BATCH_JOB_DEFINITION"
          value = "subscr-optinist-job-definition"
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        },
        {
          name  = "AWS_BATCH_FREE_QUEUE"
          value = aws_batch_job_queue.free_tier.name
        },
        {
          name  = "AWS_BATCH_PAID_QUEUE"
          value = aws_batch_job_queue.paid_tier.name
        },
        {
          name  = "AWS_BATCH_LOG_STREAM_PREFIX"
          value = "subscr-optinist-for-cloud"
        },
        {
          name  = "AWS_ECR_REPOSITORY"
          value = "${var.ecr_repository_url}:latest"
        },
        {
          name  = "AWS_BATCH_LOG_GROUP"
          value = "/aws/batch/job"
        },
        {
          name  = "AWS_BATCH_JOB_TIMEOUT"
          value = "3600"
        },
        {
          name  = "LOG_LEVEL"
          value = "DEBUG"
        },
        {
          name  = "UVICORN_ACCESS_LOG"
          value = "1"
        },
        {
          name  = "CORS_ORIGINS"
          value = "*"
        },
        {
          name  = "PYTHONUNBUFFERED"
          value = "1"
        },
        {
          name  = "OPTINIST_DIR"
          value = "/app/studio_data"
        },
      ]

      mountPoints = [
        {
          sourceVolume  = "subscr-optinist-cloud-snmk-volume"
          containerPath = "/app/.snakemake"
          readOnly      = false
        },
        {
          sourceVolume  = "subscr-optinist-cloud-studio-data-volume"
          containerPath = "/app/studio_data"
          readOnly      = false
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -v http://127.0.0.1:8000/health"]
        interval    = 300
        timeout     = 5
        retries     = 3
        startPeriod = 300
      }

      dockerLabels = {
        "health.check.enabled" = "true"
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/subscr-optinist-cloud-taskdef"
          "mode"                  = "non-blocking"
          "awslogs-multiline-pattern" = "^\\[\\d{4}-\\d{2}-\\d{2}\\s\\d{2}:\\d{2}:\\d{2}"
          "max-buffer-size"       = "25m"
          "awslogs-region"        = "ap-northeast-1"
          "awslogs-create-group"  = "true"
          "awslogs-stream-prefix" = "ecs"
          "mode"                  = "non-blocking"
        }
      }
    }
  ])

  volume {
    name = "subscr-optinist-cloud-studio-data-volume"
  }

  volume {
    name = "subscr-optinist-cloud-snmk-volume"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.snmk.id
      root_directory = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.snmk.id
        iam            = "DISABLED"
      }
    }
  }

  tags = {
    Name = "subscr-optinist-cloud-taskdef"
  }
}
# ===========
# ECS Service
# ===========
resource "aws_ecs_service" "main" {
  name             = "subscr-optinist-cloud-service"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.app.arn
  desired_count    = 1
  deployment_maximum_percent        = 200
  deployment_minimum_healthy_percent = 0

  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.main.name
    weight           = 1
    base            = 0
  }

  enable_execute_command = true

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "subscr-optinist-cloud-container"
    container_port   = 8000
  }

  depends_on = [
    aws_autoscaling_group.main,
    aws_db_instance.main,
    aws_lb.main,
    aws_lb_listener.http
  ]

  health_check_grace_period_seconds = 300

  tags = {
    Name = "subscr-optinist-cloud-service"
  }
}

# ============================
# Auto Scaling for ECS Service
# ============================
#resource "aws_appautoscaling_target" "ecs_target" {
#  max_capacity       = 5
#  min_capacity       = 0
#  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
#  scalable_dimension = "ecs:service:DesiredCount"
#  service_namespace  = "ecs"
#}
#
#resource "aws_appautoscaling_policy" "ecs_policy" {
#  name               = "subscr-optinist-cloud-autoscaling-policy"
#  policy_type        = "TargetTrackingScaling"
#  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
#  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
#  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace
#
#  target_tracking_scaling_policy_configuration {
#    target_value = 75.0
#    predefined_metric_specification {
#      predefined_metric_type = "ECSServiceAverageCPUUtilization"
#    }
#  }
#}

# ========================
# AWS batch job definition
# ========================
resource "aws_batch_job_definition" "optinist" {
  name = "subscr-optinist-job-definition"
  type = "container"

  container_properties = jsonencode({
    image = "${var.ecr_repository_url}:latest"
    vcpus = 2
    memory = 4096
    jobRoleArn = aws_iam_role.ecs_task.arn

    command = ["python", "/app/studio/app/common/core/rules/func.py"]

    mountPoints = [
        {
          sourceVolume = "tmp"
          containerPath = "/tmp"
          readOnly = false
        }
      ]

    environment = [
      {
        name = "DB_HOST"
        value = split(":", aws_db_instance.main.endpoint)[0]
      },
      {
        name = "DB_PORT"
        value = split(":", aws_db_instance.main.endpoint)[1]
      },
      {
        name = "DB_USER"
        value = var.mysql_user
      },
      {
        name = "DB_PASSWORD"
        value = var.mysql_password
      },
      {
        name = "DB_NAME"
        value = var.mysql_database
      },
      {
        name = "AWS_DEFAULT_REGION"
        value = var.aws_region
      },
      {
        name = "S3_DEFAULT_BUCKET_NAME"
        value = aws_s3_bucket.app_storage.id
      },
      {
        name = "USE_AWS_BATCH"
        value = "true"
      }
    ]
  })
}

# =======
# Outputs
# =======
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value = {
    public1 = aws_subnet.public1.id
    public2 = aws_subnet.public2.id
  }
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value = {
    private1 = aws_subnet.private1.id
    private2 = aws_subnet.private2.id
  }
}

output "public_subnet_cidrs" {
  description = "CIDR blocks of public subnets"
  value = {
    public1 = aws_subnet.public1.cidr_block
    public2 = aws_subnet.public2.cidr_block
  }
}

output "private_subnet_cidrs" {
  description = "CIDR blocks of private subnets"
  value = {
    private1 = aws_subnet.private1.cidr_block
    private2 = aws_subnet.private2.cidr_block
  }
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.main.dns_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.main.name
}

output "efs_id" {
  description = "ID of the EFS file system"
  value       = aws_efs_file_system.snmk.id
}

output "app_storage_bucket" {
  description = "S3 bucket for application storage"
  value       = aws_s3_bucket.app_storage.id
}

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.main.name
}

output "launch_template_id" {
  description = "ID of the Launch Template"
  value       = aws_launch_template.ecs.id
}

# Configuration Outputs
output "frontend_config" {
  description = "Configuration values for frontend/.env.production"
  value = {
    REACT_APP_SERVER_HOST = aws_lb.main.dns_name
    REACT_APP_SERVER_PORT = "80"
    REACT_APP_SERVER_PROTO = "http"
    REACT_APP_EXPDB_METADATA_EDITABLE=true
  }
}

output "backend_config" {
  description = "Configuration values for studio/auth/config/.env"
  value = {
    S3_DEFAULT_BUCKET_NAME = aws_s3_bucket.app_storage.id
  }
}

output "aws_batch_config" {
  description = "AWS Batch configuration values for batch_config"
  value = {
    AWS_BATCH_JOB_ROLE = aws_iam_role.ecs_task.arn
    AWS_BATCH_S3_BUCKET_NAME = aws_s3_bucket.app_storage.id
    AWS_BATCH_S3_USER_DATA_BUCKET = aws_s3_bucket.user_data.id
    AWS_BATCH_FREE_QUEUE = aws_batch_job_queue.free_tier.name
    AWS_BATCH_PAID_QUEUE = aws_batch_job_queue.paid_tier.name
    AWS_BATCH_JOB_DEFINITION = aws_batch_job_definition.optinist.name
  }
}

# Output the key information
output "ssh_key_name" {
  description = "Name of the generated SSH key pair"
  value       = aws_key_pair.subscr_optinist_cloud_key_pair.key_name
}

output "ssh_private_key_path" {
  description = "Path to the private key file"
  value       = local_file.private_key.filename
}

output "ssh_command" {
  description = "SSH command to connect to instances"
  value       = "ssh -i ${local_file.private_key.filename} ec2-user@<INSTANCE_IP>"
}
