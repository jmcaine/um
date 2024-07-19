__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

import aiosqlite

from aiohttp import web
from sqlite3 import PARSE_DECLTYPES

from . import html
from . import db
from . import settings


# Logging ---------------------------------------------------------------------

logging.getLogger('aiosqlite').setLevel(logging.CRITICAL) # or ERROR might be fine
logging.getLogger('asyncio').setLevel(logging.CRITICAL) # or ERROR might be fine
logging.getLogger('aiohttp').setLevel(logging.ERROR if settings.debug else logging.CRITICAL) # ERROR and INFO will dump tracebacks on console upon "500 Internal Server Error" failures - essential to development; INFO will add informational lines re: GETs and such; DEBUG would be fine here, but aiohttp internal debug info not necessarily useful; probably just noisy

logging.basicConfig(format = '%(asctime)s - %(levelname)s : %(name)s:%(lineno)d -- %(message)s', level = logging.DEBUG if settings.debug else logging.CRITICAL)
l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

rt = web.RouteTableDef()
hr = lambda text: web.Response(text = text, content_type = 'text/html')  #ALT: def hr(text): return web.Response(text = text, content_type = 'text/html')


# Init / Shutdown -------------------------------------------------------------

async def _init(app):
	l.info('Initializing...')
	await _init_db(app)
	l.info('...initialization complete')

async def _shutdown(app):
	l.info('Shutting down...')
	l.info('...shutdown complete')

async def _init_db(app):
	l.info('...initializing database...')

	conn = await aiosqlite.connect(settings.db_filename, isolation_level = None, detect_types = PARSE_DECLTYPES) # "isolation_level = None disables the Python wrapper's automatic handling of issuing BEGIN etc. for you. What's left is the underlying C library, which does do "autocommit" by default. That autocommit, however, is disabled when you do a BEGIN (b/c you're signaling a transaction with that statement" - from https://stackoverflow.com/questions/15856976/transactions-with-python-sqlite3 - thanks Thanatos
	conn.row_factory = aiosqlite.Row
	await conn.execute('pragma journal_mode = wal') # see https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/ - since we're using async/await from a wsgi stack, this is appropriate
	await conn.execute('pragma foreign_keys = ON')
	#await conn.execute('pragma case_sensitive_like = true')

	app['db'] = conn # sqlite3 offers an "efficient" approach that involves just using the database (conn) directly - a temp cursor is auto-created under the hood): https://pysqlite.readthedocs.io/en/latest/sqlite3.html#using-sqlite3-efficiently ... however, there's nothing wrong with using conn.cursor() (or, now, app['db'].cursor) to get and interact (in the more conventional way) with a cursor object rather than interacting with the DB connection object itself.  Note that doing so does not automatically imply a separate transaction for every cursor....

	l.info('...database initialized...')


# Run server like so, from cli, from root directory (containing 'app' directory):
#		python -m aiohttp.web -H localhost -P 8080 app.main:init
#		python -m aiohttp.web -H localhost -P 8462 app.main:init
#         https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers
# Or, using adev (from parent directory!):
#		adev runserver -s static --livereload app
def init(argv):
	app = web.Application()

	# Add standard routes:
	app.add_routes(rt)

	# Add startup/shutdown hooks:
	app.on_startup.append(_init)
	app.on_shutdown.append(_shutdown)

	return app


# Alternately, use adev to run:
#		adev runserver -s static --livereload app
#def app():
#	return init(None)


# Pages -----------------------------------------------------------------------

if settings.debug:
	rt.static('/static', settings.debug_static)
#else use "real" reverse proxy set up in nginx, e.g., to map static directly

@rt.get('/test')
async def test(rq):
	return hr(html.test())

@rt.get('/test_person/{name}')
async def test(rq):
	person = await db.test_fetch(rq.app['db'], rq.match_info['name'])
	return hr(html.test(person))

