#!/usr/bin/env bash
# One-time Google Cloud setup for the Title Agent engine (v2, docs/PLAN-v2.md). Run it in Cloud Shell
# (console.cloud.google.com → the >_ button, top right) signed in as the project owner. Safe to run again.
#
# It creates, in the Firebase project:
#   - the engine's own identity (title-agent-engine): reads and writes Firestore and Storage, nothing else
#   - a deploy identity for GitHub (github-deploy): may only update the engine on Cloud Run and push its image
#   - a keyless link from this GitHub repository to that deploy identity (no key file to leak)
#   - the image registry (Artifact Registry "title-agent")
# and prints the one value to save in GitHub as GCP_WORKLOAD_IDENTITY_PROVIDER.
set -uo pipefail

PROJECT=title-commitment-agent
REGION=us-east1
GITHUB_REPO=RemyTCHB/TITLE-COMMITMENT-AGENT
# GitHub's permanent id for that repository: it survives renames and moves, and is never reused
GITHUB_REPO_ID=1431672941

RUNTIME=title-agent-engine@$PROJECT.iam.gserviceaccount.com
DEPLOY=github-deploy@$PROJECT.iam.gserviceaccount.com
ok() {  # run once; quiet when the thing already exists (running the script again), loud for anything else
  local out
  out=$("$@" 2>&1) || { grep -qi "already exists" <<<"$out" || echo "$out"; }
}

gcloud config set project "$PROJECT" >/dev/null
echo "1/6 Turning on Cloud Run, Artifact Registry and keyless sign-in…"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com \
  sts.googleapis.com firestore.googleapis.com storage.googleapis.com

echo "2/6 Image registry…"
ok gcloud artifacts repositories create title-agent --repository-format=docker --location="$REGION" \
  --description="Title Agent engine images"

echo "3/6 The engine's identity (Firestore + Storage only)…"
ok gcloud iam service-accounts create title-agent-engine --display-name="Title Agent engine (Cloud Run)"
for role in roles/datastore.user roles/storage.objectAdmin; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$RUNTIME" --role="$role" \
    --condition=None >/dev/null
done

echo "4/6 GitHub's deploy identity (update the engine, push its image)…"
ok gcloud iam service-accounts create github-deploy --display-name="GitHub deploys the Title Agent engine"
sleep 15  # new identities take a few seconds to be usable in permissions
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$DEPLOY" --role=roles/run.admin \
  --condition=None >/dev/null
gcloud artifacts repositories add-iam-policy-binding title-agent --location="$REGION" \
  --member="serviceAccount:$DEPLOY" --role=roles/artifactregistry.writer >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME" --member="serviceAccount:$DEPLOY" \
  --role=roles/iam.serviceAccountUser >/dev/null

echo "5/6 Keyless link from GitHub ($GITHUB_REPO only, by its id $GITHUB_REPO_ID)…"
ok gcloud iam workload-identity-pools create github --location=global --display-name="GitHub"
ok gcloud iam workload-identity-pools providers create-oidc title-agent --location=global \
  --workload-identity-pool=github --display-name="Title Agent repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id" \
  --attribute-condition="assertion.repository_id == '$GITHUB_REPO_ID'"
NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
POOL="projects/$NUMBER/locations/global/workloadIdentityPools/github"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/$POOL/attribute.repository_id/$GITHUB_REPO_ID" >/dev/null

echo "6/6 Done. Save this in GitHub (Settings → Secrets and variables → Actions → New repository secret):"
echo
echo "  Name:   GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "  Secret: $POOL/providers/title-agent"
echo
