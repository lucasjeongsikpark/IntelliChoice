output "vpc_id" {
  value = aws_vpc.this.id
}

output "vpc_cidr" {
  value = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "availability_zones" {
  value = local.azs
}

output "nat_gateway_id" {
  description = "The NAT gateway giving private subnets internet egress, or null when disabled."
  value       = try(aws_nat_gateway.this[0].id, null)
}
