variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "project" {
  type    = string
  default = "interview-eval"
}
variable "vpc_id" { type = string }
variable "public_subnet_id" {
  type        = string
  description = "Public subnet for the app EC2 instance"
}
variable "db_subnet_ids" {
  type        = list(string)
  description = "At least two subnets in different AZs (private recommended) for RDS"
}
variable "key_name" {
  type        = string
  description = "Existing EC2 key pair used by Jenkins to SSH"
}
variable "ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH (your Jenkins server IP, e.g. 203.0.113.10/32)"
}
variable "instance_type" {
  type    = string
  default = "t3.small"
}
variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}
variable "db_allocated_storage" {
  type    = number
  default = 20
}
variable "db_name" {
  type    = string
  default = "interview_db"
}
variable "db_username" {
  type    = string
  default = "interview_admin"
}
variable "multi_az" {
  type    = bool
  default = false
}
variable "deletion_protection" {
  type    = bool
  default = false
}
variable "openai_api_key" {
  type      = string
  sensitive = true
  default   = ""
}
