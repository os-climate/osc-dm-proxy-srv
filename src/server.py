# Copyright 2024 Broda Group Software Inc.
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
#
# Created:  2024-04-15 by eric.broda@brodagroupsoftware.com
import logging
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import re
import os
import yaml
from typing import Callable
from functools import wraps
import httpx
import base64

import state
from registrar import Registrar
from stats import Stats
from bgsexception import BgsException, BgsNotFoundException

REQUEST_TIMEOUT = 5


app = FastAPI()

#####
#
# ATTENTION: as an interm step to get code working,
# I have setup the service to bypass CORS (cross
# checks (request from host other than
# originating host).
#
# This should be fixed properly with a PROXY
#
#####

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Specify the allowed origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Set up logging
LOGGING_FORMAT = "%(asctime)s - %(module)s:%(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger(__name__)

DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT=8000
DEFAULT_CONFIG="./config/config.yaml"

STATE_ROUTES="routes"
STATE_REGISTRAR="registrar"
STATE_ROOT="root"
STATE_DOMAINS="domains"
STATE_STATS="stats"

ENDPOINT_PREFIX = "/api"

def safe_decode(data):
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        # Return a base64 encoded string if UTF-8 decoding fails
        return base64.b64encode(data).decode('utf-8')

def tracer(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        # Find the request object in args or kwargs
        request = kwargs.get('request') if 'request' in kwargs else None
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

        # Extract body if the request is found
        if request:
            body = {}
            # Check if the request is likely to have a body
            if request.method not in ["GET", "HEAD", "OPTIONS"]:
                try:
                    body = await request.json()
                except Exception:
                    # Handle other content types like form-data or raw bodies
                    try:
                        body = await request.body()
                        body = safe_decode(body)  # Decode safely
                    except Exception as e:
                        body = f"Failed to read body: {str(e)}"

            # Call the actual endpoint
            try:
                response = await func(*args, **kwargs)

                # Log request and response details
                request_info = {
                    "url": str(request.url),
                    "method": request.method,
                    "headers": dict(request.headers),
                    "parameters": dict(request.query_params),
                    "body": body
                }
                response_info = {
                    "status_code": response.status_code,
                    "body": safe_decode(response.body) if response.body else "No Body"
                }

                logger.info(f"TRACE REQ: {request_info}")
                logger.info(f"TRACE RSP: {response_info}")

            except Exception as e:
                logger.error(f"Exception: {str(e)}")
                raise e

            return response
        else:
            return await func(*args, **kwargs)

    return wrapper


@app.get(ENDPOINT_PREFIX + "/statistics")
@tracer
async def statistics_get():
    logger.info("Getting statistics")
    stats = state.gstate(STATE_STATS)
    response = {
        "statistics":stats.info(),
        "details":stats.details(),
        "errors":stats.errors()
    }
    logger.info(f"Statistics response:{response}")
    return response

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@tracer
async def route_path(request: Request, path: str):
    logger.info(f"Routing path:{path} request:{request}")

    response = None
    try:
        response = await handle_request(request, path)
    except BgsNotFoundException as e:
        msg = f"Path not found:{path}, exception:{str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=404, detail=msg)
    except HTTPException as e:
        msg = f"HTTP exception: {str(e)}"
        logger.error(msg)
        raise
    except Exception as e:
        msg = f"Unknown exception: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    return response


async def handle_request(request: Request, path: str):
    logger.info(f"Handling request path:{path} request:{request}")

    routes = state.gstate(STATE_ROUTES)
    logger.info(f"Using routes:{routes}")

    # Note that routing tables with REGEX can easily
    # have unintentional errors such that multiple potential routes
    # can match a particular REGEX, which ideally should NEVER happen.
    # When routes are correct, then use the matching target_route.
    # When there are two matches, and one of them is the catchall
    # route, then use the available match (not the catchall).
    # When there are several matching routes, capture a list of all
    # matches, log them, and raise an exception

    catchall_route = None
    matching_routes = []
    for route in routes:
        # logger.info(f"Using route:{route}")
        pattern = route['source']
        # logger.info(f"Using source pattern:{pattern}")

        if re.match(pattern, "/" + path):
            # Check if this is the catch-all route
            if pattern == "/.*":
                catchall_route = route
            else:
                matching_routes.append(route)

    # If only one matching route is found, proceed with it
    if len(matching_routes) == 1:
        route = matching_routes[0]
        target = route['target']

        # Check if the target is a static endpoint or requires dynamic resolution
        resolver = "dataproduct_resolver"
        if target == "dataproduct_resolver":
            logger.info(f"Using resolver:{resolver}")
            resolved_target = None
            try:
                resolved_target = await dynamic_resolver(path)
            except BgsNotFoundException as e:
                msg = f"Could not find dynamic path:{path}, exception:{str(e)}"
                logger.error(msg)
                raise BgsNotFoundException(msg)
            target_route = resolved_target + "/" + path
        else:
            target_route = target + "/" + path

        logger.info(f"Using target_route:{target_route}")

        content, status_code, headers = await _forward_request(request, target_route)
        response = Response(content=content, status_code=status_code, headers=dict(headers))

        logger.info(f"Response:{response}")
        return response

    # If no specific routes are found but catch-all route exists, use it
    elif len(matching_routes) == 0 and catchall_route:
        target_route = catchall_route['target'] + "/" + path
        logger.info(f"Using catch-all route for target_route:{target_route}")

        content, status_code, headers = await _forward_request(request, target_route)
        response = Response(content=content, status_code=status_code, headers=dict(headers))

        logger.info(f"Response:{response}")
        return response

    # If multiple matching routes are found, log them and raise an exception
    elif len(matching_routes) > 1:
            msg = f"Multiple matching routes found for path {path}"
            for route in matching_routes:
                logger.error(f"{msg} Route: {route}")
            raise BgsException(msg)

    # Handle the case where no matching route is found
    else:
        msg = f"No matching route found for path {path}"
        logger.error(msg)
        raise BgsException(msg)


async def dynamic_resolver(path: str) -> str:
    # Logic to resolve the path to an IP address
    logger.info(f"Resolving path:{path}")
    resolved_path = await _service_discovery(path)
    logger.info(f"Resolved path:{path} to:{resolved_path}")
    return resolved_path


async def _service_discovery(path: str):
    logger.info(f"Discovering service from path:{path}")

    # Note that the path may have multiple UUIDs, but only the
    # first one will be found, which is the product UUID
    # that is used for service discovery
    uuid = None
    uuid_regex = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    match = re.search(uuid_regex, path)
    if match:
        uuid = match.group()
        logger.info(f"Retrieved uuid:{uuid} in path:{path}")
    else:
        msg = f"Invalid uuid in path:{path}"
        logger.error(msg)
        raise BgsNotFoundException(msg)

    registrar: Registrar = state.gstate(STATE_REGISTRAR)
    address = await registrar.retrieve_product_address(uuid)
    logger.info(f"Discovered uuid:{uuid} address:{address} from path:{path}")

    return address


async def _forward_request(request: Request, url: str):
    try:
        logger.info(f"Forwarding (async) request: {request} to URL: {url}")
        method = request.method
        headers = dict(request.headers)
        content = await request.body()

        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, headers=headers, content=content, timeout=REQUEST_TIMEOUT)
            return resp.content, resp.status_code, resp.headers.items()

    except httpx.ConnectTimeout:
        msg = f"Connect (async) timeout error occurred, timeout:{REQUEST_TIMEOUT}, url:{url}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=504, detail=msg)

    except httpx.ConnectError:
        msg = f"Connect (async) error occurred, url:{url}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=503, detail=msg)

    except httpx.NetworkError:
        msg = f"Network error (async) while trying to connect to URL: {url}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=503, detail="Network Error")

    except httpx.ReadTimeout:
        msg = f"Read (async) timeout error occurred, url:{url}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=504, detail=msg)

    except httpx.HTTPStatusError as e:
        msg = f"HTTP (async) status error occurred, url:{url} exception:{e}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=e.response.status_code, detail=msg)

    except httpx.RequestError as e:
        msg = f"Request (async) error occurred, url:{url} exception:{e}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=502, detail=msg)

    except Exception as e:
        msg = f"An unexpected error occurred, url:{url} exception:{e}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


if __name__ == "__main__":

    # Set up argument parsing
    import argparse
    parser = argparse.ArgumentParser(description="Proxy CLI (Command Language Interface)")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"Host for the server (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port for the server (default: {DEFAULT_PORT})")
    parser.add_argument("--configuration", default=DEFAULT_CONFIG, help=f"Configuration file (default: {DEFAULT_CONFIG})")
    args = parser.parse_args()

    # Read the configuration file
    configuration = None
    with open(args.configuration, 'r') as file:
        configuration = yaml.safe_load(file)

    # Get routing table configuration
    routes = configuration["routes"]
    state.gstate(STATE_ROUTES, routes)
    logger.info(f"Using routes:{routes}")

    # Get host and port for registrar
    registrar_host = configuration["registrar"]["host"]
    registrar_port = configuration["registrar"]["port"]
    registrar = Registrar({
        "host": registrar_host,
        "port": registrar_port,
    })
    state.gstate(STATE_REGISTRAR, registrar)
    logger.info(f"Using registrar:{registrar}")

    stats = Stats()
    state.gstate(STATE_STATS, stats)

    logger.info(f"Using current working directory:{os.getcwd()}")
    logger.info(f"START: Starting service on host:{args.host} port:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)

    logger.info(f"DONE: Starting service on host:{args.host} port:{args.port}")