#!/usr/bin/env bash
# Runs on the Mac AFTER `gcloud auth login` + a project with billing exists.
# Creates the Always-Free e2-micro VM, opens web ports, copies the app +
# secrets, and runs the on-VM setup. Re-runnable.
set -euo pipefail

PROJECT="${1:?usage: create_and_deploy.sh <PROJECT_ID> <path-to-app.env>}"
ENV_SRC="${2:?path to app.env with secrets}"
ZONE="us-central1-a"          # Always-Free region
REGION="us-central1"
VM="angc-vm"
IP_NAME="angc-ip"
REPO="/Users/piyush/Projects/cx-agent"

gcloud config set project "$PROJECT"
gcloud services enable compute.googleapis.com

echo "== static external IP (free while attached) =="
gcloud compute addresses describe "$IP_NAME" --region "$REGION" >/dev/null 2>&1 \
  || gcloud compute addresses create "$IP_NAME" --region "$REGION"

echo "== firewall: allow 80/443 to tagged VM =="
gcloud compute firewall-rules describe angc-web >/dev/null 2>&1 \
  || gcloud compute firewall-rules create angc-web --allow tcp:80,tcp:443 --target-tags angc-web --direction INGRESS

echo "== create e2-micro Always-Free VM =="
if ! gcloud compute instances describe "$VM" --zone "$ZONE" >/dev/null 2>&1; then
  gcloud compute instances create "$VM" \
    --zone "$ZONE" \
    --machine-type e2-micro \
    --image-family debian-12 --image-project debian-cloud \
    --boot-disk-size 30GB --boot-disk-type pd-standard \
    --address "$IP_NAME" \
    --tags angc-web
fi

echo "== wait for SSH =="
until gcloud compute ssh "$VM" --zone "$ZONE" --command "echo ready" >/dev/null 2>&1; do
  echo "  ...waiting for VM"; sleep 8
done

echo "== copy app code + secrets to the VM =="
gcloud compute ssh "$VM" --zone "$ZONE" --command "rm -rf ~/angc-upload && mkdir -p ~/angc-upload"
gcloud compute scp --zone "$ZONE" --recurse \
  "$REPO/src" "$REPO/deploy" "$REPO/pyproject.toml" "$REPO/README.md" \
  "$VM":~/angc-upload/
gcloud compute scp --zone "$ZONE" "$ENV_SRC" "$VM":~/angc-upload/app.env

echo "== install into /opt/angc and run setup =="
gcloud compute ssh "$VM" --zone "$ZONE" --command "
  sudo mkdir -p /opt/angc &&
  sudo cp -r ~/angc-upload/src ~/angc-upload/deploy ~/angc-upload/pyproject.toml ~/angc-upload/README.md /opt/angc/ &&
  sudo cp ~/angc-upload/app.env /opt/angc/app.env &&
  sudo chown -R \$(whoami) /opt/angc &&
  chmod 600 /opt/angc/app.env &&
  bash /opt/angc/deploy/gcp/setup_vm.sh
"
echo
echo "Done. External IP:"
gcloud compute addresses describe "$IP_NAME" --region "$REGION" --format "value(address)"
