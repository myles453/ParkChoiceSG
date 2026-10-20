"""Recommendation HTTP entry point. Run with uvicorn app:app --no-access-log."""
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from onemap_adapter import Coordinate, OneMapClient
from model_adapter import configured_predictor
from operator_auth import verify_operator
from recommendation import TripRequest, recommend

app = FastAPI(title='ParkChoiceSG backend', version='0.1.0')
# Local Flutter web development only. Native mobile clients do not need CORS.
app.add_middleware(CORSMiddleware,allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                   allow_methods=['GET','POST'],allow_headers=['Content-Type'])
app.state.predictor = configured_predictor()


class PointInput(BaseModel):
    """WGS84 point sent by the app. Strict floats reject strings and NaN."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90,strict=True)
    longitude: float = Field(ge=-180, le=180,strict=True)

    def coordinate(self):
        return Coordinate(self.latitude,self.longitude)


class SearchInput(BaseModel):
    """Free-text destination query passed to OneMap search."""
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    query: str = Field(min_length=1,max_length=200)


class RecommendationInput(BaseModel):
    """Trip request body. Ranges match recommendation.TripRequest."""
    model_config = ConfigDict(extra='forbid')
    origin: PointInput
    destination: PointInput
    duration_minutes: int = Field(ge=1,le=1440,strict=True)
    candidate_limit: int = Field(default=3,ge=1,le=5,strict=True)
    radius_meters: int = Field(default=1500,ge=100,le=3000,strict=True)
    payment_method: Literal['parking_sg','paper_coupon'] = 'parking_sg'


class OperatorLoginInput(BaseModel):
    """Operator console credential. Never logged or echoed in errors."""
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1,max_length=100)
    password: str = Field(min_length=1,max_length=200)


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    # Default validation output includes submitted values. Keep location/search
    # inputs out of error responses, while retaining useful field names.
    return JSONResponse(status_code=422,content={'detail':[
        {'field':'.'.join(str(part) for part in error['loc']), 'type':error['type']}
        for error in exc.errors()]})


@app.get('/health')
def health():
    """Process liveness, not a claim that all external providers are healthy."""
    return {'status':'ok','prediction_configured':getattr(app.state.predictor,'ready',False) is True,
            'prediction_output':getattr(app.state.predictor,'output_kind',None)}


@app.post('/destinations')
def destinations(body: SearchInput):
    """Return destination choices; the driver chooses the correct one."""
    try:
        result = OneMapClient.from_env().search(body.query)
    except ValueError:
        raise HTTPException(503,'Routing setup is incomplete or the search input is invalid') from None
    if result.status not in {'ok','no_results'}:
        raise HTTPException(503,{'provider':'onemap','status':result.status})
    return asdict(result)


@app.post('/recommend')
def recommendations(body: RecommendationInput):
    """Read-only route, cost and arrival-availability comparison."""
    try:
        client=OneMapClient.from_env()
    except ValueError:
        raise HTTPException(503,'Routing setup is incomplete') from None
    try:
        trip = TripRequest(body.origin.coordinate(),body.destination.coordinate(),body.duration_minutes,
                           body.candidate_limit,body.radius_meters,body.payment_method)
        return recommend(trip,client,app.state.predictor)
    except ValueError:
        raise HTTPException(422,'Invalid trip or routing configuration') from None
    except Exception:
        # Database errors may contain connection details; no raw trace/body is
        # returned. Expected route/model failures are candidate-level statuses.
        raise HTTPException(503,'Recommendation data is temporarily unavailable') from None


@app.post('/operator/login')
def operator_login(body: OperatorLoginInput):
    """Check the single operator credential. Drivers never sign in."""
    try:
        ok = verify_operator(body.username,body.password)
    except ValueError:
        raise HTTPException(503,'Operator login is not configured') from None
    if not ok:
        raise HTTPException(401,'Incorrect operator username or password')
    return {'status':'ok'}
