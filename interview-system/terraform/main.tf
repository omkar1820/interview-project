locals {
  name = var.project
  tags = { Project = var.project, ManagedBy = "terraform" }
}

# ---------------------------------------------------------------- Container registry
resource "aws_ecr_repository" "app" {
  name                 = "interview-eval-system"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 20 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20 }
      action       = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------- Security groups
resource "aws_security_group" "app" {
  name_prefix = "${local.name}-app-"
  vpc_id      = var.vpc_id
  description = "App server"

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "SSH from Jenkins"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "db" {
  name_prefix = "${local.name}-db-"
  vpc_id      = var.vpc_id
  description = "RDS MySQL - only reachable from the app server"

  ingress {
    description     = "MySQL from app"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  tags = local.tags
}

# ---------------------------------------------------------------- RDS MySQL
resource "random_password" "db" {
  length  = 24
  special = false
}

resource "aws_db_subnet_group" "db" {
  name       = "${local.name}-db"
  subnet_ids = var.db_subnet_ids
  tags       = local.tags
}

resource "aws_db_parameter_group" "db" {
  name   = "${local.name}-mysql8"
  family = "mysql8.0"
  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }
  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }
  tags = local.tags
}

resource "aws_db_instance" "db" {
  identifier              = "${local.name}-mysql"
  engine                  = "mysql"
  engine_version          = "8.0"
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  max_allocated_storage   = var.db_allocated_storage * 5
  storage_type            = "gp3"
  storage_encrypted       = true
  db_name                 = var.db_name
  username                = var.db_username
  password                = random_password.db.result
  db_subnet_group_name    = aws_db_subnet_group.db.name
  parameter_group_name    = aws_db_parameter_group.db.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  publicly_accessible     = false
  multi_az                = var.multi_az
  backup_retention_period = 7
  deletion_protection     = var.deletion_protection
  skip_final_snapshot     = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${local.name}-final" : null
  auto_minor_version_upgrade = true
  tags                    = local.tags
}

# ---------------------------------------------------------------- Secrets Manager
resource "aws_secretsmanager_secret" "db" {
  name                    = "interview-eval/db"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    host     = aws_db_instance.db.address
    port     = aws_db_instance.db.port
    dbname   = var.db_name
  })
}

resource "random_password" "admin_key" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "interview-eval/app"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    OPENAI_API_KEY = var.openai_api_key
    ADMIN_API_KEY  = random_password.admin_key.result
  })
}

# ---------------------------------------------------------------- App server (EC2)
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-app"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy" "secrets" {
  name = "read-app-secrets"
  role = aws_iam_role.app.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.db.arn, aws_secretsmanager_secret.app.arn]
    }]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name}-app"
  role = aws_iam_role.app.name
}

resource "aws_instance" "app" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = aws_iam_instance_profile.app.name
  key_name                    = var.key_name
  associate_public_ip_address = true

  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    volume_size = 20
    encrypted   = true
  }
  user_data = <<-EOT
    #!/bin/bash
    dnf install -y docker jq curl
    systemctl enable --now docker
    usermod -aG docker ec2-user
  EOT
  tags = merge(local.tags, { Name = "${local.name}-app" })
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
  tags     = local.tags
}
