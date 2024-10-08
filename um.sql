--
-- File generated with SQLiteStudio v3.4.4 on Sat Sep 7 20:23:39 2024
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: email
CREATE TABLE email (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL);

-- Table: id_key
CREATE TABLE id_key (id INTEGER PRIMARY KEY AUTOINCREMENT, idid TEXT, key TEXT UNIQUE, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, timestamp TEXT NOT NULL, expires TEXT);

-- Table: message
CREATE TABLE message (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT, author INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, reply_to INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, sms INTEGER DEFAULT (0), created TEXT NOT NULL, sent TEXT, deleted TEXT);

-- Table: message_flag
CREATE TABLE message_flag (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, reminder TEXT);

-- Table: message_read
CREATE TABLE message_read (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, read_by INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_recipient
CREATE TABLE message_recipient (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, recipient INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_tag
CREATE TABLE message_tag (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, tag INTEGER REFERENCES tag (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: person
CREATE TABLE person (id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT NOT NULL, last_name TEXT NOT NULL);

-- Table: phone
CREATE TABLE phone (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL);

-- Table: reset_code
CREATE TABLE reset_code (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, timestamp TEXT);

-- Table: role
CREATE TABLE role (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);

-- Table: tag
CREATE TABLE tag (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT (1), sms_messages INTEGER DEFAULT (0) NOT NULL, admin_only_post INTEGER DEFAULT (0) NOT NULL, priority INTEGER DEFAULT (5));

-- Table: user
CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, created TEXT, verified TEXT, active INTEGER DEFAULT (0) NOT NULL);

-- Table: user_role
CREATE TABLE user_role (user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, role INTEGER REFERENCES role (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: user_tag
CREATE TABLE user_tag (user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, tag INTEGER REFERENCES tag (id) ON DELETE CASCADE ON UPDATE CASCADE);

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
