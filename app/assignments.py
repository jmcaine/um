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
	subj_id = hd.task.state['subj_id'] = hd.payload.get('subj_id', hd.task.state.get('subj_id', None)) # prefer filt sent in payload, then filt already recorded, and, finally, if nothing, default to viewing `current` assignments (only)

	person_id = hd.payload.get('person_id', 0) if hd.admin else None
	uid = (await db.get_person_user(hd.dbc, person_id))['id'] if hd.admin and person_id else hd.uid

	fs = hd.task.state.get('filtersearch', {})
	assignments = await db.get_assignments(hd.dbc, uid,
							like = fs.get('searchtext', ''),
							filt = filt,
							subj_id = subj_id,
							limit = None if fs.get('dont_limit', False) else db.k_assignment_resultset_limit)
	subjects = set([(a['subject_name'], a['subject_id']) for a in assignments])
	await ws.send_sub_content(hd, 'filter_container', html.assignments_filter(filt, subjects, subj_id))

	tsk = 'show_assignments_print' if filt == Filter.all and hd.admin else 'show_assignments'
	#WISH (see comment on next line): await ws.send_sub_content(hd, k_container_id, html.assignments(assignments))
	await ws.send_content(hd, tsk, html.assignments(assignments)) # TODO would prefer the above ("WISH"), to centralize k_container_id, but have to refactor the send_content semantics to handle sub_content hide_dialog() behavior....


@ws.handler(auth_func = authorize_logged_in)
async def mark_complete(hd):
	await db.mark_assignment_complete(hd.dbc, hd.uid, int(hd.payload['assignment_id']), bool(hd.payload['checked'])) # TODO: handle return value (error)!

