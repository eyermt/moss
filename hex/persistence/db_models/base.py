from __future__ import annotations
from neomodel import StructuredNode, StringProperty, RelationshipTo

class Category(StructuredNode):
    name = StringProperty(required=True)
    description = StringProperty(required=True)