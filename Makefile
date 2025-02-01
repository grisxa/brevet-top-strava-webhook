PORT ?= 8080
CLOUD_URL ?= "https://us-central1-baltic-star-cloud.cloudfunctions.net"

deploy:
	gcloud beta functions deploy stravaWebhook \
	  --entry-point StravaWebhook \
	  --runtime go122 \
	  --trigger-http \
	  --memory 128MB \
	  --timeout 10s \
	  --allow-unauthenticated \
	  --set-env-vars 'PUBSUB_TOPIC=strava,GCLOUD_PROJECT=baltic-star-cloud' \
	  --set-secrets 'STRAVA=projects/baltic-star-cloud/secrets/strava:latest'

# export VERIFY_TOKEN=secret
verify:
	curl "localhost:$(PORT)/baltic-star-cloud/us-central1/stravaWebhook?hub.mode=subscribe&hub.challenge=random&hub.verify_token=${VERIFY_TOKEN}"

verify-online:
	curl "https://brevet.top/strava-webhook?hub.mode=subscribe&hub.challenge=random&hub.verify_token=${VERIFY_TOKEN}"

test:
	go test -v -coverprofile=coverage.out
	go tool cover -html=coverage.out

# curl "https://us-central1-baltic-star-cloud.cloudfunctions.net/stravaWebhookGo
test-create:
	curl "$(CLOUD_URL)/stravaWebhook" \
	  -X POST \
	  -H "Content-Type:application/json" \
	  -d '@strava_create.json'


#	curl "localhost:$(PORT)/baltic-star-cloud/us-central1/stravaWebhook"
test-update:
	curl "$(CLOUD_URL)/stravaWebhook" \
	  -X POST \
	  -H "Content-Type:application/json" \
	  -d '@strava_update.json'

test-revoke:
	curl "$(CLOUD_URL)/stravaWebhook" \
	  -X POST \
	  -H "Content-Type:application/json" \
	  -d '@strava_revoke.json'
