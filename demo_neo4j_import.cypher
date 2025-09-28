// Clear existing data (uncomment if needed)
// MATCH (n) DETACH DELETE n;

// Create constraints and indexes
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Keyword) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Attribute) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Community) REQUIRE n.name IS UNIQUE;

// Create nodes
// Create entity nodes
MERGE (:Entity {name: 'FC Barcelona', `chunk id`: '0FCIUkTr', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Copa del Rey', `chunk id`: '0FCIUkTr', `schema_type`: 'event'});
MERGE (:Entity {name: 'Real Madrid', `chunk id`: '0FCIUkTr', `schema_type`: 'organization'});
MERGE (:Entity {name: 'La Liga', `chunk id`: '0FCIUkTr', `schema_type`: 'event'});
MERGE (:Entity {name: 'European Cup', `chunk id`: '0FCIUkTr', `schema_type`: 'event'});
MERGE (:Entity {name: '2006-07 season', `chunk id`: 'rpQTmzHn', `schema_type`: 'time_period'});
MERGE (:Entity {name: '2006 FIFA Club World Cup', `chunk id`: 'rpQTmzHn', `schema_type`: 'event'});
MERGE (:Entity {name: 'Champions League', `chunk id`: 'rpQTmzHn', `schema_type`: 'event'});
MERGE (:Entity {name: 'Diego Maradona', `chunk id`: '0FCIUkTr', `schema_type`: 'person'});
MERGE (:Entity {name: 'Boca Juniors', `chunk id`: '0FCIUkTr', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Napoli', `chunk id`: '0FCIUkTr', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Luis', `chunk id`: '0FCIUkTr', `schema_type`: 'person'});
MERGE (:Entity {name: 'Terry Venables', `chunk id`: '0FCIUkTr', `schema_type`: 'person'});
MERGE (:Entity {name: 'manager', `chunk id`: '0FCIUkTr'});
MERGE (:Entity {name: '1984–85 season', `chunk id`: '0FCIUkTr', `schema_type`: 'time_period'});
MERGE (:Entity {name: 'Bernd Schuster', `chunk id`: '0FCIUkTr', `schema_type`: 'person'});
MERGE (:Entity {name: 'Steaua Bucureşti', `chunk id`: '0FCIUkTr', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Seville', `chunk id`: '0FCIUkTr', `schema_type`: 'location'});
MERGE (:Entity {name: 'European Cup final', `chunk id`: '0FCIUkTr'});
MERGE (:Entity {name: 'pre-season US tour', `chunk id`: 'rpQTmzHn', `schema_type`: 'event'});
MERGE (:Entity {name: 'string of injuries', `chunk id`: 'rpQTmzHn'});
MERGE (:Entity {name: 'Eto\'o', `chunk id`: 'rpQTmzHn', `schema_type`: 'person'});
MERGE (:Entity {name: 'Frank Rijkaard', `chunk id`: 'rpQTmzHn', `schema_type`: 'person'});
MERGE (:Entity {name: 'Lionel Messi', `chunk id`: 'rpQTmzHn', `schema_type`: 'person'});
MERGE (:Entity {name: 'Diego Maradona\'s goal of the century', `chunk id`: 'rpQTmzHn', `schema_type`: 'event'});
MERGE (:Entity {name: 'Royal Spanish Football Federation', `chunk id`: 'CbHylu8o', `schema_type`: 'organization'});
MERGE (:Entity {name: 'La Masia', `chunk id`: 'CbHylu8o', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Cesc Fàbregas', `chunk id`: 'CbHylu8o', `schema_type`: 'person'});
MERGE (:Entity {name: 'Gerard Piqué', `chunk id`: 'CbHylu8o', `schema_type`: 'person'});
MERGE (:Entity {name: 'Baby Dream Team', `chunk id`: 'CbHylu8o', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Cadetes A', `chunk id`: 'CbHylu8o', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Copa Catalunya final', `chunk id`: 'CbHylu8o', `schema_type`: 'event'});
MERGE (:Entity {name: 'plastic protector', `chunk id`: 'CbHylu8o', `schema_type`: 'object'});
MERGE (:Entity {name: 'Barcelona', `chunk id`: 'CbHylu8o', `schema_type`: 'location'});
MERGE (:Entity {name: 'Ronaldinho', `chunk id`: 'rpQTmzHn', `schema_type`: 'person'});
MERGE (:Entity {name: 'Getafe', `chunk id`: 'rpQTmzHn', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Internacional', `chunk id`: 'rpQTmzHn', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Liverpool', `chunk id`: 'rpQTmzHn', `schema_type`: 'organization'});
MERGE (:Entity {name: 'England', `chunk id`: 'CbHylu8o', `schema_type`: 'location'});
MERGE (:Entity {name: 'league', `chunk id`: 'CbHylu8o'});
MERGE (:Entity {name: 'Spanish cup', `chunk id`: 'CbHylu8o'});
MERGE (:Entity {name: 'Catalan cup', `chunk id`: 'CbHylu8o'});
MERGE (:Entity {name: 'Espanyol', `chunk id`: 'CbHylu8o', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Arsenal', `chunk id`: 'CbHylu8o', `schema_type`: 'organization'});
MERGE (:Entity {name: 'Spain', `chunk id`: 'CbHylu8o', `schema_type`: 'location'});

// Create attribute nodes
MERGE (:Attribute {name: 'type: football club', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'status: active', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'status: favourites', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'status: started strongly', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'status: finished without trophies', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'position: footballer', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'transfer_fee: 5 million', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'status: transferred', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'position: coach', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'type: football tournament', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'description: Spanish football cup competition', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'status: champions', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'position: manager', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'time: football season', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'type: football league', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'description: Spanish football league', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'position: German midfielder', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'type: city', `chunk id`: '0FCIUkTr'});
MERGE (:Attribute {name: 'description: football season', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'description: blamed for injuries', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'position: leading scorer', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'status: injured', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'position: rising star', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'position: football player', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'status: completed growth hormone treatment aged 14', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'status: lack of fitness affected form', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'description: football team', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'description: famous football goal', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'description: international football competition', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'description: Brazilian football side', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'description: European football competition', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'status: eventual runners-up', `chunk id`: 'rpQTmzHn'});
MERGE (:Attribute {name: 'type: youth academy', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'location: Barcelona', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'type: football federation', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'abbreviation: RFEF', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'relation: teammate', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'type: youth football team', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'description: Barcelona\'s greatest-ever youth side', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'achievement: unprecedented treble winner', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'location: England', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'type: football match', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'description: partido de la máscara (final of the mask)', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'score: 4-1 victory', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'type: medical equipment', `chunk id`: 'CbHylu8o'});
MERGE (:Attribute {name: 'purpose: facial protection', `chunk id`: 'CbHylu8o'});

// Create community nodes
MERGE (:Community {name: 'FC-Barcelona-Legends', `description`: 'A community of legendary FC Barcelona players and associated clubs, including icons like Messi, Ronaldinho, and Maradona.', `members`: '[\'FC Barcelona\', \'Diego Maradona\', \'Bernd Schuster\', "Eto\'o", \'Lionel Messi\', \'Ronaldinho\', \'Liverpool\', \'Cesc Fàbregas\', \'Gerard Piqué\', \'Baby Dream Team\', \'Arsenal\']'});
MERGE (:Community {name: 'Spanish-Football-Competitions', `description`: 'A network of major Spanish and international football competitions, clubs, and governing bodies like La Liga and Copa del Rey.', `members`: '[\'Boca Juniors\', \'Copa del Rey\', \'Real Madrid\', \'Napoli\', \'La Liga\', \'European Cup\', \'Steaua Bucureşti\', \'Getafe\', \'Internacional\', \'Royal Spanish Football Federation\', \'Cadetes A\', \'Espanyol\', \'Copa Catalunya final\']'});
MERGE (:Community {name: 'Barcelona-Managers', `description`: 'A group centered on Luis and featuring notable FC Barcelona managers like Frank Rijkaard and Terry Venables.', `members`: '[\'Luis\', \'Terry Venables\', \'manager\', \'Frank Rijkaard\']'});
MERGE (:Community {name: 'Historic-Football-Seasons', `description`: 'A group of significant football seasons and landmark achievements, including Maradona\'s goal and the Champions League.', `members`: '[\'1984–85 season\', \'2006-07 season\', "Diego Maradona\'s goal of the century", \'2006 FIFA Club World Cup\', \'Champions League\']'});
MERGE (:Community {name: 'Andalusian-Football', `description`: 'A small community connecting the city of Seville with the famed FC Barcelona youth academy, La Masia.', `members`: '[\'Seville\', \'La Masia\']'});
MERGE (:Community {name: 'European-Spanish-Competitions', `description`: 'Community centered around major European and Spanish football competitions, including Barcelona\'s domestic and international cup campaigns.', `members`: '[\'European Cup final\', \'Spanish cup\', \'Catalan cup\', \'Barcelona\', \'Spain\']'});
MERGE (:Community {name: 'US-Tour-Injuries', `description`: 'Community focused on the pre-season US tour, impacted by a string of injuries and equipment protection.', `members`: '[\'pre-season US tour\', \'string of injuries\', \'plastic protector\']'});
MERGE (:Community {name: 'English-League', `description`: 'Community discussing league football matters specifically within the context of England.', `members`: '[\'league\', \'England\']'});

// Create keyword nodes
MERGE (:Keyword {name: 'FC Barcelona'});
MERGE (:Keyword {name: 'Diego Maradona'});
MERGE (:Keyword {name: 'Luis'});
MERGE (:Keyword {name: 'Copa del Rey'});
MERGE (:Keyword {name: 'Real Madrid'});
MERGE (:Keyword {name: 'Terry Venables'});
MERGE (:Keyword {name: '1984–85 season'});
MERGE (:Keyword {name: 'La Liga'});
MERGE (:Keyword {name: 'Bernd Schuster'});
MERGE (:Keyword {name: 'Seville'});
MERGE (:Keyword {name: 'manager'});
MERGE (:Keyword {name: 'European Cup final'});
MERGE (:Keyword {name: '2006-07 season'});
MERGE (:Keyword {name: 'pre-season US tour'});
MERGE (:Keyword {name: 'Lionel Messi'});
MERGE (:Keyword {name: 'Frank Rijkaard'});
MERGE (:Keyword {name: 'Diego Maradona\'s goal of the century'});
MERGE (:Keyword {name: '2006 FIFA Club World Cup'});
MERGE (:Keyword {name: 'Champions League'});
MERGE (:Keyword {name: 'string of injuries'});
MERGE (:Keyword {name: 'La Masia'});
MERGE (:Keyword {name: 'Cesc Fàbregas'});
MERGE (:Keyword {name: 'Cadetes A'});
MERGE (:Keyword {name: 'Copa Catalunya final'});
MERGE (:Keyword {name: 'plastic protector'});
MERGE (:Keyword {name: 'league'});
MERGE (:Keyword {name: 'Spanish cup'});
MERGE (:Keyword {name: 'Catalan cup'});
MERGE (:Keyword {name: 'Barcelona'});
MERGE (:Keyword {name: 'Spain'});
MERGE (:Keyword {name: 'England'});

// Create relationships
// Create has_attribute relationships between entity and attribute
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Attribute {name: 'status: active'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Attribute {name: 'status: favourites'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Attribute {name: 'status: started strongly'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Attribute {name: 'status: finished without trophies'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Attribute {name: 'position: footballer'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Attribute {name: 'transfer_fee: 5 million'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Attribute {name: 'status: transferred'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Boca Juniors'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Luis'}), (end:Attribute {name: 'position: coach'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Copa del Rey'}), (end:Attribute {name: 'type: football tournament'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Copa del Rey'}), (end:Attribute {name: 'description: Spanish football cup competition'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Real Madrid'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Real Madrid'}), (end:Attribute {name: 'status: champions'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Napoli'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Terry Venables'}), (end:Attribute {name: 'position: manager'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: '1984–85 season'}), (end:Attribute {name: 'time: football season'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'La Liga'}), (end:Attribute {name: 'type: football league'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'La Liga'}), (end:Attribute {name: 'description: Spanish football league'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Bernd Schuster'}), (end:Attribute {name: 'position: German midfielder'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'European Cup'}), (end:Attribute {name: 'type: football tournament'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Steaua Bucureşti'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Seville'}), (end:Attribute {name: 'type: city'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: '2006-07 season'}), (end:Attribute {name: 'description: football season'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'pre-season US tour'}), (end:Attribute {name: 'description: blamed for injuries'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Eto\'o'}), (end:Attribute {name: 'position: leading scorer'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Eto\'o'}), (end:Attribute {name: 'status: injured'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Attribute {name: 'position: rising star'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Attribute {name: 'status: injured'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Attribute {name: 'position: football player'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Attribute {name: 'status: completed growth hormone treatment aged 14'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Frank Rijkaard'}), (end:Attribute {name: 'position: coach'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Ronaldinho'}), (end:Attribute {name: 'status: lack of fitness affected form'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Getafe'}), (end:Attribute {name: 'description: football team'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Diego Maradona\'s goal of the century'}), (end:Attribute {name: 'description: famous football goal'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: '2006 FIFA Club World Cup'}), (end:Attribute {name: 'description: international football competition'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Internacional'}), (end:Attribute {name: 'description: Brazilian football side'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Champions League'}), (end:Attribute {name: 'description: European football competition'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Liverpool'}), (end:Attribute {name: 'status: eventual runners-up'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'La Masia'}), (end:Attribute {name: 'type: youth academy'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'La Masia'}), (end:Attribute {name: 'location: Barcelona'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Royal Spanish Football Federation'}), (end:Attribute {name: 'type: football federation'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Royal Spanish Football Federation'}), (end:Attribute {name: 'abbreviation: RFEF'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Cesc Fàbregas'}), (end:Attribute {name: 'position: football player'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Cesc Fàbregas'}), (end:Attribute {name: 'relation: teammate'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Gerard Piqué'}), (end:Attribute {name: 'position: football player'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Gerard Piqué'}), (end:Attribute {name: 'relation: teammate'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Baby Dream Team'}), (end:Attribute {name: 'type: youth football team'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Baby Dream Team'}), (end:Attribute {name: 'description: Barcelona\'s greatest-ever youth side'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Attribute {name: 'type: youth football team'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Attribute {name: 'achievement: unprecedented treble winner'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Espanyol'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Arsenal'}), (end:Attribute {name: 'type: football club'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Arsenal'}), (end:Attribute {name: 'location: England'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Copa Catalunya final'}), (end:Attribute {name: 'type: football match'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Copa Catalunya final'}), (end:Attribute {name: 'description: partido de la máscara (final of the mask)'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'Copa Catalunya final'}), (end:Attribute {name: 'score: 4-1 victory'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'plastic protector'}), (end:Attribute {name: 'type: medical equipment'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);
MATCH (start:Entity {name: 'plastic protector'}), (end:Attribute {name: 'purpose: facial protection'}) MERGE (start)-[:HAS_ATTRIBUTE]->(end);

// Create participates_in relationships between entity and entity
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'Copa del Rey'}) MERGE (start)-[:PARTICIPATES_IN]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'Copa del Rey'}) MERGE (start)-[:PARTICIPATES_IN]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'European Cup'}) MERGE (start)-[:PARTICIPATES_IN]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: '2006-07 season'}) MERGE (start)-[:PARTICIPATES_IN]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: '2006 FIFA Club World Cup'}) MERGE (start)-[:PARTICIPATES_IN]->(end);
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'Champions League'}) MERGE (start)-[:PARTICIPATES_IN]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Copa Catalunya final'}) MERGE (start)-[:PARTICIPATES_IN]->(end);

// Create defeated relationships between entity and entity
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'Real Madrid'}) MERGE (start)-[:DEFEATED]->(end);
MATCH (start:Entity {name: 'Steaua Bucureşti'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:DEFEATED]->(end);

// Create won relationships between entity and entity
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'La Liga'}) MERGE (start)-[:WON]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Entity {name: 'league'}) MERGE (start)-[:WON]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Entity {name: 'Spanish cup'}) MERGE (start)-[:WON]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Entity {name: 'Catalan cup'}) MERGE (start)-[:WON]->(end);

// Create located_in relationships between entity and entity
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Entity {name: 'La Liga'}) MERGE (start)-[:LOCATED_IN]->(end);
MATCH (start:Entity {name: 'European Cup final'}), (end:Entity {name: 'Seville'}) MERGE (start)-[:LOCATED_IN]->(end);
MATCH (start:Entity {name: 'Barcelona'}), (end:Entity {name: 'Spain'}) MERGE (start)-[:LOCATED_IN]->(end);

// Create member_of relationships between entity and community
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Boca Juniors'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Luis'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Copa del Rey'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Real Madrid'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Napoli'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Terry Venables'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: '1984–85 season'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'La Liga'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Bernd Schuster'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'European Cup'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Steaua Bucureşti'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Seville'}), (end:Community {name: 'Andalusian-Football'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'manager'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'European Cup final'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: '2006-07 season'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'pre-season US tour'}), (end:Community {name: 'US-Tour-Injuries'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Eto\'o'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Frank Rijkaard'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Ronaldinho'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Getafe'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Diego Maradona\'s goal of the century'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: '2006 FIFA Club World Cup'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Internacional'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Champions League'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Liverpool'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'string of injuries'}), (end:Community {name: 'US-Tour-Injuries'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'La Masia'}), (end:Community {name: 'Andalusian-Football'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Royal Spanish Football Federation'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Cesc Fàbregas'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Gerard Piqué'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Baby Dream Team'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Espanyol'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Arsenal'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Copa Catalunya final'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'plastic protector'}), (end:Community {name: 'US-Tour-Injuries'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'league'}), (end:Community {name: 'English-League'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Spanish cup'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Catalan cup'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Barcelona'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'Spain'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:MEMBER_OF]->(end);
MATCH (start:Entity {name: 'England'}), (end:Community {name: 'English-League'}) MERGE (start)-[:MEMBER_OF]->(end);

// Create represented_by relationships between entity and keyword
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Keyword {name: 'FC Barcelona'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Keyword {name: 'Diego Maradona'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Luis'}), (end:Keyword {name: 'Luis'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Copa del Rey'}), (end:Keyword {name: 'Copa del Rey'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Real Madrid'}), (end:Keyword {name: 'Real Madrid'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Terry Venables'}), (end:Keyword {name: 'Terry Venables'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: '1984–85 season'}), (end:Keyword {name: '1984–85 season'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'La Liga'}), (end:Keyword {name: 'La Liga'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Bernd Schuster'}), (end:Keyword {name: 'Bernd Schuster'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Seville'}), (end:Keyword {name: 'Seville'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'manager'}), (end:Keyword {name: 'manager'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'European Cup final'}), (end:Keyword {name: 'European Cup final'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: '2006-07 season'}), (end:Keyword {name: '2006-07 season'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'pre-season US tour'}), (end:Keyword {name: 'pre-season US tour'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Keyword {name: 'Lionel Messi'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Frank Rijkaard'}), (end:Keyword {name: 'Frank Rijkaard'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Diego Maradona\'s goal of the century'}), (end:Keyword {name: 'Diego Maradona\'s goal of the century'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: '2006 FIFA Club World Cup'}), (end:Keyword {name: '2006 FIFA Club World Cup'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Champions League'}), (end:Keyword {name: 'Champions League'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'string of injuries'}), (end:Keyword {name: 'string of injuries'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'La Masia'}), (end:Keyword {name: 'La Masia'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Cesc Fàbregas'}), (end:Keyword {name: 'Cesc Fàbregas'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Keyword {name: 'Cadetes A'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Copa Catalunya final'}), (end:Keyword {name: 'Copa Catalunya final'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'plastic protector'}), (end:Keyword {name: 'plastic protector'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'league'}), (end:Keyword {name: 'league'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Spanish cup'}), (end:Keyword {name: 'Spanish cup'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Catalan cup'}), (end:Keyword {name: 'Catalan cup'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Barcelona'}), (end:Keyword {name: 'Barcelona'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'Spain'}), (end:Keyword {name: 'Spain'}) MERGE (start)-[:REPRESENTED_BY]->(end);
MATCH (start:Entity {name: 'England'}), (end:Keyword {name: 'England'}) MERGE (start)-[:REPRESENTED_BY]->(end);

// Create kw_filter_by relationships between entity and keyword
MATCH (start:Entity {name: 'FC Barcelona'}), (end:Keyword {name: 'FC Barcelona'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Keyword {name: 'Diego Maradona'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Luis'}), (end:Keyword {name: 'Luis'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Copa del Rey'}), (end:Keyword {name: 'Copa del Rey'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Real Madrid'}), (end:Keyword {name: 'Real Madrid'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Terry Venables'}), (end:Keyword {name: 'Terry Venables'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: '1984–85 season'}), (end:Keyword {name: '1984–85 season'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'La Liga'}), (end:Keyword {name: 'La Liga'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Bernd Schuster'}), (end:Keyword {name: 'Bernd Schuster'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Seville'}), (end:Keyword {name: 'Seville'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'manager'}), (end:Keyword {name: 'manager'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'European Cup final'}), (end:Keyword {name: 'European Cup final'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: '2006-07 season'}), (end:Keyword {name: '2006-07 season'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'pre-season US tour'}), (end:Keyword {name: 'pre-season US tour'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Keyword {name: 'Lionel Messi'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Frank Rijkaard'}), (end:Keyword {name: 'Frank Rijkaard'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Diego Maradona\'s goal of the century'}), (end:Keyword {name: 'Diego Maradona\'s goal of the century'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: '2006 FIFA Club World Cup'}), (end:Keyword {name: '2006 FIFA Club World Cup'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Champions League'}), (end:Keyword {name: 'Champions League'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'string of injuries'}), (end:Keyword {name: 'string of injuries'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'La Masia'}), (end:Keyword {name: 'La Masia'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Cesc Fàbregas'}), (end:Keyword {name: 'Cesc Fàbregas'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Cadetes A'}), (end:Keyword {name: 'Cadetes A'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Copa Catalunya final'}), (end:Keyword {name: 'Copa Catalunya final'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'plastic protector'}), (end:Keyword {name: 'plastic protector'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'league'}), (end:Keyword {name: 'league'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Spanish cup'}), (end:Keyword {name: 'Spanish cup'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Catalan cup'}), (end:Keyword {name: 'Catalan cup'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Barcelona'}), (end:Keyword {name: 'Barcelona'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'Spain'}), (end:Keyword {name: 'Spain'}) MERGE (start)-[:KW_FILTER_BY]->(end);
MATCH (start:Entity {name: 'England'}), (end:Keyword {name: 'England'}) MERGE (start)-[:KW_FILTER_BY]->(end);

// Create belongs_to relationships between entity and entity
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:BELONGS_TO]->(end);
MATCH (start:Entity {name: 'Terry Venables'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:BELONGS_TO]->(end);
MATCH (start:Entity {name: 'Bernd Schuster'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:BELONGS_TO]->(end);
MATCH (start:Entity {name: 'Eto\'o'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:BELONGS_TO]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:BELONGS_TO]->(end);
MATCH (start:Entity {name: 'Ronaldinho'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:BELONGS_TO]->(end);

// Create transferred_from relationships between entity and entity
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Entity {name: 'Boca Juniors'}) MERGE (start)-[:TRANSFERRED_FROM]->(end);

// Create transferred_to relationships between entity and entity
MATCH (start:Entity {name: 'Diego Maradona'}), (end:Entity {name: 'Napoli'}) MERGE (start)-[:TRANSFERRED_TO]->(end);

// Create precedes relationships between entity and entity
MATCH (start:Entity {name: 'Real Madrid'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:PRECEDES]->(end);

// Create is_a relationships between entity and entity
MATCH (start:Entity {name: 'Terry Venables'}), (end:Entity {name: 'manager'}) MERGE (start)-[:IS_A]->(end);

// Create influences relationships between entity and entity
MATCH (start:Entity {name: 'pre-season US tour'}), (end:Entity {name: 'string of injuries'}) MERGE (start)-[:INFLUENCES]->(end);

// Create related_to relationships between entity and entity
MATCH (start:Entity {name: 'Eto\'o'}), (end:Entity {name: 'Frank Rijkaard'}) MERGE (start)-[:RELATED_TO]->(end);
MATCH (start:Entity {name: 'Internacional'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:RELATED_TO]->(end);
MATCH (start:Entity {name: 'Liverpool'}), (end:Entity {name: 'FC Barcelona'}) MERGE (start)-[:RELATED_TO]->(end);

// Create comparable_to relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Diego Maradona\'s goal of the century'}) MERGE (start)-[:COMPARABLE_TO]->(end);

// Create enrolled in relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Royal Spanish Football Federation'}) MERGE (start)-[:ENROLLED_IN]->(end);

// Create studied at relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'La Masia'}) MERGE (start)-[:STUDIED_AT]->(end);

// Create befriended relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Cesc Fàbregas'}) MERGE (start)-[:BEFRIENDED]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Gerard Piqué'}) MERGE (start)-[:BEFRIENDED]->(end);

// Create part_of relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Baby Dream Team'}) MERGE (start)-[:PART_OF]->(end);
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Cadetes A'}) MERGE (start)-[:PART_OF]->(end);

// Create used_by relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'plastic protector'}) MERGE (start)-[:USED_BY]->(end);

// Create chose to remain in relationships between entity and entity
MATCH (start:Entity {name: 'Lionel Messi'}), (end:Entity {name: 'Barcelona'}) MERGE (start)-[:CHOSE_TO_REMAIN_IN]->(end);

// Create left for relationships between entity and entity
MATCH (start:Entity {name: 'Cesc Fàbregas'}), (end:Entity {name: 'England'}) MERGE (start)-[:LEFT_FOR]->(end);
MATCH (start:Entity {name: 'Gerard Piqué'}), (end:Entity {name: 'England'}) MERGE (start)-[:LEFT_FOR]->(end);

// Create made offer to relationships between entity and entity
MATCH (start:Entity {name: 'Arsenal'}), (end:Entity {name: 'Lionel Messi'}) MERGE (start)-[:MADE_OFFER_TO]->(end);

// Create keyword_of relationships between keyword and community
MATCH (start:Keyword {name: 'FC Barcelona'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Lionel Messi'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Cesc Fàbregas'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Bernd Schuster'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Diego Maradona'}), (end:Community {name: 'FC-Barcelona-Legends'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Luis'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Terry Venables'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'manager'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Frank Rijkaard'}), (end:Community {name: 'Barcelona-Managers'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'La Liga'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Copa del Rey'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Cadetes A'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Real Madrid'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Copa Catalunya final'}), (end:Community {name: 'Spanish-Football-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Seville'}), (end:Community {name: 'Andalusian-Football'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'La Masia'}), (end:Community {name: 'Andalusian-Football'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: '1984–85 season'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: '2006-07 season'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Diego Maradona\'s goal of the century'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: '2006 FIFA Club World Cup'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Champions League'}), (end:Community {name: 'Historic-Football-Seasons'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'pre-season US tour'}), (end:Community {name: 'US-Tour-Injuries'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'string of injuries'}), (end:Community {name: 'US-Tour-Injuries'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'plastic protector'}), (end:Community {name: 'US-Tour-Injuries'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'European Cup final'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Spanish cup'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Catalan cup'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Barcelona'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'Spain'}), (end:Community {name: 'European-Spanish-Competitions'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'league'}), (end:Community {name: 'English-League'}) MERGE (start)-[:KEYWORD_OF]->(end);
MATCH (start:Keyword {name: 'England'}), (end:Community {name: 'English-League'}) MERGE (start)-[:KEYWORD_OF]->(end);
