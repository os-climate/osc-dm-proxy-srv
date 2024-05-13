# Copyright 2024 Broda Group Software Inc.
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
#
# Created:  2024-04-15 by eric.broda@brodagroupsoftware.com
# NOTE: It is important to ensure this file is identical to that
# in the bgssrv-dmregistry server models.py or you will
# get 422 Unprocessed Entity errors

from pydantic import BaseModel, HttpUrl, Field
from typing import List, Union, Optional, Dict
from enum import Enum

class Product(BaseModel):
    uuid: Optional[str] = None
    namespace: str
    name: str
    publisher: str
    description: str
    tags: List[str]
    address: Optional[str] = None
    createtimestamp: Optional[str] = None
    updatetimestamp: Optional[str] = None

class Contact(BaseModel):
    name: str
    email: str
    phone: str

class User(BaseModel):
    uuid: Optional[str] = None
    contact: Contact
    # address: Address
    createtimestamp: Optional[str] = None
    updatetimestamp: Optional[str] = None

class Publisher(BaseModel):
    uuid: Optional[str] = None
    contact: Contact
    # address: Address
    createtimestamp: Optional[str] = None
    updatetimestamp: Optional[str] = None

class Subscriber(BaseModel):
    uuid: Optional[str] = None
    contact: Contact
    # address: Address
    createtimestamp: Optional[str] = None
    updatetimestamp: Optional[str] = None

class Administrator(BaseModel):
    uuid: Optional[str] = None
    contact: Contact
    # address: Address
    createtimestamp: Optional[str] = None
    updatetimestamp: Optional[str] = None