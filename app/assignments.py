__author__ = 'J. Michael Caine'
__copyright__ = '2025'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import fields
from . import html
from . import task
from . import text
from . import valid
from . import ws

from .assignments_const import *


l = logging.getLogger(__name__)


async def authorize_admin(hd):
	return hd.admin

async def authorize_logged_in(hd):
	return hd.uid


k_container_id = 'assignments_container'

@ws.handler(auth_func = authorize_logged_in)
async def main(hd, reverting = False):
	if task.just_started(hd, main):
		await ws.send_sub_content(hd, 'topbar_container', html.assignments_topbar())
		await ws.send_content(hd, 'content', html.container(text.loading_assignments, k_container_id))

	filt = hd.task.state['filt'] = hd.payload.get('filt', hd.task.state.get('filt', Filter.current)) # prefer filt sent in payload, then filt already recorded, and, finally, if nothing, default to viewing `current` assignments (only)
	await ws.send_sub_content(hd, 'filter_container', html.assignments_filter(filt))

	person_id = hd.payload.get('person_id', 0) if hd.admin else None
	uid = (await db.get_person_user(hd.dbc, person_id))['id'] if hd.admin and person_id else hd.uid

	fs = hd.task.state.get('filtersearch', {})
	a = await db.get_assignments(hd.dbc, uid,
							like = fs.get('searchtext', ''),
							filt = filt,
							limit = None if fs.get('dont_limit', False) else db.k_assignment_resultset_limit)
	#WISH (see comment on next line): await ws.send_sub_content(hd, k_container_id, html.assignments(a))
	await ws.send_content(hd, 'show_assignments', html.assignments(a)) # TODO would prefer the above ("WISH"), to centralize k_container_id, but have to refactor the send_content semantics to handle sub_content hide_dialog() behavior....


@ws.handler(auth_func = authorize_logged_in)
async def mark_complete(hd):
	await db.mark_assignment_complete(hd.dbc, hd.uid, int(hd.payload['assignment_id']), bool(hd.payload['checked'])) # TODO: handle return value (error)!

