from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from prometheus_fastapi_instrumentator import Instrumentator


# -----------------------
# Logging
# -----------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(message)s",
)
log = logging.getLogger("sre-starter")
webhook_log = logging.getLogger("alert-recv")


# -----------------------
# App
# -----------------------
app = FastAPI(title="sre-starter", version="0.1.0")
ENV = os.getenv("APP_ENV", "dev")


# -----------------------
# Middleware: JSON access log
# -----------------------
@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        latency_ms = (time.perf_counter() - start) * 1000.0
        status = getattr(locals().get("response", None), "status_code", 500)

        # 간단한 JSON 로그 (너가 이전에 보던 형태)
        log.info(
            json.dumps(
                {
                    "env": ENV,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "latency_ms": round(latency_ms, 2),
                },
                ensure_ascii=False,
            )
        )


# -----------------------
# Global exception handler (500 통일)
# -----------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 서버 로그에 에러 기록
    log.error(
        json.dumps(
            {
                "level": "error",
                "msg": "unhandled_exception",
                "error": repr(exc),
                "path": request.url.path,
                "method": request.method,
            },
            ensure_ascii=False,
        )
    )
    # 클라이언트에는 단순한 500 응답
    return JSONResponse(status_code=500, content={"detail": "internal_error"})


# -----------------------
# Prometheus metrics
# -----------------------
instrumentator = Instrumentator(
    should_group_status_codes=True,   # status="2xx/4xx/5xx" 형태로 나옴
    should_ignore_untemplated=True,   # handler 라벨 깔끔하게
    excluded_handlers=["/metrics"],   # metrics 자체는 기본 카운트 제외(원하면 제거)
)
instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# -----------------------
# Routes
# -----------------------
@app.get("/", include_in_schema=False)
def root():
    return {"ok": True, "service": "sre-starter", "env": ENV}


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}


@app.get("/fail")
def fail():
    # 알람 테스트용 500 발생
    raise RuntimeError("intentional failure for alert test")


@app.post("/alertmanager", include_in_schema=False)
async def alertmanager_webhook(req: Request):
    """
    Alertmanager webhook receiver.
    Alertmanager -> { receiver, status, alerts: [...], groupLabels, commonLabels, ... }
    """
    payload: Dict[str, Any] = await req.json()

    # 보기 좋게 핵심만 로그로 찍고 싶으면 아래처럼 요약도 가능
    summary = {
        "receiver": payload.get("receiver"),
        "status": payload.get("status"),
        "alerts_count": len(payload.get("alerts", [])),
        "alertnames": sorted(
            list({a.get("labels", {}).get("alertname") for a in payload.get("alerts", [])})
        ),
    }

    webhook_log.warning(
        "ALERTMANAGER_WEBHOOK %s",
        json.dumps({"summary": summary, "payload": payload}, ensure_ascii=False),
    )

    return {"ok": True}
