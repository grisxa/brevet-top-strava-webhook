all:
	functions_framework --target=strava_webhook --signature-type http --port 9090 --debug

deploy:
	gcloud beta functions deploy stravaWebhook \
	  --entry-point StravaWebhook \
	  --runtime go116 \
	  --trigger-http \
	  --memory 128MB \
	  --timeout 10s \
	  --allow-unauthenticated \
	  --set-env-vars 'PUBSUB_TOPIC=strava,GCLOUD_PROJECT=baltic-star-cloud' \
	  --set-secrets 'STRAVA=projects/baltic-star-cloud/secrets/strava:latest'

# export VERIFY_TOKEN=secret
verify:
	curl "localhost:9090/baltic-star-cloud/us-central1/stravaWebhook?hub.mode=subscribe&hub.challenge=random&hub.verify_token=${VERIFY_TOKEN}"

verify-online:
	curl "https://brevet.top/strava-webhook?hub.mode=subscribe&hub.challenge=random&hub.verify_token=${VERIFY_TOKEN}"

test:
	python -m pytest -v
	pylama
