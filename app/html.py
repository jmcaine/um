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


# Shortcuts -------------------------------------------------------------------

checkbox_value = lambda data, field: 1 if data.get(field) in (1, '1', 'on') else 0

_scripts = lambda scripts: [t.script(src = f'/static/js/{script}') for script in scripts]
_yes_or_no = lambda value: 'yes' if value else 'no'
_format_phone = lambda num: '(' + num[-10:-7] + ') ' + num[-7:-4] + '-' + num[-4:] # TODO: international extention prefixes [0:-11]
_send = lambda app, task, **args: f'{app}.send("{task}"' + (f', {{ {", ".join([f"{key}: {value}" for key, value in args.items()])} }})' if args else ')')

_cancel_button = lambda title = text.cancel: t.button(title, onclick = 'main.send("finish")')

# Pages -----------------------------------------------------------------------

# Note that there's really only one "page", main()...

def main(ws_url: str):
	d = _doc('')
	with d:
		t.div(id = 'gray_screen', cls = 'gray_screen hide') # invisible at first; for "dialog box" divs, later
		t.div(id = 'dialog_container', cls = 'dialog_container small hide') # invisible at first....
		with t.div(id = 'page'):
			t.div(t.div(id = 'banner_container', cls = 'container')) # for later ws-delivered banner messages
			with t.div(id = 'content_container', cls = 'container'):
				t.div("Loading...")
		with t.div(id = 'scripts', cls = 'container'):
			t.script(raw(f'var ws = new WebSocket("{ws_url}");'))
			[script for script in _scripts(('basic.js', 'ws.js', 'persistence.js', 'main.js', 'admin.js', 'submit.js', 'messages.js'))]
	return d.render()


def test(person = None):
	d = _doc('Test')
	with d:
		if person:
			t.div(f'Hello {person["first_name"]}!')
		t.div('This is a test')
	return d.render()


# Main-content "Pages" --------------------------------------------------------

def login_or_join():
	return t.div(
		t.div(text.welcome),
		t.div(t.button(text.login, onclick = 'main.send("login")'), cls = 'center'),
		t.div(t.button(text.join, onclick = 'main.send("join")'), cls = 'center'),
	)

def messages(admin):
	result = t.div()
	with result:
		with t.div(cls = 'button_band'):
			#    ҉ Ѱ Ψ Ѫ Ѭ Ϯ ϖ Ξ Δ ɸ Θ Ѥ ΐ Γ Ω ¤ ¥ § Þ × ÷ þ Ħ ₪ ☼ ♀ ♂ ☺ ☻ ♠ ♣ ♥ ♦
			t.button('+', title = 'new message', onclick = 'send_task("new_message")')
			filterbox()
			filterbox_checkbox(text.deep_search, 'deep_search')
			with t.div(cls = 'right'):
				t.button('...', title = text.change_settings, onclick = 'send_task("settings")')
				if admin:
					t.button('Ѫ', title = text.admin, onclick = 'admin.send("users")')
				t.button('Θ', title = text.logout, onclick = 'send_task("logout")')
		t.hr()
		t.div('Main messages...')

	return result



def users_page(users):
	result = t.div(admin_button_band())
	with result:
		t.hr()
		admin_menu_button_band((t.button('+', title = text.invite_new_user, onclick = 'main.send("invite")'),))
		t.div(user_table(users), id = 'user_table_container')
	return result

def tags_page(tags):
	result = t.div(admin_button_band())
	with result:
		t.hr()
		admin_menu_button_band((t.button('+', title = text.create_new_tag, onclick = 'admin.send("new_tag")'),))
		t.div(tag_table(tags), id = 'tag_table_container')
	return result


# Divs/fieldsets/partials -----------------------------------------------------


def info(msg: str):
	return t.div(msg, cls = 'info')

def error(msg: str):
	return t.div(msg, cls = 'error')

def warning(msg: str):
	return t.div(msg, cls = 'warning')

def test1(msg: str):
	return t.div(msg)


def build_fields(fields, data = None, label_prefix = None, invalids = None):
	return [field.html_field.build(name, data, label_prefix, invalids) \
		for name, field in fields.items()]

def login(fields):
	button = _ws_submit_button(text.login, fields.keys())
	forgot = t.button(text.forgot_password, onclick = 'main.send("forgot_password")')
	result = fieldset(text.login, build_fields(fields), button, forgot)
	return result

def forgot_password(fields):
	button = _ws_submit_button(text.send, fields.keys())
	result = fieldset(text.password_reset, build_fields(fields), button)
	return result


def admin_button_band():
	result = t.div(cls = 'button_band')
	with result:
		filterbox()
		filterbox_checkbox(text.show_inactives, 'show_inactives')
		with t.div(cls = 'right'):
			t.button('...', title = text.change_settings, onclick = 'main.send("settings")')
			t.button('Ξ', title = text.messages, onclick = 'messages.send("messages")')
			t.button('Θ', title = text.logout, onclick = 'main.send("logout")')
	return result

def admin_menu_button_band(left_buttons):
	result = t.div(*left_buttons, cls = 'button_band')
	with result:
		with t.div(cls = 'right'):
			t.button('☺', title = text.users, onclick = 'admin.send("users")')
			t.button('#', title = text.tags, onclick = 'admin.send("tags")')
	return result


def filterbox(extra = '$("show_inactives").checked'): # set extra = 'false' to remove extra
	return Input(text.filtersearch, type_ = 'search', autofocus = True, attrs = {
		'autocomplete': 'off',
		'oninput': _send('main', 'filtersearch', searchtext = 'this.value', include_extra = extra),
	}).build('filtersearch')

def filterbox_checkbox(label, name):
	return Input(label, type_ = 'checkbox', attrs = {
		'onclick': _send('main', 'filtersearch', searchtext = '$("filtersearch").value', include_extra = 'this.checked'),
	}).build(name)


def fieldset(title: str, html_fields: list, button: t.button, alt_button: t.button = _cancel_button(), more_func: str | None = None) -> t.fieldset:
	result = t.fieldset()
	with result:
		t.legend(title + '...')
		for field in html_fields:
			t.div(field)
		if more_func:
			t.div(t.button(text.more_detail, onclick = more_func))
		if alt_button:
			t.div(t.span(button, alt_button))
		else:
			t.div(button)
	return result

def user_table(users):
	result = t.table(cls = 'full_width')
	user_detail = lambda user: _send('admin', 'user_detail', id = user['user_id'])
	with result:
		with t.tr(cls = 'midlin'):
			t.th('Username', align = 'right')
			t.th('Name', align = 'left')
			t.th('Created', align = 'center')
			t.th('Verified', align = 'center')
			t.th('Active', align = 'center')
		for user in users:
			with t.tr(cls = 'midlin'):
				t.td(user['username'], cls = 'pointered', align = 'right', onclick = user_detail(user))
				t.td(f"{user['first_name']} {user['last_name']}", cls = 'pointered', align = 'left', onclick = _send('admin', 'person_detail', id = user['person_id']))
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
				t.td(tag['num_subscribers'], cls = 'pointered', align = 'center', onclick = _send('admin', 'tag_users', tag_id = tag['id'], tag_name = f'"{tag["name"]}"'))
	return result


def dialog(title, html_fields, field_names, button_title = text.save, alt_button: t.button = _cancel_button(), more_func = None):
	return t.div(
		t.div(id = 'detail_banner_container', cls = 'container'), # for later ws-delivered banner messages
		fieldset(title, html_fields, _ws_submit_button(button_title, field_names), alt_button, more_func),
	)

def dialog2(title, fields, data = None, button_title = text.save, alt_button: t.button = _cancel_button(), more_func = None):
	return dialog(title, build_fields(fields, data), fields.keys(), button_title, alt_button, more_func)


def more_person_detail(person_id, emails, phones):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		with t.fieldset():
			t.legend(text.emails)
			for email in emails:
				t.div(t.span(
					email['email'],
					t.button(text.edit, onclick = _send('admin', 'email_detail', person_id = person_id, id = email['id'])),
					t.button(text.delete, onclick = f'delete_email({email["id"]})'),
				))
			t.div(t.button(text.add, onclick = _send('admin', 'email_detail', person_id = person_id,  id = 0)))
		with t.fieldset():
			t.legend(text.phones)
			for phone in phones:
				t.div(t.span(
					_format_phone(phone['phone']),
					t.button(text.edit, onclick = _send('admin', 'phone_detail', person_id = person_id, id = phone['id'])),
					t.button(text.delete, onclick = f'delete_phone({phone["id"]})'),
				))
			t.div(t.button(text.add, onclick = _send('admin', 'phone_detail', person_id = person_id, id = 0)))
		t.div(_cancel_button(text.done)) # cancel just reverts to prior task; added/changed emails/phones are saved - those deeds are done, we're just "closing" this more_person_detail portal
	return result


def tag_users_and_nonusers(tun_table):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		with t.div(cls = 'button_band'):
			t.div(filterbox())
			filterbox_checkbox(text.show_inactives, 'show_inactives')
		t.div(tun_table, id = 'users_and_nonusers_table_container')
	return result

def tag_users_and_nonusers_table(tag_name, users, nonusers):
	un_name = lambda user: f"{user['username']} ({user['first_name']} {user['last_name']})" if user else ''
	result = t.table(cls = 'full_width')
	with result:
		with t.tr(cls = 'midlin'):
			t.th(f'Subscribed to {tag_name}', align = 'right')
			t.th(t.button(text.done, onclick = _send('admin', 'tag_users', finished = 'true')), colspan = 2)
			t.th('NOT Subscribed', align = 'left')
		for count in range(15): # TODO: 15 is hardcode equivalent to db/sql 'limit'; that is, the active "list size" - 'nonusers', here, COULD actually be bigger than 15, so... limiting here, as well
			user = users.pop(0) if len(users) > 0 else {}
			nonuser = nonusers.pop(0) if len(nonusers) > 0 else {}
			if not user and not nonuser:
				break # done
			with t.tr(cls = 'midlin'):
				t.td(un_name(user), align = 'right')
				t.td(t.button('-', cls = 'singleton_button red_bg', onclick = _send('admin', 'remove_user_from_tag', user_id = user['id'])) if user else '')
				t.td(t.button('+', cls = 'singleton_button green_bg', onclick = _send('admin', 'add_user_to_tag', user_id = nonuser['id'])) if nonuser else '')
				t.td(un_name(nonuser), align = 'left')
	return result



def user_tags(ut_table):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		with t.div(cls = 'button_band'):
			t.div(filterbox())
			filterbox_checkbox(text.show_inactives, 'show_inactives')
		t.div(ut_table, id = 'user_tags_table_container')
	return result

def user_tags_table(user_tags, other_tags):
	result = t.table(cls = 'full_width')
	with result:
		with t.tr(cls = 'midlin'):
			t.th(f'Subscribed', align = 'right')
			t.th(t.button(text.done, onclick = _send('admin', 'user_tags', finished = 'true')), colspan = 2)
			t.th('NOT Subscribed', align = 'left')
		for count in range(15): # TODO: 15 is hardcode equivalent to db/sql 'limit'; that is, the active "list size" - 'other_tags', here, COULD actually be bigger than 15, so... limiting here, as well
			utag = user_tags.pop(0) if len(user_tags) > 0 else {}
			otag = other_tags.pop(0) if len(other_tags) > 0 else {}
			if not utag and not otag:
				break # done
			with t.tr(cls = 'midlin'):
				t.td(utag.get('name', ''), align = 'right')
				t.td(t.button('-', cls = 'singleton_button red_bg', onclick = _send('admin', 'remove_tag_from_user', tag_id = utag['id'])) if utag else '')
				t.td(t.button('+', cls = 'singleton_button green_bg', onclick = _send('admin', 'add_tag_to_user', tag_id = otag['id'])) if otag else '')
				t.td(otag.get('name', ''), align = 'left')
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


def _ws_submit_button(title: str, field_names: list):
	args = ', '.join([f"'{name}': $('{name}').value" for name in field_names])
	return t.button(title, id = 'submit', type = 'submit', onclick = f'submit_fields({{ {args} }})')


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
			result = t.div(result, t.span(invalids[name], cls = 'invalid'))
		return result

