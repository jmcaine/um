--
-- File generated with SQLiteStudio v3.4.4 on Fri Aug 22 10:09:25 2025
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: attachment
CREATE TABLE attachment (id INTEGER PRIMARY KEY, filename TEXT NOT NULL, upload TEXT);

-- Table: child_guardian
CREATE TABLE child_guardian (id INTEGER PRIMARY KEY, child INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE, guardian INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE, active INTEGER DEFAULT (1));

-- Table: edit_history
CREATE TABLE edit_history (id INTEGER PRIMARY KEY, message_id INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, content TEXT, datetime TEXT);

-- Table: email
CREATE TABLE email (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL);

-- Table: id_key
CREATE TABLE id_key (id INTEGER PRIMARY KEY AUTOINCREMENT, idid TEXT, key TEXT UNIQUE, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, login_timestamp TEXT NOT NULL, touch_timestamp TEXT, expires TEXT);

-- Table: marriage
CREATE TABLE marriage (id INTEGER PRIMARY KEY, husband INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE, wife INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message
CREATE TABLE message (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT, author INTEGER REFERENCES user (id) ON DELETE RESTRICT ON UPDATE CASCADE, reply_to INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, reply_chain_patriarch INTEGER, sms INTEGER DEFAULT (0), created TEXT NOT NULL, sent TEXT, thread_updated TEXT, deleted TEXT, teaser TEXT, attachments INTEGER DEFAULT (0));

-- Table: message_attachment
CREATE TABLE message_attachment (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, attachment INTEGER REFERENCES attachment (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_pin
CREATE TABLE message_pin (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, reminder TEXT);

-- Table: message_recipient_DEPRECATE
CREATE TABLE message_recipient_DEPRECATE (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, recipient INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_stashed
CREATE TABLE message_stashed (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, stashed_by INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: message_tag
CREATE TABLE message_tag (message INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, tag INTEGER REFERENCES tag (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: person
CREATE TABLE person (id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT NOT NULL, last_name TEXT NOT NULL, birth_date TEXT);

-- Table: phone
CREATE TABLE phone (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL);

-- Table: resend_history
CREATE TABLE resend_history (id INTEGER PRIMARY KEY, message_id INTEGER REFERENCES message (id) ON DELETE CASCADE ON UPDATE CASCADE, tags TEXT, datetime TEXT);

-- Table: reset_code
CREATE TABLE reset_code (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, timestamp TEXT);

-- Table: role
CREATE TABLE role (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);

-- Table: tag
CREATE TABLE tag (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, user REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, active INTEGER NOT NULL DEFAULT (1), sms_messages INTEGER DEFAULT (0) NOT NULL, admin_only_post INTEGER DEFAULT (0) NOT NULL);

-- Table: user
CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT, person INTEGER REFERENCES person (id) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, created TEXT, verified TEXT, active INTEGER DEFAULT (0) NOT NULL);

-- Table: user_role
CREATE TABLE user_role (user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, role INTEGER REFERENCES role (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Table: user_tag
CREATE TABLE user_tag (user INTEGER REFERENCES user (id) ON DELETE CASCADE ON UPDATE CASCADE, tag INTEGER REFERENCES tag (id) ON DELETE CASCADE ON UPDATE CASCADE);

-- Index: message_pin_unique
CREATE UNIQUE INDEX message_pin_unique ON message_pin (message, user);

-- Index: message_read_unique
CREATE UNIQUE INDEX message_read_unique ON message_stashed (message, stashed_by);

-- Index: message_tag_unique
CREATE UNIQUE INDEX message_tag_unique ON message_tag (message, tag);

-- Trigger: auto_reply_chain_patriarch
CREATE TRIGGER auto_reply_chain_patriarch AFTER INSERT ON message FOR EACH ROW WHEN NEW.reply_chain_patriarch IS NULL BEGIN UPDATE message SET reply_chain_patriarch = NEW.id WHERE rowid = NEW.rowid; END;

-- Trigger: create_user_tag
CREATE TRIGGER create_user_tag AFTER INSERT ON tag WHEN NEW.user is not NULL  BEGIN insert into user_tag (user, tag) values (NEW.user, NEW.id); END;

-- Trigger: create_users_tag
CREATE TRIGGER create_users_tag AFTER INSERT ON user FOR EACH ROW BEGIN insert into tag (name, user, active) values (NEW.username, NEW.id, 1); END;

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
