variable "aws_region" {
  type = string
   default = "us-east-1"
  }
variable "project" {
  type = string
   default = "careerflow"
  }
variable "instance_type" {
  type = string
   default = "t3.micro"
  }
variable "domain_name" {
  type = string
   default = ""
   description = "Full DNS name for HTTPS, e.g. careers.example.com. Strongly recommended for sign-in."
  }
variable "hosted_zone_id" {
  type = string
   default = ""
   description = "Existing Route53 hosted zone ID. Leave empty only for HTTP-only infrastructure smoke tests."
  }
variable "my_cidr" {
  type = string
   default = "0.0.0.0/0"
   description = "Optional IP restriction on web ingress; default public careers site."
  }
