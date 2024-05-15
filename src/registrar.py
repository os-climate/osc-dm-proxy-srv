# Copyright 2024 Broda Group Software Inc.
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
#
# Created:  2024-04-15 by eric.broda@brodagroupsoftware.com
import logging
import uuid
from datetime import datetime

# Set up logging
LOGGING_FORMAT = "%(asctime)s - %(module)s:%(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger(__name__)

from etcd import Etcd
from bgsexception import BgsException, BgsNotFoundException

STATUS_AUTHORIZED = "authorized"
STATUS_UNAUTHORIZED = "unauthorized"

import utilities

class Registrar():

    def __init__(self, config: dict):
        """
        Connect to ETCD (our service registry)
        """
        logger.info(f"Using config:{config}")
        self.registrar_host = config["host"]
        self.registrar_port = config["port"]

    async def retrieve_product_address(self, uuid: str):
        logger.info(f"Retrieving product address uuid:{uuid}")
        service = f"/api/registrar/products/uuid/{uuid}"
        method = "GET"
        response = await utilities.httprequest(self.registrar_host, self.registrar_port, service, method)

        product_json = response
        logger.info(f"Using product_json:{product_json}")
        address = product_json["address"]
        logger.info(f"Retrieved product address uuid:{uuid}, address:{address}")
        return address
