__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

import bcrypt # cf https://security.stackexchange.com/questions/133239/what-is-the-specific-reason-to-prefer-bcrypt-or-pbkdf2-over-sha256-crypt-in-pass

from datetime import datetime
from uuid import uuid4
from random import choices as random_choices
from string import ascii_uppercase

import aiosqlite

from sqlite3 import PARSE_DECLTYPES, IntegrityError

from . import exception as ex

l = logging.getLogger(__name__)


async def connect(filename):
	result = await aiosqlite.connect(filename, isolation_level = None, detect_types = PARSE_DECLTYPES) # "isolation_level = None disables the Python wrapper's automatic handling of issuing BEGIN etc. for you. What's left is the underlying C library, which does do "autocommit" by default. That autocommit, however, is disabled when you do a BEGIN (b/c you're signaling a transaction with that statement" - from https://stackoverflow.com/questions/15856976/transactions-with-python-sqlite3 - thanks Thanatos
	result.row_factory = aiosqlite.Row
	await result.execute('pragma journal_mode = wal') # see https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/ - since we're using async/await from a wsgi stack, this is appropriate
	await result.execute('pragma foreign_keys = ON')
	#await result.execute('pragma case_sensitive_like = true')
	return result

async def cursor(connection):
	return await connection.cursor()


async def test_fetch(dbc, pattern):
	r = await dbc.execute('select * from person where first_name like ?', (f'%{pattern}%',))
	return await r.fetchone()
	# alternately, one-liner, using _fetchone() util:
	#return await _fetchone(dbc, 'select * from person where first_name like ?', (f'%{pattern}%',))


async def begin(dbc):
	await dbc.execute('begin')

async def commit(dbc):
	await dbc.execute('commit')

async def rollback(dbc):
	await dbc.execute('rollback')


async def add_person(dbc, first_name, last_name):
	r = await dbc.execute('insert into person (first_name, last_name) values (?, ?)', (first_name, last_name))
	return r.lastrowid

async def get_person(dbc, id):
	return await _fetchone(dbc, 'select * from person where id = ? limit 1', (id,))

async def modify_person(dbc, id, first_name, last_name):
	return await _update1(dbc, 'update person set first_name = ?, last_name = ? where id = ?', (first_name, last_name, id))

async def get_persons(dbc, like = None):
	where = ' where ' + like if like else ''
	return await _fetchall(dbc, 'select * from person ' + where + ' order by last_name')

async def add_email(dbc, person_id, email):
	return await _insert1(dbc, 'insert into email (address, person) values (?, ?)', (email, person_id))

async def add_phone(dbc, person_id, number):
	return await _insert1(dbc, 'insert into phone (number, person) values (?, ?)', (number, person_id))

async def username_exists(dbc, username):
	return await _fetchone(dbc, 'select 1 from user where username = ?', (username,)) != None

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

async def verify_new_user(dbc, username):
	return await _update1(dbc, 'update user set verified = date("now") where username = ? and active = 1', (username,))

async def login(dbc, username, password):
	if not password: # password is required!
		return None
	#else...
	r = await _fetchone(dbc, 'select id, password from user where username = ? and active = 1', (username,))
	if r and bcrypt.checkpw(password.encode(), r['password']):
		return await _login(dbc, r['id'])
	#else...
	return None

async def force_login(dbc, user_id):
	# use, e.g., to auto-login user when user first creates self (don't ask for password again right after creation)
	r = await _fetchone(dbc, 'select id from user where id = ? and active = 1', (user_id,))
	return await _login(dbc, r['id'])

async def authenticated(dbc, uuid):
	return await _fetchone(dbc, 'select id from user_login where active = 1 and uuid = ?', (uuid,)) != None

async def logout(dbc, uuid):
	await dbc.execute('update user_login set active = 0 where uuid = ?', (uuid,))

async def get_username(dbc, uuid):
	r = await _fetchone(dbc, 'select username from user join user_login on user_login.user = user.id where user_login.uuid = ?', (uuid,))
	return r['username'] if r else None

async def get_user_id(dbc, username):
	r = await _fetchone(dbc, 'select id from user where username = ?', (username,))
	return r['id'] if r else None

async def get_user_id_by_email(dbc, email):
	r = await _fetchone(dbc, 'select id from user join person on user.person = person.id join email on person.id = email.person where email.address = ?', (email,))
	return r['id'] if r else None

async def get_user_emails(dbc, user_id):
	return await _fetchall(dbc, 'select address from email join person on email.person = person.id join user on person.id = user.person where user.id = ?', (user_id,))

async def generate_password_reset_code(dbc, user_id):
	code = ''.join(random_choices(ascii_uppercase, k=6))
	await dbc.execute('insert into reset_code (code, user, timestamp) values (?, ?, ?)', (code, user_id, datetime.now().isoformat()))
	return code

async def validate_reset_password_code(dbc, code, user_id):
	r = await _fetchone(dbc, 'select id from reset_code where code = ? and user = ?', (code, user_id))
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


# Utils -----------------------------------------------------------------------

async def _fetchone(dbc, sql, args = None):
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

async def _login(dbc, user_id):
	uuid = str(uuid4())
	await dbc.execute('insert into user_login (user, uuid, timestamp) values (?, ?, ?)', (user_id, uuid, datetime.now().isoformat()))
	return uuid

