__author__ = 'J. Michael Caine'
__copyright__ = '2025'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import fields
from . import html
from . import shared
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


@ws.handler(auth_func = authorize_admin)
async def classes(hd, reverting = False):
	if task.just_started(hd, classes):
		await ws.send_sub_content(hd, 'topbar_container', html.school_topbar())
		await ws.send_sub_content(hd, 'filter_container', html.classes_mainbar())

	ays = await db.get_academic_years(hd.dbc)

	ay = hd.task.state['academic_year'] = hd.payload.get('academic_year', hd.task.state.get('academic_year', ays[0]['id']))
	fs = hd.task.state.get('filtersearch', {})
	r = await db.get_classes(hd.dbc,
							academic_year = ay,
							active = not fs.get('show_inactives', False),
							like = fs.get('searchtext', ''),
							get_enrollment_count = True,
							limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit)
	#await ws.send_sub_content(hd, 'filter_container', html.assignments_filter(filt, subjects, subj_id))

	await ws.send_content(hd, 'content', html.classes_page(r))


@ws.handler(auth_func = authorize_admin)
async def class_students(hd, reverting = False):
	container = 'enrollments_table_container'
	if task.just_started(hd, class_students, ('academic_year',)) or reverting:
		hd.task.state['class_instance_id'] = int(hd.payload.get('id'))
		await ws.send_content(hd, 'dialog', html.table_dialog(await class_students_table(hd), 'assignments', 'class_students', container))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await class_students_table(hd), container = container)


async def class_students_table(hd):
	fs = hd.task.state.get('filtersearch', {})
	limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit
	cid = hd.task.state['class_instance_id']
	enrollments, nons = await db.get_enrollments(hd.dbc, cid,
													limit = limit,
													like = fs.get('searchtext', ''),
													include_others = True)
	sections = await db.get_class_sections(hd.dbc, cid)
	return html.class_enrollments_table(enrollments, nons, 'add_enrollment', 'remove_enrollment', limit, sections)


async def _class_setter(hd, data):
	name = data['name']
	await db.set_class(hd.dbc, hd.task.state['db_data']['id'], name, html.checkbox_value(data, 'active'))
	await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'"{name}"')))


@ws.handler(auth_func = authorize_admin)
async def class_detail(hd, reverting = False):
	return await shared.edit_detail(hd, class_detail, reverting, db.get_class, text.clss, fields.CLASS, _class_setter)


async def _announce_enrollment_change(hd, message, pid):
	person = await db.get_person(hd.dbc, pid, 'first_name, last_name')
	await ws.send_content(hd, 'detail_banner', html.info(message.format(name = f"{person['first_name']} {person['last_name']}")))

@ws.handler(auth_func = authorize_admin)
async def remove_enrollment(hd):
	eid = int(hd.payload['enrollment_id'])
	pid = await db.get_enrollment_person_id(hd.dbc, eid)
	await db.remove_enrollment(hd.dbc, eid)
	await _announce_enrollment_change(hd, text.removed_person_from_class, pid)
	await hd.task.handler(hd) # make current handler re-draw (the table)

@ws.handler(auth_func = authorize_admin)
async def add_enrollment(hd):
	pid = int(hd.payload['person_id'])
	s = hd.task.state
	await db.add_enrollment(hd.dbc, pid, s['class_instance_id'], s['academic_year'])
	await _announce_enrollment_change(hd, text.added_person_to_class, pid)
	await hd.task.handler(hd) # make current handler re-draw (the table)

@ws.handler(auth_func = authorize_admin)
async def change_enrollment_section(hd):
	await _set_enrollment_x(hd, db.change_enrollment_section, text.changed_persons_class_section)

@ws.handler(auth_func = authorize_admin)
async def set_enrollment_audit(hd):
	await _set_enrollment_x(hd, db.change_enrollment_audit, text.changed_persons_class_audit_status)

@ws.handler(auth_func = authorize_admin)
async def set_enrollment_teacher(hd):
	await _set_enrollment_x(hd, db.change_enrollment_teacher, text.changed_persons_class_teacher_status)

async def _set_enrollment_x(hd, fn, message):
	eid = int(hd.payload['id'])
	await fn(hd.dbc, eid, int(hd.payload['value']))
	pid = await db.get_enrollment_person_id(hd.dbc, eid)
	await _announce_enrollment_change(hd, message, pid)
	# no need to redraw - change is already visible

