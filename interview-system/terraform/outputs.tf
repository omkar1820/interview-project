output "rds_endpoint" { value = aws_db_instance.db.address }
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "app_public_ip" { value = aws_eip.app.public_ip }
output "db_secret_id" { value = aws_secretsmanager_secret.db.name }
output "app_secret_id" { value = aws_secretsmanager_secret.app.name }
