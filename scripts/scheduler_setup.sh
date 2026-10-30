#!/usr/bin/env bash
# One-time: Google Cloud Scheduler calls the engine at 8:00 AM Eastern every weekday, and the engine sends the daily
# email straight away, then catches up the Team Hub (titleagent/daily.py, POST /v1/tasks/morning). GitHub's
# scheduled runs start late or not at all, so they are only the backup now.
#
# Run it in Cloud Shell (console.cloud.google.com → the >_ button, top right) signed in as the project owner, after
# the engine has been deployed with this change. Safe to run again.
#
# It creates, in the Firebase project:
#   - an identity for the scheduler (title-agent-scheduler): it has no permissions; the engine only accepts its
#     Google-signed token on /v1/tasks/morning
#   - the job "title-agent-morning": weekdays 8:00 AM America/New_York, tries again up to 3 times if the engine fails
set -uo pipefail

PROJECT=title-commitment-agent
REGION=us-east1
SERVICE=title-agent-engine
CALLER=title-agent-scheduler@$PROJECT.iam.gserviceaccount.com
JOB=title-agent-morning

retry() {  # a new identity can take a few seconds before it can be named: try up to 6 times
  local i
  for i in 1 2 3 4 5 6; do "$@" >/dev/null 2>&1 && return 0; sleep 10; done
  "$@"  # last try shows Google's error
}

gcloud config set project "$PROJECT" >/dev/null
echo "1/3 Turning on Cloud Scheduler…"
gcloud services enable cloudscheduler.googleapis.com

echo "2/3 The scheduler's identity…"
gcloud iam service-accounts describe "$CALLER" >/dev/null 2>&1 \
  || gcloud iam service-accounts create title-agent-scheduler --display-name="Cloud Scheduler: the 8 AM email"

echo "3/3 The 8:00 AM job…"
URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
ARGS=(--location="$REGION" --schedule="0 8 * * 1-5" --time-zone="America/New_York"
      --uri="$URL/v1/tasks/morning" --http-method=POST
      --oidc-service-account-email="$CALLER" --oidc-token-audience="$URL"
      --attempt-deadline=300s --max-retry-attempts=3 --min-backoff=60s)
if gcloud scheduler jobs describe "$JOB" --location="$REGION" >/dev/null 2>&1; then
  retry gcloud scheduler jobs update http "$JOB" "${ARGS[@]}"
else
  retry gcloud scheduler jobs create http "$JOB" "${ARGS[@]}"
fi

echo
gcloud scheduler jobs describe "$JOB" --location="$REGION" \
  --format='value(schedule,timeZone,state)' | sed 's/^/Done: /'
echo "The next weekday at 8:00 AM Eastern, the engine sends the email. Settings → Connections → Daily Email shows it."
