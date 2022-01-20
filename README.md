# Receiver for the Strava events

This is a simple implementation of the
[Strava Webhook API](https://developers.strava.com/docs/webhooks/)
for a local cycling community.

### Validation request [GET]
Comes with the following query parameters:
- _hub.mode_ = _subscribe_
- _hub.verify_token_ = a secret used for subscription
- _hub.challenge_ = a random string to send back

The response is a JSON string with the same _hub.challenge_.

### Event data request [POST]
Comes as a JSON string with the following keys:
- _subscription_id_ = the webhook's unique id
- _aspect_type_ = type of change, either _create_ or _update_ (_delete_ is being ignored)
- _updates_ = what has been changed
  - _type_ = the only update supported is the type switch to _Ride_
  - _authorized_ = _false_ when the athlete unsubscribes
- _object_type_ = _athlete_ or _activity_
- _owner_id_ = the athlete's unique number
- _object_id_ = either activity's unique number or the athlete's if they unsubscribes

In case all the requirements are met the whole request goes to a Google Pub/Sub service queue
and triggers another cloud function to pick it up on the other side.

**WARNING**. If the hook doesn't manage to finish in 2 sec. (when _cold_ started) Strava gonna repeat the request in 2 min.
Next attempt has more chances to succeed due to a _warm_ cloud function state.