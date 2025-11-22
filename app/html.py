__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from copy import copy
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from datetime import datetime, date, timedelta, timezone
from random import randint
import regex as re
from zoneinfo import ZoneInfo

from dominate import document as dominate_document
from dominate import tags as t
from dominate.util import raw

from . import text
from . import messages_const
from . import assignments_const

from .const import *
from .settings import cache_buster


# Logging ---------------------------------------------------------------------

l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

checkbox_value = lambda data, field: 1 if data.get(field) in (1, '1', 'on') else 0

_yes_or_no = lambda value: 'yes' if value else 'no'
_format_phone = lambda num: '(' + num[-10:-7] + ') ' + num[-7:-4] + '-' + num[-4:] # TODO: international extention prefixes [0:-11]
_send = lambda app, task, **args: f"{app}.send_ws('{task}'" + (f', {{ {", ".join([f"{key}: {value}" for key, value in args.items()])} }})' if args else ')')

_cancel_button = lambda title = text.cancel: t.button(title, onclick = _send('main', 'finish'))

k_url_rec = re.compile(k_url_re)

# Document --------------------------------------------------------------------

# Note that there's really only one "document"

def document(ws_url: str, initial = ''):
	d = _doc(('common.css',))
	with d:
		t.div(id = 'gray_screen', cls = 'hide') # invisible at first; for dialog_screen, later
		t.div(id = 'dialog_screen', cls = 'hide') # invisible at first
		with t.div(id = 'header_pane'):
			t.div(id = 'topbar_container', cls = 'container')
			t.div(id = 'filter_container', cls = 'container')
			t.div(id = 'banner_container', cls = 'container') # for later ws-delivered banner messages
			t.hr(cls = 'top')

		with t.div(id = 'main_pane'):
			t.input_(type = 'file', id = 'file_upload', multiple = 'true', hidden = 'true', accept = 'image/png, image/jpeg, video/mp4, application/pdf')
			raw(f'''<dialog id="dialog" class="dialog" closedby="any" autofocus="dialog"><div style="float:right"> <button title="{text.download}" onclick="messages.download()"><i class="i i-download"></i></button>  <button title="{text.close}" onclick="$('dialog').close()"><i class="i i-close"></i></button></div><div id="dialog_contents"></div></dialog>''') # there's no t.dialog!
			with t.div(id = 'content_container', cls = 'container', style = 'clear:both'):
				t.div(text.loading)

		with t.div(id = 'scripts', cls = 'container'):
			t.script(raw(f'var ws = new WebSocket("{ws_url}");'))
			t.script(raw(f'const initial = "{initial}";'))
			for script in ('basic.js', 'ws.js', 'persistence.js', 'main.js', 'admin.js', 'submit.js', 'messages.js', 'assignments.js'): # TODO: only load admin.js if user is an admin (somehow? - dom-manipulate with $('scripts').insertAdjacentHTML("beforeend", ...) after login!)!
				t.script(src = f'/static/js/{script}')

	return d


# Main-content "Pages" (and main page parts) ----------------------------------

def login_or_join():
	return t.div(
		t.div(text.welcome),
		t.div(t.button(text.login, onclick = _send('main', 'login')), cls = 'center'),
		t.div(t.button(text.join, onclick = _send('main', 'join')), cls = 'center'),
	)

# button symbols:    ҉ Ѱ Ψ Ѫ Ѭ Ϯ ϖ Ξ Δ ɸ Θ Ѥ ΐ Γ Ω ¤ ¥ § Þ × ÷ þ Ħ ₪ ☼ ♀ ♂ ☺ ☻ ♠ ♣ ♥ ♦ ►
def messages_topbar(admin, enrolled, sub_manager):
	result = t.div(t.button('+', title = 'new message', onclick = _send('messages', 'new_message')), cls = 'buttonbar')
	filterbox(result, {'deep_search': text.deep_search})
	with result:
		t.div(cls = 'spacer')
		#TODO: t.button('...', title = text.change_settings, onclick = _send('main', 'settings'))
		if admin:
			t.button('Ѫ', title = text.admin, onclick = _send('admin', 'users'))
		if enrolled:
			t.button('A', title = text.assignments, onclick = _send('assignments', 'main'))
		if sub_manager:
			t.button('S', title = text.subs, onclick = _send('assignments', 'teachers_subs'))
		t.button('Θ', title = text.session_account_details, onclick = _send('admin', 'session'))
	return result

def messages_filter(filt):
	result = t.div(cls = 'buttonbar')
	with result:
		filt_button = lambda title, hint, _filt: t.button(title, title = hint, cls = 'selected' if filt == _filt else '', onclick = f'messages.filter(id, "{_filt}")')
		filt_button(text.news, text.show_news, messages_const.Filter.new)
		filt_button(text.alls, text.show_alls, messages_const.Filter.all)
		filt_button(text.days, text.show_days, messages_const.Filter.day)
		filt_button(text.this_weeks, text.show_this_weeks, messages_const.Filter.this_week)
		filt_button(text.pins, text.show_pins, messages_const.Filter.pinned)
		filt_button(text.pegs, text.show_pegs, messages_const.Filter.pegged)
	return result


def users_tags_topbar():
	result = t.div(cls = 'buttonbar')
	with result:
		t.div(cls = 'spacer')
		#TODO: t.button('...', title = text.change_settings, onclick = _send('main', 'settings'))
		t.button(t.i(cls = 'i i-messages'), title = text.messages, onclick = _send('messages', 'messages')) # Ξ
		t.button('Θ', title = text.session_account_details, onclick = _send('admin', 'session'))
	return result

def users_mainbar():
	return _mainbar(text.invite_new_user, _send('main', 'invite'), [
			t.button(t.i(cls = 'i i-one'), title = text.users, cls = 'selected', onclick = _send('admin', 'users')), # for this one, onclick() just reloads content
			t.button(t.i(cls = 'i i-all'), title = text.tags, onclick = _send('admin', 'tags')),
		])

def tags_mainbar():
	return _mainbar(text.create_new_tag, _send('admin', 'new_tag'), [
			t.button(t.i(cls = 'i i-one'), title = text.users, onclick = _send('admin', 'users')),
			t.button(t.i(cls = 'i i-all'), title = text.tags, cls = 'selected', onclick = _send('admin', 'tags')), # for this one, onclick() just reloads content
		])

def users_page(users):
	return t.div(user_table(users), id = 'user_table_container')

def tags_page(tags):
	return t.div(tag_table(tags), id = 'tag_table_container')



def assignments_topbar(admin):
	result = t.div(cls = 'buttonbar')
	#filterbox(result, {'deep_search': text.deep_search})
	with result:
		t.div(cls = 'spacer')
		t.button(t.i(cls = 'i i-messages'), title = text.messages, onclick = _send('messages', 'messages')) # Ξ
		if admin:
			t.button(t.i(cls = 'i i-class'), title = text.classes, onclick = _send('assignments', 'classes'))
		t.button('Θ', title = text.session_account_details, onclick = _send('admin', 'session'))
	return result

def assignments_filter(filt, subjects, subject_id):
	result = t.div(cls = 'buttonbar')
	with result:
		filt_button = lambda title, hint, _filt: t.button(title, title = hint, cls = 'selected' if filt == _filt else '', onclick = f'assignments.filter("{_filt}")')
		filt_button(text.currents, text.show_currents, assignments_const.Filter.current)
		filt_button(text.previouses, text.show_previouses, assignments_const.Filter.previous)
		filt_button(text.nexts, text.show_nexts, assignments_const.Filter.next)
		filt_button(text.alls, text.show_all_assignments, assignments_const.Filter.all)
	if len(subjects) > 1:
		droplist_button(result, 'subject_chooser', text.subject, subjects, text.all_subjects, subject_id)
	else:
		result.add(t.button(text.all_subjects, onclick = f'assignments.subject_filter(0)'))
	return result



def classes_mainbar():
	return _mainbar(text.add_new_class, _send('assignments', 'new_class'), [
			t.button(t.i(cls = 'i i-one'), title = text.students, onclick = _send('assignments', 'students')),
			t.button(t.i(cls = 'i i-class'), title = text.classes, cls = 'selected', onclick = _send('assignments', 'classes')), # for this one, onclick() just reloads content
		], {'show_inactives': text.show_inactives, 'dont_limit': text.dont_limit})

def students_mainbar(title):
	return _mainbar(text.add_new_enrollment, _send('assignments', 'new_enrollment'), [
			t.button(t.i(cls = 'i i-one'), title = text.students, onclick = _send('assignments', 'students')),
			t.button(t.i(cls = 'i i-class'), title = text.classes, cls = 'selected', onclick = _send('assignments', 'classes')), # for this one, onclick() just reloads content
		], {'dont_limit': text.dont_limit})

def classes_page(classes):
	return t.div(classes_table(classes), cls = 'container center_flex', id = 'classes_table_container')

def students_page(students):
	return t.div(students_table(students), cls = 'container center_flex', id = 'students_table_container')

def teachers_subs_page(teachers_subs, current_week):
	return t.div(teachers_subs_table(teachers_subs, current_week), cls = 'container center_flex', id = 'teachers_subs_table_container')


def common_topbar():
	result = t.div(cls = 'buttonbar')
	with result:
		t.div(cls = 'spacer')
		t.button(t.i(cls = 'i i-messages'), title = text.messages, onclick = _send('messages', 'messages')) # Ξ
		t.button('Θ', title = text.session_account_details, onclick = _send('admin', 'session'))
	return result

def teachers_subs_mainbar():
	return _mainbar(text.add_new_class, None, [], {'show_inactives': text.show_inactives, 'dont_limit': text.dont_limit})


def _mainbar(add_button_title, add_onclick, right_buttons, filter_checkboxes = None): # TODO: use this for more, like user_tags, tag_users, message_tags?, etc.
	if not filter_checkboxes:
		filter_checkboxes = {'dont_limit': text.dont_limit}
	bar = t.div(cls = 'buttonbar')
	if add_button_title and add_onclick:
		bar.add(t.button('+', title = add_button_title, onclick = add_onclick))
	filterbox(bar, filter_checkboxes)
	bar.add(t.div(cls = 'spacer'))
	for button in right_buttons:
		bar.add(button)
	return t.div(bar)



def container(placeholder_text, id):
	return t.div(placeholder_text, cls = 'container', id = id)



# Divs/fieldsets/partials -----------------------------------------------------


def info(msg: str):
	return t.div(msg, id = 'banner_content', cls = 'info fadeout_mid')

def error(msg: str):
	return t.div(msg, id = 'banner_content', cls = 'error fadeout_long')

def warning(msg: str):
	return t.div(msg, id = 'banner_content', cls = 'warning fadeout_long')

def test1(msg: str):
	return t.div(msg)


def build_fields(fields, data = None, label_prefix = None, invalids = None):
	return [field.html_field.build(name, data, label_prefix, invalids) \
		for name, field in fields.items()]

def login(fields, username = None):
	button = _ws_submit_button(text.login, fields.keys())
	forgot = t.button(text.forgot_password, onclick = _send('main', 'forgot_password'))
	data = {'username': username, 'password': ''} if username else None
	result = fieldset(text.login, build_fields(fields, data), button, forgot)
	return result

def forgot_password(fields):
	button = _ws_submit_button(text.send, fields.keys())
	result = fieldset(text.password_reset, build_fields(fields), button)
	return result

def password_reset_code(fields):
	button = _ws_submit_button(text.submit, fields.keys())
	result = fieldset(text.reset_code, build_fields(fields), button)
	return result

def new_password(fields):
	button = _ws_submit_button(text.submit, fields.keys())
	result = fieldset(text.new_password, build_fields(fields), button)
	return result

def session_options(other_logins):
	result = t.div(cls = 'center_flex')
	with result:
		t.div(_cancel_button(text.cancel_return))
		t.div(t.button(text.logout, onclick = _send('main', 'logout')))
		t.div(t.button(text.account_details, onclick = _send('admin', 'my_account_detail')))
		#t.button(t.i(cls = 'i i-clear'), title = text.clear, style = 'max-height: 10px', onclick = f'''(function() {{ clear_filtersearch(); {go('""')}; }})()''') # Ξ
		t.hr()
		t.div(text.switch_to)
		for user in other_logins:
			color = user['color'] if (user['color'] and user['color'] != '#ffffff') else '#919191'
			t.div(t.button(user['username'], style = f'background-color: {color}', onclick = _send('main', 'switch_login', username = f'''"{user['username']}"''', require_password_on_switch = user['require_password_on_switch'])))
		t.hr()

	return result


def filterbox(parent, filtersearch_checkboxes):
	kwargs = dict([(name, f'$("{name}").checked') for name in filtersearch_checkboxes.keys()])
	go = lambda searchstring: _send('main', 'filtersearch', searchtext = searchstring, **kwargs)
	with parent:
		t.div(Input(text.filtersearch, type_ = 'search', autofocus = True, attrs = { # NOTE: autofocus = True is the supposed cause of Firefox FOUC https://bugzilla.mozilla.org/show_bug.cgi?id=1404468 - but it does NOT cause the warning in FF console to go away AND we don't see any visual blink evidence, so we're leaving autofocus=True, but an alternative would be to set autofocus in the JS that loads the header content
			'autocomplete': 'off',
			'oninput': go('this.value'),
		}).build('filtersearch')) # TODO: does the Input() really need to go in a t.div container?!!!
		t.button(t.i(cls = 'i i-clear'), title = text.clear, style = 'max-height: 10px', onclick = f'''(function() {{ clear_filtersearch(); {go('""')}; }})()''') # Ξ
		for key, label in filtersearch_checkboxes.items():
			Input(label, type_ = 'checkbox', attrs = {'onclick': go('$("filtersearch").value')}).build(key)
	return parent

def fieldset(title: str, html_fields: list, button: t.button, alt_button: t.button = _cancel_button(), more_funcs: tuple | None = None) -> t.fieldset:
	result = t.fieldset()
	with result:
		t.legend(title + '...')
		for field in html_fields:
			t.div(field)
		if more_funcs:
			for title, click in more_funcs:
				t.div(t.button(title, onclick = click))
		if alt_button:
			t.div(t.span(button, alt_button))
		else:
			t.div(button)
	return result

def user_table(users):
	result = t.table(cls = 'full_width')
	user_detail = lambda user: _send('admin', 'user_detail', id = user['user_id'])
	with result:
		with t.tr():
			t.th('Username', align = 'right')
			t.th('Name', align = 'left')
			t.th('Created', align = 'center')
			t.th('Verified', align = 'center')
			t.th('Active', align = 'center')
		for user in users:
			with t.tr():
				t.td(user['username'], cls = 'pointered', align = 'right', onclick = user_detail(user))
				t.td(f"{user['first_name']} {user['last_name']}", cls = 'pointered', align = 'left', onclick = _send('admin', 'person_detail', person_id = user['person_id']))
				t.td(datetime.fromisoformat(user['created']).strftime('%m/%d/%Y %H:%M'), align = 'center')
				t.td(user['verified'] or '', cls = 'pointered', align = 'center', onclick = user_detail(user))
				t.td(_yes_or_no(int(user['active'])), align = 'center', cls = 'pointered', onclick = user_detail(user))
	return result


def tag_table(tags):
	result = t.table(cls = 'full_width')
	with result:
		with t.tr():
			t.th('Name', align = 'right')
			t.th('Active')
			t.th('Subscriptions')
		for tag in tags:
			st = _send('admin', 'tag_detail', id = tag['id'])
			with t.tr():
				t.td(tag['name'], cls = 'pointered', align = 'right', onclick = st)
				t.td(_yes_or_no(int(tag['active'])), align = 'center', cls = 'pointered', onclick = st)
				t.td(tag['num_subscribers'], cls = 'pointered', align = 'center', onclick = _send('admin', 'tag_users', tag_id = tag['id']))
	return result


def dialog(title, html_fields, field_names, button_title = text.save, alt_button: t.button = _cancel_button(), more_funcs = None):
	return t.div(
		t.div(id = 'detail_banner_container', cls = 'container'), # for later ws-delivered banner messages
		fieldset(title, html_fields, _ws_submit_button(button_title, field_names), alt_button, more_funcs),
	)

def dialog2(title, fields, data = None, button_title = text.save, alt_button: t.button = _cancel_button(), more_funcs = None):
	return dialog(title, build_fields(fields, data), fields.keys(), button_title, alt_button, more_funcs)


def more_person_detail(person_id, emails, phones, spouse, children):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		with t.fieldset():
			t.legend(text.emails)
			for email in emails:
				t.div(t.span(
					email['email'],
					t.button(text.edit, onclick = _send('admin', 'email_detail', person_id = person_id, id = email['id'])),
					t.button(text.delete, onclick = f'admin.delete_email({email["id"]})'),
				))
			t.div(t.button(text.add, onclick = _send('admin', 'email_detail', person_id = person_id,  id = 0)))
		with t.fieldset():
			t.legend(text.phones)
			for phone in phones:
				t.div(t.span(
					_format_phone(phone['phone']),
					t.button(text.edit, onclick = _send('admin', 'phone_detail', person_id = person_id, id = phone['id'])),
					t.button(text.delete, onclick = f'admin.delete_phone({phone["id"]})'),
				))
			t.div(t.button(text.add, onclick = _send('admin', 'phone_detail', person_id = person_id, id = 0)))
		#TODO: spouse
		with t.fieldset():
			t.legend(text.children)
			for child in children:
				bd = datetime.fromisoformat(child['birth_date']).strftime('%m/%d/%Y')
				child_line = f"{child['first_name']} {child['last_name']} ({bd})"
				if child['username']:
					child_line += f" - {child['username']}"
				t.div(t.span(
					child_line,
					t.br(),
					t.button(text.edit, onclick = _send('admin', 'child_detail', person_id = person_id, id = child['id'])),
					t.button(text.delete, onclick = f'admin.orphan_child({child["id"]}, {person_id})'),
					t.hr(),
				))
			t.div(t.button(text.add, onclick = _send('admin', 'child_detail', person_id = person_id, id = 0)))
		t.div(_cancel_button(text.done)) # cancel just reverts to prior task; added/changed emails/phones are saved - those deeds are done, we're just "closing" this more_person_detail portal
	return result







def students_table(students):
	result = t.table()
	with result:
		with t.tr():
			t.th(text.name, align = 'right')
			t.th(text.classes)
		for student in students:
			with t.tr():
				t.td(f"{student['first_name']} {student['last_name']}", align = 'right')
				t.td(student['num_classes'], cls = 'pointered', align = 'left', onclick = _send('assignments', 'student_classes', person_id = student['id']))
	return result


def classes_table(classes):
	result = t.table()
	with result:
		with t.tr():
			t.th(text.name, align = 'right')
			t.th(text.students, align = 'center')
		for clss in classes:
			with t.tr():
				t.td(clss['name'], align = 'right', cls = 'pointered', onclick = _send('assignments', 'class_detail', id = clss['id']))
				t.td(clss['num_enrolled'], align = 'center', cls = 'pointered', onclick = _send('assignments', 'class_students', id = clss['id']))
	return result



def teachers_subs_table(teachers_subs, current_week):
	result = t.table()
	with result:
		with t.tr():
			t.th(text.clss, align = 'right')
			t.th(text.two_weeks_back, align = 'center')
			t.th(text.previouses, align = 'center')
			t.th(text.currents, align = 'center')
			t.th(text.nexts, align = 'center')
			t.th(text.two_weeks, align = 'center')
	clss = None
	row = None
	row_ts = [None, None, None, None, None]
	def _complete_row(r, rs):
		if r:
			for i in range(5):
				r.add(t.td(_ts_table_button(rs[i]), align = 'center'))
			result.add(r)

	for ts in teachers_subs:
		if ts['class_id'] != clss:
			_complete_row(row, row_ts)
			clss = ts['class_id']
			row = t.tr()
			row.add(t.td(ts['class_name'], align = 'right'))
			row_ts = [None, None, None, None, None]
		row_ts[ts['week'] - current_week + 2] = ts
	_complete_row(row, row_ts)
	return result

def _ts_table_button(ts):
	onclick = _send('assignments', 'choose_teacher_sub', class_teacher_sub_id = ts['class_teacher_sub_id'])
	return t.button(f"{ts['teacher_first_name']} {ts['teacher_last_name']}", cls = 'green', onclick = onclick) if ts['teacher_id'] else t.button(text.choose, onclick = onclick)




def table_dialog(cs_table, container_id, done_app = None, done_task = None):
	result = t.div(cls = 'container center_flex')
	with result:
		t.div(id = 'detail_banner_container', cls = 'container') # for later ws-delivered banner messages
		filterbox(t.div(cls = 'buttonbar'), {'dont_limit': text.dont_limit})
		if done_app and done_task:
			t.button(text.done, onclick = _send(done_app, done_task, finished = 'true'))
		else:
			t.button(text.cancel, onclick = 'hide_dialog()')
		t.div(cs_table, id = container_id)
	return result

def class_enrollments_table(enrolleds, nons, adder_task, remover_task, count, sections):
	s_name = lambda s: f"{s['first_name']} {s['last_name']}"
	adder = lambda id: _send('assignments', adder_task, person_id = id)
	remover = lambda id: _send('assignments', remover_task, enrollment_id = id)
	section_chooser = Chooser_Column('change_enrollment_section', text.section, 'section', sections)
	teacher_checkboxer = Checkbox_Column('set_enrollment_teacher', text.teacher, 'teacher')
	audit_checkboxer = Checkbox_Column('set_enrollment_audit', text.audit, 'audit')
	return _xaa_table(nons, enrolleds, s_name, text.not_in_class, text.in_class, adder, remover, count, (section_chooser, teacher_checkboxer, audit_checkboxer))

def guardians_table(guardians, done_app, done_task, limit):
	result = t.table()
	with result:
		with t.tr():
			t.th(text.name)
		for guardian in guardians:
			with t.tr():
				t.td(f"{guardian['first_name']} {guardian['last_name']}", cls = 'pointered', onclick = _send(done_app, done_task, person_id = guardian['id'], finished = 'true'))
	return result

@dataclass(slots = True)
class Chooser_Column:
	task: str
	column_title: str
	field_name: str
	options: int
	def render(self, id, current_value):
		result = t.select(onchange = _send('assignments', self.task, id = id, value = 'this.value'))
		for opt in range(1, self.options + 1):
			topt = t.option(str(opt), value = opt)
			if opt == current_value:
				topt['selected'] = 'selected'
			result.add(topt)
		return result

@dataclass(slots = True)
class Checkbox_Column:
	task: str
	column_title: str
	field_name: str
	def render(self, id, current_value):
		result = t.input_(type = 'checkbox', onchange = _send('assignments', self.task, id = id, value = 'this.checked'))
		if current_value:
			result['checked'] = 'checked'
		return result




def student_classes(sc_table):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		filterbox(t.div(cls = 'buttonbar'), {'dont_limit': text.dont_limit})
		t.button(text.done, onclick = _send('assignments', 'student_classes', finished = 'true'))
		t.div(sc_table, id = 'student_classes_table_container')
	return result

def student_classes_table(classes, nons, count):
	name = lambda c: c['name']
	adder = lambda id: _send('assignments', 'add_class_to_student', class_id = id)
	remover = lambda id: _send('assignments', 'remove_class_from_student', class_id = id)
	return _xaa_table(nons, classes, name, text.not_in_classes, text.in_classes, adder, remover, count)







def tag_users_and_nonusers(tun_table):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		filterbox(t.div(cls = 'buttonbar'), {'show_inactives': text.show_inactives, 'dont_limit': text.dont_limit})
		t.button(text.done, onclick = _send('admin', 'tag_users', finished = 'true'))
		t.div(tun_table, id = 'users_and_nonusers_table_container')
	return result

def tag_users_table(tag_name, users, nonusers, count):
	un_name = lambda user: user['username'] # ({user['first_name']} {user['last_name']})
	adder = lambda id: _send('admin', 'add_user_to_tag', user_id = id)
	remover = lambda id: _send('admin', 'remove_user_from_tag', user_id = id)
	return _xaa_table(nonusers, users, un_name, 'NOT Subscribers:', f'Subscribers (to {tag_name}):', adder, remover, count)


def user_tags(ut_table):
	return _x_tags(ut_table, 'user_tags_table_container', 'admin', 'user_tags')

def user_tags_table(user_tags, available_tags, count):
	adder = lambda id: _send('admin', 'add_tag_to_user', tag_id = id)
	remover = lambda id: _send('admin', 'remove_tag_from_user', tag_id = id)
	return _xaa_table(available_tags, user_tags, lambda tag: tag['name'], 'NOT Subscribed to:', 'Subscribed to:', adder, remover, count)


def choose_message_draft(drafts):
	result = t.div(t.div(info(text.choose_message_draft), id = 'detail_banner_container', cls = 'container'))
	with result:
		filterbox(t.div(cls = 'buttonbar'), {})
		t.div(choose_message_draft_table(drafts), id = 'choose_message_draft_table_container')
	return result

def choose_message_draft_table(drafts):
	result = t.table(cls = 'full_width')
	with result:
		for draft in drafts:
			with t.tr():
				t.td(f"{casual_date(draft['created'])}: {draft['teaser']}", cls = 'pointered', onclick = _send('messages', 'edit_message', message_id = draft['id'])) # note, 'teaser' is already a substring - no need to chop here
				if not draft['deleted']: # only allow "untrashed" messages to be trashed; can't "permanently" delete anything
					t.td(t.button(t.i(cls = 'i i-trash'), title = text.trash_draft, cls = 'red_bg', onclick = f"""messages.delete_draft_in_list({draft['id']}, "{text.delete_confirmation}")"""))
		t.tr(t.td(t.button(text.brand_new_message, onclick = _send('messages', 'brand_new_message')), _cancel_button(), align = 'left'))
	return result

def edit_message(message_id, content):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		t.div(raw(content) if content else '', contenteditable = 'true', id = f'edit_message_content_{message_id}', cls = 'edit_message_content') # raw(content) throws exception when content is ''
		t.div(id = f'attachments_for_message_{message_id}')
		with t.div(cls = 'buttonbar'):
			t.button(t.i(cls = 'i i-attach'), title = text.attach, onclick = f"messages.attach_upload({message_id})")
			t.button(t.i(cls = 'i i-all'), title = text.recipients, onclick = _send('messages', 'message_tags', message_id = message_id)),
			t.button(t.i(cls = 'i i-folder'), title = text.save_draft, onclick = f'messages.save_draft({message_id})') # ▼
			t.button(t.i(cls = 'i i-send'), title = text.send_message, onclick = f"messages.send_message({message_id})") # ►
			t.div(cls = 'spacer')
			t.button(t.i(cls = 'i i-trash'), title = text.delete_message, onclick = f"messages.delete_message({message_id}, true)")
	return result

def inline_reply_box(message_id, parent_mid, content = None):
	result = t.div(id = f"message_{message_id}", cls = 'container yellow_border')
	with result:
		t.div(raw(content) if content else '', contenteditable = 'true', id = f"edit_message_content_{message_id}", cls = 'edit_message_content',
		  onfocus = f'messages.start_saving(this, {message_id})', onblur = f'messages.stop_saving({message_id})') # raw(content) throws exception when content is ''
		t.div(id = f'attachments_for_message_{message_id}')
		with t.div(cls = 'buttonbar'):
			t.button(t.i(cls = 'i i-attach'), title = text.attach, onclick = f"messages.attach_upload({message_id})")
			t.button(t.i(cls = 'i i-all'), id = f"rr_all_{message_id}", title = text.reply_all, onclick = f'messages.reply_recipient_one({message_id})')
			t.button(t.i(cls = 'i i-one'), id = f"rr_one_{message_id}", cls = 'hide', title = text.reply_one, onclick = f'messages.reply_recipient_all({message_id})')
			t.button(t.i(cls = 'i i-send'), title = text.send_message,
				onclick = f'''messages.send_reply({message_id}, {parent_mid}, $('reply_recipient_{message_id}').dataset.replyrecipient)''') # ►
			t.div(cls = 'spacer')
			t.button(t.i(cls = 'i i-trash'), title = text.delete, onclick = f"""messages.delete_unsent_reply_draft({message_id}, "{text.delete_confirmation}")""")
			t.div(id = f"reply_recipient_{message_id}", cls = 'hide', data_replyrecipient = 'A')
	return result

def no_messages(searchtext = None):
	return t.div(t.p(text.not_found.format(searchtext = searchtext) if searchtext else text.no_messages))

def assignments(assignments):
	result = t.div(cls = 'container')
	class_name = None
	resource_name = None
	class_div = None
	week = None
	class_counter = 0
	right_page = False
	for assignment in assignments:
		# Insert page-break to go to new week ("left page") if we're on a new week
		if assignment['week'] != week:
			class_name = None # force reset of class, to make hr()s appropriate, etc.
			result.add(t.hr(cls = 'page_break_after')) # even first time 'round, when week is None, in order to get the first detail page to be a back-side (double-sided print)
			if not right_page and week != None:
				result.add(t.div(cls = 'page_break_after zero')) # a SECOND page-break, for a blank right page, so that starts are always on left pages
			week = assignment['week']
			right_page = False
			class_counter = 0
			start_date, end_date = casual_date2(assignment['start_date']), casual_date2(assignment['end_date'])
			header = f"{text.week} {week} ({start_date} - {end_date})"
			if False:
				header += f"- {assignment['first_name']} {assignment['last_name']}"
			result.add(t.div(header, cls = 'week_header'))
		if assignment['class_name'] != class_name:
			class_name = assignment['class_name']
			result.add(t.hr(cls = 'gray'))
			# Insert page-break to shift to "right page" if necessary:
			class_counter += 1
			if not right_page and class_counter > assignments_const.k_classes_per_page:
				result.add(t.div(cls = 'page_break_after zero'))
				right_page = True
		if assignment['resource_name'] != resource_name:
			resource_name = assignment['resource_name']
			full_class_name = class_name + (f'(S{assignment["section"]}) - ' if assignment['teacher'] else ' - ')
			result.add(t.div(full_class_name, t.em(resource_name), cls = 'assignment_header'))

		instruction = assignment['instruction']
		instruction = instruction.replace('{chapters}', str(assignment['chapters']))
		instruction = instruction.replace('{pages}', str(assignment['pages']))
		instruction = instruction.replace('{items}', str(assignment['items']))
		instruction = instruction.replace('{skips}', str(assignment['skips']) if assignment['skips'] else '')
		if assignment['optional']:
			instruction = '<b>[optional]</b> ' + instruction
		if assignment['teacher']:
			instruction = f'<b>{instruction}</b>'

		checkbox = t.input_(type = 'checkbox', onclick = f"assignments.mark_complete({assignment['assignment_id']}, {assignment['enrollment_id']}, this)")
		if assignment['complete']:
			checkbox['checked'] = 'checked'
		result.add(t.div(t.label(checkbox, raw(instruction))))

	return result

def messages(msgs, user_id, is_admin, stashable, last_thread_patriarch = None, skip_first_hr = False, searchtext = None, whole_thread = False):
	top = t.div(cls = 'container')
	parents = {None: top}
	for msg in msgs:
		if msg['sender_id'] == user_id and not msg['sent'] and msg['reply_to'] != None: # if this is a user's unsent reply (draft), then include it in editable, inline draft mode:
			last_thread_patriarch = msg['reply_chain_patriarch']
			html_message = inline_reply_box(msg['id'], msg['reply_to'], msg['message'])
		elif msg['sent']: # this test ensures we don't try to present draft messages that aren't replies - user has to re-engage with those in a different way ("new message", then select among drafts)... note that the data (msgs) DO include (or MAY include) non-reply (top-level parent) draft messages; we don't want those messages in our message list here
			last_thread_patriarch, html_message = message(msg, user_id, is_admin, stashable, last_thread_patriarch, skip_first_hr, searchtext = searchtext, whole_thread = whole_thread)
		parent = parents.get(msg['reply_to'], top)
		parent.add(html_message)
		parents[msg['id']] = html_message
	return top

def message(msg, user_id, is_admin, stashable, thread_patriarch = None, skip_first_hr = False, injection = False, searchtext = None, whole_thread = False):
	editable = msg['sender_id'] == user_id or is_admin
	cls = 'container'
	if injection:
		cls += ' injection'
	if whole_thread:
		cls += ' bluish'
	result = t.div(id = f"message_{msg['id']}", cls = cls)
	with result:
		continuation = False
		if skip_first_hr and thread_patriarch == None: # first time through, skip hr (just assign thread_patriarch):
			thread_patriarch = msg['reply_chain_patriarch']
		else: # thereafter, prepend each (next) msg with an hr() or "gray" hr() (for replies), to separate messages:
			if msg['reply_chain_patriarch'] == thread_patriarch:
				t.hr(cls = 'gray') # continued thread
				continuation = True
			else:
				t.hr() # new thread ... OR thread_patriarch is None because we're loading a set of newly-fetched messages, BUT, if this IS a reply, it's possible that the parent is sitting just above, from the last load (we lost track of that old thread_patriarch)... this is fine - it might be nice, actually, for really long reply-chains, to occasionally have the "reminder" when the user keeps scrolling to see more....)
				thread_patriarch = msg['reply_chain_patriarch']

		if msg['reply_to'] and not continuation: # then this msg is actually a reply, but the patriarch is elsewhere (e.g., stashed... or see above comment on t.hr()), so we need to provide the reply-prefix teaser:
			t.div(f'''Reply to "{msg['parent_teaser']}...":''', cls = 'italic')
		if msg['edited']:
			t.div(text.edited + ':', cls = 'italic bold')

		t.div(raw(re.sub(k_url_rec, k_url_replacement, msg['message']))) # replace url markdown "links" with real <a href>s

		if msg['attachments']:
			with t.div(id = f"attachments_for_message_{msg['id']}"):
				thumbnail_strip(msg['attachments'].split(','))

		with t.div(cls = 'buttonbar'):
			if stashable and not msg['stashed']: # the second test is a check; if not checked and the stash button is presented, and the user uses it on an already-stashed message, it would result in a db UNIQUE integrity error upon insert into message_stashed table
				t.button(t.i(cls = 'i i-stash'), title = text.stash, onclick = f"messages.stash({msg['id']})") # '▼'
			t.button(t.i(cls = 'i i-reply'), title = text.reply, onclick = _send('messages', 'compose_reply', message_id = msg['id'])) # '◄'
			if msg['pinned']:
				t.button(t.i(cls = 'i i-pin'), title = text.unpin, cls = 'selected', onclick = f"messages.unpin({msg['id']}, this)") # 'Ϯ'
			else:
				t.button(t.i(cls = 'i i-pin'), title = text.pin, onclick = f"messages.pin({msg['id']}, this)") # 'Ϯ'
			if editable:
				t.button(t.i(cls = 'i i-edit'), title = text.edit_message, onclick = _send('messages', 'edit_message', message_id = msg['id']))
			t.div(cls = 'spacer')
			with t.div():
				t.span(t.b('by '), msg['sender'])
		with t.div(cls = 'buttonbar'): # row 2 (looks nicer on phones; but consider reverting back to the 1-row motif for wider screens)
			max_recipients = 3
			all_recipients = '' if not msg['tags'] else msg['tags'].split(',')
			recipients = ', '.join(all_recipients[0:max_recipients]) # NOTE: would be nice if, in db.py, we could use GROUP_CONCAT(DISTINCT tag.name, ', '), to avoid this replace(',', ', '), but DISTINCT requires one arg only - can't provide a delimiter in that case, unfortunately
			if len(all_recipients) > max_recipients:
				recipients += ', ...'
			edit_button = t.button(t.i(cls = 'i i-all'), title = text.recipients,
								onclick = f"messages.change_recipients({msg['id']})") if editable else ''
			thread_button = t.button(t.i(cls = 'i i-thread'), title = text.thread,
								onclick = _send('messages', 'show_whole_thread', message_id = msg['id'], patriarch_id = msg['reply_chain_patriarch'])) if not whole_thread else '' # no thread-button when whole-thread is already expanded
			isodate = local_date_iso(msg["sent"]).isoformat()[:-6] # [:-6] to trim offset from end, as javascript code will expect a naive iso variant, and will interpret as "local"
			t.div(cls = 'spacer')
			t.span(t.b(' to '), edit_button, recipients, thread_button, ' · ')
			t.span(text.just_now if injection else '...', cls = 'time_updater', data_isodate = isodate) # 'sent' date/time
			if editable:
				t.button(t.i(cls = 'i i-trash'), title = text.delete_message, onclick = f"messages.delete_message({msg['id']}, false)")
	return thread_patriarch, result


def message_tags(mt_table):
	return _x_tags(mt_table, 'message_tags_table_container')
	
def message_tags_table(message_tags, available_tags, mid, count):
	adder = lambda id: _send('messages', 'add_tag_to_message', message_id = mid, tag_id = id)
	remover = lambda id: _send('messages', 'remove_tag_from_message', message_id = mid, tag_id = id)
	return _xaa_table(available_tags, message_tags, lambda tag: tag['name'],  text.not_recipients, text.recipients, adder, remover, count, None, 'messages', 'message_tags')

def thumbnail_strip(filenames):
	result = t.div(cls = 'thumbnail_strip')
	cache_bust = randint(1000, 9999)
	with result:
		for name in filenames:
			path = f'/{k_upload_path}{name}'
			lilname = name.lower()
			poster_path = path + k_thumb_appendix
			if lilname.endswith(k_video_formats):
				onclick = f'messages.play_video("{path}", "{poster_path}")'
			elif lilname.endswith(k_image_formats):
				onclick = f'messages.play_image("{path}")'
			elif lilname.endswith(k_pdf_formats):
				onclick = f'messages.play_pdf("{path}")'
			t.span(t.img(src = f'/{k_upload_path}{name}{k_thumb_appendix}?cache_bust={cache_bust}', alt = name), onclick = onclick)
	return result


# Utils -----------------------------------------------------------------------


def _doc(css = None): # `css` expected to be a list/tuple of filenames, like ('default.css', 'extra.css', )
	d = dominate_document(title = text.doc_title)
	with d.head:
		t.meta(name = 'viewport', content = 'width=device-width, initial-scale=1')
		if css:
			for c in css:
				t.link(href = f'/static/css/{c}?{cache_buster}', rel = 'stylesheet')
		t.script(raw('let FF_FOUC_FIX;')) # trick to avoid possible FOUC complaints (https://stackoverflow.com/questions/21147149/flash-of-unstyled-content-fouc-in-firefox-only-is-ff-slow-renderer) - note that this doesn't cause the warning to go away, it seems, but may cause the problem (if it actually ever visually exhibited) to go away.

	return d


def _ws_submit_button(title: str, field_names: list):
	args = ', '.join([f"'{name}': $('{name}').value" for name in field_names])
	return t.button(title, id = 'submit', type = 'submit', onclick = f'submit_fields({{ {args} }})')


def _x_tags(xt_table, div_id, task_app = None, task = None):
	result = t.div(cls = 'center_flex container')
	with result:
		t.div(id = 'detail_banner_container', cls = 'container') # for later ws-delivered banner messages
		filterbox(t.div(cls = 'buttonbar'), {'dont_limit': text.dont_limit})
		if task_app: # and task, presumably (assert?!)
			t.button(text.done, onclick = _send(task_app, task, finished = 'true'))
		t.div(xt_table, id = div_id)
	return result

def _xaa_table(availables, assigneds, name_fetcher, left_title, right_title, adder, remover, count, extra_columns = None, task_app = None, task = None):
	add_done_button = True if task_app and len(assigneds) > 0 else False
	if add_done_button:
		done_button = t.button(text.done, onclick = _send(task_app, task, finished = 'true'))
	#add_cancel_button = True if task_app and len(assigneds) == 0 else False
	#if add_cancel_button:
	#	cancel_button = t.button(text.cancel, onclick = _send(task_app, task, finished = 'false'))
	result = t.table()
	with result:
		with t.tr():
			t.th(left_title, t.br(), text.click_to_add, align = 'right')
			t.th(right_title, t.br(), text.click_to_remove, align = 'left')
			for column in (extra_columns if extra_columns else []):
				t.th(column.column_title)
		left_elide = text.filter_for_more if count and count == len(availables) else ''
		right_elide = text.filter_for_more if count and count == len(assigneds) else ''
		for line in range(max(len(availables), len(assigneds))):
			available = availables.pop(0) if len(availables) > 0 else {}
			assigned = assigneds.pop(0) if len(assigneds) > 0 else {}
			if not assigned and not available:
				break # done
			with t.tr():
				avd = t.div(name_fetcher(available), cls = 'container gray pointered', onclick = adder(available['id'])) if available else ''
				t.td(avd, align = 'right')
				if assigned:
					t.td(t.div(name_fetcher(assigned), cls = 'container pointered', onclick = remover(assigned['id'])), align = 'left')
					for column in (extra_columns if extra_columns else []):
						t.td(column.render(assigned['id'], assigned[column.field_name]))
				elif add_done_button:
					t.td(done_button)
					add_done_button = False # just add once
		if left_elide or right_elide:
			t.tr(t.td(left_elide, align = 'right'), t.td(right_elide, align = 'left'))
		if add_done_button:
			t.tr(t.td(), t.td(done_button))
	return result


k_fake_localtz = 'America/Los_Angeles' # TODO - implement user-local timezones (this will be a per-user field in db)!
def local_date_iso(raw_date, zone_info = None):
	assert raw_date != None
	zi = zone_info or ZoneInfo(k_fake_localtz) # manage all datetimes wrt/ user's local tz, so that "yesterday" means that from the local user's perspective, not from UTC or server-local
	return datetime.fromisoformat(raw_date).astimezone(zi).astimezone(None) # no need to .replace(tzinfo = timezone.utc) on fromisoformat result because we put the trailing 'Z' on dates in the db, so this fromisoformat() will interpret the datetime not as naive, but at explicitly UTC

def casual_date(raw_date): # NOTE: we have an equivalent version of this in Javascript, client-side, in order to update periodically.
	zi = ZoneInfo(k_fake_localtz)
	dt = local_date_iso(raw_date, zi)
	now = datetime.now(timezone.utc).astimezone(zi)
	today = datetime.combine(now.date(), datetime.min.time(), now.tzinfo)
	if now - dt < timedelta(hours = 1): # within the last hour
		diff = now - dt
		if diff.seconds < 2:
			return 'just now'
		elif diff.seconds < 60:
			return f"{diff.seconds} seconds ago"
		else:
			return f"{diff.seconds // 60} minutes ago"
	elif dt >= today: # earlier today
		return dt.strftime('%I:%M %p')
	elif today - timedelta(days = 1) < dt < today: # yesterday
		return f"yesterday @ {dt.strftime('%I:%M %p')}"
	else: # before yesterday
		return dt.strftime('%m/%d/%Y')

def casual_date2(raw_date):
	zi = ZoneInfo(k_fake_localtz)
	dt = local_date_iso(raw_date, zi)
	now = datetime.now(timezone.utc).astimezone(zi)
	today_zero = datetime.combine(now.date(), datetime.min.time(), now.tzinfo)
	dt_zero = datetime.combine(dt.date(), datetime.min.time(), now.tzinfo)
	if today_zero == dt_zero:
		return text.today
	elif today_zero.year == dt.year:
		return dt.strftime('%b %d')
	else:
		return dt.strftime('%m/%d/%Y')


def droplist_button(container, id, hint, options, title = None, selected_id = None):
	if not title:
		title = options[0][0]
	with container:
		with t.button(title + ' ▾', cls = 'dropdown', title = hint, onclick = f'assignments.show_dropdown_options("{id}", this)'):
			with t.div(id = id, cls = 'dropdown_content hide'):
				t.div(title, onclick = 'assignments.subject_filter(0)')
				for option_name, option_id in options:
					t.div(option_name, onclick = f'assignments.subject_filter({option_id})')


@dataclass(slots = True, frozen = True)
class Input: # HTML input element, `frozen` with the intention of avoiding side-effects of a build() on a future use of the input; note that fields.py contains "constant" fields used by all, to reduce the need to re-build the same ones over and over, but an assignment to a member variable in build() (or via some other way) would then change the input for all other uses system-wide!
	label: str | None = None # label, or None, to indicate that label should be auto-calculated by name arg (in build()) as name.replace('_', ' ').title()
	placeholder: str | bool = True # placeholder string (for inside field box) OR `False` (for none) or `True` to use `label` as placeholder (instead of as a prompt, in front)
	type_: str = 'text' # HTML `input` arg `type`, such as 'password' for a password input field; defaults to plain 'text' type
	autofocus: bool = False # True if this field should get autofocus upon form load
	attrs: dict = dataclass_field(default_factory = dict) # other HTML field attrs like 'maxlength', 'autocomplete', etc.
	bool_attrs: list = dataclass_field(default_factory = list) # other HTML bool attrs like 'readonly'
	prompt_note: str | None = None

	def __post_init__(self):
		if self.autofocus:
			self.bool_attrs.append('autofocus')
		self.attrs.update(dict([(f, f) for f in self.bool_attrs])) # Note that use of "true" (or "false") is forbidden, but attr="attr" is perfectly normal alternative to simply declaring the attr without assignment (see HTML spec)  (Note that dominate converts True bools to the attr name, anyway, also guarding against use of forbidden "true" or "false" values - so we're covered here even if we did this incorrectly.)

	def build(self, name: str, data: dict | None = None, label_prefix: str | None = None, invalids: dict | None = None) -> t.html_tag:
		label = self.label
		if not label:
			label = name.replace('_', ' ')
			if label_prefix:
				label = label_prefix + ' ' + label
			label = label.capitalize()
		value = data[name] if data else None
		attrs = copy(self.attrs) # don't change attrs - this is just a build() instrument; should not change self!
		if data and self.type_ == 'checkbox':
			if value:
				attrs['checked'] = 'checked'  # would prefer to make these mods to 'i' (t.input_), later, but it seems impossible
			elif 'checked' in attrs: # (and NOT value) - default value vestige to clear!
				del attrs['checked'] # would prefer to make these mods to 'i' (t.input_), later, but it seems impossible

		i = t.input_(name = name, id = name, type = self.type_ if self.type_ else 'text', **(attrs))
		if self.type_ == 'checkbox' and 'onclick' not in attrs: # don't do the following if there's already a script assigned, to do some other thing
			i['onclick'] = "this.value = this.checked ? '1' : '0';"
		if value:
			i['value'] = value
		if self.placeholder and self.type_ in ('text', 'search', 'url', 'tel', 'email', 'password', 'number'):
			if type(self.placeholder) == str:
				i['placeholder'] = self.placeholder
			elif self.placeholder == True:
				i['placeholder'] = label
			result = t.label(i)
		elif self.type_ != 'hidden': # (unless this is a 'hidden') no placeholder was provided; so pre-prompt with label:
			if self.type_ == 'checkbox':
				result = t.label(i, label)
			else:
				result = t.label(label + ':', t.br(), i)
		else:
			result = i
		if invalids and name in invalids.keys():
			result = t.div(result, t.span(invalids[name], cls = 'invalid container'))
		elif self.prompt_note: # don't really need both - prompt_note is good clarification for field on first encounter, but no need to duplicate if we've got invalids and need to draw focus to that (above)....
			result = t.div(t.div(self.prompt_note), result, cls = 'container')
		return result

