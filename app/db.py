__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging


# Logging ---------------------------------------------------------------------

l = logging.getLogger(__name__)


async def test_fetch(dbc, pattern):
	r = await dbc.execute('select * from person where first_name like ?', (f'%{pattern}%',))
	return await r.fetchone()

async def add_person(dbc, data):
	r = await dbc.execute('insert into person (first_name, last_name) values (?, ?)', (data['first_name'], data['last_name']))
	return r.lastrowid

async def get_person(dbc, id):
	r = await dbc.execute('select * from person where id = ? limit 1', (id,))
	return await r.fetchone()

async def modify_person(dbc, data):
	r = await dbc.execute('update person set first_name = ?, last_name = ? where id = ?', (data['first_name'], data['last_name'], data['id']))
	return True

async def get_persons(dbc, like = None):
	where = ' where ' + like if like else ''
	r = await dbc.execute('select * from person ' + where + ' order by last_name')
	return await r.fetchall()
