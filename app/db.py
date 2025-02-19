__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import re
import unittest

from copy import copy
from datetime import datetime, date, timedelta
from enum import Enum
from hashlib import sha256
from random import choices as random_choices
from string import ascii_uppercase
from uuid import uuid4

import aiosqlite
import bcrypt # cf https://security.stackexchange.com/questions/133239/what-is-the-specific-reason-to-prefer-bcrypt-or-pbkdf2-over-sha256-crypt-in-pass
from sqlite3 import PARSE_DECLTYPES, IntegrityError

from . import exception as ex
from .messages_const import *

l = logging.getLogger(__name__)

# Unit testing suite/setup ----------------------------------------------------
# Decorator motif, to allow test functions to be added right after the implementation functions, below
class Tests(unittest.TestCase):
	pass
def addtest():
	def decorator(func):
		setattr(Tests, func.__name__, func)
		return func
	return decorator
def unittests():
	unittest.main()
#Note the '__main__' at end of this file, which can be used to run from parent dir as:
#   python -m app.db

# -----------------------------------------------------------------------------

k_now_ = '%Y-%m-%d %H:%M:%SZ'
k_now = f"strftime('{k_now_}')" # could use datetime('now'), but that produces a result in UTC (what we want) but WITHOUT the 'Z' at the end; the problem with this is that using python datetime.fromisoformat() then interprets the datetime to be naive, rather than explicitly UTC, which results in the need to do a .replace(tzinfo = timezone.utc) in order to proceed with timezone shifts.  This use of sqlite's strftime(), where we explicitly append the Z, results in python calls to fromisoformat() returning UTC-specific datetime objects automatically.

async def connect(filename):
	result = await aiosqlite.connect(filename, isolation_level = None, detect_types = PARSE_DECLTYPES) # "isolation_level = None disables the Python wrapper's automatic handling of issuing BEGIN etc. for you. What's left is the underlying C library, which does do "autocommit" by default. That autocommit, however, is disabled when you do a BEGIN (b/c you're signaling a transaction with that statement" - from https://stackoverflow.com/questions/15856976/transactions-with-python-sqlite3 - thanks Thanatos
	def dict_factory(cursor, row):
		fields = [column[0] for column in cursor.description]
		return {key: value for key, value in zip(fields, row)}
	result.row_factory = dict_factory # aiosqlite.Row is more feature-full, but we often really want dict semantics, so, dict is better
	await result.execute('pragma journal_mode = wal') # see https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/ - since we're using async/await from a wsgi stack, this is appropriate
	await result.execute('pragma foreign_keys = ON')
	#await result.execute('pragma case_sensitive_like = true')
	return result

async def cursor(connection):
	return await connection.cursor()


async def test_fetch(dbc, pattern):
	r = await dbc.execute('select * from person where first_name like ?', (f'%{pattern}%',))
	return await r.fetchone()
	# alternately, one-liner, using _fetch1() util:
	#return await _fetch1(dbc, 'select * from person where first_name like ?', (f'%{pattern}%',))


async def begin(dbc):
	await dbc.execute('begin')

async def commit(dbc):
	await dbc.execute('commit')

async def rollback(dbc):
	await dbc.execute('rollback')


async def add_idid_key(dbc, idid, key):
	r = await dbc.execute(f'insert into id_key (idid, key, timestamp) values (?, ?, {k_now})', (idid, key))
	return r.lastrowid

async def get_user_by_id_key(dbc, idid, pub, hsh):
	r = await _fetch1(dbc, f'select key, user from id_key where idid = ?', (idid,))
	if not r:
		return None # not found; new idid-key pair is going to be needed (see add_idid_key())
	hsh2 = sha256(r['key'].encode("utf-8") + pub.encode("utf-8")).hexdigest()
	return r['user'] if hsh2 == hsh else None

async def add_person(dbc, first_name, last_name):
	r = await dbc.execute('insert into person (first_name, last_name) values (?, ?)', (first_name, last_name))
	return r.lastrowid

async def get_person(dbc, id, fields: str | None = None):
	if not fields:
		fields = '*'
	return await _fetch1(dbc, f'select {fields} from person where id = ?', (id,))

async def get_persons(dbc, like = None):
	where = ' where ' + like if like else ''
	return await _fetchall(dbc, 'select * from person ' + where + ' order by last_name')

async def set_person(dbc, id, first_name, last_name):
	return await _update1(dbc, 'update person set first_name = ?, last_name = ? where id = ?', (first_name, last_name, id))

async def add_email(dbc, person_id, email):
	return await _insert1(dbc, 'insert into email (email, person) values (?, ?)', (email, person_id))

async def get_email(dbc, email_id):
	return await _fetch1(dbc, 'select email from email where id = ?', (email_id,))

async def set_email(dbc, email_id, email):
	return await _update1(dbc, 'update email set email = ? where id = ?', (email, email_id))

async def get_person_emails(dbc, person_id):
	return await _fetchall(dbc, 'select email.id, email from email join person on email.person = person.id where person.id = ?', (person_id,))

async def add_phone(dbc, person_id, phone):
	return await _insert1(dbc, 'insert into phone (phone, person) values (?, ?)', (phone, person_id))

async def get_phone(dbc, phone_id):
	return await _fetch1(dbc, 'select phone from phone where id = ?', (phone_id,))

async def set_phone(dbc, phone_id, phone):
	return await _update1(dbc, 'update phone set phone = ? where id = ?', (phone, phone_id))

async def get_person_phones(dbc, person_id):
	return await _fetchall(dbc, 'select phone.id, phone from phone join person on phone.person = person.id where person.id = ?', (person_id,))


async def delete_person_detail(dbc, table, id):
	if table not in ('phone', 'email'):
		raise Exception(f'Unexpected table: {table} - not expecting to delete from this table with this function')
	#else:
	await dbc.execute(f'delete from {table} where id = ?', (id,))

async def username_exists(dbc, username):
	return await _fetch1(dbc, 'select 1 from user where username = ?', (username,)) != None

async def suggest_username(dbc, person):
	username = username_base = '%s.%s' % (person['first_name'].lower(), person['last_name'].lower())
	if await username_exists(dbc, username):
		# First pass (first_name.last_name) didn't work, so try appending numbers...
		for x in range(1, 100):
			username = username_base + str(x)
			if not await username_exists(dbc, username):
				break
			elif x >= 99:
				raise Exception('Unexpected - over a hundred users with that same name?!')
	return username

async def add_user(dbc, person_id, username):
	try:
		# Note that user is inactive until reset_user_password() completes, and activates (inactive until password is set, that is)
		r = await dbc.execute(f'insert into user (username, person, created, active) values (?, ?, {k_now}, 0)', (username, person_id,)) # NOTE: this TRIGGERs (SQL) to insert new tag (user's own tag) and that, in turn, TRIGGERs an insert into user_tag
		return r.lastrowid
	except IntegrityError:
		raise ex.AlreadyExists() # should be rare if username_exists() is used properly, but there's still a chance

async def update_user(dbc, id, fields, data):
	return await _update1(dbc, f"update user set {', '.join([f'{name} = ?' for name in fields])} where id = ?",
							  [data[name] for name in fields] + [id,])

async def get_users(dbc, active = True, persons = True, like = None, limit = 15):
	where = []
	args = ()
	join = ''
	join_fields = ''
	if active:
		where.append('active = 1')
	if like:
		like = f'%{like}%'
		likes = 'username like ?'
		args = (like,)
		if persons:
			likes = f'({likes} or person.first_name like ? or person.last_name like ?)'
			args = (like, like, like)
		where.append(likes)
	if persons:
		join = 'join person on person.id = user.person' 
		join_fields = ', person.id as person_id, first_name, last_name'
	where = 'where ' + " and ".join(where) if where else ''
	return await _fetchall(dbc, f'select user.id as user_id, username, created, verified, active {join_fields} from user {join} {where} order by username limit {limit}', args)

async def verify_new_user(dbc, username):
	return await _update1(dbc, f'update user set verified = {k_now} where username = ? and active = 1', (username,))

async def login(dbc, idid, username, password):
	if password: # password is required!
		r = await _fetch1(dbc, 'select id, password from user where username = ? and active = 1', (username,))
		if r and bcrypt.checkpw(password.encode(), r['password']):
			if await _login(dbc, idid, r['id']):
				return r['id']
	#else...
	return None

async def force_login(dbc, idid, user_id):
	# use, e.g., to auto-login user when user first creates self (don't ask for password again right after creation)
	r = await _fetch1(dbc, 'select id from user where id = ? and active = 1', (user_id,))
	if await _login(dbc, idid, r['id']):
		return r['id']
	#else...
	return None

async def authorized(dbc, uid, role):
	if uid == None:
		raise Exception()
	result = await _fetch1(dbc, 'select 1 from role join user_role on role.id = user_role.role join user on user.id = user_role.user where user.id = ? and role.name = ?', (uid, role))
	return bool(result)

async def authorized_roles(dbc, uid, roles):
	users_roles = await _fetchall(dbc, 'select role.name from role join user_role on role.id = user_role.role join user on user.id = user_role.user where user.id = ?', (uid,))
	return bool(set([role['name'] for role in users_roles]).intersection(roles))

async def logout(dbc, uid):
	if type(uid) == int:
		await dbc.execute('delete from id_key where user = ?', (uid,))

async def get_username(dbc, idid):
	r = await _fetch1(dbc, 'select username from user join id_key on user.id = id_key.user where id_key.idid = ?', (idid,))
	return r['username'] if r else None

async def get_user(dbc, id, fields: str | None = None):
	if not fields:
		fields = '*'
	return await _fetch1(dbc, f'select {fields} from user where id = ?', (id,))

async def get_user_id(dbc, username):
	r = await _fetch1(dbc, 'select id from user where username = ?', (username,))
	return r['id'] if r else None

async def get_user_id_by_email(dbc, email):
	r = await _fetch1(dbc, 'select id from user join person on user.person = person.id join email on person.id = email.person where email.email = ?', (email,))
	return r['id'] if r else None

async def get_user_emails(dbc, user_id):
	return await _fetchall(dbc, 'select email from email join person on email.person = person.id join user on person.id = user.person where user.id = ?', (user_id,))

async def generate_password_reset_code(dbc, user_id):
	code = ''.join(random_choices(ascii_uppercase, k=6))
	await dbc.execute(f'insert into reset_code (code, user, timestamp) values (?, ?, {k_now})', (code, user_id))
	return code

async def validate_reset_password_code(dbc, code, user_id):
	r = await _fetch1(dbc, 'select id from reset_code where code = ? and user = ?', (code, user_id))
	if r:
		await dbc.execute('delete from reset_code where id = ?', (r['id'],)) # done with it!
		return True
	return False

async def reset_user_password(dbc, uid, new_password):
	# note that this re-activates a de-activated user (see deactivate_user())
	return await _update1(dbc, 'update user set password = ?, active = 1 where id = ?', (_hashpw(new_password), uid,))

async def deactivate_user(dbc, username):
	# note: use reset_user_password() to re-activate
	await dbc.execute('update user set active = 0 where username = ?', [username,])


async def add_role(dbc, user_id, role):
	await add_roles(dbc, user_id, (role,))

async def add_roles(dbc, user_id, roles):
	all_roles = await _fetchall(dbc, ('select id, name from role', ()))
	roles = [(user_id, role['id']) for role in all_roles if role['name'] in roles]
	await add_role_ids(dbc, roles, None)

async def add_role_id(dbc, role_id, user_id = None):
	return add_role_ids(dbc, (role_id,), user_id)

async def add_role_ids(dbc, role_ids, user_id = None):
	'''
	`role_ids` can either be a list of 2-tuples, each as (user_id, role_id)
	(Note that user_id might be the same in many tuples, if you're adding many
	roles for the same user), or else role_ids can be a plain list (or tuple)
	of role_ids, and the list-of-tuples will be built for you using the provided
	`user_id`.
	'''
	if user_id:
		role_ids = [(user_id, role_id) for role_id in role_ids]
	#else role_ids is already a list of (user_id, role_id) tuples
	await dbc.executemany('insert into user_role (user, role) values (?, ?)', role_ids)


async def get_tags(dbc, active = True, like = None, get_subscribers = False, limit = 15):
	where, args = [], []
	if active:
		where.append('active = 1')
	_add_like(like, ('name',), where, args)
	where = 'where ' + ' and '.join(where) if where else ''
	count, join = '', ''
	if get_subscribers:
		count = ', count(user_tag.tag) as num_subscribers'
		join = 'left join user_tag on tag.id = user_tag.tag'
	limit = f'limit {limit}' if limit else ''
	result = await _fetchall(dbc, f'select tag.* {count} from tag {join} {where} group by tag.id order by name {limit}', args)
	return result if len(result) > 0 and result[0]['id'] != None else [] # convert weird "1-empty-record" result to an empty-list, instead; this happens in the left join case - a single record is returned with id=None and every other field = None except 'count', which = 0; we don't care about this case, so remove it.'

async def new_tag(dbc, name, active):
	return await _insert1(dbc, 'insert into tag (name, active) values (?, ?)', (name, active))

async def get_tag(dbc, id, fields: str | None = None):
	if not fields:
		fields = '*'
	return await _fetch1(dbc, f'select {fields} from tag where id = ?', (id,))

async def set_tag(dbc, id, name, active):
	return await _update1(dbc, 'update tag set name = ?, active = ? where id = ?', (name, active, id))


async def get_tag_users(dbc, tag_id, active = True, like = None, limit = 15, include_unsubscribed = False):
	where, args = ['user_tag.tag = ?',], [tag_id,]
	if active:
		where.append('active = 1')
	_add_like(like, ('username', 'first_name', 'last_name'), where, args)
	where1 = 'where ' + " and ".join(where) if where else ''
	fields = 'user.id, username, first_name, last_name'
	order = 'order by username'
	tag_users = await _fetchall(dbc, f'select {fields} from user join user_tag on user.id = user_tag.user join person on user.person = person.id {where1} {order} limit {limit}', args)
	if not include_unsubscribed:
		return tag_users
	#else:
	where2 = 'where ' + " and ".join(where[1:]) if where[1:] else ''
	all_users = await _fetchall(dbc, f'select {fields} from user join person on user.person = person.id {where2} {order}', args[1:]) # NOTE: must NOT 'limit' this fetch, as many of these may be weeded out in selection, below, and we have to have plenty to make a full rhs list!
	return tag_users, [r for r in all_users if r not in tag_users]


async def remove_user_from_tag(dbc, user_id, tag_id):
	return await dbc.execute(f'delete from user_tag where user = ? and tag = ?', (user_id, tag_id))

async def add_user_to_tag(dbc, user_id, tag_id):
	return await _insert1(dbc, 'insert into user_tag (user, tag) values (?, ?)', (user_id, tag_id))

async def get_user_tags(dbc, user_id, active = True, like = None, limit = 15, include_unsubscribed = False):
	where, args = ['user_tag.user = ?',], [user_id,]
	if active:
		where.append('active = 1')
	_add_like(like, ('name',), where, args)
	where = 'where ' + " and ".join(where) if where else ''
	limit = f'limit {limit}' if limit else ''
	user_tags = await _fetchall(dbc, f'select tag.* from tag join user_tag on tag.id = user_tag.tag {where} order by name {limit}', args)
	if not include_unsubscribed:
		return user_tags
	#else:
	all_tags = await get_tags(dbc, active = active, like = like, get_subscribers = False, limit = None) # NOTE: must NOT 'limit' this fetch, as many of these may be weeded out in selection, below, and we have to have plenty to make a full rhs list!
	return user_tags, [r for r in all_tags if r not in user_tags]

async def new_message(dbc, user_id, reply_to = None, reply_chain_patriarch = None):
	fields = ['message', 'author', 'created',]
	values = f'"", ?, {k_now}'
	args = [user_id,]
	if reply_to:
		fields.append('reply_to')
		values += ', ?'
		args.append(reply_to)
		assert(reply_chain_patriarch != None)
		fields.append('reply_chain_patriarch') # NOTE that a trigger auto-sets reply_chain_patriarch to id, after insert, for normal (non-reply) messages; thus, new messages (not replies), for which reply_chain_patriarch is left as None, above, will get a reply_chain_patriarch set to the newly inserted record's id (that is, itself); this is desirable.  All messages must have a reply_chain_patriarch, and new top-level messages' reply_chain_patriarch values should be their own ids
		values += ', ?'
		args.append(reply_chain_patriarch)
	else:
		fields.append('thread_updated') # a field for root messages, only; gets updated when replies chain on
		values += f', {k_now}'
	return await _insert1(dbc, f'insert into message ({", ".join(fields)}) values ({values})', args)

async def get_message_drafts(dbc, user_id, include_trashed = False, like = None,  limit = 15):
	where, args = ['sent is null and author = ?',], [user_id,]
	if not include_trashed:
		where.append('deleted is null')
	_add_like(like, ('message',), where, args)
	where = 'where ' + " and ".join(where)
	limit = f'limit {limit}' if limit else ''
	return await _fetchall(dbc, f'select id, teaser, created, deleted from message {where} order by created desc {limit}', args)

async def trash_message(dbc, message_id):
	return await _update1(dbc, f'update message set deleted = {k_now} where id = ?', (message_id,))

async def save_message(dbc, message_id, content):
	args = [content, make_teaser(content), message_id]
	more = ''
	if not content: # save the message, but as trashed ('deleted'), until content actually has something in it
		more = f'deleted = {k_now}, '
	else: # otherwise, even if it used to be deleted, if we're 'saving' it now, then untrash it!
		more = 'deleted = null, '
	return await _update1(dbc, f'update message set {more} message = ?, teaser = ? where id = ?', args)

Send_Message_Result = Enum('SMR', ('EmptyMessage', 'NoTags', 'Success'))
async def send_message(dbc, user_id, message_id) -> Send_Message_Result | dict:
	if not await _fetch1(dbc, f'select 1 from message_tag where message_tag.message = ?', (message_id,)):
		return Send_Message_Result.NoTags # can't send a message without tags (recipients)
	message = await get_message(dbc, user_id, message_id)
	content = message['message']
	if not content or content == '<div></div>':
		return Send_Message_Result.EmptyMessage # can't send empty message

	more = ''
	args = [message_id,]
	if not content.startswith('<div>'):
		message['message'] = content = '<div>' + content + '</div>' # make sure all messages are div-bracketed (one-liner messages don't come to us this way by default)
		more += 'message = ?, '
		args.insert(-1, content) # message_id has to stay "last" in arg list
	if message['deleted']:
		more += 'deleted = null, ' # un-trash the message if it's now being sent
	await _update1(dbc, f'update message set {more} sent = {k_now} where id = ?', args)
	message['sent'] = datetime.utcnow().strftime(k_now_) # kludge - parties using the return from this function (message) sometimes need that 'sent' field, but it's not actually set upon update, in the message object itself, and it seems needless to do a fetch; so, just set the date the same as it is in the DB... (NOTE: # yes, utcnow() generates a tz-unaware datetime and that's exactly right; utcnow() only has to return the current utc time, but without tz info is FINE!)
	if message['reply_chain_patriarch'] != message['id']:
		# Need to update reply_chain_patriarch's thread_updated field, too:
		await _update1(dbc, f'update message set thread_updated = {k_now} where id = ?', (message['reply_chain_patriarch'],))
	return message

def make_teaser(content):
	return strip_tags(content[:50])[:20] # [:50] to just operate on opening portion of content, but then, once stripped of tags, whittle down to [:20]; if only one of these was used, "taggy" content would be rather over-shrunk or under-taggy content would be rather under-shrunk

def strip_tags(content):
	return re.sub('<.*', '', re.sub('<[^<]+?>', '', re.sub('</[^<]+?>', '...', content)))

@addtest()
def test_strip_tags(self):
	t = lambda to_strip, result: self.assertEqual(strip_tags(to_strip), result)
	t('hello', 'hello')
	t('<div>hello</di', 'hello')
	t('<div>hello</div>', 'hello...')
	t('<div>hello</div><di', 'hello...')
	t('<div>hello</div><div>', 'hello...')
	t('<div>hello</div><div>oh', 'hello...oh')


_mega_message_select = 'select message.id, message.message, message.reply_chain_patriarch, message.teaser, parent.teaser as parent_teaser, sender.username as sender, sender.id as sender_id, message.reply_to, message.sent as sent, message.deleted, patriarch.thread_updated as thread_updated, GROUP_CONCAT(DISTINCT tag.name) as tags, (select 1 from message_pin where user = ? and message = message.id) as pinned, (select 1 from message_read where read_by = ? and message = message.id) as archived from message join user as sender on message.author = sender.id join message as patriarch on message.reply_chain_patriarch = patriarch.id left join message as parent on message.reply_to = parent.id' # NOTE that GROUP_CONCAT(DISTINCT tag.name) is the only way to get singles (not multiple copies) of group names - using GROUP_CONCAT(tag.name, ', ') would be nice, since the default doesn't place a space after the comma, but providing the ', ' argument only works if you do NOT use DISTINCT, which isn't an option for us.


_message_tag_join = 'left join message_tag on message.id = message_tag.message left join tag on message_tag.tag = tag.id'

_user_tag_join = 'left join user_tag on tag.id = user_tag.tag'

async def get_message(dbc, user_id, message_id):
	return await _fetch1(dbc, f'{_mega_message_select} {_message_tag_join} where message.id = ?', (user_id, user_id, message_id,))

async def get_messages(dbc, user_id, include_trashed = False, deep = False, like = None, filt = Filter.unarchived, skip = 0, limit = 15):
	where = []
	args = [user_id, user_id,] # first two user_ids are for sub-selects in _mega_message_select; third is for our 'where user.id = ?' (see line above)
	if not include_trashed:
		where.append('message.deleted is null')
	if like:
		if deep:
			_add_like(like, ('message.message', 'tag.name'), where, args)
		else:
			_add_like(like, ('SUBSTR(message.message, 0, 30)', 'tag.name'), where, args)
	match filt:
		case Filter.unarchived:
			where.append('message.id not in (select message from message_read where read_by = ?)')
			args.append(user_id)
		case Filter.archived:
			where.append('message.id in (select message from message_read where read_by = ?)')
			args.append(user_id)
		case Filter.pinned:
			where.append(f'message.id in (select message from message_pin where user = ?)')
			args.append(user_id)
		case Filter.day:
			where.append(f'message.sent >= "{(datetime.utcnow() - timedelta(days=1)).isoformat()}Z"') # yes, utcnow() generates a tz-unaware datetime and that's exactly right; utcnow() only has to return the current utc time, but without tz info is FINE!
		case Filter.this_week: # we'll interpret as "7 days back"
			where.append(f'message.sent >= "{(datetime.combine(datetime.utcnow().date(), datetime.min.time()) - timedelta(days=7)).isoformat()}Z"') # yes, utcnow() generates a tz-unaware datetime and that's exactly right; utcnow() only has to return the current utc time, but without tz info is FINE!
	where.append('((message.sent is not null and user_tag.user = ?) or (message.author = ? and (message.reply_to is not null or message.sent is not null)))')
	args += [user_id, user_id]
	where = 'where ' + ' and '.join(where)
	group_by = 'group by message.id' # query produces many rows for a message, one per tag for that message; this is required to consolidate to one row, but allows GROUP_CONCAT() to properly build the list of tags that match
	asc_order = f'order by thread_updated asc, sent asc nulls last' # "nulls last" is for unsent messages, which don't yet have 'sent' set (so, it's null) - those should be "lowest" in the list
	query = f'{_mega_message_select} {_message_tag_join} {_user_tag_join} {where} {group_by}'
	if skip < 0: # usually indicating "backing up", but -1 indicates "last page" / "latest stuff"
		this_skip = 0 if skip == -1 else skip # skip 0 if it's the flag "-1"; else skip `skip` (negative numbers will result proper 
		desc_order = f'order by thread_updated desc, sent desc'
		query = f'select * from ({query} {desc_order} limit {-this_skip}, {limit}) {asc_order} limit {limit}' # subquery on desc_order to get the LIMIT right, then properly asc_order that final resultset
	else:
		query = f'{query} {asc_order} limit {skip}, {limit}'
	#l.debug(f'get_messages query: {query}    ... args: {args}')
	# SEE: giant_sql_laid_out.txt to show/study the above laid out for straight comprehension.
	return await _fetchall(dbc, query, args)

async def delivery_recipient(dbc, user_id, message_id):
	return await _fetch1(dbc, f'select 1 from message {_message_tag_join} {_user_tag_join} where (user_tag.user = ? or message.author = ?) and message.id = ?', (user_id, user_id, message_id))

async def get_message_tags(dbc, message_id, active = True, like = None, limit = 15, include_others = False):
	# TODO: this is very similar to get_user_tags - consider consolidating?
	where, args = ['message_tag.message = ?',], [message_id,]
	if active:
		where.append('active = 1')
	_add_like(like, ('name',), where, args)
	where = 'where ' + " and ".join(where) if where else ''
	limit = f'limit {limit}' if limit else ''
	message_tags = await _fetchall(dbc, f'select tag.* from tag join message_tag on tag.id = message_tag.tag {where} order by name {limit}', args)
	if not include_others:
		return message_tags
	#else:
	all_tags = await get_tags(dbc, active = active, like = like, get_subscribers = False, limit = None) # NOTE: must NOT 'limit' this fetch, as many of these may be weeded out in selection, below, and we have to have plenty to make a full rhs list!
	return message_tags, [r for r in all_tags if r not in message_tags]

async def remove_tag_from_message(dbc, message_id, tag_id):
	return await dbc.execute(f'delete from message_tag where message = ? and tag = ?', (message_id, tag_id))

async def add_tag_to_message(dbc, message_id, tag_id):
	return await _insert1(dbc, 'insert into message_tag (message, tag) values (?, ?)', (message_id, tag_id))

async def delete_draft(dbc, message_id):
	return await _update1(dbc, f'update message set deleted = {k_now} where id = ?', (message_id,))


async def get_author_tag(dbc, message_id):
	return await _fetch1(dbc, 'select tag.* from tag join message on message.author = tag.user where message.id = ?', (message_id,))

async def set_reply_message_tags(dbc, message_id):
	message = await _fetch1(dbc, 'select author, reply_to from message where message.id = ?', (message_id,))
	tags = await _fetchall(dbc, 'select tag as tag_id from message_tag join tag on tag_id = tag.id where message_tag.message = ? and (tag.user is null or tag.user != ?)', (message['reply_to'], message['author'],)) # get all tags EXCEPT the tag that corresponds to the reply author - we don't want to inherit that tag, or we'll just be sending the reply to the reply's own author ("self")!
	if not tags:
		# this means the only tag on the parent message was the tag coorseponding to this very (reply) author; in this case, we want the tag to correspond to the PARENT author, not ourself! (that is, we want this to become a directy reply to the parent, even though the replier apparently selected "all", as if there were other possible recipients) TODO: even though this code should remain as a safeguard, we should only present the user with the "1" vs. "all" option when there is indeed a difference between the two!
		return await _insert1(dbc, 'insert into message_tag (message, tag) select ?, tag.id from tag join message on message.author = tag.user where message.id = ?', (message_id, message['reply_to']))
	else:
		# this is the "normal" case, in which the parent has one or more tags (other than the reply's author), and we're to inherit them:
		data = [(message_id, i['tag_id']) for i in tags]
		return await dbc.executemany('insert into message_tag (message, tag) values (?, ?)', data)

async def archive_message(dbc, message_id, user_id):
	return await _insert1(dbc, 'insert into message_read (message, read_by) values (?, ?)', (message_id, user_id))

async def unarchive_message(dbc, message_id, user_id):
	return await dbc.execute('delete from message_read where message = ? and read_by = ?', (message_id, user_id))

async def pin_message(dbc, message_id, user_id):
	return await _insert1(dbc, 'insert into message_pin (message, user) values (?, ?)', (message_id, user_id))

async def unpin_message(dbc, message_id, user_id):
	return await dbc.execute('delete from message_pin where message = ? and user = ?', (message_id, user_id))

async def get_parent_message(dbc, message_id):
	return await _fetch1(dbc, 'select message.* from message as parent join message as child on parent.id = child.reply_to where child.id = ?', (message_id,))

async def get_patriarch_message_id(dbc, message_id):
	r = await _fetch1(dbc, 'select patriarch.id from message as patriarch join message as child on patriarch.id = child.reply_chain_patriarch where child.id = ?', (message_id,))
	return r['id'] if r else None
	

# Utils -----------------------------------------------------------------------

async def _fetch1(dbc, sql, args = None):
	#DO?: sql += ' limit 1' -- should be unnecessary (no efficiency gain) based on how execute() and fetchone() work
	r = await dbc.execute(sql, args)
	return await r.fetchone()

async def _fetchall(dbc, sql, args = None):
	r = await dbc.execute(sql, args)
	return await r.fetchall()

async def _update1(dbc, sql, args):
	r = await dbc.execute(sql, args)
	assert(r.rowcount < 2) # 0 or 1
	return (r.rowcount == 1) # True if the update occurred

async def _insert1(dbc, sql, args):
	r = await dbc.execute(sql, args)
	return r.lastrowid

def _hashpw(password):
	return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

async def _login(dbc, idid, user_id):
	return await _update1(dbc, 'update id_key set user = ? where idid = ?', (user_id, idid))

def _add_like(like, fields, where, args):
	if like:
		likes = ' or '.join([f'{field} like ?' for field in fields])
		where.append(f'({likes})')
		args.extend([f'%{like}%'] * len(fields))

if __name__ == '__main__':
	unittests()
