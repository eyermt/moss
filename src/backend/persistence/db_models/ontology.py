from __future__ import annotations
from src.moss.lib.models.base import Category
from neomodel import StructuredNode, StringProperty, RelationshipTo

class Author(StructuredNode):
    description = StringProperty(required=True)

class SoftwareApplication(StructuredNode):
    description = StringProperty(required=True)

class SoftwareEngineer(StructuredNode):
    description = StringProperty(required=True)

class SoftwarePackage(StructuredNode):
    description = StringProperty(required=True)

class Researcher(StructuredNode):
    description = StringProperty(required=True)

class _501C3(StructuredNode):
    description = StringProperty(required=True)

class Corporation(StructuredNode):
    name = StringProperty(required=True)

class AcademicInstitution(StructuredNode):
    description = StringProperty(required=True)

class Domain(Category):
    related_to = RelationshipTo('Domain', 'RELATED_TO')
    subdomain_of = RelationshipTo('Domain', 'SUBDOMAIN_OF')

class Topic(Category):
    related_to = RelationshipTo('Topic', 'RELATED_TO')
    subtopic_of = RelationshipTo('Topic', 'SUBTOPIC_OF')
    within_field = RelationshipTo('Field', 'WITHIN')
    within_domain = RelationshipTo('Domain', 'WITHIN')

class Field(Category):
    related_to = RelationshipTo('Field', 'RELATED_TO')
    subfield = RelationshipTo('Field', 'SUBFIELD_OF')
    within = RelationshipTo('Domain', 'WITHIN')
