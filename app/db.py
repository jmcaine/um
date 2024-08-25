__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from datetime import datetime
from uuid import uuid4
from random import choices as random_choices
from string import ascii_uppercase
from hashlib import sha256

import bcrypt # cf https://security.stackexchange.com/questions/133239/what-is-the-specific-reason-to-prefer-bcrypt-or-pbkdf2-over-sha256-crypt-in-pass
import aiosqlite
from sqlite3 import PARSE_DECLTYPES, IntegrityError

from . import exception as ex

l = logging.getLogger(__name__)


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
	r = await dbc.execute('insert into id_key (idid, key, timestamp) values (?, ?, ?)', (idid, key, datetime.now().isoformat()))
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
		# Note: user is inactive until reset_user_password() completes, and activates (inactive until password is set, that is)
		r = await dbc.execute('insert into user (username, person, created, active) values (?, ?, ?, 0)', (username, person_id, datetime.now().isoformat()))
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
	return await _update1(dbc, 'update user set verified = date("now") where username = ? and active = 1', (username,))

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
	result = await _fetch1(dbc, 'select 1 from role join user_role on role.id = user_role.role join user on user.id = user_role.user where user.id = ?', (uid,))
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
	await dbc.execute('insert into reset_code (code, user, timestamp) values (?, ?, ?)', (code, user_id, datetime.now().isoformat()))
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



async def get_tags(dbc, active = True, like = None, limit = 15):
	args, where = [], []
	if active:
		where.append('active = 1')
	_add_like(like, ('name',), args, where)
	where = 'where ' + " and ".join(where) if where else ''
	return await _fetchall(dbc, f'select * from tag {where} order by name limit {limit}', args)

async def new_tag(dbc, name, active):
	return await _insert1(dbc, 'insert into tag (name, active) values (?, ?)', (name, active))

async def get_tag(dbc, id, fields: str | None = None):
	if not fields:
		fields = '*'
	return await _fetch1(dbc, f'select {fields} from tag where id = ?', (id,))

async def set_tag(dbc, id, name, active):
	return await _update1(dbc, 'update tag set name = ?, active = ? where id = ?', (name, active, id))

async def get_tag_users(dbc, tag_id, like = None):
	args, where = [tag_id], ['user_tag.tag = ?']
	_add_like(like, ('username', 'first_name', 'last_name'), args, where)
	where = 'where ' + " and ".join(where)
	return await _fetchall(dbc, f'select user.id, username, first_name, last_name from user join user_tag on user.id = user_tag.user join person on user.person = person.id {where} order by username', args)

def _add_like(like, fields, args, where):
	if like:
		likes = ' or '.join([f'{field} like ?' for field in fields])
		where.append(f'({likes})')
		args.extend([f'%{like}%'] * len(fields))


async def get_tag_users_and_nonusers(dbc, tag_id, like = None):
	args, where = [], []
	_add_like(like, ('username', 'first_name', 'last_name'), args, where)
	where = 'where ' + " and ".join(where) if where else ''
	tag_users = await get_tag_users(dbc, tag_id, like)
	all_users = await _fetchall(dbc, f'select user.id, username, first_name, last_name from user join person on user.person = person.id {where} order by username', args)
	return tag_users, [r for r in all_users if r not in tag_users]

async def remove_user_from_tag(dbc, user_id, tag_id):
	return await dbc.execute(f'delete from user_tag where user = ? and tag = ?', (user_id, tag_id))

async def add_user_to_tag(dbc, user_id, tag_id):
	return await _insert1(dbc, 'insert into user_tag (user, tag) values (?, ?)', (user_id, tag_id))


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


