__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from aiohttp import web

from . import html
from . import settings


# Logging ---------------------------------------------------------------------

logging.getLogger('aiohttp').setLevel(logging.INFO if settings.debug else logging.CRITICAL) # INFO will dump tracebacks on console upon "500 Internal Server Error" failures - essential to development; DEBUG would be fine here, but aiohttp internal debug info not necessarily useful; probably just noisy

logging.basicConfig(format = '%(asctime)s - %(levelname)s : %(name)s:%(lineno)d -- %(message)s', level = logging.DEBUG if settings.debug else logging.CRITICAL)
l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

rt = web.RouteTableDef()
hr = lambda text: web.Response(text = text, content_type = 'text/html')  #ALT: def hr(text): return web.Response(text = text, content_type = 'text/html')


# Init / Shutdown -------------------------------------------------------------

async def _init(app):
	l.info('Initializing...')
	l.info('...initialization complete')

async def _shutdown(app):
	l.info('Shutting down...')
	l.info('...shutdown complete')


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
def app():
	return init(None)


# Pages -----------------------------------------------------------------------

@rt.get('/test')
async def test(rq):
	return hr(html.test(str(rq.url.origin())))

