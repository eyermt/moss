//Clean House

//Delete Nodes & Relationships
MATCH (n) DETACH DELETE n;

//Drop Indices
DROP INDEX projectsByID IF EXISTS;
DROP INDEX packagesByID IF EXISTS;
DROP INDEX organizationsByID IF EXISTS;
DROP INDEX initiativesByID IF EXISTS;
DROP INDEX personsByName IF EXISTS;
DROP INDEX papersByName IF EXISTS;
DROP INDEX instByName IF EXISTS;
DROP INDEX conceptByName IF EXISTS;
DROP INDEX domainByName IF EXISTS;

//import nodes

/////////////////////////////////////////////IMPORT ALL ELEMENTS
LOAD CSV WITH HEADERS FROM "file:///ecosystms_output.csv" AS row

CALL apoc.create.node([row.Label],
        CASE row.Label
                WHEN 'Project' THEN {
                        Name: row.Name,
                        Description: row.Description,
                        Homepage: row.Homepage,
                        //License
                        Language: split(row.Language, ' | '),
                        Dependency: split(row.Dependency, ' | '),
                        Complementary: split(row.Complementary, ' | '),
                        Enhancement: split(row.Enhancement, ' | '),
                        Downstream: split(row.Downstream, ' | '),
                        Alternatives: split(row.Alternatives, ' | '),
                        `Fiscal Sponsor`: row.`Fiscal Sponsor`,
                        `Granting Organization A | B | C`: row.`Granting Organization A | B | C`,
                        Domain: row.Domain,
                        Subdomain: row.Subdomain,
                        Subfield: split(row.Subfield, ' | ')
                }
                WHEN 'Package' THEN {
                        Name: row.Name,
                        `Project/Package's Affiliated Projects`: split(row.`Project/Package's Affiliated Projects`, ' | '),
                        `Sustaining/Parent`: row.`Sustaining/Parent`,
                        Subfield: split(row.Subfield, ' | '),
                        `Project Tags`: split(row.`Project Tags`, ' | '),
                        Dependency: split(row.Dependency, ' | ')
                }
                WHEN 'Organization' THEN {
                        Name: row.Name,
                        `Consortium Affiliation`: row.`Consortium Affiliation`,
                        `Org Type`: row.`Org Type`,
                        `Focus Area`: split(row.`Focus Area`, ' | '),
                        Location: row.Location,
                        Website: row.Website,
                        `Contact Information`: row.`Contact Information`,
                        `Year Established`: row.`Year Established`,
                        Status: row.Status,
                        `Fiscal Sponsor`: row.`Fiscal Sponsor`
                }
                WHEN 'Initiative' THEN {
                        Name: row.Name,
                        `Affiliated Org`: row.`Affiliated Org`,
                        `Focus Area`: split(row.`Focus Area`, ' | '),
                        `Initiative Description`: row.`Initiative Description`,
                        Tag: row.Tag
                }
                WHEN 'Paper' THEN {
                        Name: row.Name,
                        Authors: split(row.Authors, ' | '),
                        ORCID: row.ORCID,
                        `Publication Date`: row.`Publication Date`,
                        Journal: row.Journal,
                        Abstract: row.Abstract,
                        DOI: row.DOI,
                        `Projects/Packages Cited`:  split(row.`Projects/Packages Cited`, ' | '),
                        `Granting Organization A | B | C`:  split(row.`Granting Organization A | B | C`, ' | '),
                        `Sustainable Development Goals`: split(row.`Sustainable Development Goals`, ' | '),
                        Concepts: split(row.Concepts, ' | '),
                        Domains: split(row.Domains, ' | ')
                }       
                WHEN 'Person' THEN {
                        Name: row.Name,
                        `Person's Associated Projects`: split(row.`Person's Associated Projects`, ' | '),
                        `Person's Associated Packages`: split(row.`Person's Associated Packages`, ' | '),
                        `Person's Affiliated Institutions`: split(row.`Persons Affiliated Institutions`, ' | '),
                        URL: row.URL
                }                
                WHEN 'Concept' THEN {
                        Name: row.Name,
                        Id: row.ID,
                        Wikidata_ID: row.Wikidata,
                        Level: row.Concept_level                        
                }
                WHEN 'Domain' THEN {
                        Name: row.Name,
                        Id: row.ID,
                        `Is major topic`: row.Is_major_topic                       
                }
                ELSE {
                        Name: row.Name
                }
        END
) YIELD node
RETURN node;




//Create Indices
CREATE INDEX projectsByID FOR (n:Project) ON (n.Name);
CREATE INDEX packagesByID FOR (n:Package) ON (n.Name);
CREATE INDEX organizationsByID FOR (n:Organization) ON (n.Name);
CREATE INDEX initiativesByID FOR (n:Initiative) ON (n.Name);
CREATE INDEX personsByName FOR (n:Person) ON (n.Name);
CREATE INDEX papersByName FOR (n:Paper) ON (n.Name);
CREATE INDEX instByName FOR (n:Institution) ON (n.Name);
CREATE INDEX conceptByName FOR (n:Concept) ON (n.Name);
CREATE INDEX domainByName FOR (n:Domain) ON (n.Name);
CALL db.awaitIndexes();





//create relationships

/////////////////////////////////////////// Project ->
// Project -> FISCALLY_SPONSORED_BY -> Organization
MATCH (n0:Project)
UNWIND n0.`Fiscal Sponsor` as i
MATCH (n1:Organization)
WHERE n1.Name = i
MERGE (n0)-[:FISCALLY_SPONSORED_BY]->(n1);

// Project -> DEPENDS_ON -> Project
MATCH (n0:Project)
UNWIND n0.Dependency as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:DEPENDS_ON]->(n1);

// Project -> DEPENDS_ON -> Package
MATCH (n0:Project)
UNWIND n0.Dependency as i
MATCH (n1:Package)
WHERE n1.Name = i
MERGE (n0)-[:DEPENDS_ON]->(n1);

// Project -> COMPLEMENTS -> Project
MATCH (n0:Project)
UNWIND n0.Complementary as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:COMPLEMENTS]->(n1);

// Project -> ENHANCES -> Project
MATCH (n0:Project)
UNWIND n0.Enhancement as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:ENHANCES]->(n1);

// Project <- DOWNSTREAM_OF <- Project
MATCH (n0:Project)
UNWIND n0.Downstream as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n1)-[:DOWNSTREAM_OF]->(n0);

// Project <- ALTERNATIVE_TO <- Project
MATCH (n0:Project)
UNWIND n0.Alternatives as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n1)-[:DOWNSTREAM_OF]->(n0);

/////////////////////////////////////////// Package ->
// Package -> AFFILIATED_PROJECT -> Project
MATCH (n0:Package)
UNWIND n0.`Project/Package's Affiliated Projects` as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:AFFILIATED_PROJECT]->(n1);

// Package -> DEPENDS_ON -> Package
MATCH (n0:Package)
UNWIND n0.Dependency as i
MATCH (n1:Package)
WHERE n1.Name = i
MERGE (n0)-[:DEPENDS_ON]->(n1);

// Package -> DEPENDS_ON -> Project
MATCH (n0:Package)
UNWIND n0.Dependency as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:DEPENDS_ON]->(n1);

/////////////////////////////////////////// Organization ->
// Organization -> FISCALLY_SPONSORED_BY -> Organization
MATCH (n0:Organization)
UNWIND n0.`Fiscal Sponsor` as i
MATCH (n1:Organization)
WHERE n1.Name = i
MERGE (n0)-[:FISCALLY_SPONSORED_BY]->(n1);

// Organization -> AFFILIATED_WITH_CONSORTIUM -> Organization
MATCH (n0:Organization)
UNWIND n0.`Consortium Affiliation` as i
MATCH (n1:Organization)
WHERE n1.Name = i
MERGE (n0)-[:AFFILIATED_WITH_CONSORTIUM]->(n1);


/////////////////////////////////////////// Initiative ->
// Initiative -> AFFILIATED_WITH_ORGANIZATION -> Organization
MATCH (n0:Initiative)
UNWIND n0.`Affiliated Org` as i
MATCH (n1:Organization)
WHERE n1.Name = i
MERGE (n0)-[:AFFILIATED_WITH_ORGANIZATION]->(n1);

/////////////////////////////////////////// Person ->
// Person -> ASSOCIATED_TO_PROJECT -> Project
MATCH (n0:Person)
UNWIND n0.`Person's Associated Projects` as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:ASSOCIATED_TO_PROJECT]->(n1);

// Person -> ASSOCIATED_TO_PACKAGE -> Package
MATCH (n0:Person)
UNWIND n0.`Person's Associated Packages` as i
MATCH (n1:Package)
WHERE n1.Name = i
MERGE (n0)-[:ASSOCIATED_TO_PACKAGE]->(n1);


// Person -> AFFILIATED_WITH_INSTITUTION -> Institution
MATCH (n0:Person)
UNWIND n0.`Person's Affiliated Institutions` as i
MATCH (n1:Institution)
WHERE n1.Name = i
MERGE (n0)-[:AFFILIATED_WITH_INSTITUTION]->(n1);


/////////////////////////////////////////// Paper ->
// Paper -> WRITTEN_BY -> Person
MATCH (n0:Paper)
UNWIND n0.Authors as i
MATCH (n1:Person)
WHERE n1.Name = i
MERGE (n0)-[:WRITTEN_BY]->(n1);


// Paper -> CITES -> Project
MATCH (n0:Paper)
UNWIND n0.`Projects/Packages Cited` as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:CITES]->(n1);

// Paper -> CITES -> Package
MATCH (n0:Paper)
UNWIND n0.`Projects/Packages Cited` as i
MATCH (n1:Package)
WHERE n1.Name = i
MERGE (n0)-[:CITES]->(n1);

// Paper -> ADDRESSES -> SDG
MATCH (n0:Paper)
UNWIND n0.`Sustainable Development Goals` as i
MATCH (n1:SDG)
WHERE n1.Name = i
MERGE (n0)-[:ADDRESSES]->(n1);

// Paper -> CONCEPTUALIZE -> Concept
MATCH (n0:Paper)
UNWIND n0.Concepts as i
MATCH (n1:Concept)
WHERE n1.Name = i
MERGE (n0)-[:CONCEPTUALIZE]->(n1);

// Paper -> IN_DOMAIN -> Domain
MATCH (n0:Paper)
UNWIND n0.Domains as i
MATCH (n1:Domain)
WHERE n1.Name = i
MERGE (n0)-[:IN_DOMAIN]->(n1);


// Paper -> GRANTING_ORGANIZATION -> Organization
MATCH (n0:Paper)
UNWIND n0.`Granting Organization A | B | C` as i
MATCH (n1:Organization)
WHERE n1.Name = i
MERGE (n0)-[:GRANTING_ORGANIZATION]->(n1);


