package webhook

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"

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
var secret stravaCredentials

// Setup Strava credentials and PubSub client.
func init() {
	var err error
	log.SetFlags(0)

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

	if err != nil {
		log.Fatalf("Failed to create a log client: %v", err)

		return
	}

	if request.Method == "GET" {
		verify(response, request.URL.Query())

		return
	}

	if request.Method == "POST" {
		enqueue(response, request)

		return
	}

	log.Fatalf("Method not allowed %s", request.Method)
	http.Error(response, fmt.Sprintf("Method not allowed: %s", request.Method), http.StatusMethodNotAllowed)
}

// Webhook verification request handler.
func verify(response http.ResponseWriter, data url.Values) {
	mode := data.Get("hub.mode")
	token := data.Get("hub.verify_token")
	challenge := data.Get("hub.challenge")

	if mode != "subscribe" {
		log.Printf("Mode not supported %s", mode)
		http.Error(response, fmt.Sprintf("Mode not supported: %s", mode), http.StatusBadRequest)

		return
	}

	if token == "" || token != secret.VerifyToken {
		log.Printf("Wrong token %s", token)
		http.Error(response, "Wrong token", http.StatusUnauthorized)

		return
	}

	fmt.Fprintf(response, `{"hub.challenge": "%s"}`, challenge)
}

// Put the request in a queue.
func enqueue(response http.ResponseWriter, request *http.Request) {
	activity := activityAction{}
	if err := json.NewDecoder(request.Body).Decode(&activity); err != nil {
		log.Printf("Wrong request %v", err)
		http.Error(response, fmt.Sprintf("Wrong request: %v", err), http.StatusBadRequest)

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
		log.Fatalf("JSON error %v", err)
		http.Error(response, "Error converting message", http.StatusInternalServerError)

		return
	}

	forwardMessage(response, request, payload)

	log.Printf("Athlete %d %ss %d",
			activity.OwnerID,
			activity.AspectType,
			activity.ObjectID)
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
		log.Printf("Ignoring action %s", activity.AspectType)

		return true
	}
}

func invalidSubscription(activity activityAction) bool {
	if activity.SubscriptionID != secret.SubscriptionID {
		log.Printf("Invalid subscription id %d", activity.SubscriptionID)

		return true
	}

	return false
}

func forwardMessage(response http.ResponseWriter, request *http.Request, payload []byte) {
	message := &pubsub.Message{Data: payload}

	messageID, err := pubClient.Topic(os.Getenv("PUBSUB_TOPIC")).Publish(request.Context(), message).Get(request.Context())
	if err != nil {
		log.Panicf("Error publishing message %v", err)
		http.Error(response, "Error publishing message", http.StatusInternalServerError)

		return
	}

	log.Printf("Message sent %s", messageID)
}
