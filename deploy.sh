#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh – Build and push the Streamlit dashboard to AWS App Runner via ECR.
#
# Prerequisites:
#   - AWS CLI configured  (aws configure)
#   - Docker running
#   - jq installed        (brew install jq)
#
# First-time setup:
#   export AWS_REGION=ap-southeast-2      # Sydney
#   export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
#   ./deploy.sh --create          # create App Runner service on first run
#
# Subsequent deploys:
#   ./deploy.sh                   # build → push → App Runner auto-deploys
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
APP_NAME="austral-dashboard"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${APP_NAME}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { echo "→ $*"; }
error() { echo "✗ $*" >&2; exit 1; }

# ── 1. Authenticate Docker → ECR ─────────────────────────────────────────────
info "Logging in to ECR (${AWS_REGION})…"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ── 2. Create ECR repo if it doesn't exist ────────────────────────────────────
if ! aws ecr describe-repositories --repository-names "${APP_NAME}" \
       --region "${AWS_REGION}" &>/dev/null; then
  info "Creating ECR repository '${APP_NAME}'…"
  aws ecr create-repository --repository-name "${APP_NAME}" \
      --region "${AWS_REGION}" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256
fi

# ── 3. Build ──────────────────────────────────────────────────────────────────
info "Building image (Dockerfile.streamlit)…"
docker build \
  --platform linux/amd64 \
  -f Dockerfile.streamlit \
  -t "${APP_NAME}:${IMAGE_TAG}" \
  -t "${ECR_REPO}:${IMAGE_TAG}" \
  .

# ── 4. Push ───────────────────────────────────────────────────────────────────
info "Pushing to ECR → ${ECR_REPO}:${IMAGE_TAG}"
docker push "${ECR_REPO}:${IMAGE_TAG}"

# ── 5. Create or update App Runner service ────────────────────────────────────
SERVICE_ARN=$(aws apprunner list-services --region "${AWS_REGION}" \
  --query "ServiceSummaryList[?ServiceName=='${APP_NAME}'].ServiceArn" \
  --output text 2>/dev/null || true)

if [[ -z "${SERVICE_ARN}" ]] || [[ "${1:-}" == "--create" ]]; then
  info "Creating App Runner service '${APP_NAME}'…"
  # Read secrets from local .env (never baked into the image)
  ANTHROPIC_KEY=$(grep '^ANTHROPIC_API_KEY=' backend/.env 2>/dev/null | cut -d= -f2 || echo "")
  FUEL_KEY=$(grep '^NSW_FUELCHECK_API_KEY=' backend/.env 2>/dev/null | cut -d= -f2 || echo "")
  FUEL_SECRET=$(grep '^NSW_FUELCHECK_API_SECRET=' backend/.env 2>/dev/null | cut -d= -f2 || echo "")

  aws apprunner create-service \
    --region "${AWS_REGION}" \
    --service-name "${APP_NAME}" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"${ECR_REPO}:${IMAGE_TAG}\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"8501\",
          \"RuntimeEnvironmentVariables\": {
            \"ANTHROPIC_API_KEY\": \"${ANTHROPIC_KEY}\",
            \"NSW_FUELCHECK_API_KEY\": \"${FUEL_KEY}\",
            \"NSW_FUELCHECK_API_SECRET\": \"${FUEL_SECRET}\"
          }
        }
      },
      \"AutoDeploymentsEnabled\": true
    }" \
    --instance-configuration '{"Cpu":"1 vCPU","Memory":"2 GB"}' \
    --health-check-configuration '{"Protocol":"HTTP","Path":"/_stcore/health","Interval":10,"Timeout":5}' \
    | jq -r '.Service.ServiceUrl'
  info "Service created! URL above ↑"

else
  info "Triggering deployment on existing service (${SERVICE_ARN})…"
  aws apprunner start-deployment \
    --region "${AWS_REGION}" \
    --service-arn "${SERVICE_ARN}"
  info "Deployment triggered. Check status:"
  echo "  aws apprunner describe-service --service-arn '${SERVICE_ARN}' --region '${AWS_REGION}' --query 'Service.Status'"
fi

info "Done."
