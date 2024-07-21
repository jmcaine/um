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

