package webhook

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"

	"cloud.google.com/go/logging"
	"cloud.google.com/go/pubsub"
)

type stravaCredentials struct {
	ClientID       int    `json:"client_id"`
	ClientSecret   string `json:"client_secret"`
	SubscriptionID int    `json:"subscription_id"`
	VerifyToken    string `json:"verify_token"`
}

type activityUpdates struct {
	Type       string `json:"type"`
	Authorized string `json:"authorized"`
}

type activityAction struct {
	SubscriptionID int             `json:"subscription_id"`
	AspectType     string          `json:"aspect_type"`
	ObjectType     string          `json:"object_type"`
	Updates        activityUpdates `json:"updates"`
	OwnerID        int             `json:"owner_id"`
	ObjectID       int             `json:"object_id"`
}

var pubClient *pubsub.Client
var logClient *logging.Client
var logger *logging.Logger
var secret stravaCredentials

// Setup Strava credentials and PubSub client.
func init() {
	var err error

	if err = json.Unmarshal([]byte(os.Getenv("STRAVA")), &secret); err != nil {
		log.Fatalf("Wrong Strava settings %v", err)
	}

	pubClient, err = pubsub.NewClient(context.Background(), os.Getenv("GCLOUD_PROJECT"))
	if err != nil {
		log.Fatalf("Pubsub client error %v", err)
	}
}

// Entry point.
func StravaWebhook(response http.ResponseWriter, request *http.Request) {
	var err error

	logClient, err = logging.NewClient(context.Background(), os.Getenv("GCLOUD_PROJECT"))
	if err != nil {
		log.Fatalf("Failed to create a log client: %v", err)

		return
	}
	defer logClient.Close()
	logger = logClient.Logger("cloudfunctions.googleapis.com/cloud-functions")

	if request.Method == "GET" {
		verify(response, request.URL.Query())

		return
	}

	if request.Method == "POST" {
		enqueue(response, request)

		return
	}

	logger.Log(logging.Entry{
		Payload:  fmt.Sprintf("Method not allowed %s", request.Method),
		Severity: logging.Error,
	})
	http.Error(response, fmt.Sprintf("Method not allowed: %s", request.Method), http.StatusMethodNotAllowed)
}

// Webhook verification request handler.
func verify(response http.ResponseWriter, data url.Values) {
	mode := data.Get("hub.mode")
	token := data.Get("hub.verify_token")
	challenge := data.Get("hub.challenge")

	if mode != "subscribe" {
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("Mode not supported %s", mode),
			Severity: logging.Warning,
		})
		http.Error(response, fmt.Sprintf("Mode not supported: %s", mode), http.StatusBadRequest)

		return
	}

	if token == "" || token != secret.VerifyToken {
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("Wrong token %s", token),
			Severity: logging.Warning,
		})
		http.Error(response, "Wrong token", http.StatusUnauthorized)

		return
	}

	fmt.Fprintf(response, `{"hub.challenge": "%s"}`, challenge)
}

// Put the request in a queue.
func enqueue(response http.ResponseWriter, request *http.Request) {
	activity := activityAction{}
	if err := json.NewDecoder(request.Body).Decode(&activity); err != nil {
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("Wrong request %v", err),
			Severity: logging.Warning,
		})
		http.Error(response, fmt.Sprintf("Wrong request: %v", err), http.StatusBadRequest)

		return
	}

	if ignoredAthlete(activity) {
		fmt.Fprint(response, "OK")

		return
	}

	if invalidSubscription(activity) {
		http.Error(response, "Invalid subscription id", http.StatusForbidden)

		return
	}

	if invalidAction(activity) {
		fmt.Fprint(response, "OK")

		return
	}

	payload, err := json.Marshal(activity)
	if err != nil {
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("JSON error %v", err),
			Severity: logging.Error,
		})
		http.Error(response, "Error converting message", http.StatusInternalServerError)

		return
	}

	forwardMessage(response, request, payload)

	logger.Log(logging.Entry{
		Payload: fmt.Sprintf("Athlete %d %ss %d",
			activity.OwnerID,
			activity.AspectType,
			activity.ObjectID),
		Severity: logging.Info,
	})
	fmt.Fprint(response, "OK")
}

func invalidAction(activity activityAction) bool {
	switch {
	case activity.AspectType == "create":
		// publish
		return false
	case activity.AspectType == "update" &&
		activity.ObjectType == "activity" &&
		activity.Updates.Type == "Ride":
		// publish
		return false
	case activity.AspectType == "update" &&
		activity.ObjectType == "athlete" &&
		activity.Updates.Authorized == "false":
		// publish
		return false
	default:
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("Ignoring action %s", activity.AspectType),
			Severity: logging.Warning,
		})

		return true
	}
}

func invalidSubscription(activity activityAction) bool {
	if activity.SubscriptionID != secret.SubscriptionID {
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("Invalid subscription id %d", activity.SubscriptionID),
			Severity: logging.Warning,
		})

		return true
	}

	return false
}

func ignoredAthlete(activity activityAction) bool {
	if activity.OwnerID == 43380524 {
		return true
	}

	return false
}

func forwardMessage(response http.ResponseWriter, request *http.Request, payload []byte) {
	message := &pubsub.Message{Data: payload}

	messageID, err := pubClient.Topic(os.Getenv("PUBSUB_TOPIC")).Publish(request.Context(), message).Get(request.Context())
	if err != nil {
		logger.Log(logging.Entry{
			Payload:  fmt.Sprintf("Error publishing message %v", err),
			Severity: logging.Alert,
		})
		http.Error(response, "Error publishing message", http.StatusInternalServerError)

		return
	}

	logger.Log(logging.Entry{
		Payload:  fmt.Sprintf("Message sent %s", messageID),
		Severity: logging.Info,
	})
}
