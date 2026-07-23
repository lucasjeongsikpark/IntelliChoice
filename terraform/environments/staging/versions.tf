terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Bootstrapped by hand once (chicken-and-egg - the bucket can't be managed by the
  # state it holds): `aws s3api create-bucket` + versioning + encryption + public-access
  # block, see the S32/D-084 session log. `use_lockfile` is Terraform >=1.10's native S3
  # conditional-write locking - no DynamoDB lock table needed.
  backend "s3" {
    bucket       = "intellichoice-terraform-state-320503430250"
    key          = "staging/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

# No `profile` pinned here - resolved via the standard AWS credential chain
# (AWS_PROFILE env var locally, OIDC-assumed role credentials in GitHub Actions) so the
# same config works in both places without an environment-specific code change.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
