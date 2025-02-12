from neomodel import StructuredRel, DateTimeProperty, FloatProperty

class RelatedTo(StructuredRel):
    score = FloatProperty()

class ContributedTo(StructuredRel):
    date = DateTimeProperty()