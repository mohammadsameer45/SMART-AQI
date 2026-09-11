"""
Web Push delivery (RFC 8030 + VAPID) for threshold alerts. No third-party
push provider account is needed — VAPID lets this server sign pushes
itself; the browser's own push service (Chrome -> FCM, Firefox -> Mozilla's
autopush, etc.) handles delivery to the device.
"""
from __future__ import annotations

import json
import logging

from pywebpush import WebPushException, webpush

from backend.config import config
from backend.models import mongo_models as M

log = logging.getLogger("smart_aqi.push")


def configured() -> bool:
    return bool(config.VAPID_PRIVATE_KEY_PEM and config.VAPID_SUBJECT)


def send_to_user(user_id: str, title: str, body: str, url: str = "/app/settings") -> int:
    """Push to every subscription this user has (multiple browsers/devices).
    Returns how many deliveries succeeded; prunes dead subscriptions."""
    if not configured():
        return 0
    sent = 0
    for sub in M.col(M.PUSH_SUBSCRIPTIONS).find({"user_id": user_id}):
        if _send_one(sub, title, body, url):
            sent += 1
    return sent


def _send_one(sub: dict, title: str, body: str, url: str) -> bool:
    subscription_info = {"endpoint": sub["endpoint"], "keys": sub["keys"]}
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=config.VAPID_PRIVATE_KEY_PEM,
            vapid_claims={"sub": config.VAPID_SUBJECT},
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            # subscription expired / unsubscribed on the browser side
            M.col(M.PUSH_SUBSCRIPTIONS).delete_one({"_id": sub["_id"]})
        else:
            log.warning("push delivery failed (%s): %s", status, e)
        return False
