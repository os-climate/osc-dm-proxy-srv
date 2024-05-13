# Copyright 2024 Broda Group Software Inc.
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
#
# Created:  2024-04-15 by eric.broda@brodagroupsoftware.com
import logging
import re
from collections import defaultdict
from fastapi import Request

# Set up logging
LOGGING_FORMAT = "%(asctime)s - %(module)s:%(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger(__name__)

class Stats():

    def __init__(self):
        self.statistics = defaultdict(int)
        self.reqs = []
        self.errs = []


    def error(self, request: Request, msg: str):
        self.statistics["error"] += 1
        err = {
            "path": request.url.path,
            "msg": msg
        }
        self.errs.append(err)


    # Function to extract statistics based on regex patterns
    def process(self, request: Request):
        logger.info(f"Processing request:{request}")
        # Split path into segments
        path = request.url.path
        segments = request.url.path.split('/')
        logger.info(f"segments:{segments}")

        # Build incremental paths
        self.statistics["/"] += 1
        incremental_path = ''
        for segment in segments[1:]:
            # Append the current segment to the incremental path
            incremental_path += '/' + segment

            # Increment statistics for the current incremental path
            self.statistics[incremental_path] += 1

        req = {
            "path": path
        }
        self.reqs.append(req)


    def info(self):
        return dict(self.statistics)


    def details(self):
        return self.reqs


    def errors(self):
        return self.errs