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

_scripts = lambda scripts: [t.script(src = f'/static/js/{script}') for script in scripts]
_yes_or_no = lambda value: 'yes' if value else 'no'
_format_phone = lambda num: '(' + num[-10:-7] + ') ' + num[-7:-4] + '-' + num[-4:] # TODO: international extention prefixes [0:-11]
_send_task = lambda task, **args: f'send_task("{task}"' + (f', {{ {", ".join([f"{key}: {value}" for key, value in args.items()])} }})' if args else ')')


CANCEL_BUTTON = t.button(text.cancel, onclick = 'cancel()')

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
			[script for script in _scripts(('basic.js', 'ws.js', 'persistence.js', 'main.js', 'admin.js', 'submit.js', 'users.js', 'messages.js'))]
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
		t.div(t.button(text.login, onclick = 'send_task("login")'), cls = 'center'),
		t.div(t.button(text.join, onclick = 'send_task("join")'), cls = 'center'),
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
					t.button('Ѫ', title = text.admin, onclick = 'send_task("admin_screen")')
				t.button('Θ', title = text.logout, onclick = 'send_task("logout")')

		t.hr()
		t.div('Main messages...')

	return result



def users_page(users):
	result = t.div(admin_button_band())
	with result:
		t.hr()
		admin_menu_button_band((t.button('+', title = text.invite_new_user, onclick = 'send_task("invite")'),))
		t.div(user_table(users), id = 'user_table')
	return result

def tags_page(tags):
	result = t.div(admin_button_band())
	with result:
		t.hr()
		admin_menu_button_band((t.button('+', title = text.create_new_tag, onclick = 'send_task("admin_new_tag")'),))
		t.div(tag_table(tags), id = 'tag_table')
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
	forgot = t.button(text.forgot_password, onclick = 'send_task("forgot_password")')
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
			t.button('...', title = text.change_settings, onclick = 'send_task("settings")')
			t.button('Ξ', title = text.messages, onclick = 'send_task("messages")')
			t.button('Θ', title = text.logout, onclick = 'send_task("logout")')
	return result

def admin_menu_button_band(left_buttons):
	result = t.div(*left_buttons, cls = 'button_band')
	with result:
		with t.div(cls = 'right'):
			t.button('☺', title = text.users, onclick = 'send_task("admin_users")')
			t.button('#', title = text.tags, onclick = 'admin.send("tags")')
	return result


def filterbox():
	return Input(text.filtersearch, type_ = 'search', autofocus = True, attrs = {
		'autocomplete': 'off',
		'oninput': _send_task('filtersearch', searchtext = 'this.value', include_extra = '$("show_inactives").checked'),
	}).build('filtersearch')

def filterbox_checkbox(label, name):
	return Input(label, type_ = 'checkbox', attrs = {'onclick': _send_task('filtersearch', searchtext = '$("filtersearch").value', include_extra = 'this.checked')}).build(name)

def filterbox_plain():
	return Input(text.filtersearch, type_ = 'search', autofocus = True,
					attrs = {'autocomplete': 'off', 'oninput': 'filtersearch(this.value, false)'}).build('filtersearch')



def fieldset(title: str, html_fields: list, button: t.button, alt_button: t.button = CANCEL_BUTTON, more_func: str | None = None) -> t.fieldset:
	result = t.fieldset()
	with result:
		t.legend(title + '...')
		for field in html_fields:
			t.div(field)
		if more_func:
			t.div(t.button(text.more_detail, onclick = f'send_task("{more_func}")'))
		if alt_button:
			t.div(t.span(button, alt_button))
		else:
			t.div(button)
	return result

def user_table(users):
	result = t.table(cls = 'full_width')
	user_detail = lambda user: _send_task('detail', table = '"user"', id = user['user_id'])
	with result:
		with t.tr():
			t.th('Username')
			t.th('Name')
			t.th('Created')
			t.th('Verified')
			t.th('Active')
		for user in users:
			with t.tr():
				t.td(user['username'], cls = 'pointered', onclick = user_detail(user))
				t.td(f"{user['first_name']} {user['last_name']}", cls = 'pointered', onclick = _send_task('detail', table = '"person"', id = user['person_id']))
				t.td(datetime.fromisoformat(user['created']).strftime('%m/%d/%Y %H:%M'))
				t.td(user['verified'] or '', cls = 'pointered', onclick = user_detail(user))
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
			st = _send_task('detail', table = '"tag"', id = tag['id'])
			with t.tr():
				t.td(tag['name'], cls = 'pointered', align = 'right', onclick = st)
				t.td(_yes_or_no(int(tag['active'])), align = 'center', cls = 'pointered', onclick = st)
				t.td(tag['num_subscribers'], cls = 'pointered', align = 'center', onclick = _send_task('admin_tag_users', tag_id = tag['id'], tag_name = f'"{tag["name"]}"'))
	return result


def dialog(title, html_fields, field_names, button_title = text.save, alt_button: t.button = CANCEL_BUTTON, more_func = None):
	return t.div(
		t.div(id = 'detail_banner_container', cls = 'container'), # for later ws-delivered banner messages
		fieldset(title, html_fields, _ws_submit_button(button_title, field_names), alt_button, more_func),
	)


def dialog2(title, fields, data = None, button_title = text.save, alt_button: t.button = CANCEL_BUTTON, more_func = None):
	return dialog(title, build_fields(fields, data), fields.keys(), button_title, alt_button, more_func)


def cancel_to_mpd_button():
	return t.button(text.cancel, onclick = 'send_task("more_person_detail")')



def more_person_detail(emails, phones):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		with t.fieldset():
			t.legend(text.emails)
			for email in emails:
				t.div(t.span(
					email['email'],
					t.button(text.edit, onclick = _send_task('mpd_detail', table = '"email"', id = email['id'])),
					t.button(text.delete, onclick = f'delete_email({email["id"]})'),
				))
			t.div(t.button(text.add, onclick = _send_task('mpd_detail', table = '"email"', id = 0)))
		with t.fieldset():
			t.legend(text.phones)
			for phone in phones:
				t.div(t.span(
					_format_phone(phone['phone']),
					t.button(text.edit, onclick = _send_task('mpd_detail', table = '"phone"', id = phone['id'])),
					t.button(text.delete, onclick = f'delete_phone({phone["id"]})'),
				))
			t.div(t.button(text.add, onclick = _send_task('mpd_detail', table = '"phone"', id = 0)))
		t.div(t.button(text.close, onclick = 'cancel()')) # cancel just reverts to priortask; added/changed emails/phones are saved - those deeds are done, we're just "closing" this mpd portal
	return result

def tag_users_and_nonusers(tag_name, users, nonusers):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		t.div(filterbox_plain())
		t.div(tag_users_and_nonusers_table(tag_name, users, nonusers), id = 'users_and_nonusers_table_container')
	return result

def tag_users_and_nonusers_table(tag_name, users, nonusers):
	un_name = lambda user: f"{user['username']} ({user['first_name']} {user['last_name']})" if user else ''
	result = t.table(cls = 'full_width')
	with result:
		with t.tr(cls = 'midlin'):
			t.th(f'Subscribed to {tag_name}')
			t.th(t.button(text.done, onclick = 'cancel()'), colspan = 2)
			t.th('NOT Subscribed')
		done = False
		while not done:
			user = users.pop(0) if len(users) > 0 else {}
			nonuser = nonusers.pop(0) if len(nonusers) > 0 else {}
			if not user and not nonuser:
				break # done
			with t.tr(cls = 'midlin'):
				t.td(un_name(user), align = 'right')
				t.td(t.button('-', cls = 'singleton_button red_bg', onclick = f"remove_user_from_tag({user['id']})") if user else '')
				t.td(t.button('+', cls = 'singleton_button green_bg', onclick = f"add_user_to_tag({nonuser['id']})") if nonuser else '')
				t.td(un_name(nonuser), align = 'left')
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
		if data and self.type_ == 'checkbox':
			if value:
				self.attrs['checked'] = 'checked'  # would prefer to make these mods to 'i' (t.input_), later, but it seems impossible
			elif 'checked' in self.attrs: # default value vestige
				del self.attrs['checked'] # would prefer to make these mods to 'i' (t.input_), later, but it seems impossible

		i = t.input_(name = name, id = name, type = self.type_ if self.type_ else 'text', **(self.attrs))
		if self.type_ == 'checkbox' and 'onclick' not in self.attrs: # don't do the following if there's already a script assigned, to do some other thing
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

