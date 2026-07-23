-- Dev-fake schema simulating go.intellichoice.org's real MySQL PII store (SPEC §5.4.1).
-- Mounted at /docker-entrypoint-initdb.d/ - runs once, on first-ever container boot against
-- an empty data volume. Deliberately plain SQL, not Alembic: this table set simulates an
-- external system IntelliChoice doesn't own, kept out of packages/db's own migrated schema.

CREATE DATABASE IF NOT EXISTS intellichoice;
CREATE DATABASE IF NOT EXISTS intellichoice_test;

CREATE USER IF NOT EXISTS 'intellichoice'@'%' IDENTIFIED BY 'intellichoice';
GRANT ALL PRIVILEGES ON intellichoice.* TO 'intellichoice'@'%';
GRANT ALL PRIVILEGES ON intellichoice_test.* TO 'intellichoice'@'%';
FLUSH PRIVILEGES;

USE intellichoice;

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

USE intellichoice_test;

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
