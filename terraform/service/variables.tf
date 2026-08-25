variable "aws_secret_name" {
  description = "The path to the AWS Secret Manager resource which contains the Github App .pem file"
  type        = string
}

variable "aws_bucket_name" {
  description = "The name of the S3 bucket which the cloud config is stored in. This should not include the environment name (i.e. sdp-dev) as it will be added automatically."
  type        = string
  default     = "github-repository-archive-script"
}

variable "env_name" {
  description = "AWS environment"
  type        = string
  default     = "sdp-dev"
}

variable "lambda_name" {
  description = "AWS Lambda Function Name"
  type        = string
  default     = "lambda-function"
}

variable "lambda_arch" {
  description = "AWS Lambda Architecture"
  type        = string
  default     = "x86_64"
}

variable "ecr_repository" {
  description = "Name of the ECR repository containing the Lambda image"
  type        = string
}

variable "container_ver" {
  description = "Container tag"
  type        = string
  default     = "v1.0.0"
}

variable "lambda_timeout" {
  description = "AWS Lambda Timeout Value in Seconds"
  type        = number
  default     = 60
}

variable "schedule" {
  description = "The schedule to trigger the lambda, rate(value minutes|hours|days) or cron(minutes hours day-of-month month day-of-week year)"
  type        = string
  default     = "cron(0 6 ? * 2 *)" // every Monday at 6am
}

variable "log_retention_days" {
  description = "Lambda log retention in days"
  type        = number
  default     = 90
}

variable "github_org" {
  description = "Github Organisation"
  type        = string
  default     = "ONS-Innovation"
}

variable "github_app_client_id" {
  description = "Github App Client ID"
  type        = string
}

variable "lambda_memory" {
  description = "AWS Lambda Memory Size in MB"
  type        = number
  default     = 128
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-2"
}

variable "project_tag" {
  description = "Project"
  type        = string
  default     = "SDP"
}

variable "team_owner_tag" {
  description = "Team Owner"
  type        = string
  default     = "Knowledge Exchange Hub"
}

variable "business_owner_tag" {
  description = "Business Owner"
  type        = string
  default     = "DST"
}

locals {
  bucket_name    = "${var.env_name}-${var.aws_bucket_name}"
  aws_account_id = data.aws_caller_identity.current.account_id
}