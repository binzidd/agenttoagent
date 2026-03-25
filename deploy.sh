#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh – Build, push, and deploy the Austral Agent Stack to AWS.
#
# Two deployment targets:
#
#   ./deploy.sh dashboard     – Streamlit UI → AWS App Runner (port 8501)
#                               Uses Dockerfile.streamlit
#
#   ./deploy.sh agentcore     – Backend agents → AWS Bedrock AgentCore (port 8080)
#                               Uses Dockerfile
#
#   ./deploy.sh all           – Both targets
#
# Prerequisites:
#   - AWS CLI v2 configured  (aws configure)
#   - Docker Desktop running
#   - jq installed           (brew install jq)
#
# Environment (defaults to Sydney region):
#   export AWS_REGION=ap-southeast-2
#   export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

TARGET="${1:-all}"

AWS_REGION="${AWS_REGION:-ap-southeast-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

DASHBOARD_NAME="austral-dashboard"
AGENTCORE_NAME="austral-agentcore"

info()  { echo "▶ $*"; }
ok()    { echo "✓ $*"; }
error() { echo "✗ $*" >&2; exit 1; }

# ── Helper: ensure ECR repo exists ───────────────────────────────────────────
ensure_ecr_repo() {
  local name="$1"
  if ! aws ecr describe-repositories --repository-names "${name}" \
         --region "${AWS_REGION}" &>/dev/null; then
    info "Creating ECR repository '${name}'…"
    aws ecr create-repository \
      --repository-name "${name}" \
      --region "${AWS_REGION}" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256 >/dev/null
    ok "Created ${name}"
  fi
}

# ── Helper: ECR login ────────────────────────────────────────────────────────
ecr_login() {
  info "Authenticating Docker → ECR (${AWS_REGION})…"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${ECR_BASE}"
  ok "Logged in"
}

# ── Helper: read a value from backend/.env ───────────────────────────────────
env_val() {
  grep "^${1}=" backend/.env 2>/dev/null | cut -d= -f2- || echo ""
}

# ═════════════════════════════════════════════════════════════════════════════
# TARGET: dashboard (Streamlit → App Runner)
# ═════════════════════════════════════════════════════════════════════════════
deploy_dashboard() {
  info "=== DASHBOARD → App Runner ==="

  local repo="${ECR_BASE}/${DASHBOARD_NAME}"
  ensure_ecr_repo "${DASHBOARD_NAME}"

  info "Building Dockerfile.streamlit (linux/amd64)…"
  docker build \
    --platform linux/amd64 \
    -f Dockerfile.streamlit \
    -t "${DASHBOARD_NAME}:latest" \
    -t "${repo}:latest" \
    .

  info "Pushing to ECR…"
  docker push "${repo}:latest"
  ok "Pushed ${repo}:latest"

  # Create or update App Runner service
  local svc_arn
  svc_arn=$(aws apprunner list-services \
    --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${DASHBOARD_NAME}'].ServiceArn" \
    --output text 2>/dev/null || true)

  if [[ -z "${svc_arn}" ]]; then
    info "Creating App Runner service '${DASHBOARD_NAME}'…"
    local url
    url=$(aws apprunner create-service \
      --region "${AWS_REGION}" \
      --service-name "${DASHBOARD_NAME}" \
      --source-configuration "{
        \"ImageRepository\": {
          \"ImageIdentifier\": \"${repo}:latest\",
          \"ImageRepositoryType\": \"ECR\",
          \"ImageConfiguration\": {
            \"Port\": \"8501\",
            \"RuntimeEnvironmentVariables\": {
              \"ANTHROPIC_API_KEY\":        \"$(env_val ANTHROPIC_API_KEY)\",
              \"NSW_FUELCHECK_API_KEY\":    \"$(env_val NSW_FUELCHECK_API_KEY)\",
              \"NSW_FUELCHECK_API_SECRET\": \"$(env_val NSW_FUELCHECK_API_SECRET)\"
            }
          }
        },
        \"AutoDeploymentsEnabled\": true
      }" \
      --instance-configuration '{"Cpu":"1 vCPU","Memory":"2 GB"}' \
      --health-check-configuration '{"Protocol":"HTTP","Path":"/_stcore/health","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}' \
      | jq -r '.Service.ServiceUrl')
    ok "Dashboard live at: https://${url}"
  else
    info "Triggering deployment on existing service…"
    aws apprunner start-deployment \
      --region "${AWS_REGION}" \
      --service-arn "${svc_arn}" >/dev/null
    local url
    url=$(aws apprunner describe-service \
      --region "${AWS_REGION}" \
      --service-arn "${svc_arn}" \
      | jq -r '.Service.ServiceUrl')
    ok "Deployment triggered: https://${url}"
  fi
}

# ═════════════════════════════════════════════════════════════════════════════
# TARGET: agentcore (Backend → AWS Bedrock AgentCore)
# ═════════════════════════════════════════════════════════════════════════════
deploy_agentcore() {
  info "=== BACKEND → Bedrock AgentCore ==="

  local repo="${ECR_BASE}/${AGENTCORE_NAME}"
  ensure_ecr_repo "${AGENTCORE_NAME}"

  info "Building Dockerfile (linux/amd64)…"
  docker build \
    --platform linux/amd64 \
    -f Dockerfile \
    -t "${AGENTCORE_NAME}:latest" \
    -t "${repo}:latest" \
    .

  info "Pushing to ECR…"
  docker push "${repo}:latest"
  ok "Pushed ${repo}:latest"

  # Create or update Bedrock AgentCore agent runtime
  # AgentCore requires an IAM role with bedrock:InvokeModel + ecr:* permissions
  local runtime_arn=""
  runtime_arn=$(aws bedrock-agentcore list-agent-runtimes \
    --region "${AWS_REGION}" \
    --query "agentRuntimes[?agentRuntimeName=='${AGENTCORE_NAME}'].agentRuntimeArn" \
    --output text 2>/dev/null || true)

  if [[ -z "${runtime_arn}" ]]; then
    info "Creating AgentCore runtime '${AGENTCORE_NAME}'…"
    info "NOTE: Set AGENTCORE_ROLE_ARN to your IAM role ARN before first deploy."
    info "      Role needs: AmazonBedrockAgentCoreExecutionPolicy + ECR pull permissions"
    ROLE_ARN="${AGENTCORE_ROLE_ARN:-}"
    if [[ -z "${ROLE_ARN}" ]]; then
      echo ""
      echo "  export AGENTCORE_ROLE_ARN=arn:aws:iam::${AWS_ACCOUNT_ID}:role/AustralAgentCoreRole"
      echo "  ./deploy.sh agentcore"
      echo ""
      error "AGENTCORE_ROLE_ARN not set — cannot create runtime."
    fi

    aws bedrock-agentcore create-agent-runtime \
      --region "${AWS_REGION}" \
      --agent-runtime-name "${AGENTCORE_NAME}" \
      --agent-runtime-artifact "{
        \"containerConfiguration\": {
          \"containerUri\": \"${repo}:latest\"
        }
      }" \
      --network-configuration '{"networkMode":"PUBLIC"}' \
      --execution-role-arn "${ROLE_ARN}" \
      --environment-variables "{
        \"ANTHROPIC_API_KEY\":        \"$(env_val ANTHROPIC_API_KEY)\",
        \"NSW_FUELCHECK_API_KEY\":    \"$(env_val NSW_FUELCHECK_API_KEY)\",
        \"NSW_FUELCHECK_API_SECRET\": \"$(env_val NSW_FUELCHECK_API_SECRET)\"
      }" | jq '{agentRuntimeArn, status}'
    ok "AgentCore runtime created."
  else
    info "Updating existing AgentCore runtime (${runtime_arn})…"
    aws bedrock-agentcore update-agent-runtime \
      --region "${AWS_REGION}" \
      --agent-runtime-id "${runtime_arn##*/}" \
      --agent-runtime-artifact "{
        \"containerConfiguration\": {
          \"containerUri\": \"${repo}:latest\"
        }
      }" | jq '{agentRuntimeArn, status}'
    ok "AgentCore runtime updated."
  fi
}

# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
case "${TARGET}" in
  dashboard)
    ecr_login
    deploy_dashboard
    ;;
  agentcore)
    ecr_login
    deploy_agentcore
    ;;
  all)
    ecr_login
    deploy_dashboard
    echo ""
    deploy_agentcore
    ;;
  *)
    echo "Usage: ./deploy.sh [dashboard|agentcore|all]"
    exit 1
    ;;
esac

ok "Done."
