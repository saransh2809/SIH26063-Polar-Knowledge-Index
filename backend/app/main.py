from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health, public, staff
from app.services.llm import LLMNotConfigured, LLMUnavailable

app = FastAPI(
    title="NCPOR Polar Knowledge Index",
    description="SIH26063 prototype: harvested NCPOR archive, cited answers, reviewed drafts.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMNotConfigured)
def llm_not_configured(_: Request, exc: LLMNotConfigured) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "llm_not_configured"})


@app.exception_handler(LLMUnavailable)
def llm_unavailable(_: Request, exc: LLMUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "The language model is unreachable right now and this request is not cached. "
                           "Search and archive pages still work.", "code": "llm_unavailable"},
    )


app.include_router(health.router)
app.include_router(public.router)
app.include_router(staff.router)
