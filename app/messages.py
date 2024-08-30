__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import html
from . import task
from . import ws

from .admin import authorize

l = logging.getLogger(__name__)


#async def authorize(hd, user_id):
#	return await db.authorized(hd.dbc, user_id, 'admin')


@ws.handler
async def messages(hd):
	if not task.started(hd, messages):
		await ws.send_content(hd, 'content', html.messages(await authorize(hd, hd.uid)))
	else:
		await ws.send_content(hd, 'content', html.messages(await authorize(hd, hd.uid))) # TODO: SWAP for a sub_content / table-only .....


