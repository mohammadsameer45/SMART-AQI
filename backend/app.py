"""
SMART AQI Flask application factory.

React -> this API -> MongoDB (local). Secrets come from backend/.env via
backend.config. Every response uses the {ok, data|error} envelope.
"""
from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from backend.config import config
from backend.models import mongo_models as M
from backend.utils.responses import ApiError

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smart_aqi")


def create_app() -> Flask:
    config.validate(require_secrets=True)
    app = Flask(__name__)

    CORS(app, resources={r"/api/*": {"origins": [config.FRONTEND_URL]}},
         supports_credentials=False, methods=["GET", "POST", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"])

    from backend.routes import (aqi_routes, auth_routes, forecast_routes,
                                health_routes, location_routes, map_routes,
                                model_routes, weather_routes)
    for mod in (auth_routes, location_routes, aqi_routes, forecast_routes,
                health_routes, model_routes, weather_routes, map_routes):
        app.register_blueprint(mod.bp)

    # ------------------------------------------------------------- health ----
    @app.get("/api/health")
    def health():
        try:
            ver = M.ping()
            db_ok = True
        except Exception as e:                       # pragma: no cover
            ver, db_ok = str(e), False
        return jsonify({"ok": True, "data": {
            "service": "smart-aqi-api", "mongo_ok": db_ok, "mongo": ver,
            "db": config.MONGO_DB}})

    # --------------------------------------------------------- error handlers
    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        return jsonify({"ok": False,
                        "error": {"code": e.code, "message": e.message,
                                  **e.extra}}), e.status

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException):
        return jsonify({"ok": False,
                        "error": {"code": e.name.lower().replace(" ", "_"),
                                  "message": e.description}}), e.code

    @app.errorhandler(Exception)
    def _unhandled(e: Exception):                    # pragma: no cover
        log.exception("unhandled error on %s %s", request.method, request.path)
        return jsonify({"ok": False,
                        "error": {"code": "internal_error",
                                  "message": "Something went wrong"}}), 500

    @app.after_request
    def _log(resp):
        log.info("%s %s -> %s", request.method, request.path, resp.status_code)
        return resp

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=config.DEBUG)
