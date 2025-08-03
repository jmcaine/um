--
-- File generated with SQLiteStudio v3.4.4 on Sat Aug 2 20:41:32 2025
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: attachment
DROP TABLE IF EXISTS attachment;
CREATE TABLE attachment (id INTEGER PRIMARY KEY, filename TEXT NOT NULL, upload TEXT);

-- Table: edit_history
DROP TABLE IF EXISTS edit_history;
CREATE TABLE edit_history (id INTEGER PRIMARY KEY, message_id INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, content TEXT, datetime TEXT);

-- Table: email
DROP TABLE IF EXISTS email;
CREATE TABLE email (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL);

-- Table: id_key
DROP TABLE IF EXISTS id_key;
CREATE TABLE id_key (id INTEGER PRIMARY KEY AUTOINCREMENT, idid TEXT, key TEXT UNIQUE, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, timestamp TEXT NOT NULL, expires TEXT);

-- Table: message
DROP TABLE IF EXISTS message;
CREATE TABLE message (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT, author INTEGER REFERENCES user (id) ON DELETE RESTRICT ON UPDATE CASCADE, reply_to INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, reply_chain_patriarch INTEGER, sms INTEGER DEFAULT (0), created TEXT NOT NULL, sent TEXT, thread_updated TEXT, deleted TEXT, teaser TEXT, attachments INTEGER DEFAULT (0));

-- Table: message_attachment
DROP TABLE IF EXISTS message_attachment;
CREATE TABLE message_attachment (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, attachment INTEGER REFERENCES attachment (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_pin
DROP TABLE IF EXISTS message_pin;
CREATE TABLE message_pin (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, reminder TEXT);

-- Table: message_stashed
DROP TABLE IF EXISTS message_stashed;
CREATE TABLE message_stashed (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, stashed_by INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_tag
DROP TABLE IF EXISTS message_tag;
CREATE TABLE message_tag (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, tag INTEGER REFERENCES tag (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: person
DROP TABLE IF EXISTS person;
CREATE TABLE person (id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT NOT NULL, last_name TEXT NOT NULL);

-- Table: phone
DROP TABLE IF EXISTS phone;
CREATE TABLE phone (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL);

-- Table: resend_history
DROP TABLE IF EXISTS resend_history;
CREATE TABLE resend_history (id INTEGER PRIMARY KEY, message_id INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, tags TEXT, datetime TEXT);

-- Table: reset_code
DROP TABLE IF EXISTS reset_code;
CREATE TABLE reset_code (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, timestamp TEXT);

-- Table: role
DROP TABLE IF EXISTS role;
CREATE TABLE role (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);

-- Table: tag
DROP TABLE IF EXISTS tag;
CREATE TABLE tag (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, user REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, active INTEGER NOT NULL DEFAULT (1), sms_messages INTEGER DEFAULT (0) NOT NULL, admin_only_post INTEGER DEFAULT (0) NOT NULL);

-- Table: user
DROP TABLE IF EXISTS user;
CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, created TEXT, verified TEXT, active INTEGER DEFAULT (0) NOT NULL);

-- Table: user_role
DROP TABLE IF EXISTS user_role;
CREATE TABLE user_role (user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, role INTEGER REFERENCES role (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: user_tag
DROP TABLE IF EXISTS user_tag;
CREATE TABLE user_tag (user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, tag INTEGER REFERENCES tag (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Index: message_pin_unique
DROP INDEX IF EXISTS message_pin_unique;
CREATE UNIQUE INDEX message_pin_unique ON message_pin (message, user);

-- Index: message_read_unique
DROP INDEX IF EXISTS message_read_unique;
CREATE UNIQUE INDEX message_read_unique ON message_stashed (message, stashed_by);

-- Index: message_tag_unique
DROP INDEX IF EXISTS message_tag_unique;
CREATE UNIQUE INDEX message_tag_unique ON message_tag (message, tag);

-- Trigger: auto_reply_chain_patriarch
DROP TRIGGER IF EXISTS auto_reply_chain_patriarch;
CREATE TRIGGER auto_reply_chain_patriarch AFTER INSERT ON message FOR EACH ROW WHEN NEW.reply_chain_patriarch IS NULL BEGIN UPDATE message SET reply_chain_patriarch = NEW.id WHERE rowid = NEW.rowid; END;

-- Trigger: create_user_tag
DROP TRIGGER IF EXISTS create_user_tag;
CREATE TRIGGER create_user_tag AFTER INSERT ON tag WHEN NEW.user is not NULL  BEGIN insert into user_tag (user, tag) values (NEW.user, NEW.id); END;

-- Trigger: create_users_tag
DROP TRIGGER IF EXISTS create_users_tag;
CREATE TRIGGER create_users_tag AFTER INSERT ON user FOR EACH ROW BEGIN insert into tag (name, user, active) values (NEW.username, NEW.id, 1); END;

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
