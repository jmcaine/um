__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from copy import copy
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

from dominate import document as dominate_document
from dominate import tags as t
from dominate.util import raw

from . import text
from .settings import cache_buster


# Logging ---------------------------------------------------------------------

l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

checkbox_value = lambda data, field: 1 if data.get(field) in (1, '1', 'on') else 0

_yes_or_no = lambda value: 'yes' if value else 'no'
_format_phone = lambda num: '(' + num[-10:-7] + ') ' + num[-7:-4] + '-' + num[-4:] # TODO: international extention prefixes [0:-11]
_send = lambda app, task, **args: f"{app}.send('{task}'" + (f', {{ {", ".join([f"{key}: {value}" for key, value in args.items()])} }})' if args else ')')

_cancel_button = lambda title = text.cancel: t.button(title, onclick = 'main.send("finish")')

# Document --------------------------------------------------------------------

# Note that there's really only one "document"

def document(ws_url: str):
	d = _doc(('common.css',))
	with d:
		t.div(id = 'gray_screen', cls = 'hide') # invisible at first; for dialog_screen, later
		t.div(id = 'dialog_screen', cls = 'hide') # invisible at first
		t.div(id = 'header_pane')

		with t.div(id = 'main_pane'):
			t.div(t.div(id = 'banner_container', cls = 'container')) # for later ws-delivered banner messages
			with t.div(id = 'content_container', cls = 'container'):
				t.div("Loading...")

		with t.div(id = 'scripts', cls = 'container'):
			t.script(raw(f'var ws = new WebSocket("{ws_url}");'))
			for script in ('basic.js', 'ws.js', 'persistence.js', 'main.js', 'admin.js', 'submit.js', 'messages.js'): # TODO: only load admin.js if user is an admin (somehow? - dom-manipulate with $('scripts').insertAdjacentHTML("beforeend", ...) after login!)!
				t.script(src = f'/static/js/{script}')

	return d.render()


# Main-content "Pages" --------------------------------------------------------

def login_or_join():
	return t.div(
		t.div(text.welcome),
		t.div(t.button(text.login, onclick = 'main.send("login")'), cls = 'center'),
		t.div(t.button(text.join, onclick = 'main.send("join")'), cls = 'center'),
	)

def messages_head(admin):
	result = t.div()
	with result:
		with t.div(cls = 'button_band'):
			# button symbols:    ҉ Ѱ Ψ Ѫ Ѭ Ϯ ϖ Ξ Δ ɸ Θ Ѥ ΐ Γ Ω ¤ ¥ § Þ × ÷ þ Ħ ₪ ☼ ♀ ♂ ☺ ☻ ♠ ♣ ♥ ♦ ►
			t.button('+', title = 'new message', onclick = 'messages.send("new_message")')
			filterbox()
			filterbox_checkbox(text.deep_search, 'deep_search')
			with t.div(cls = 'right'):
				t.button('...', title = text.change_settings, onclick = 'main.send("settings")')
				if admin:
					t.button('Ѫ', title = text.admin, onclick = 'admin.send("users")')
				t.button('Θ', title = text.logout, onclick = 'main.send("logout")')
		with t.div(cls = 'clear_both'):
			t.span(
				t.button(text.news, title = text.show_new, onclick = _send('messages', 'messages', filt = '"unarchived"')),
				t.button(text.day, title = text.show_day, onclick = _send('messages', 'messages', filt = '"day"')),
				t.button(text.this_weeks, title = text.show_this_week, onclick = _send('messages', 'messages', filt = '"this_week"')),
				t.button(text.pinneds, title = text.show_pinned, onclick = _send('messages', 'messages', filt = '"pinned"')),
				t.button(text.archiveds, title = text.show_archived, onclick = _send('messages', 'messages', filt = '"archived"')),
				#t.button(text.alls, title = text.show_all, onclick = _send('messages', 'messages', filt = '"all"')), # NO SUCH thing as "all" - we need only "new" ("unarchived") and "archived".  (even "day" and "this_weeks", do NOT include unread messages! - make those "sub-categories" of "Archived" to force user to always "interact" with archived messages except when in "processing new messages (only)" mode.
			)
	return result

def messages_container():
	return t.div(text.loading_messages, cls = 'scroller container', id = 'messages_container')


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
	return Input(text.filtersearch, type_ = 'search', autofocus = True, attrs = { # NOTE: autofocus = True is the supposed cause of Firefox FOUC https://bugzilla.mozilla.org/show_bug.cgi?id=1404468 - but it does NOT cause the warning in FF console to go away AND we don't see any visual blink evidence, so we're leaving autofocus=True, but an alternative would be to set autofocus in the JS that loads the header content
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
				t.td(t.button('-', cls = 'singleton_button red_bg', onclick = _send('admin', 'remove_user_from_tag', user_id = user['id'])) if user else '', align = 'right')
				t.td(t.button('+', cls = 'singleton_button green_bg', onclick = _send('admin', 'add_user_to_tag', user_id = nonuser['id'])) if nonuser else '', align = 'left')
				t.td(un_name(nonuser), align = 'left')
	return result



def user_tags(ut_table):
	return _x_tags(ut_table, 'user_tags_table_container')

def user_tags_table(user_tags, other_tags):
	return _x_tags_table(user_tags, other_tags, 'Subscribed', 'NOT Subscribed', 'admin', 'user_tags', 'remove_tag_from_user', 'add_tag_to_user')


def choose_message_draft(drafts):
	result = t.div(t.div(info(text.choose_message_draft), id = 'detail_banner_container', cls = 'container'))
	with result:
		with t.div(cls = 'button_band'):
			t.div(filterbox(extra = '$("show_trashed").checked'))
			filterbox_checkbox(text.show_trashed, 'show_trashed')
		t.div(choose_message_draft_table(drafts), id = 'choose_message_draft_table_container')
	return result

def choose_message_draft_table(drafts):
	result = t.table(cls = 'full_width')
	with result:
		for draft in drafts:
			with t.tr(cls = 'midlin'):
				t.td(f"{casual_date(draft['created'])}: {draft['teaser']}", cls = 'pointered', onclick = _send('messages', 'edit_message', message_id = draft['id'])) # note, 'teaser' is already a substring - no need to chop here
				if not draft['deleted']: # only allow "untrashed" messages to be trashed; can't "permanently" delete anything
					t.td(t.button('x', title = text.trash, cls = 'singleton_button red_bg', onclick = _send('messages', 'trash_message', message_id = draft['id'])))
		t.tr(t.td(t.button(text.brand_new_message, onclick = _send('messages', 'brand_new_message')), align = 'left'))		
	return result

def edit_message(content):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		#TODO: raw(content) - but seems to cause exception (at least when content is '')
		t.div(raw(content), contenteditable = 'true', id = 'edit_message_content')
		with t.div(cls = 'button_band'):
			with t.div(cls = 'right'):
				t.button('#', title = text.tags, onclick = 'messages.send("message_tags")')
				t.button('▼', title = text.save_draft, onclick = 'messages.save_draft()')
				t.button('►', title = text.send_message, onclick = 'messages.send_message()')
	return result

def inline_reply_box(to_sender_only):
	result = t.div(id = 'reply_container')
	with result:
		t.div(contenteditable = 'true', id = 'edit_message_content')
		with t.div(cls = 'button_band'):
			with t.div(cls = 'right'):
				t.button("1" if to_sender_only else "A", onclick = 'flip_reply_recipient()') # TODO: replace "1" and "A"
				#TODO?!: t.button('▼', title = text.save_draft, onclick = 'messages.save_draft()')
				t.button('►', title = text.send_message, onclick = f'messages.send_message({to_sender_only})')
	return result

def messages(ms):
	result = t.div(id = 'messages', cls = 'container')
	last_thread_updated = None
	with result:
		for message in ms:
			if last_thread_updated == None: # first time through, skip (just assign last_thread_updated:
				last_thread_updated = message['thread_updated']
			else: # thereafter, prepend each (next) message with an hr() or dashed-hr(), to separate messages:
				if message['thread_updated'] == last_thread_updated:
					t.hr(cls = 'dashed-hr') # continued thread
				else:
					t.hr() # new thread
					last_thread_updated = message['thread_updated']
			with t.div(id = f"message_{message['id']}", cls = 'container'):
				t.div(raw(message['message']))
				with t.div(cls = 'button_band'):
					if message['archived']:
						t.button('▲', title = text.unarchive, cls = 'selected', onclick = _send('messages', 'unarchive', message_id = message['id']))
					else:
						t.button('▼', title = text.archive, onclick = _send('messages', 'archive', message_id = message['id']))
					t.button('◄', title = text.reply, onclick = _send('messages', 'compose_reply', message_id = message['id']))
					if message['pinned']:
						t.button('Ϯ', title = text.unpin, cls = 'selected', onclick = _send('messages', 'unpin', message_id = message['id']))
					else:
						t.button('Ϯ', title = text.pin, onclick = _send('messages', 'pin', message_id = message['id']))
					t.div(t.span(t.b('by '), message['sender'], t.b(' to '), message['tags'], f' · {casual_date(message["sent"])}'), cls = 'right')
	return result

def message(content):
	return raw(content)

def message_tags(mt_table):
	return _x_tags(mt_table, 'message_tags_table_container')
	
def message_tags_table(message_tags, other_tags):
	return _x_tags_table(message_tags, other_tags, text.recipients, text.not_recipients, 'messages', 'message_tags', 'remove_tag_from_message', 'add_tag_to_message')



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


def _x_tags(xt_table, div_id):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		with t.div(cls = 'button_band'):
			t.div(filterbox())
			filterbox_checkbox(text.show_inactives, 'show_inactives')
		t.div(xt_table, id = div_id)
	return result

def _x_tags_table(tags, other_tags, left_title, right_title, task_app, task, remove_task, add_task):
	result = t.table(cls = 'full_width')
	with result:
		with t.tr(cls = 'midlin'):
			t.th(left_title, align = 'right')
			t.th(t.button(text.done, onclick = _send(task_app, task, finished = 'true')), colspan = 2)
			t.th(right_title, align = 'left')
		for count in range(15): # TODO: 15 is hardcode equivalent to db/sql 'limit'; that is, the active "list size" - 'other_tags', here, COULD actually be bigger than 15, so... limiting here, as well
			tag = tags.pop(0) if len(tags) > 0 else {}
			otag = other_tags.pop(0) if len(other_tags) > 0 else {}
			if not tag and not otag:
				break # done
			with t.tr(cls = 'midlin'):
				t.td(tag.get('name', ''), align = 'right')
				t.td(t.button('-', cls = 'singleton_button red_bg', onclick = _send(task_app, remove_task, tag_id = tag['id'])) if tag else '', align = 'right')
				t.td(t.button('+', cls = 'singleton_button green_bg', onclick = _send(task_app, add_task, tag_id = otag['id'])) if otag else '', align = 'left')
				t.td(otag.get('name', ''), align = 'left')
	return result

k_fake_localtz = 'America/Los_Angeles' # TODO - implement user-local timezones (this will be a per-user field in db)!
def casual_date(raw_date):
	zi = ZoneInfo(k_fake_localtz) # manage all datetimes wrt/ user's local tz, so that "yesterday" means that from the local user's perspective, not from UTC or server-local
	dt = datetime.fromisoformat(raw_date).astimezone(zi) # no need to .replace(tzinfo = timezone.utc) on fromisoformat result because we put the trailing 'Z' on dates in the db, so this fromisoformat() will interpret the datetime not as naive, but at explicitly UTC
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

