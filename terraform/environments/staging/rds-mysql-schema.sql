-- Adapted from mysql-init/001-schema.sql for RDS (S32/D-084) - the local dev-compose
-- init script's CREATE DATABASE/CREATE USER/GRANT statements don't apply here: RDS
-- already creates the db_name database and master user via Terraform (random-generated
-- password in Secrets Manager, not the hardcoded local dev 'intellichoice'/'intellichoice'
-- pair), so only the table DDL is reused. Keep in sync with mysql-init/001-schema.sql by
-- hand if that file's table shapes change - deliberately not the same file since the two
-- bootstrap flows differ structurally, not just cosmetically.

CREATE TABLE IF NOT EXISTS users (
    external_id VARCHAR(64) PRIMARY KEY,
    role ENUM('student', 'parent') NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    grade VARCHAR(16) NULL,
    branch_external_id VARCHAR(64) NULL
);

CREATE TABLE IF NOT EXISTS parent_child_links (
    parent_external_id VARCHAR(64) NOT NULL,
    child_external_id VARCHAR(64) NOT NULL,
    PRIMARY KEY (parent_external_id, child_external_id)
);

-- No 'unknown' status: a missing row is what AttendanceStatus.UNKNOWN means (fail closed).
CREATE TABLE IF NOT EXISTS attendance (
    student_external_id VARCHAR(64) NOT NULL,
    week_key VARCHAR(16) NOT NULL,
    status ENUM('present', 'absent') NOT NULL,
    PRIMARY KEY (student_external_id, week_key)
);

CREATE TABLE IF NOT EXISTS branches (
    external_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    manager_email VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL
);
