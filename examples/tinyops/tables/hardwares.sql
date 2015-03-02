---
CREATE EXTENSION HSTORE;

CREATE TYPE hardware_state AS ENUM ('premount', 'mounted', 'kickstart', 'ready', 'online', 'offline');
CREATE TYPE hardware_environment AS ENUM ('dev', 'beta', 'prod', 'buffer');

CREATE TABLE IF NOT EXISTS datacenters (id SERIAL PRIMARY KEY, name VARCHAR(60) UNIQUE, contacts VARCHAR(252));

CREATE TABLE IF NOT EXISTS locations (id SERIAL PRIMARY KEY,
                                dc_id INT REFERENCES datacenters(id),
                                rack VARCHAR(60),
                                start_unit INT);

CREATE TABLE IF NOT EXISTS models (id SERIAL PRIMARY KEY, model VARCHAR(60), params HSTORE);

CREATE TABLE IF NOT EXISTS hardwares (id SERIAL PRIMARY KEY,
                                hostname VARCHAR(60) UNIQUE NOT NULL,
                                lan_ip CIDR UNIQUE NOT NULL,
                                oob_ip CIDR UNIQUE,
                                lan_mac MACADDR NOT NULL,
                                oob_mac MACADDR,
                                state hardware_state NOT NULL,
                                environment hardware_environment NOT NULL,
                                model_id INT REFERENCES models(id),
                                loc_id INT REFERENCES locations(id),
                                purchased_at TIMESTAMP WITHOUT TIME ZONE,
                                warrant_until TIMESTAMP WITHOUT TIME ZONE);






-- CREATE TABLE IF NOT EXISTS comments (id SERIAL PRIMARY KEY, hardware_id INT REFERENCES hardwares(id));

-- CREATE TABLE IF NOT EXISTS amendations (id SERIAL PRIMARY KEY, hardware_id INT REFERENCES hardwares(id), comment HSTORE);
