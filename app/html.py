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
from .const import *
from .settings import cache_buster
from .messages_const import *


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
			t.input_(type = 'file', id = 'file_upload', multiple = 'true', hidden = 'true', accept = 'image/png, image/jpeg, video/mp4')
			raw(f'''<dialog id="dialog" class="dialog" closedby="any" autofocus="dialog"><div style="float:right">  <button title="{text.close}" onclick="$('dialog').close()"><i class="i i-close"></i></div><div id="dialog_contents"></div></dialog>''') # there's no t.dialog!
			with t.div(id = 'content_container', cls = 'container', style = 'clear:both'):
				t.div("Loading...")

		with t.div(id = 'scripts', cls = 'container'):
			t.script(raw(f'var ws = new WebSocket("{ws_url}");'))
			t.script(raw(f'const initial = "{initial}";'))
			for script in ('basic.js', 'ws.js', 'persistence.js', 'main.js', 'admin.js', 'submit.js', 'messages.js'): # TODO: only load admin.js if user is an admin (somehow? - dom-manipulate with $('scripts').insertAdjacentHTML("beforeend", ...) after login!)!
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
def messages_topbar(admin):
	result = t.div(t.button('+', title = 'new message', onclick = _send('messages', 'new_message')), cls = 'buttonbar')
	filterbox(result, {'deep_search': text.deep_search})
	with result:
		t.div(cls = 'spacer')
		#TODO: t.button('...', title = text.change_settings, onclick = _send('main', 'settings'))
		if admin:
			t.button('Ѫ', title = text.admin, onclick = _send('admin', 'users'))
		t.button('Θ', title = text.logout, onclick = _send('main', 'logout'))
	return result

def users_tags_topbar():
	result = t.div(cls = 'buttonbar')
	with result:
		t.div(cls = 'spacer')
		#TODO: t.button('...', title = text.change_settings, onclick = _send('main', 'settings'))
		t.button(t.i(cls = 'i i-messages'), title = text.messages, onclick = _send('messages', 'messages')) # Ξ
		t.button('Θ', title = text.logout, onclick = _send('main', 'logout'))
	return result

def _users_tags_mainbar(title, add_onclick):
	result = t.div(t.button('+', title = title, onclick = add_onclick), cls = 'buttonbar')
	filterbox(result, {'show_inactives': text.show_inactives, 'dont_limit': text.dont_limit})
	with result:
		t.div(cls = 'spacer')
		t.button(t.i(cls = 'i i-all'), title = text.users, onclick = _send('admin', 'users')) # ☺
		t.button('#', title = text.tags, onclick = _send('admin', 'tags'))
	return result

def users_mainbar():
	return _users_tags_mainbar(text.invite_new_user, _send('main', 'invite'))

def tags_mainbar():
	return _users_tags_mainbar(text.create_new_tag, _send('admin', 'new_tag'))


def users_page(users):
	return t.div(user_table(users), id = 'user_table_container')

def tags_page(tags):
	return t.div(tag_table(tags), id = 'tag_table_container')


def messages_filter(filt):
	result = t.div(cls = 'buttonbar')
	with result:
		filt_button = lambda title, hint, _filt: t.button(title, title = hint, cls = 'selected' if filt == _filt else '', onclick = f'messages.filter(id, "{_filt}")')
		filt_button(text.news, text.show_news, Filter.new)
		filt_button(text.alls, text.show_alls, Filter.all)
		filt_button(text.days, text.show_days, Filter.day)
		filt_button(text.this_weeks, text.show_this_weeks, Filter.this_week)
		filt_button(text.pinneds, text.show_pinneds, Filter.pinned)
	return result

def messages_container():
	return t.div(text.loading_messages, cls = 'container', id = 'messages_container')




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

def login(fields):
	button = _ws_submit_button(text.login, fields.keys())
	forgot = t.button(text.forgot_password, onclick = _send('main', 'forgot_password'))
	result = fieldset(text.login, build_fields(fields), button, forgot)
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

def filterbox(parent, filtersearch_checkboxes):
	kwargs = dict([(name, f'$("{name}").checked') for name in filtersearch_checkboxes.keys()])
	with parent:
		t.div(Input(text.filtersearch, type_ = 'search', autofocus = True, attrs = { # NOTE: autofocus = True is the supposed cause of Firefox FOUC https://bugzilla.mozilla.org/show_bug.cgi?id=1404468 - but it does NOT cause the warning in FF console to go away AND we don't see any visual blink evidence, so we're leaving autofocus=True, but an alternative would be to set autofocus in the JS that loads the header content
			'autocomplete': 'off',
			'oninput': _send('main', 'filtersearch', searchtext = 'this.value', **kwargs),
		}).build('filtersearch')) # TODO: does the Input() really need to go in a t.div container?!!!
		for key, label in filtersearch_checkboxes.items():
			Input(label, type_ = 'checkbox', attrs = {'onclick': _send('main', 'filtersearch', searchtext = '$("filtersearch").value', **kwargs)}).build(key)
	return parent

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
		filterbox(t.div(cls = 'buttonbar'), {'show_inactives': text.show_inactives, 'dont_limit': text.dont_limit})
		t.div(tun_table, id = 'users_and_nonusers_table_container')
	return result

def tag_users_table(tag_name, users, nonusers, count):
	un_name = lambda user: user['username'] # ({user['first_name']} {user['last_name']})
	adder = lambda id: _send('admin', 'add_user_to_tag', user_id = id)
	remover = lambda id: _send('admin', 'remove_user_from_tag', user_id = id)
	return _xaa_table(nonusers, users, un_name, 'NOT Subscribers:', f'Subscribers (to {tag_name}):', 'admin', 'tag_users', adder, remover, count)


def user_tags(ut_table):
	return _x_tags(ut_table, 'user_tags_table_container')

def user_tags_table(user_tags, available_tags, count):
	adder = lambda id: _send('admin', 'add_tag_to_user', user_id = id)
	remover = lambda id: _send('admin', 'remove_tag_from_user', user_id = id)
	return _xaa_table(available_tags, user_tags, lambda tag: tag['name'], 'NOT Subscribed to:', 'Subscribed to:', 'admin', 'user_tags', adder, remover, count)


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
			with t.tr(cls = 'midlin'):
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

def messages(msgs, user_id, is_admin, stashable, last_thread_patriarch = None, skip_first_hr = False):
	top = t.div(id = 'messages', cls = 'container')
	parents = {None: top}
	for msg in msgs:
		if msg['sender_id'] == user_id and not msg['sent'] and msg['reply_to'] != None: # if this is a user's unsent reply (draft), then include it in editable, inline draft mode:
			last_thread_patriarch = msg['reply_chain_patriarch']
			html_message = inline_reply_box(msg['id'], msg['reply_to'], msg['message'])
		elif msg['sent']: # this test ensures we don't try to present draft messages that aren't replies - user has to re-engage with those in a different way ("new message", then select among drafts)... note that the data (msgs) DO include (or MAY include) non-reply (top-level parent) draft messages; we don't want those messages in our message list here
			last_thread_patriarch, html_message = message(msg, user_id, is_admin, stashable, last_thread_patriarch, skip_first_hr)
		parent = parents.get(msg['reply_to'], top)
		parent.add(html_message)
		parents[msg['id']] = html_message
	return top

def message(msg, user_id, is_admin, stashable, thread_patriarch = None, skip_first_hr = False, injection = False):
	editable = msg['sender_id'] == user_id or is_admin
	cls = 'container'
	if injection:
		cls += ' injection'
	result = t.div(id = f"message_{msg['id']}", cls = cls)
	with result:
		if skip_first_hr and thread_patriarch == None: # first time through, skip hr (just assign thread_patriarch):
			thread_patriarch = msg['reply_chain_patriarch']
		else: # thereafter, prepend each (next) msg with an hr() or "gray" hr() (for replies), to separate messages:
			if msg['reply_chain_patriarch'] == thread_patriarch:
				t.hr(cls = 'gray') # continued thread
			else:
				t.hr() # new thread (or clean_top is False, so we never set thread_patriarch; but this is fine, as we would never want a 'gray' line in that case; the oddity is that the following reply-prefix is likely to be set, if this is a reply, and it's possible that the parent is just above, but was simply sitting there from the last load (last call to messages(), so we lost track of that old thread_patriarch)... this is fine.  It might be nice, actually, for really long reply-chains, to occasionally have the "reminder" when the user keeps scrolling down to see more....)
				thread_patriarch = msg['reply_chain_patriarch']
				if msg['id'] != thread_patriarch: # then this msg is actually a reply, but the patriarch is elsewhere (e.g., stashed), so we need to provide the reply-prefix teaser:
					t.div(f'''Reply to "{msg['parent_teaser']}...":''', cls = 'italic')

		t.div(raw(re.sub(k_url_rec, k_url_replacement, msg['message']))) # replace url markdown "links" with real <a href>s

		if msg['attachments']:
			with t.div(id = f"attachments_for_message_{msg['id']}"):
				thumbnail_strip(msg['attachments'].split(','))

		with t.div(cls = 'buttonbar'):
			if stashable and not msg['stashed']:
				t.button(t.i(cls = 'i i-stash'), title = text.stash, onclick = f"messages.stash({msg['id']})") # '▼'
			t.button(t.i(cls = 'i i-reply'), title = text.reply, onclick = _send('messages', 'compose_reply', message_id = msg['id'])) # '◄'
			if msg['pinned']:
				t.button(t.i(cls = 'i i-pin'), title = text.unpin, cls = 'selected', onclick = f"messages.unpin({msg['id']}, this)") # 'Ϯ'
			else:
				t.button(t.i(cls = 'i i-pin'), title = text.pin, onclick = f"messages.pin({msg['id']}, this)") # 'Ϯ'
			if editable:
				t.button(t.i(cls = 'i i-edit'), title = text.edit_message, onclick = _send('messages', 'edit_message', message_id = msg['id']))
			t.div(cls = 'spacer')
			isodate = local_date_iso(msg["sent"]).isoformat()[:-6] # [:-6] to trim offset from end, as javascript code will expect a naive iso variant, and will interpret as "local"
			max_recipients = 3
			all_recipients = '' if not msg['tags'] else msg['tags'].split(',')
			recipients = ', '.join(all_recipients[0:max_recipients]) # NOTE: would be nice if, in db.py, we could use GROUP_CONCAT(DISTINCT tag.name, ', '), to avoid this replace(',', ', '), but DISTINCT requires one arg only - can't provide a delimiter in that case, unfortunately
			if len(all_recipients) > max_recipients:
				recipients += ', ...'
			with t.div():
				edit_button = t.button(t.i(cls = 'i i-all'), title = text.recipients, onclick = f"messages.change_recipients({msg['id']})") if editable else ''
				t.span(t.b('by '), msg['sender'], t.b(' to '), edit_button, recipients, ' ·'),
				t.span(text.just_now if injection else '...', cls = 'time_updater', data_isodate = isodate) # 'sent' date/time
			if editable:
				t.button(t.i(cls = 'i i-trash'), title = text.delete_message, onclick = f"messages.delete_message({msg['id']}, false)")
	return thread_patriarch, result


def message_tags(mt_table):
	return _x_tags(mt_table, 'message_tags_table_container')
	
def message_tags_table(message_tags, available_tags, mid, count):
	adder = lambda id: _send('messages', 'add_tag_to_message', message_id = mid, tag_id = id)
	remover = lambda id: _send('messages', 'remove_tag_from_message', message_id = mid, tag_id = id)
	return _xaa_table(available_tags, message_tags, lambda tag: tag['name'],  text.not_recipients, text.recipients, 'messages', 'message_tags', adder, remover, count)

def thumbnail_strip(filenames):
	result = t.div(cls = 'thumbnail_strip')
	cache_bust = randint(1000, 9999)
	with result:
		for name in filenames:
			path = f'/{k_upload_path}{name}'
			poster_path = path + k_thumb_appendix
			onclick = f'messages.play_video("{path}", "{poster_path}")' if name.lower().endswith(k_video_formats) else f'messages.play_image("{path}")'
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


def _x_tags(xt_table, div_id):
	result = t.div(t.div(id = 'detail_banner_container', cls = 'container')) # for later ws-delivered banner messages
	with result:
		filterbox(t.div(cls = 'buttonbar'), {'dont_limit': text.dont_limit})
		t.div(xt_table, id = div_id)
	return result

name_fetcher = lambda a: a.get('name', '')
def _xaa_table(availables, assigneds, name_fetcher, left_title, right_title, task_app, task, adder, remover, count):
	result = t.table(cls = 'full_width')
	with result:
		with t.tr(cls = 'midlin'):
			t.th(left_title, align = 'right')
			t.th(t.button(text.done, onclick = _send(task_app, task, finished = 'true')), colspan = 2)
			t.th(right_title, align = 'left')
		left_elide = text.filter_for_more if count and count == len(availables) else ''
		right_elide = text.filter_for_more if count and count == len(assigneds) else ''
		for line in range(max(len(availables), len(assigneds))):
			available = availables.pop(0) if len(availables) > 0 else {}
			assigned = assigneds.pop(0) if len(assigneds) > 0 else {}
			if not assigned and not available:
				break # done
			with t.tr(cls = 'midlin'):
				c1, c2 = '', ''
				if available:
					c1 = name_fetcher(available)
					c2 = t.button('+', cls = 'green_bg', onclick = adder(available['id']))
				t.td(c1, align = 'right')
				t.td(c2, align = 'left')
				c1, c2 = '', ''
				if assigned:
					c1 = t.button('-', cls = 'red_bg', onclick = remover(assigned['id']))
					c2 = name_fetcher(assigned)
				t.td(c1, align = 'right')
				t.td(c2, align = 'left')
		if left_elide or right_elide:
			t.tr(t.td(left_elide), t.td(''),  t.td(''), t.td(right_elide), cls = 'midlin')

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
			result = t.div(result, t.span(invalids[name], cls = 'invalid container'))
		return result

