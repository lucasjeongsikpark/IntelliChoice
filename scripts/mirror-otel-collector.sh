#!/usr/bin/env bash
#
# Mirror the AWS Distro for OpenTelemetry collector into this account's private ECR.
#
# Why this exists (S39/D-103): the ECS tasks run in private subnets with **no NAT gateway**
# (D-084's cost posture). They reach private ECR through the `ecr.dkr`/`ecr.api` interface
# endpoints plus S3 for layers - but `public.ecr.aws` is a different registry with no
# interface endpoint, so it is unroutable from there. Found live, not predicted: the first
# sidecar deploy failed with
#
#   CannotPullContainerError: ... failed to resolve ref
#   public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3 ...
#   dial tcp 75.2.101.78:443: i/o timeout
#
# and retried until the services were rolled back. Mirroring one image is the cheap fix; a
# NAT gateway (~$32/month) to pull it is not.
#
# Run from a machine with internet access. Idempotent apart from ECR's IMMUTABLE tag policy,
# which makes re-pushing the same tag fail loudly rather than silently changing what is
# deployed - the same protection D-096 added for the app images.
set -euo pipefail

VERSION="${VERSION:-v0.43.3}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-jeongsik-staging-admin}"
SOURCE="public.ecr.aws/aws-observability/aws-otel-collector:${VERSION}"

# Must match `runtime_platform.cpu_architecture` in modules/ecs-service - an amd64 image on
# an ARM64 task fails at startup with an exec format error, which looks nothing like a
# platform mismatch in the logs.
PLATFORM="linux/arm64"

ACCOUNT_ID="$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
TARGET="${REGISTRY}/aws-otel-collector:${VERSION}"

echo "==> pulling ${SOURCE} (${PLATFORM})"
docker pull --platform "$PLATFORM" "$SOURCE"

echo "==> retagging as ${TARGET}"
docker tag "$SOURCE" "$TARGET"

echo "==> logging in to ${REGISTRY}"
aws ecr get-login-password --region "$AWS_REGION" --profile "$AWS_PROFILE" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> pushing"
docker push "$TARGET"

echo
echo "Mirrored: ${TARGET}"
echo "Point terraform's ecs-service var.otel_collector_image at that value."
