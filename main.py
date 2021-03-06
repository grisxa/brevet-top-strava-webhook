"""
Accepts events from the Strava back-end as described in the Webhook API.

https://developers.strava.com/docs/webhooks/

Supports both Event Data (POST) and Validation (GET) requests.
Events go then to a Goggle Pub/Sub queue.
"""
import logging
import os
from json import JSONDecodeError
from typing import Optional

import google.cloud.logging
import google.cloud.pubsub
from flask import Request, json, abort

pub_client: google.cloud.pubsub.PublisherClient = None


def init_logger():
    """
    Set up the logging.

    :return:
    """
    log_client = google.cloud.logging.Client()
    log_client.get_default_handler()
    log_client.setup_logging(log_level=logging.INFO)
    logging.basicConfig(level=logging.INFO)


def strava_webhook(request: Request):
    """
    Register the Strava API webhook.

    :param request: HTTP request
    :return: JSON response
    """
    init_logger()
    logging.info(
        "Request args %s | json %s", request.args.to_dict(), request.get_json()
    )

    try:
        if request.method == "GET":
            return verify(request.args)

        if request.method == "POST":
            return enqueue(request.get_json())

        return abort(405)

    except KeyError as error:
        logging.error(str(error))
        # exception means a parameter not given
        return abort(400)


def verify(data: Optional[dict]):  # pylint: disable=unsubscriptable-object
    """
    Webhook verification request handler.

    :param data: HTTP request parameters
    :return: JSON with a challenge code
    """
    # Secret Manager exposed to the environment
    secret = json.loads(os.getenv("STRAVA"))

    if "hub.mode" in data:
        if (
            data["hub.mode"] != "subscribe"
            or data["hub.verify_token"] != secret["verify_token"]
        ):
            return abort(401)

        return {"hub.challenge": data["hub.challenge"]}
    return abort(400)


def enqueue(data: Optional[dict]):  # pylint: disable=unsubscriptable-object
    """
    Put the request in a queue.

    :param data: JSON request parameters
    :return: OK
    """
    secret: dict = {}
    # Secret Manager exposed to the environment
    try:
        secret = json.loads(os.getenv("STRAVA"))
    except (TypeError, JSONDecodeError) as error:
        logging.error("Wrong Strava settings: %s", str(error))
        abort(500)

    if int(data["subscription_id"]) != int(secret["subscription_id"]):
        logging.error("Invalid subscription id")
        abort(403)

    if data["aspect_type"] == "create":
        pass
    elif (
        data["aspect_type"] == "update"
        and data["object_type"] == "activity"
        and data.get("updates", {}).get("type") == "Ride"
    ):
        pass
    elif (
        data["aspect_type"] == "update"
        and data["object_type"] == "athlete"
        and data.get("updates", {}).get("authorized") == "false"
    ):
        pass
    else:
        logging.warning("Ignoring action %s", data["aspect_type"])
        return "OK"

    forward_message(data)

    # "Athlete 123 creates/updates 456"
    logging.info(
        "Athlete %s %ss %s",
        data["owner_id"],
        data["aspect_type"],
        data["object_id"],
    )

    return "OK"


def forward_message(data: dict):
    """
    Send a message further in the chain: to a PubSub topic.

    :param data: message to send
    """
    global pub_client  # pylint: disable=global-statement,invalid-name

    project_id = os.getenv("GCLOUD_PROJECT")
    topic = os.getenv("PUBSUB_TOPIC")

    # put the request in the queue
    pub_client = pub_client or google.cloud.pubsub.PublisherClient()
    topic_path = pub_client.topic_path(project_id, topic)  # pylint: disable=no-member
    pub_client.publish(topic_path, json.dumps(data).encode("utf-8"))
