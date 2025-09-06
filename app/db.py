__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import random
import re
import string
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
	# pip install bcrypt
from sqlite3 import PARSE_DECLTYPES, IntegrityError, Error as SQL_Error

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

k_default_resultset_limit = 10

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
	r = await dbc.execute(f'insert into id_key (idid, key, login_timestamp) values (?, ?, {k_now})', (idid, key))
	return r.lastrowid

async def get_user_by_id_key(dbc, idid, pub, hsh):
	r = await _fetch1(dbc, f'select key, user from id_key join user on user.id = id_key.user where id_key.idid = ? and user.active = 1', (idid,))
	if not r:
		return None # not found (id-key doesn't exist or user is (now) inactive); new idid-key pair is going to be needed (see add_idid_key())  NOTE: inactive user is an exception, and a potential point of confusion, but essential to security; must be able to deactivate a user, as an admin, for example, to disable login/auto-login and activity
	await _update1(dbc, f'update id_key set touch_timestamp = {k_now} where idid = ?', (idid,))
	hsh2 = sha256(r['key'].encode("utf-8") + pub.encode("utf-8")).hexdigest()
	return r['user'] if hsh2 == hsh else None

async def add_person(dbc, first_name, last_name):
	r = await dbc.execute('insert into person (first_name, last_name) values (?, ?)', (first_name, last_name))
	return r.lastrowid

async def get_person(dbc, id, fields: str | None = None):
	if not fields:
		fields = '*'
	return await _fetch1(dbc, f'select {fields} from person where id = ?', (id,))

async def get_user_person(dbc, uid):
	return await _fetch1(dbc, 'select person.* from person join user on user.person = person.id where user.id = ?', (uid,))

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


async def add_child(dbc, guardian_person_id, first_name, last_name, birth_date):
	try:
		await begin(dbc)
		id = await _insert1(dbc, 'insert into person (first_name, last_name, birth_date) values (?, ?, ?)', (first_name, last_name, birth_date))
		await _insert1(dbc, 'insert into child_guardian (child, guardian) values (?, ?)', (id, guardian_person_id))
		await commit(dbc)
		return id
	except:
		await rollback(dbc)
		raise

async def get_child(dbc, child_person_id, include_is_user = False):
	select = 'select person.id, first_name, last_name, birth_date'
	args = [child_person_id]
	if include_is_user:
		select += ', (select 1 from user where user.person = ? and user.active = 1)'
		args.append(child_person_id)
	select += ' as is_user from person where id = ?'
	return await _fetch1(dbc, select, args)

async def set_child(dbc, child_person_id, first_name, last_name, birth_date):
	return await _update1(dbc, 'update person set first_name = ?, last_name = ?, birth_date = ? where id = ?', (first_name, last_name, birth_date, child_person_id))

async def get_person_children(dbc, guardian_person_id):
	return await _fetchall(dbc, "select person.id, first_name, last_name, birth_date, case when user.active = 1 then username else '' end as username from person join child_guardian on person.id = child_guardian.child left join user on user.person = person.id where child_guardian.guardian = ?", (guardian_person_id,))

async def get_user_children_ids(dbc, user_id):
	return await _fetchall(dbc, 'select person.id from person join child_guardian on person.id = child_guardian.child join user on user.person = child_guardian.guardian where user.id  = ?', (user_id,))

async def orphan_child(dbc, child_person_id, guardian_person_id): # i.e., "delete" child from family (but don't delete the base child record)
	await dbc.execute(f'delete from child_guardian where child = ? and guardian = ?', (child_person_id, guardian_person_id))


async def get_person_spouse(dbc, person_id):
	return await _fetch1(dbc, 'select first_name, last_name from person !!!')

async def is_a_guardian(dbc, person_id):
	return True if await _fetch1(dbc, 'select 1 from child_guardian where guardian = ? limit 1', (person_id,)) else False

async def is_guardian_of(dbc, uid, child_username):
	return True if await _fetch1(dbc, '''select 1 from user as guardian_user
		join child_guardian on guardian_user.person = child_guardian.guardian
		join user as child_user on child_user.person = child_guardian.child
		where guardian_user.id = ? and child_user.username = ? limit 1''', (uid, child_username)) else False

async def _get_guardians(dbc, person_id):
	return await _fetchall(dbc, 'select g.* from child_guardian join person as g on child_guardian.guardian = g.id join person as c on child_guardian.child = c.id where c.id = ?', (person_id,))




async def delete_person_detail(dbc, table, id):
	if table not in ('phone', 'email'):
		raise Exception(f'Unexpected table: {table} - not expecting to delete from this table with this function')
	#else:
	await dbc.execute(f'delete from {table} where id = ?', (id,))

async def username_exists(dbc, username):
	return await _fetch1(dbc, 'select 1 from user where username = ?', (username,)) != None

async def suggest_username(dbc, person):
	username = username_base = '%s.%s' % (person['first_name'].lower().replace(' ', ''), person['last_name'].lower().replace(' ', ''))
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

async def get_users(dbc, active = True, persons = True, like = None, limit = k_default_resultset_limit):
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
	limit = f'limit {limit}' if limit else ''
	return await _fetchall(dbc, f'select user.id as user_id, username, created, verified, active {join_fields} from user {join} {where} order by username {limit}', args)

async def verify_new_user(dbc, username):
	return await _update1(dbc, f'update user set verified = {k_now} where username = ? and active = 1', (username,))

async def login(dbc, idid, username, password):
	if password: # password is required!
		r = await _fetch1(dbc, 'select id, password from user where username = ? COLLATE NOCASE and active = 1', (username,))
		id = r['id'] if r else None
		if not id:
			# Try email:
			id = await get_user_id_by_email(dbc, username)
			r = await _fetch1(dbc, 'select password from user where id = ? and active = 1', (id,))
		if r and bcrypt.checkpw(password.encode(), r['password']):
			if await _login(dbc, idid, id):
				return id
	#else...
	return None

async def force_login(dbc, idid, user_id):
	# use, e.g., to auto-login user when user first creates self (don't ask for password again right after creation)
	if await _login(dbc, idid, user_id):
		return user_id
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
	r = await _fetch1(dbc, 'select user.id from user join person on user.person = person.id join email on person.id = email.person where email.email = ?', (email,))
	return r['id'] if r else None

async def get_user_emails(dbc, user_id):
	return await _fetchall(dbc, 'select email from email join person on email.person = person.id join user on person.id = user.person where user.id = ?', (user_id,))

k_reset_code_length = 6
async def generate_password_reset_code(dbc, user_id):
	code = ''.join(random_choices(ascii_uppercase, k = k_reset_code_length))
	await dbc.execute(f'insert into reset_code (code, user, timestamp) values (?, ?, {k_now})', (code, user_id))
	return code

async def validate_reset_password_code(dbc, code, user_id):
	r = await _fetch1(dbc, 'select id from reset_code where code = ? and user = ?', (code, user_id))
	if r:
		await dbc.execute('delete from reset_code where id = ?', (r['id'],)) # done with it!
		return True
	return False

async def get_user_id_by_reset_code(dbc, code):
	# note that user need not be active at this point... active will be set to 1 in reset_user_password()
	r = await _fetch1(dbc, 'select user from reset_code where code = ?', (code,))
	if r:
		return r['user']
	return None

async def reset_user_password(dbc, uid, new_password):
	# note that this re-activates a de-activated user (see deactivate_user())
	# TODO: consider: this is a potential loophole: if a user is marked "not active" (user.active = 0), then a password-reset cycle, initiated by the user, will result in a reset_user_password() call that will re-activate user
	return await _update1(dbc, 'update user set password = ?, active = 1 where id = ?', (_hashpw(new_password), uid,))

async def deactivate_user(dbc, username):
	# note: use reset_user_password() to re-activate
	user_id = '(select id from user where user.username = ?)'
	try:
		await begin(dbc)
		await dbc.execute(f'delete from id_key where user = {user_id}', (username,))
		await _update1(dbc, 'update user set active = 0 where username = ?', (username,))
		await _update1(dbc, f'update tag set active = 0 where user = {user_id}', (username,))
		await commit(dbc)
		return True # superfluous, at best (?!)
	except SQL_Error:
		await rollback(dbc)
		raise

async def set_child_password(dbc, child_person_id, password):
	# Note: returns positively in THREE cases: if the user was deactivated ('' password), if the user's password was reset, or if the user was created (not already existing for child_person_id); returns False in any other case.
	r = await _fetch1(dbc, 'select id, username from user where person = ?', (child_person_id,))
	if r:
		# user already exists, either set `password` or, if `password` is null, deactivate user:
		if not password:
			return await deactivate_user(dbc, r['username']) # should always succeed
		else:
			return await reset_user_password(dbc, r['id'], password)
	else:
		# user doesn't yet exist; create, as long as password is real
		if password:
			child = await get_person(dbc, child_person_id)
			uid = await add_user(dbc, child_person_id, await suggest_username(dbc, child))
			if uid:
				return await reset_user_password(dbc, uid, password) # TODO?: this is second DB xaction; possibly commit/rollback?
	return False

async def get_other_logins(dbc, uid):
	person = await get_user_person(dbc, uid)
	pid = person['id']
	guardian_pids = [r['guardian'] for r in (await _fetchall(dbc, 'select guardian from child_guardian where child = ?', (pid,)))]
	if guardian_pids: # then uid is a child
		children_pids = [r['child'] for r in (await _fetchall(dbc, 'select child from child_guardian where guardian in ({seq})'.format(seq = ','.join(['?']*len(guardian_pids))), guardian_pids))]
	else: # uid is a guardian
		children_pids = [r['child'] for r in (await _fetchall(dbc, 'select child from child_guardian where guardian = ?', (pid,)))]
	all_pids = guardian_pids + children_pids
	try: all_pids.remove(pid)
	except ValueError: pass
	r = await _fetchall(dbc, 'select id, username, require_password_on_switch, color from user where active = 1 and person in ({seq})'.format(seq = ','.join(['?']*len(all_pids))), all_pids)
	return r

async def get_user_color(dbc, username):
	r = await _fetch1(dbc, 'select color from user where username = ?', (username,))
	return r['color'] if (r and r['color']) else '#ffffff'


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


async def get_tags(dbc, active = True, like = None, get_subscriber_count = False, limit = k_default_resultset_limit):
	where, args = ['tag.user is null'], [] # 'user is null' to weed out the pseudo-groups connected to every user
	if active:
		where.append('active = 1')
	_add_like(like, ('name',), where, args)
	where = 'where ' + ' and '.join(where) if where else ''
	count, join = '', ''
	if get_subscriber_count:
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


async def get_tag_users(dbc, tag_id, limit, active = True, like = None, include_unsubscribed = False):
	return await _get_xaa(dbc,
		select = 'user.id, user.username from user', # , person.first_name, person.last_name (before 'from user')
		where = 'user_tag.tag = ?',
		where_arg = tag_id,
		active = active,
		like = like,
		likes = ('username', ), # 'first_name', 'last_name'
		join = 'user_tag on user.id = user_tag.user', # join person on user.person = person.id
		order = 'username',
		limit = limit,
		include_others = include_unsubscribed,
		non_join = 'user_tag where user.id = user_tag.user and user_tag.tag = ?',
	)


async def remove_user_from_tag(dbc, user_id, tag_id):
	return await dbc.execute(f'delete from user_tag where user = ? and tag = ?', (user_id, tag_id))

async def add_user_to_tag(dbc, user_id, tag_id):
	return await _insert1(dbc, 'insert into user_tag (user, tag) values (?, ?)', (user_id, tag_id))

async def get_user_tags(dbc, user_id, limit, active = True, like = None, include_unsubscribed = False):
	return await _get_xaa(dbc,
		select = 'tag.* from tag',
		where = 'user_tag.user = ?',
		where_arg = user_id,
		active = active,
		like = like,
		likes = ('name',),
		join = 'user_tag on tag.id = user_tag.tag',
		order = 'name',
		limit = limit,
		include_others = include_unsubscribed,
		non_join = 'user_tag where tag.id = user_tag.tag and user_tag.user = ?',
	)

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

async def get_message_drafts(dbc, user_id, include_trashed = False, like = None,  limit = k_default_resultset_limit):
	where, args = ['sent is null and author = ?',], [user_id,]
	if not include_trashed:
		where.append('deleted is null')
	_add_like(like, ('message',), where, args)
	where = 'where ' + " and ".join(where)
	limit = f'limit {limit}' if limit else ''
	return await _fetchall(dbc, f'select id, teaser, created, deleted from message {where} order by created desc {limit}', args)

async def save_message(dbc, message_id, content):
	args = [content, make_teaser(content), message_id]
	more = ''
	#TODO: NOT LIKE THIS!  don't mark it as 'deleted', but merely as a draft....  Actually, this may be already done, these days!
	if not content: # save the message, but as trashed ('deleted'), until content actually has something in it
		more = f'deleted = {k_now}, '
	else: # otherwise, even if it used to be deleted, if we're 'saving' it now, then untrash it!
		more = 'deleted = null, '
	return await _update1(dbc, f'update message set {more} message = ?, teaser = ? where id = ?', args)

Send_Message_Result = Enum('SMR', ('EmptyMessage', 'NoTags', 'Success'))
async def send_message(dbc, user_id, message_id) -> Send_Message_Result | dict:
	if not await has_tags(dbc, message_id):
		return Send_Message_Result.NoTags # can't send a message without tags (recipients)
	message = await get_message(dbc, user_id, message_id)
	content = message['message']
	if not content or content == '<div></div>' or content == '<br>':
		return Send_Message_Result.EmptyMessage # can't send empty message

	sets = []
	args = [message_id,]
	if not content.startswith('<div>'):
		message['message'] = content = '<div>' + content + '</div>' # make sure all messages are div-bracketed (one-liner messages don't come to us this way by default)
		sets.append('message = ?')
		args.insert(-1, content) # message_id has to stay "last" in arg list
	if message['deleted']:
		sets.append('deleted = null') # un-delete the message if it's now being sent
	if not message['sent']: # don't mess with an already set 'sent' value (i.e., message being edited, after sent)
		sets.append(f'sent = {k_now}')
		message['sent'] = datetime.utcnow().strftime(k_now_) # kludge - parties using the return from this function (the message) sometimes need that 'sent' field, but it's not actually set upon update, in the message object itself, and it seems needless to do a fetch; so, just set the date the same as it is in the DB... (NOTE: # yes, utcnow() generates a tz-unaware datetime and that's exactly right; utcnow() only has to return the current utc time, but without tz info is FINE!)
	else:
		message['edited'] = 1 # kludge - parties using the return from this function (the message) need that 'edited' field, and, in fact, need it to be meaningful for a wide audience, such as: in order to "deliver" (inject) the message to all live clients, in real time.  This value for message['edited'] (1) makes the most sense if the message was ALREADY ['sent'], before, and yet here we are in send_message (obviously "re-sending", e.g., an edit). In another arc, e.g., when a user loads new messages, this ['edited'] value gets set to 1, for that user alone, fetching the message(s), when it lands in his "unstashed" (which only happens if it was previously in his "stashed").
	if message['reply_chain_patriarch'] == message['id']: # if this is the patriarch of the thread, update its thread_updated
		sets.append(f'thread_updated = {k_now}')
	if sets: # only continue if there's actually something to set(); else no-op
		sets = 'set ' + ', '.join(sets)
		try:
			await begin(dbc)
			await _update1(dbc, f'update message {sets} where id = ?', args)
			await dbc.execute('insert into message_unstashed (message, unstashed_for) select message, stashed_by from message_stashed where message_stashed.message = ?', (message_id,))
			await dbc.execute('delete from message_stashed where message = ?', (message_id,))
			if message['reply_chain_patriarch'] != message['id']:
				# Need to update reply_chain_patriarch's thread_updated field, too:
				await _update1(dbc, f'update message set thread_updated = {k_now} where id = ?', (message['reply_chain_patriarch'],))
			await commit(dbc)
		except SQL_Error:
			await rollback(dbc)
			raise

	return message

async def has_tags(dbc, message_id):
	result = await _fetch1(dbc, f'select 1 from message_tag where message_tag.message = ?', (message_id,))
	return True if await _fetch1(dbc, f'select 1 from message_tag where message_tag.message = ?', (message_id,)) else False

def make_teaser(content):
	return strip_tags(content[:100])[:50] # [:50] to just operate on opening portion of content, but then, once stripped of tags, whittle down to [:20]; if only one of these was used, "taggy" content would be rather over-shrunk or under-taggy content would be rather under-shrunk

def strip_tags(content):
	return re.sub(r'&nbsp;', '', re.sub(r'<.*', '', re.sub(r'<[^<]+?>', '', re.sub(r'</[^<]+?>', '...', content))))

@addtest()
def test_strip_tags(self):
	t = lambda to_strip, result: self.assertEqual(strip_tags(to_strip), result)
	t('hello', 'hello')
	t('<div>hello</di', 'hello')
	t('<div>hello</div>', 'hello...')
	t('<div>hello</div><di', 'hello...')
	t('<div>hello</div><div>', 'hello...')
	t('<div>hello</div><div>oh', 'hello...oh')

_mega_message_select = lambda message: f"select message.id, {message}, message.deleted, GROUP_CONCAT(DISTINCT attachment.filename) as attachments, message.reply_chain_patriarch, message.teaser, parent.teaser as parent_teaser, sender.username as sender, sender.id as sender_id, message.reply_to, message.sent as sent, message.deleted, patriarch.thread_updated as thread_updated, GROUP_CONCAT(DISTINCT tag.name) as tags, (select 1 from message_pin where user = ? and message = message.id) as pinned, (select 1 from message_peg where message = message.id) as pegged,  (select 1 from message_stashed where stashed_by = ? and message = message.id) as stashed, (select 1 from message_unstashed where unstashed_for = ? and message = message.id) as edited  from message join user as sender on message.author = sender.id join message as patriarch on message.reply_chain_patriarch = patriarch.id left join message as parent on message.reply_to = parent.id left join message_attachment on message.id = message_attachment.message left join attachment on attachment.id = message_attachment.attachment" # NOTE that GROUP_CONCAT(DISTINCT tag.name) is the only way to get singles (not multiple copies) of group names - using GROUP_CONCAT(tag.name, ', ') would be nice, since the default doesn't place a space after the comma, but providing the ', ' argument only works if you do NOT use DISTINCT, which isn't an option for us.  Similar goes for attachment.filename


_message_tag_join = 'left join message_tag on message.id = message_tag.message left join tag on message_tag.tag = tag.id'

_user_tag_join = 'left join user_tag on tag.id = user_tag.tag'

async def get_message(dbc, user_id, message_id):
	return await _fetch1(dbc, f'{_mega_message_select("message.message")} {_message_tag_join} where message.id = ?', (user_id, user_id, user_id, message_id,))

async def get_whole_thread(dbc, user_id, patriarch_id):
	where = ['((message.sent is not null and user_tag.user = ?) or (message.author = ? and (message.reply_to is not null or message.sent is not null)))', 'message.reply_chain_patriarch = ?']
	args = [user_id, user_id, user_id, user_id, user_id, patriarch_id] # first three user_ids are for sub-selects in _mega_message_select; third is for our 'where user.id = ?' (see line above)
	where = 'where ' + ' and '.join(where)
	group_by = 'group by message.id' # query produces many rows for a message, one per tag for that message; this is required to consolidate to one row, but allows GROUP_CONCAT() to properly build the list of tags that match
	asc_order = f'order by thread_updated asc, sent asc nulls last' # "nulls last" is for unsent messages, which don't yet have 'sent' set (so, it's null) - those should be "lowest" in the list
	query = f'{_mega_message_select("message.message")} {_message_tag_join} {_user_tag_join} {where} {group_by} {asc_order}'
	#l.debug(f'get_messages query: {query}    ... args: {args}')
	# SEE: giant_sql_laid_out.txt to show/study the above laid out for straight comprehension.
	return await _fetchall(dbc, query, args)


async def get_messages(dbc, user_id, include_trashed = False, deep = False, like = None, filt = Filter.new, ignore = None, limit = k_default_resultset_limit):
	where = ['message.message != ""' ]
	args = [user_id, user_id, user_id, ] # three user_ids are for sub-selects in _mega_message_select
	if not include_trashed:
		where.append('message.deleted is null')
	if like:
		if deep:
			_add_like(like, ('message.message', 'tag.name', 'sender.username'), where, args)
		else:
			_add_like(like, ('message.teaser', 'tag.name', 'sender.username'), where, args) # SUBSTR(message.message, 0, 30) would get us arbitrarily deep, rather than relying on teaser, but would be more computationally expensive
	match filt:
		case Filter.new:
			where.append('message.id not in (select message from message_stashed where stashed_by = ?)')
			args.append(user_id)
		case Filter.pinned:
			where.append(f'message.id in (select message from message_pin where user = ?)')
			args.append(user_id)
		case Filter.pegged:
			where.append(f'message.id in (select message from message_peg)')
		case Filter.day:
			where.append(f'message.sent >= "{(datetime.utcnow() - timedelta(days=1)).isoformat()}Z"') # yes, utcnow() generates a tz-unaware datetime and that's exactly right; utcnow() only has to return the current utc time, but without tz info is FINE!
		case Filter.this_week: # we'll interpret as "7 days back"
			where.append(f'message.sent >= "{(datetime.combine(datetime.utcnow().date(), datetime.min.time()) - timedelta(days=7)).isoformat()}Z"') # yes, utcnow() generates a tz-unaware datetime and that's exactly right; utcnow() only has to return the current utc time, but without tz info is FINE!
	if ignore:
		where.append('message.id not in ({seq})'.format(seq = ','.join(['?']*len(ignore))))
		args.extend(ignore)

	where.append('((message.sent is not null and user_tag.user = ?) or (message.author = ? and (message.reply_to is not null or message.sent is not null)))')
	args += [user_id, user_id]
	where = 'where ' + ' and '.join(where)
	group_by = 'group by message.id' # query produces many rows for a message, one per tag for that message; this is required to consolidate to one row, but allows GROUP_CONCAT() to properly build the list of tags that match
	asc_order = f'order by thread_updated asc, sent asc nulls last' # "nulls last" is for unsent messages, which don't yet have 'sent' set (so, it's null) - those should be "lowest" in the list
	msg_field = f'''REPLACE(message.message, "{like}", "<span class='highlight'>{like}</span>") as message''' if like else 'message.message'
	query = f'{_mega_message_select(msg_field)} {_message_tag_join} {_user_tag_join} {where} {group_by}'

	if filt == Filter.new:
		query = f'{query} {asc_order} limit {limit}'
	else: # for all other cases, the first `limit` result set should be the NEWEST, then we step back to olders bit by bit as user scrolls UP
		query = f'select * from ({query} order by thread_updated desc, sent desc limit {limit}) {asc_order}'
	#l.debug(f'get_messages query: {query}    ... args: {args}')
	# SEE: giant_sql_laid_out.txt to show/study the above laid out for straight comprehension.
	return await _fetchall(dbc, query, args)

async def delivery_recipient(dbc, user_id, message_id):
	return await _fetch1(dbc, f'select 1 from message {_message_tag_join} {_user_tag_join} where (user_tag.user = ? or message.author = ?) and message.id = ?', (user_id, user_id, message_id))

async def get_message_tags(dbc, message_id, limit, active = True, like = None, include_others = False):
	'''
	include_others can simply be True or False, or it can be a user-id.  If False, then only the message-tags for `message_id` will be returned; if True, then a 2-tuple will be returned (message-tags, other-tags), where other-tags is a list of tags that are NOT associated with the message; if user-id, then the same 2-tuple will be returned, but the second element will only contained other-tags to which the user belongs.
	'''
	io = ('join user_tag on tag.id = user_tag.tag', 'user_tag.user = ?', include_others) if isinstance(include_others, int) else include_others
	non_join = 'message_tag where tag.id = message_tag.tag and message_tag.message = ?'
	result = await _get_xaa(dbc,
		select = 'tag.* from tag',
		where = 'message_tag.message = ?',
		where_arg = message_id,
		active = active,
		like = like,
		likes = ('name',),
		join = 'message_tag on tag.id = message_tag.tag',
		order = 'CASE WHEN tag.user IS NULL THEN 0 ELSE 1 END ASC, tag.name ASC',
		limit = limit,
		include_others = io,
		non_join = non_join
	)
	if not include_others:
		return result
	#else:
	tags, others = result
	remaining_others = limit - len(others) if limit else None
	if (remaining_others == None or remaining_others > 0) and isinstance(include_others, int):
		# The above doesn't include 'user' tags - those pseudo-tags that correspond to individual users, as not every user is subscribed to every other user.  SO, here we add "users":
		where, args = ['tag.user is not null', 'tag.user != ?', f'not exists (select 1 from {non_join})',], [include_others, message_id,] # include_others is user_id, in this case! (and user's self is already included in above fetch, since user is (the only one) subscribed to his/her self-tag (in order to properly receive messages to that user_id!))  I.e., we'd get two copies of user if we didn't exclude, here, iwth tag.user != user_id
		if active:
			where.append('active = 1')
		_add_like(like, ('name',), where, args)
		where = " and ".join(where)
		limit = f'limit {remaining_others}' if remaining_others else ''
		others += await _fetchall(dbc, f'select tag.* from tag where {where} order by tag.name {limit}', args)
	return tags, others


async def _get_xaa(dbc, select, where, where_arg, active, like, likes, join, order, limit, include_others, non_join):
	'''
	include_others can simply be True or False, to include the "nons", or it can be a (where, where, args) triplet, such as ('join user_tag on tag.id = user_tag.tag', 'user_tag.user = ?', 5) in which case the "nons" will only present if that join/where succeeds.
	'''
	where, args = [where,], [where_arg,]
	if active:
		where.append('active = 1')
	_add_like(like, likes, where, args)
	select = f'select {select}'
	join = f'join {join}'
	order = f'order by {order}'
	where = " and ".join(where) if where else ''
	limit = f'limit {limit}' if limit else ''
	result = await _fetchall(dbc, f'{select} {join} where {where} {order} {limit}', args)
	if not include_others:
		return result
	#else:
	where2, args2 = [f'not exists (select 1 from {non_join})',], [where_arg,]
	if active:
		where2.append('active = 1')
	join2 = ''
	if isinstance(include_others, (list, tuple)) and len(include_others) == 3:
		join2 = include_others[0]
		where2.append(include_others[1])
		args2.append(include_others[2])
	_add_like(like, likes, where2, args2)
	where2 = " and ".join(where2)
	#l.debug(f'_get_xaa sql: {select} {join2} where {where2} {order} {limit} ... args: {args2}')
	others = await _fetchall(dbc, f'{select} {join2} where {where2} {order} {limit}', args2)
	return result, others


async def remove_tag_from_message(dbc, message_id, tag_id, uid):
	#TODO: add 'favorites', but not like this, as user_tag does not contain user-user records (for good reason)... not sure how to solve this well.... await _update1(dbc, 'update user_tag set popularity = MAX(0, popularity - 1) where user = ? and tag = ?', (uid, tag_id)) # sqlite apparently truncates, rather than overflow-wrapping; 2^63 is a long ways away, too
	return await dbc.execute('delete from message_tag where message = ? and tag = ?', (message_id, tag_id))

async def add_tag_to_message(dbc, message_id, tag_id, uid):
	#TODO: add 'favorites', but not like this, as user_tag does not contain user-user records (for good reason)... not sure how to solve this well.... await _update1(dbc, 'update user_tag set popularity = popularity + 1 where user = ? and tag = ?', (uid, tag_id)) # sqlite apparently truncates, rather than overflow-wrapping; 2^63 is a long ways away, too
	return await _insert1(dbc, 'insert into message_tag (message, tag) values (?, ?)', (message_id, tag_id))

async def delete_message(dbc, message_id):
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

async def stash_message(dbc, message_id, user_id):
	if not await _fetch1(dbc, 'select 1 from message_stashed where message = ? and stashed_by = ?', (message_id, user_id)):
		try:
			await begin(dbc)
			await _insert1(dbc, 'insert into message_stashed (message, stashed_by) values (?, ?)', (message_id, user_id))
			await dbc.execute('delete from message_unstashed where message = ? and unstashed_for = ?', (message_id, user_id)) # may be no-op, of course!
			await commit(dbc)
		except:
			await rollback(dbc)
			raise
		return True
	return False

async def unstash_message(dbc, message_id, user_id):
	return await dbc.execute('delete from message_stashed where message = ? and stashed_by = ?', (message_id, user_id))

async def pin_message(dbc, message_id, user_id):
	return await _insert1(dbc, 'insert into message_pin (message, user) values (?, ?)', (message_id, user_id))

async def unpin_message(dbc, message_id, user_id):
	return await dbc.execute('delete from message_pin where message = ? and user = ?', (message_id, user_id))

async def get_parent_message(dbc, message_id):
	return await _fetch1(dbc, 'select message.* from message as parent join message as child on parent.id = child.reply_to where child.id = ?', (message_id,))

async def get_patriarch_message_id(dbc, message_id):
	r = await _fetch1(dbc, 'select patriarch.id from message as patriarch join message as child on patriarch.id = child.reply_chain_patriarch where child.id = ?', (message_id,))
	return r['id'] if r else None

async def add_message_attachments(dbc, message_id, filenames):
	# TODO make this all an atomic transaction!
	await _update1(dbc, 'update message set attachments = 1 where id = ?', (message_id,))
	upload = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(4))
	await dbc.executemany('insert into attachment (filename, upload) values (?, ?)', [(fn, upload) for fn in filenames])
	await dbc.execute(f'insert into message_attachment (message, attachment) select {message_id}, id from attachment where upload = ?', (upload,))


async def receive_sms(dbc, fro, message, timestamp):
	main_admin = 2 # TODO: kludgey!
	r = await _fetch1(dbc, 'select user.id from user join phone on user.person = phone.person where phone.phone = ?', (fro,))
	fro_id = r['id'] if r else main_admin
	r2 = await dbc.execute(f'insert into message (message, author, created, sent, thread_updated, teaser) values (?, ?, {k_now}, {k_now}, {k_now}, ?)', (message, ))
	await dbc.execute(f'insert into message_tag (message, tag) values (?, ?)', (r2.lastrowid, main_admin))
	return r2.lastrowid


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
	return await _update1(dbc, f'update id_key set user = ?, login_timestamp = {k_now} where idid = ?', (user_id, idid))

def _add_like(like, fields, where, args):
	if like:
		likes = ' or '.join([f'{field} like ?' for field in fields])
		where.append(f'({likes})')
		args.extend([f'%{like}%'] * len(fields))

if __name__ == '__main__':
	unittests()
