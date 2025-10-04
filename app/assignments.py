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


k_assignments_container_id = 'assignments_container'

@ws.handler(auth_func = authorize_logged_in)
async def main(hd, reverting = False):
	if task.just_started(hd, main):
		await ws.send_sub_content(hd, 'topbar_container', html.assignments_topbar(hd.admin))
		await ws.send_content(hd, 'content', html.container(text.loading_assignments, k_assignments_container_id))

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
	#WISH (see comment on next line): await ws.send_sub_content(hd, k_assignments_container_id, html.assignments(assignments))
	await ws.send_content(hd, tsk, html.assignments(assignments)) # TODO would prefer the above ("WISH"), to centralize k_assignments_container_id, but have to refactor the send_content semantics to handle sub_content hide_dialog() behavior....


@ws.handler(auth_func = authorize_logged_in)
async def mark_complete(hd):
	await db.mark_assignment_complete(hd.dbc, hd.uid, int(hd.payload['assignment_id']), bool(hd.payload['checked'])) # TODO: handle return value (error)!


k_school_container_id = 'school_container'

@ws.handler(auth_func = authorize_admin)
async def classes(hd, reverting = False):
	if task.just_started(hd, classes):
		await ws.send_sub_content(hd, 'topbar_container', html.school_topbar())
		await ws.send_sub_content(hd, 'filter_container', html.classes_mainbar())
		await ws.send_content(hd, 'content', html.container(text.loading, k_school_container_id))

	#filt = hd.task.state['filt'] = hd.payload.get('filt', hd.task.state.get('filt', Filter.current)) # prefer filt sent in payload, then filt already recorded, and, finally, if nothing, default to viewing `current` assignments (only)
	fs = hd.task.state.get('filtersearch', {})
	r = await db.get_classes(hd.dbc,
							like = fs.get('searchtext', ''),
							limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit)
	#await ws.send_sub_content(hd, 'filter_container', html.assignments_filter(filt, subjects, subj_id))

	#WISH (see comment on next line): await ws.send_sub_content(hd, k_classes_container_id, html.classes(r))
	await ws.send_content(hd, 'show_classes', html.classes_page(r)) # TODO would prefer the above ("WISH"), to centralize k_assignments_container_id, but have to refactor the send_content semantics to handle sub_content hide_dialog() behavior....


@ws.handler(auth_func = authorize_admin)
async def student_classes(hd, reverting = False):
	if task.just_started(hd, student_classes) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		hd.task.state['class_id'] = int(hd.payload.get('class_id'))
		await ws.send_content(hd, 'dialog', html.class_students(await class_students_table(hd)))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await class_students_table(hd), container = 'class_students_table_container')

async def class_students_table(hd):
	fs = hd.task.state.get('filtersearch', {})
	limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit
	students, nons = await db.get_class_students(hd.dbc, hd.task.state['class_id'],
													limit = limit,
													like = fs.get('searchtext', ''),
													include_others = True)
	return html.class_students_table(students, nons, limit)



@ws.handler(auth_func = authorize_admin)
async def class_detail(hd, reverting = False):
	#!!!!
	if reverting:
		await task.finish(hd) # just bump back another step - see person_detail 'reverting' note...
		return # nothing more to do here
	if task.just_started(hd, class_detail):
		user_id = int(hd.payload.get('id'))
		hd.task.state['user'] = await db.get_user(hd.dbc, user_id)
		await ws.send_content(hd, 'dialog', html.dialog2(text.user, fields.USER, hd.task.state['user'], more_funcs = [
			(text.more_detail, f'admin.send_ws("user_tags", {{ user_id: {user_id} }})'),
		]))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.USER, handle_invalid, 'detail_banner'):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		un = data['username']
		if un != hd.task.state['user']['username'] and await db.username_exists(hd.dbc, un):
			await ws.send_content(hd, 'detail_banner', html.error(text.Valid.username_exists))
			return # finished
		#else all good, move on!
		data['active'] = html.checkbox_value(data, 'active')
		await db.update_user(hd.dbc, hd.task.state['user']['id'], fields.USER.keys(), data)
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'"{un}"')))
