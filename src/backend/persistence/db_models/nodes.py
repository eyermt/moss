from __future__ import annotations
from neomodel import StructuredNode, StringProperty, DateTimeProperty, BooleanProperty, UniqueIdProperty, RelationshipTo

from src.moss.lib.models.ontology import (
    Author,
    Researcher, 
    SoftwareEngineer, 
    SoftwarePackage, 
    Topic, 
    Domain, 
    Field,
    _501C3,
    Corporation,
    AcademicInstitution,
)

class Person(StructuredNode):
    name = StringProperty(required = True)
    orcid = StringProperty()
    github_username = StringProperty()
    email = StringProperty()

    is_author = RelationshipTo(Author, 'IS_A')
    is_researcher = RelationshipTo(Researcher, 'IS_A')
    software_engineer = RelationshipTo(SoftwareEngineer, 'IS_A')

    funds = RelationshipTo("Project", 'FUNDS')
    fiscally_sponsors = RelationshipTo("Project", 'FISCALLY_SPONSORS')
    authored = RelationshipTo("Paper", 'AUTHORED')
    uses = RelationshipTo("Project", 'USES')
    contributor = RelationshipTo("Project", 'CONTRIBUTES_TO')

class Project(StructuredNode):
    name = StringProperty(unique_index = True, required = True)
    url = StringProperty(unique_index =  True, required = True)

    sustained_by_org = RelationshipTo('Organization', 'SUSTAINED_BY')
    sustained_by_person = RelationshipTo(Person, 'SUSTAINED_BY')
    incubated_by_org = RelationshipTo('Organization', 'INCUBATED_BY')
    incubated_by_person = RelationshipTo(Person, 'INCUBATED_BY')

    is_package = RelationshipTo(SoftwarePackage, 'IS_A')
    used_in_field = RelationshipTo(Field, 'USED_IN')
    used_in_domain = RelationshipTo(Domain, 'USED_IN')
    used_in_topic = RelationshipTo(Topic, 'USED_IN')
    relates_to = RelationshipTo(Domain, 'RELATES_TO')


class Organization(StructuredNode):
    name = StringProperty(unique_index = True, required = True)

    funds_project = RelationshipTo(Project, 'FUNDS')
    funds_person = RelationshipTo(Person, 'FUNDS')
    fiscally_sponsors = RelationshipTo(Project, 'FISCALLY_SPONSORS')
    uses = RelationshipTo(Project, 'USES')

    is_501c3 = RelationshipTo(_501C3, 'IS_A')
    is_corporation = RelationshipTo(Corporation, 'IS_A')
    is_academic_institution = RelationshipTo(AcademicInstitution, 'IS_A')

class Paper(StructuredNode):
    title = StringProperty(unique_index = False, required = True)
    description = StringProperty(unique_index = False, required = False)
    url = StringProperty(unique_index = False, required = True)
    published_date = DateTimeProperty()
    has_public_data = BooleanProperty(required=True)
    has_public_code = BooleanProperty(required=True)

    cites_paper = RelationshipTo('Paper', 'CITES')
    cites_project = RelationshipTo(Project, 'CITES')
    mentioned = RelationshipTo(Project, 'MENTIONED')
    related_to = RelationshipTo(Domain, 'RELATED_TO')
