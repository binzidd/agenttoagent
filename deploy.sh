#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh – Build and deploy the Austral Agent Stack to AWS (ap-southeast-2)
#
#   ./deploy.sh dashboard     – Streamlit UI  → ECS Fargate (port 8501)
#   ./deploy.sh agentcore     – Backend agents → AWS Bedrock AgentCore (port 8080)
#   ./deploy.sh all           – Both targets in sequence
#
# Prerequisites: Docker Desktop running, AWS CLI v2, jq
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

TARGET="${1:-all}"

AWS_REGION="ap-southeast-2"
AWS_ACCOUNT_ID="811165582660"
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# AgentCore runtime name must match [a-zA-Z][a-zA-Z0-9_]{0,47}
DASHBOARD_REPO="austral_dashboard"
AGENTCORE_REPO="austral_agentcore"
AGENTCORE_RUNTIME_NAME="AustralAgentCore"
AGENTCORE_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/AustralAgentCoreRole"

# ECS config for Streamlit dashboard
ECS_CLUSTER="austral-cluster"
ECS_SERVICE="austral-dashboard"
ECS_TASK_FAMILY="austral-dashboard"
DEFAULT_VPC="vpc-080c49b38fc967a84"
DEFAULT_SUBNETS="subnet-0cd390117e81869ea,subnet-03ed836e946a4de7a,subnet-0b8f1188e70c6efdf"

info()  { echo "▶ $*"; }
ok()    { echo "✓ $*"; }
error() { echo "✗ $*" >&2; exit 1; }

# Read a value from backend/.env, stripping surrounding quotes
env_val() {
  local raw
  raw=$(grep "^${1}=" backend/.env 2>/dev/null | cut -d= -f2- || echo "")
  # Strip leading/trailing single or double quotes
  raw="${raw%\"}"  ; raw="${raw#\"}"
  raw="${raw%\'}"  ; raw="${raw#\'}"
  echo "${raw}"
}

# Build env-vars JSON safely using jq (handles special chars / quotes in values)
build_env_json() {
  jq -n \
    --arg anthropic     "$(env_val ANTHROPIC_API_KEY)" \
    --arg fuel_key      "$(env_val NSW_FUELCHECK_API_KEY)" \
    --arg fuel_secret   "$(env_val NSW_FUELCHECK_API_SECRET)" \
    '{ANTHROPIC_API_KEY: $anthropic,
      NSW_FUELCHECK_API_KEY: $fuel_key,
      NSW_FUELCHECK_API_SECRET: $fuel_secret}'
}

# ── Shared: ECR login + ensure repo ──────────────────────────────────────────
ecr_login() {
  info "Logging in to ECR…"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${ECR_BASE}"
}

ensure_ecr_repo() {
  local name="$1"
  if ! aws ecr describe-repositories --repository-names "${name}" \
       --region "${AWS_REGION}" &>/dev/null; then
    info "Creating ECR repo '${name}'…"
    aws ecr create-repository \
      --repository-name "${name}" \
      --region "${AWS_REGION}" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256 >/dev/null
  fi
}

# ═════════════════════════════════════════════════════════════════════════════
# TARGET: dashboard → ECS Fargate
# ═════════════════════════════════════════════════════════════════════════════
deploy_dashboard() {
  info "=== DASHBOARD → ECS Fargate ==="
  local repo="${ECR_BASE}/${DASHBOARD_REPO}"
  ensure_ecr_repo "${DASHBOARD_REPO}"

  info "Building Dockerfile.streamlit (linux/amd64)…"
  docker build --platform linux/amd64 -f Dockerfile.streamlit \
    -t "${DASHBOARD_REPO}:latest" -t "${repo}:latest" .
  docker push "${repo}:latest"
  ok "Pushed ${repo}:latest"

  # ── ECS task execution role ──────────────────────────────────────────────
  local exec_role="AustralDashboardTaskExecRole"
  if ! aws iam get-role --role-name "${exec_role}" &>/dev/null; then
    info "Creating ECS task execution role…"
    aws iam create-role --role-name "${exec_role}" \
      --assume-role-policy-document '{
        "Version":"2012-10-17",
        "Statement":[{"Effect":"Allow",
          "Principal":{"Service":"ecs-tasks.amazonaws.com"},
          "Action":"sts:AssumeRole"}]}' >/dev/null
    aws iam attach-role-policy --role-name "${exec_role}" \
      --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
    ok "Role created"
  fi
  local exec_role_arn
  exec_role_arn=$(aws iam get-role --role-name "${exec_role}" \
    --query "Role.Arn" --output text)

  # ── ECS cluster ──────────────────────────────────────────────────────────
  if ! aws ecs describe-clusters --clusters "${ECS_CLUSTER}" \
       --region "${AWS_REGION}" \
       --query "clusters[?status=='ACTIVE']" --output text | grep -q "${ECS_CLUSTER}"; then
    info "Creating ECS cluster '${ECS_CLUSTER}'…"
    aws ecs create-cluster --cluster-name "${ECS_CLUSTER}" \
      --region "${AWS_REGION}" >/dev/null
  fi

  # ── Security group for port 8501 ─────────────────────────────────────────
  local sg_id
  sg_id=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=austral-dashboard-sg" \
              "Name=vpc-id,Values=${DEFAULT_VPC}" \
    --region "${AWS_REGION}" \
    --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "")
  if [[ -z "${sg_id}" || "${sg_id}" == "None" ]]; then
    info "Creating security group for port 8501…"
    sg_id=$(aws ec2 create-security-group \
      --group-name "austral-dashboard-sg" \
      --description "Austral Streamlit dashboard – port 8501" \
      --vpc-id "${DEFAULT_VPC}" \
      --region "${AWS_REGION}" \
      --query "GroupId" --output text)
    aws ec2 authorize-security-group-ingress \
      --group-id "${sg_id}" \
      --protocol tcp --port 8501 --cidr 0.0.0.0/0 \
      --region "${AWS_REGION}" >/dev/null
    ok "Security group ${sg_id}"
  fi

  # ── Task definition ───────────────────────────────────────────────────────
  info "Registering ECS task definition…"
  local task_def_arn
  task_def_arn=$(aws ecs register-task-definition \
    --region "${AWS_REGION}" \
    --family "${ECS_TASK_FAMILY}" \
    --network-mode awsvpc \
    --requires-compatibilities FARGATE \
    --cpu "512" --memory "1024" \
    --execution-role-arn "${exec_role_arn}" \
    --container-definitions "[{
      \"name\": \"dashboard\",
      \"image\": \"${repo}:latest\",
      \"portMappings\": [{\"containerPort\": 8501, \"protocol\": \"tcp\"}],
      \"essential\": true,
      \"environment\": $(build_env_json | jq '[to_entries[] | {name:.key, value:.value}]'),
      \"logConfiguration\": {
        \"logDriver\": \"awslogs\",
        \"options\": {
          \"awslogs-group\": \"/ecs/austral-dashboard\",
          \"awslogs-region\": \"${AWS_REGION}\",
          \"awslogs-stream-prefix\": \"ecs\",
          \"awslogs-create-group\": \"true\"
        }
      }
    }]" \
    --query "taskDefinition.taskDefinitionArn" --output text)
  ok "Task definition: ${task_def_arn##*/}"

  # ── ECS service ───────────────────────────────────────────────────────────
  local svc_exists
  svc_exists=$(aws ecs describe-services \
    --cluster "${ECS_CLUSTER}" --services "${ECS_SERVICE}" \
    --region "${AWS_REGION}" \
    --query "services[?status=='ACTIVE'].serviceName" --output text 2>/dev/null || echo "")

  IFS=',' read -ra SUBNETS <<< "${DEFAULT_SUBNETS}"
  SUBNET_JSON=$(printf '"%s",' "${SUBNETS[@]}" | sed 's/,$//')

  if [[ -z "${svc_exists}" ]]; then
    info "Creating ECS service '${ECS_SERVICE}'…"
    aws ecs create-service \
      --cluster "${ECS_CLUSTER}" \
      --service-name "${ECS_SERVICE}" \
      --task-definition "${ECS_TASK_FAMILY}" \
      --desired-count 1 \
      --launch-type FARGATE \
      --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_JSON}],securityGroups=[${sg_id}],assignPublicIp=ENABLED}" \
      --region "${AWS_REGION}" >/dev/null
    ok "Service created."
  else
    info "Updating ECS service to latest task definition…"
    aws ecs update-service \
      --cluster "${ECS_CLUSTER}" \
      --service "${ECS_SERVICE}" \
      --task-definition "${ECS_TASK_FAMILY}" \
      --force-new-deployment \
      --region "${AWS_REGION}" >/dev/null
    ok "Service update triggered."
  fi

  info "Waiting for service to stabilise (this takes ~2 min)…"
  aws ecs wait services-stable \
    --cluster "${ECS_CLUSTER}" --services "${ECS_SERVICE}" \
    --region "${AWS_REGION}"

  # Print the public IP of the running task
  local task_arn
  task_arn=$(aws ecs list-tasks \
    --cluster "${ECS_CLUSTER}" --service-name "${ECS_SERVICE}" \
    --region "${AWS_REGION}" --query "taskArns[0]" --output text)
  local eni_id
  eni_id=$(aws ecs describe-tasks \
    --cluster "${ECS_CLUSTER}" --tasks "${task_arn}" \
    --region "${AWS_REGION}" \
    --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" \
    --output text)
  local public_ip
  public_ip=$(aws ec2 describe-network-interfaces \
    --network-interface-ids "${eni_id}" \
    --region "${AWS_REGION}" \
    --query "NetworkInterfaces[0].Association.PublicIp" --output text)
  ok "Dashboard live at: http://${public_ip}:8501"
}

# ═════════════════════════════════════════════════════════════════════════════
# TARGET: agentcore → AWS Bedrock AgentCore
# ═════════════════════════════════════════════════════════════════════════════
deploy_agentcore() {
  info "=== BACKEND → Bedrock AgentCore ==="
  local repo="${ECR_BASE}/${AGENTCORE_REPO}"
  ensure_ecr_repo "${AGENTCORE_REPO}"

  info "Building Dockerfile (linux/arm64 – required by AgentCore)…"
  docker build --platform linux/arm64 -f Dockerfile \
    -t "${AGENTCORE_REPO}:latest" -t "${repo}:latest" .
  docker push "${repo}:latest"
  ok "Pushed ${repo}:latest"

  # ── Resolve existing runtime (if any) ─────────────────────────────────────
  local runtime_id=""
  runtime_id=$(aws bedrock-agentcore-control list-agent-runtimes \
    --region "${AWS_REGION}" \
    --query "agentRuntimes[?agentRuntimeName=='${AGENTCORE_RUNTIME_NAME}'].agentRuntimeId" \
    --output text 2>/dev/null || echo "")

  local env_json
  env_json=$(build_env_json)

  if [[ -z "${runtime_id}" || "${runtime_id}" == "None" ]]; then
    info "Creating AgentCore runtime '${AGENTCORE_RUNTIME_NAME}'…"
    aws bedrock-agentcore-control create-agent-runtime \
      --region "${AWS_REGION}" \
      --agent-runtime-name "${AGENTCORE_RUNTIME_NAME}" \
      --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"${repo}:latest\"}}" \
      --role-arn "${AGENTCORE_ROLE_ARN}" \
      --network-configuration '{"networkMode":"PUBLIC"}' \
      --environment-variables "${env_json}" \
      | jq '{agentRuntimeId, status}'
    ok "AgentCore runtime created."
  else
    info "Updating AgentCore runtime '${AGENTCORE_RUNTIME_NAME}' (${runtime_id})…"
    aws bedrock-agentcore-control update-agent-runtime \
      --region "${AWS_REGION}" \
      --agent-runtime-id "${runtime_id}" \
      --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"${repo}:latest\"}}" \
      --role-arn "${AGENTCORE_ROLE_ARN}" \
      --network-configuration '{"networkMode":"PUBLIC"}' \
      --environment-variables "${env_json}" \
      | jq '{agentRuntimeId, status}'
    ok "AgentCore runtime updated."
  fi
}

# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
if ! docker info &>/dev/null; then
  error "Docker is not running. Start Docker Desktop first, then re-run."
fi

case "${TARGET}" in
  dashboard) ecr_login; deploy_dashboard ;;
  agentcore) ecr_login; deploy_agentcore ;;
  all)       ecr_login; deploy_dashboard; echo ""; deploy_agentcore ;;
  *)  echo "Usage: ./deploy.sh [dashboard|agentcore|all]"; exit 1 ;;
esac

ok "Done."
