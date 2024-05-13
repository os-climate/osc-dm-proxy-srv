# Copyright 2024 Broda Group Software Inc.
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
#
# Created:  2024-04-15 by eric.broda@brodagroupsoftware.com
import logging
import json
import etcd3
from tenacity import retry, stop_after_attempt, wait_fixed

# Set up logging
LOGGING_FORMAT = "%(asctime)s - %(module)s:%(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger(__name__)

class Etcd():

    def __init__(self, config: dict):
        """
        Connect to ETCD (our service registry)
        """
        logger.info(f"Using config:{config}")
        self.host = config["host"]
        self.port = config["port"]
        self._connect()

    def __str__(self):
        """
        For informal string representation, used by print()
        """
        return f"Etcd(name='{self.host}', port={self.port})"

    def __repr__(self):
        """
        For official string representation, useful for debugging
        """
        return f"Etcd(name='{self.host}', port={self.port})"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def _connect(self):
        """
        Connect to ETCD using tenacity retry mechanism.
        """
        logger.info(f"Connecting to etcd host:{self.host} port:{self.port}")
        try:
            self.client = etcd3.client(host=self.host, port=self.port)
            # If connection is successful, no exception is raised and tenacity stops retrying.
            logger.info(f"Connected to etcd host:{self.host} port:{self.port}")
        except Exception as e:
            logger.error(f"Error connecting to etcd host:{self.host} port:{self.port}, exception:{e}")
            raise  # Re-raise the exception to trigger tenacity retry.


    #####
    # INTERNAL
    #####
    def upsert(self, key: str, value: dict):
        logger.info(f"START: Upsert, key:{key} value:{value}")
        output = self.client.put(key, json.dumps(value))
        xoutput = str(output).replace('\n', ' ')
        logger.info(f"DONE: Upsert, key:{key} value:{value}, output:{xoutput}")
        return output

    def retrieve(self, key: str):
        logger.info(f"START: Retrieve, key:{key}")
        value, _ = self.client.get(key)
        if value:
            value = json.loads(value)
        logger.info(f"DONE: Retrieve, key:{key}, value:{value}")
        return value

    def retrieve_wildcard(self, wildcard_pattern: str):
        logger.info(f"wildcard_pattern:{wildcard_pattern}")

        # Fetch all keys and values under the root prefix
        all_data = [(metadata.key.decode('utf-8'), value.decode('utf-8'))
                    for value, metadata in self.client.get_prefix("/")]
        # logger.info(f"\n\n\nall_data:{all_data}")

        items = []
        for path, value in all_data:
            segments_search = wildcard_pattern.split('/')
            segments_path = path.split('/')

            # The number of segments should be the same
            if len(segments_search) != len(segments_path):
                continue

            match = True
            import fnmatch
            for s_search, s_path in zip(segments_search, segments_path):
                if not fnmatch.fnmatch(s_path, s_search):
                    match = False
                    break

            if match:
                # logger.info(f"match, path:{path} wildcard_pattern:{wildcard_pattern} value:{value}")
                value = json.loads(value)
                # logger.info(f"JSON value:{value}")
                items.append(value)

        if len(items) == 0:
            items = None

        logger.info(f"items:{items}")
        return items

    def retrieve_prefix(self, prefix: str):
        logger.info(f"START: Retrieve prefix, prefix:{prefix}")
        items = self.client.get_prefix(prefix)

        # NOTE: using prefix will retrieve all keys/values that
        # match the PREFIX.  So, "/product" will get:
        # - /product
        # - /product/1
        # - /product/1/1
        # - /product/1/1/1
        # If you only want /product and one level below,
        # then user "_retrieve_wildcard" with "/product/*"
        output = []
        for v, m in items:
            k = m.key.decode('utf-8')
            logger.info(f"Using m:{m} k:{k} v:{v}")
            output.append(json.loads(v))

        logger.info(f"DONE: Retrieve values, prefix:{prefix}, output:{output}")
        return output

    def remove(self, key: str):
        logger.info(f"START: Remove, key:{key}")
        output = self.client.delete(key)
        xoutput = str(output).replace('\n', ' ')
        logger.info(f"DONE: Remove, key:{key}, output:{xoutput}")
        return output