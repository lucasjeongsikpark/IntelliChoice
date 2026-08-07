data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  # /24s carved out of the /16: 0.x/1.x = public, 10.x/11.x = private.
  public_subnet_cidrs  = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 8, i)]
  private_subnet_cidrs = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 8, i + 10)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "public" {
  count                   = var.az_count
  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_subnet_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-public-${local.azs[count.index]}" })
}

resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_subnet_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = merge(var.tags, { Name = "${var.name_prefix}-private-${local.azs[count.index]}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = var.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# D-084: private subnets have no default internet route *by default*. Everything a
# private-subnet ECS task needs - ECR, CloudWatch Logs, Secrets Manager, Bedrock, X-Ray,
# and S3 for ECR image layers - is reachable via the VPC endpoints below, so the account
# ran with zero NAT gateways and zero internet egress.
#
# D-214 makes that conditional rather than absolute, because LangSmith is a third-party
# SaaS with no PrivateLink equivalent: `api.smith.langchain.com` is reachable only over the
# internet. Measured before deciding - `learning-api` runs in these subnets with
# `assignPublicIp=DISABLED` and the account had 0 NAT gateways, so a LangSmith API key
# alone would have produced silent upload failures and a per-graph-run timeout wait.
#
# Deliberately **one** NAT, in the first AZ, not one per AZ. It costs ~$33/month per
# gateway and the traffic crossing it is telemetry: if that AZ goes down, private tasks in
# the other AZ lose *tracing*, not function, because every path they actually need still
# goes through a VPC endpoint. Paying twice for redundancy on an observability side-channel
# is the wrong trade.
resource "aws_eip" "nat" {
  count  = var.nat_gateway_enabled ? 1 : 0
  domain = "vpc"

  tags = merge(var.tags, { Name = "${var.name_prefix}-nat-eip" })
}

resource "aws_nat_gateway" "this" {
  count         = var.nat_gateway_enabled ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  # The IGW route must exist before the NAT can reach anything.
  depends_on = [aws_internet_gateway.this]

  tags = merge(var.tags, { Name = "${var.name_prefix}-nat" })
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, { Name = "${var.name_prefix}-private-rt" })
}

# A separate `aws_route` rather than an inline `route` block, so that flipping
# `nat_gateway_enabled` back to false removes the route and restores the no-egress property
# without recreating the route table (which would briefly detach every private subnet).
resource "aws_route" "private_nat" {
  count                  = var.nat_gateway_enabled ? 1 : 0
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[0].id
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "vpc_endpoints" {
  count       = var.enable_interface_endpoints ? 1 : 0
  name        = "${var.name_prefix}-vpce-sg"
  description = "Allow HTTPS from inside the VPC to interface VPC endpoints"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTPS from within the VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpce-sg" })
}

locals {
  interface_endpoint_services = concat(
    ["ecr.api", "ecr.dkr", "logs", "secretsmanager"],
    # "bedrock-runtime" is the classic API (boto3/CLI) real Bedrock calls need from a
    # NAT-less private subnet - required regardless of provider, found live during
    # S32/D-084's troubleshooting. The "bedrock-mantle" interface endpoint (a separate
    # PrivateLink service the `anthropic` SDK's AnthropicBedrockMantle client used) was
    # removed after D-084's model-access investigation found every flagship model on
    # that surface blocked account-wide by an AWS-Sales-only access gate - Claude
    # Haiku 4.5 via this classic bedrock-runtime surface is what the app actually uses.
    var.bedrock_runtime_endpoint_enabled ? ["bedrock-runtime"] : [],
    # "xray" is what the OTel sidecar's `awsxray` exporter posts segments to. Same
    # lesson as bedrock-runtime above, and as the sidecar's own image pull (AUD-F-10):
    # in a NAT-less VPC, every AWS API the tasks call needs its own endpoint, and the
    # failure surfaces only at runtime - `terraform plan` cannot see it, and here neither
    # could the collector's health, which starts and accepts spans perfectly well before
    # discarding them ("Exporting failed. Rejecting data ... rejected_items: 64").
    var.xray_endpoint_enabled ? ["xray"] : [],
  )
}

resource "aws_vpc_endpoint" "interface" {
  for_each          = var.enable_interface_endpoints ? toset(local.interface_endpoint_services) : toset([])
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type = "Interface"
  # Single AZ, not all of aws_subnet.private (D-084 cost correction): interface
  # endpoints bill per-AZ-per-hour, so 5 endpoints x 2 AZs would run ~$73/mo - more than
  # a NAT Gateway (~$33/mo), which the "no NAT" design was supposed to save on. One AZ
  # brings it to ~$36/mo (private DNS still resolves for tasks in the other AZ, just
  # crossing AZs within the VPC - negligible at this traffic level) while keeping the
  # actual point of this design: zero general internet egress from private subnets.
  subnet_ids          = [aws_subnet.private[0].id]
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpce-${each.value}" })
}

# S3 gateway endpoint is free and covers the ECR image-layer storage (ECR stores layers
# in an AWS-managed S3 bucket) - route-table-attached, not an ENI like the interface ones.
resource "aws_vpc_endpoint" "s3" {
  count             = var.enable_interface_endpoints ? 1 : 0
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpce-s3" })
}

data "aws_region" "current" {}
