__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from copy import copy
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from datetime import datetime

from dominate import document
from dominate import tags as t
from dominate.util import raw

from . import text


# Logging ---------------------------------------------------------------------

l = logging.getLogger(__name__)


# Shortcuts -----------------------------------------------------------------------

_js_ws = lambda ws_url: raw(f'var ws = new WebSocket("{ws_url}");')
_ws_scripts = lambda ws_url, scripts: [t.script(_js_ws(ws_url))] + [_wrap_script(script) for script in scripts]
_yes_or_no = lambda value: 'yes' if value else 'no'
_format_phone = lambda num: '(' + num[-10:-7] + ') ' + num[-7:-4] + '-' + num[-4:] # TODO: international extention prefixes [0:-11]


# Whole documents -------------------------------------------------------------

def test(person = None):
	d = _doc('Test')
	with d:
		if person:
			t.div(f'Hello {person["first_name"]}!')
		t.div('This is a test')
	return d.render()


def join(ws_url: str, html_fields: list, field_names: list):
	fieldset = ws_fieldset(text.name, html_fields, field_names, text.next)
	return _fieldset_doc(text.join, fieldset, _ws_scripts(ws_url, ('basic.js', 'ws.js', 'join.js', 'submit.js')))

def invite(ws_url: str, html_fields: list, field_names: list):
	fieldset = ws_fieldset(text.name, html_fields, field_names, text.next)
	return _fieldset_doc(text.invite, fieldset, _ws_scripts(ws_url, ('basic.js', 'ws.js', 'invite.js', 'submit.js')))


def list_people(persons):
	d = _doc(text.list_people)
	with d:
		with t.table():
			for person in persons:
				with t.tr(cls = 'selectable_row', onclick = f"location.assign('/person/{person['id']}');"):
					t.td(person['first_name'], align = 'right')
					t.td(person['last_name'], align = 'left')
	return d.render()

def filterbox():
	return Input(text.filtersearch, type_ = 'search', autofocus = True,
					attrs = {'autocomplete': 'off', 'oninput': 'filtersearch(this.value, $("show_inactives").checked)'}).build('filtersearch')

def users(ws_url, users):
	d = _doc(text.users)
	with d:
		t.div(id = 'gray_screen', cls = 'gray_screen hide') # invisible at first; for "dialog box" divs, later
		t.div(id = 'dialog_container', cls = 'dialog_container small hide')
		with t.div(id = 'page'):
			t.div(t.div(id = 'message_container', cls = 'container')) # for later ws-delivered messages
			show_inactives = Input(text.show_inactives, type_ = 'checkbox',
										 attrs = {'onclick': 'filtersearch($("filtersearch").value, this.checked);'})
			t.span(filterbox(), show_inactives.build('show_inactives'))
			t.div(user_table(users), id = 'content_container', cls = 'container')
		[script for script in _ws_scripts(ws_url, ('basic.js', 'ws.js', 'users.js', 'submit.js'))]
	return d.render()


# Divs/fieldsets/partials -----------------------------------------------------


def info(msg: str):
	return t.div(msg, cls = 'info')

def error(msg: str):
	return t.div(msg, cls = 'error')

def warning(msg: str):
	return t.div(msg, cls = 'warning')

def test1(msg: str):
	return t.div(msg)

def join_succeeded():
	return t.div('Join succeeded!') # TODO: improve!

def invite_succeeded(person):
	return t.div(f"{person['first_name']} {person['last_name']} has been invited!") # TODO: improve!
	

def ws_fieldset(fieldset_title: str, html_fields: list, field_names: list, button_title: str = text.save):
	button = _ws_submit_button(button_title, field_names)
	return fieldset(fieldset_title, html_fields, button)

def fieldset(title: str, html_fields: list, button: t.button) -> t.fieldset:
	result = t.fieldset()
	with result:
		t.legend(title + '...')
		for field in html_fields:
			t.div(field)
		t.div(button)
	return result

def user_table(users):
	table = t.table(cls = 'full_width')
	with table:
		with t.tr():
			t.th('Username')
			t.th('Name')
			t.th('Created')
			t.th('Verified')
			t.th('Active')
		for user in users:
			with t.tr():
				t.td(user['username'], cls = 'pointered', onclick = f"get_user_detail({user['user_id']});")
				t.td(f"{user['first_name']} {user['last_name']}", cls = 'pointered', onclick = f"get_person_detail({user['person_id']});")
				t.td(datetime.fromisoformat(user['created']).strftime('%m/%d/%Y %H:%M'))
				t.td(user['verified'] or '', cls = 'pointered', onclick = f"get_user_detail({user['user_id']});")
				t.td(_yes_or_no(int(user['active'])), align = 'center', cls = 'pointered', onclick = f"get_user_detail({user['user_id']});")
	return table

def detail(fields, data, more_func):
	result = t.div(t.div(id = 'detail_message_container', cls = 'container')) # for later ws-delivered messages
	for name, field in fields.items():
		result.add(t.div(field.html_field.build(name, data)))
	with result:
		if more_func:
			t.div(t.button(text.more_detail, onclick = f'{more_func}();'))
		with t.div():
			with t.span():
				_ws_submit_button(text.save, data.keys())
				t.button(text.cancel, onclick = 'cancel()')
	return result

def more_person_detail(emails, phones):
	result = t.div(t.div(id = 'detail_message_container', cls = 'container')) # for later ws-delivered messages
	with result:
		with t.fieldset():
			t.legend(text.emails)
			for email in emails:
				t.div(t.span(email['email'], t.button(text.edit, onclick = f"get_email_detail({email['id']});")))
			t.div(t.button(text.add, onclick = 'get_email_detail(0)'))
		with t.fieldset():
			t.legend(text.phones)
			for phone in phones:
				t.div(t.span(_format_phone(phone['phone']), t.button(text.edit, onclick = f"get_phone_detail({phone['id']});")))
			t.div(t.button(text.add, onclick = 'get_phone_detail(0)'))
		t.div(t.button(text.close, onclick = 'get_detail("person", 0)'))
	return result

def mpd_detail(fields, data):
	result = t.div(t.div(id = 'detail_message_container', cls = 'container')) # for later ws-delivered messages
	for name, field in fields.items():
		result.add(t.div(field.html_field.build(name, data)))
	with result:
		with t.div():
			with t.span():
				_ws_submit_button(text.save, data.keys(), 'submit_mpd_fields')
				t.button(text.cancel, onclick = 'get_more_person_detail()')
	return result
	
# Utils -----------------------------------------------------------------------


k_cache_buster = '?v=1'
def _doc(title, css = None):
	d = document(title = text.doc_prefix + title)
	with d.head:
		t.meta(name = 'viewport', content = 'width=device-width, initial-scale=1')
		t.link(href = '/static/css/common.css' + k_cache_buster, rel = 'stylesheet')
		if css:
			for c in css:
				t.link(href = f'/static/css/{c}' + k_cache_buster, rel = 'stylesheet')
	return d

def _fieldset_doc(title: str, fieldset: t.fieldset, additions: list | None = None):
	doc = _doc(title)
	doc.add(t.div(id = 'message_container', cls = 'container')) # add message container for later ws-delivered messages
	doc.add(t.div(fieldset, id = 'content_container', cls = 'container'))
	if additions:
		for addition in additions:
			doc.add(addition)
	return doc.render()

def _wrap_script(script):
	return t.script(src = f'/static/js/{script}')

def _wrap_scripts(scripts):
	result = []
	if scripts:
		for script in scripts:
			result.append(_wrap_script(script))
	return result

def _ws_submit_button(title: str, field_names: list, function_name: str = 'submit_fields'):
	args = ', '.join([f"'{name}': $('{name}').value" for name in field_names])
	return t.button(title, id = 'submit', type = 'submit', onclick = f'{function_name}({{ {args} }})')


@dataclass(slots = True, frozen = True)
class Input: # HTML input element, `frozen` with the intention of avoiding side-effects of a build() on a future use of the input; note that fields.py contains "constant" fields used by all, to reduce the need to re-build the same ones over and over, but an assignment to a member variable in build() (or via some other way) would then change the input for all other uses system-wide!
	label: str | None = None # label, or None, to indicate that label should be auto-calculated by name arg (in build()) as name.replace('_', ' ').title()
	placeholder: str | bool = True # placeholder string (for inside field box) OR `False` (for none) or `True` to use `label` as placeholder (instead of as a prompt, in front)
	type_: str = 'text' # HTML `input` arg `type`, such as 'password' for a password input field; defaults to plain 'text' type
	autofocus: bool = False # True if this field should get autofocus upon form load
	attrs: dict = dataclass_field(default_factory = dict) # other HTML field attrs like 'maxlength', 'autocomplete', etc.
	bool_attrs: list = dataclass_field(default_factory = list) # other HTML bool attrs like 'readonly'

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
		i = t.input_(name = name, id = name, type = self.type_ if self.type_ else 'text', **(self.attrs))
		value = data[name] if data else None
		if value:
			i['value'] = value
		if self.type_ == 'checkbox':
			if value:
				i['checked'] = 'checked'
			if 'onclick' not in self.attrs: # don't do the following if there's already a script assigned, to do some other thing
				i['onclick'] = "this.value = this.checked ? '1' : '0';"
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
			result = t.div(result, t.span(invalids[name], cls = 'invalid'))
		return result

