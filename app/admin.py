__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import html
from . import task
from . import ws


l = logging.getLogger(__name__)


@ws.handler(admin = True)
async def tags(hd):
	#TODO?: hd.priortask = tags # return to this task after drilling down on some subtask
	if not task.started(hd, tags):
		t = await db.get_tags(hd.dbc, get_subscribers = True)
		await ws.send_content(hd, 'content', html.tags_page(t))
	else:
		t = await db.get_tags(hd.dbc, like = hd.state.get('filtersearch_text', ''), active = not hd.state.get('filtersearch_include_extra', False), get_subscribers = True)
		await hd.wsr.send_json({'task': 'hide_dialog'}) # TODO: remove the need for this!
		await ws.send_content(hd, 'sub_content', html.tag_table(t), container = 'tag_table')

