__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import re

from dataclasses import dataclass, field as dataclass_field

from . import db
from . import html
from . import settings
from . import task
from . import text
from . import ws

from .admin import authorize as is_admin
from .messages_const import *

l = logging.getLogger(__name__)


async def active(hd, user_id):
	return (await db.get_user(hd.dbc, user_id, 'active'))['active']


@ws.handler
async def enter_module(hd):
	hd.rq.app['active_module'] = 'app.messages'
	hd.state['message_notify'] = NewMessageNotify.inject

@ws.handler
async def exit_module(hd):
	hd.state['message_notify'] = NewMessageNotify.tease

@ws.handler(auth_func = active)
async def messages(hd, reverting = False):
	if hd.rq.app['active_module'] != 'messages': # frequently, messages() is called from elsewhere (other than user request), e.g., as a default startup.  In this case, the normal framework caller of our enter_module() doesn't get called, so we need to call it; this is the exception, and is because this method is a little special
		await enter_module(hd)
	if reverting and hd.state['message_notify'] != NewMessageNotify.reload:
		return # nothing to do here - don't reload messages if reverting, unless NewMessageNotify.reload

	just_started = task.just_started(hd, messages) # have to do this first, before referencing hd.task.state, below
	filt = hd.task.state['filt'] = hd.payload.get('filt', hd.task.state.get('filt', Filter.unarchived)) # prefer filt sent in payload, then filt already recorded, and, finally, if nothing, default to viewing new ('unarchived') messages (only)

	if just_started:
		await ws.send_sub_content(hd, 'topbar_container', html.messages_topbar(await is_admin(hd, hd.uid)))
		await ws.send_content(hd, 'content', html.messages_container())
		# sending the above can happen almost immediately; as message lookup might take a moment longer, we'll do it only subsequently (below), even for the very first load, so that the user at least has the framework of the page to see, and the "loading messages..." to see (or, hopefully not, if things are fast enough!)
	await ws.send_sub_content(hd, 'filter_container', html.messages_filter(filt))
	if unarchiveds := filt == Filter.unarchived:
		hd.task.state['skip'] = 0 # start at "top" (oldest (unarchived) messages), and only load new messages when user scrolls to bottom
	else:
		hd.task.state['skip'] = -1 # start at "bottom" of "last page" (newest messages), and load older messages when user scrolls to top
	ms = await _get_messages(hd)
	hd.task.state['skip'] += len(ms) if hd.task.state['skip'] >= 0 else -len(ms)
	await ws.send_content(hd, 'messages', html.messages(ms, hd.uid, None, unarchiveds), scroll_to_bottom = 0 if unarchiveds else 1, filt = filt)
	if len(ms) > 0:
		hd.task.state['last_thread_patriarch'] = ms[-1]['reply_chain_patriarch'] if unarchiveds else ms[0]['reply_chain_patriarch'] # last message, if we're scrolling down; first if up

@ws.handler(auth_func = active)
async def more_new_messages_forward_only(hd): # this is only called if a screen is taller than the default # of messages can fill, so more messages are immediately needed; note that a skip of -1 canNOT result in a more_new_messages call or we'll have an infinite loop because the number of "newest" messages fits on screen, with room for more, but calling for more incessantly won't result in any change; this method is ONLY for forward (skipping-forward, from old messages) orientations
	if hd.task.state['skip'] > 0:
		return await more_new_messages(hd)
	#else no-op

@ws.handler(auth_func = active)
async def more_new_messages(hd): # inspired by "down-scroll" below "bottom"
	if hd.task.state['filt'] != Filter.unarchived:
		return # nothing to do - all 'archived' filters show the "most current (most currently archived)" at the bottom, in the first load, so there are never any "newer" messages to load beyond those
	#else:
	assert(hd.task.state['skip'] >= 0) # true by virtue of filtering 'unarchived' messages - we're only skipping 'forward'
	ms = await _get_messages(hd)
	if len(ms) > 0:
		await ws.send_content(hd, 'more_new_messages', html.messages(ms, hd.uid, hd.task.state['last_thread_patriarch']))
		hd.task.state['skip'] += len(ms)
		hd.task.state['last_thread_patriarch'] = ms[-1]['reply_chain_patriarch']
	else:
		await ws.send(hd, 'no_more_new_messages')

@ws.handler(auth_func = active)
async def more_old_messages(hd): # inspired by "up-scroll" above "top"
	if hd.task.state['filt'] == Filter.unarchived:
		return # nothing to do - 'unarchived' load always starts with the oldest unarchived ("new") messages and never auto-expires (when scrolling "down" for "newer" new messages), so, scrolling to the top never needs to invoke any lookups, as there's nothing more to load above the oldest on top
	#else:
	assert(hd.task.state['skip'] < 0) # true by virtue of filtering 'archived' messages - we're only skipping 'backward'
	ms = await _get_messages(hd)
	if len(ms) > 0:
		await ws.send_content(hd, 'more_old_messages', html.messages(ms, hd.uid, hd.task.state['last_thread_patriarch']))
		hd.task.state['skip'] -= len(ms)
		hd.task.state['last_thread_patriarch'] = ms[0]['reply_chain_patriarch']
	#else: nothing more to do - don't ws.send() anything or update anything!  User has scrolled to the very top of the available messages for the given filter

async def _get_messages(hd):
	return await db.get_messages(hd.dbc, hd.uid,
													deep = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													filt = hd.task.state['filt'],
													skip = hd.task.state['skip'],
													limit = settings.messages_per_load)


@ws.handler(auth_func = active)
async def new_message(hd, reverting = False):
	if reverting:
		await task.finish(hd) # just bump back another step (no value in reverting to this transient task)
		return # finished here
	#else:
	first = task.just_started(hd, new_message)
	drafts = await _get_message_drafts(hd)
	if not drafts:
		await brand_new_message(hd)
		return # nothing else to do here
	#else, we have drafts to present...
	if first:
		await ws.send_content(hd, 'dialog', html.choose_message_draft(drafts))
	elif not await task.finished(hd): # dialog-box could have been "canceled" (if so, don't do the following! Rather, just let the finish finish!)
		# user did something like filtersearch update, and we're back here with a new set of drafts to present:
		await _send_message_draft_table(hd, drafts)

@ws.handler(auth_func = active)
async def brand_new_message(hd):
	await edit_message(hd, False, await db.new_message(hd.dbc, hd.uid))

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def edit_message(hd, reverting = False, message_id = None):
	first = task.just_started(hd, edit_message)
	message_id = hd.task.state['message_id'] = message_id or (hd.payload.get('message_id') or hd.task.state.get('message_id')) # using hd.task.state['message_id'] as a preserver - we may detour on a subtask, then revert here, and have lost arg message_id or payload message_id
	if reverting and hd.task.state['resume_sending_on_revert']:
		await send_message(hd, message_id) # just go straight (back) to sending the message
		return # finished
	#else:
	if not reverting and await task.finished(hd): # user pushed ▼, to save draft for later
		await ws.send_content(hd, 'banner', html.info(text.message_draft_saved)) # send banner to prior-task
		return # finished
	#else:
	if first or reverting:
		# load message: (note that send_message() handles the "send" ► action)
		message = await db.get_message(hd.dbc, hd.uid, message_id)
		await ws.send_content(hd, 'edit_message', html.edit_message(message_id, message['message']), message_id = message_id)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def trash_message(hd):
	# NOTE: not an independent task; processing expected from within 'new_message' task, during choose_message_draft processing
	await db.trash_message(hd.dbc, hd.payload['message_id'])
	banner = text.trash_succeeded
	drafts = await _get_message_drafts(hd)
	if not drafts:
		banner += '  ' + text.no_more_drafts
	await ws.send_content(hd, 'detail_banner', html.info(banner))
	await _send_message_draft_table(hd, drafts)

_strip_trailing_br = lambda content: content.rstrip('<br>')

@ws.handler(auth_func = active)
async def save_wip(hd):
	await db.save_message(hd.dbc, hd.payload['message_id'], hd.payload['content'])
	#l.debug(f"Saved WIP for mid: {hd.payload['message_id']} -- content: {hd.payload['content']}")

@ws.handler(auth_func = active)
async def send_message(hd, message_id = None):
	mid = message_id or hd.payload['message_id']
	message = await db.send_message(hd.dbc, hd.uid, mid)
	match message:
		case db.Send_Message_Result.NoTags:
			await message_tags(hd, resume_sending_on_revert = True) # note: revert is to edit_message task; send_message isn't actually a task, it's just a helper-handler!
			return # finished here
		case db.Send_Message_Result.EmptyMessage:
			await ws.send_content(hd, 'detail_banner', html.error(text.cant_send_empty_message))
			return # finished here
	# otherwise it's a real message...
	await task.finish(hd) # actually finishing the edit_message task, here! (as send_reply is not an actual task, it's just a helper called from within the context of another)
	for each_hd in hd.rq.app['hds']: # including delivery to self! (which will reload message list)
		await deliver_message(each_hd, message)
	await ws.send_content(hd, 'banner', html.info(text.message_sent)) # TODO: if this was a reply scenario, make the banner text (to the sender!) indicate that the message is now at the bottom of the chain

@ws.handler(auth_func = active)
async def send_reply(hd):
	mid = hd.payload['message_id']
	if hd.payload.get('to_sender_only') == '1': # replier wishes to send only to the original (parent_mid) sender, and leave others out of it...
		await db.add_tag_to_message(hd.dbc, mid, (await db.get_author_tag(hd.dbc, hd.payload['parent_mid']))['id'])
	else: # replier wishes to send "to all original recipients", instead...
		await db.set_reply_message_tags(hd.dbc, mid)
	message = await db.send_message(hd.dbc, hd.uid, mid)
	await task.finish(hd) # actually finishing the compose_reply task, here! (as send_reply is not an actual task, it's just a helper called from within the context of another)
	if message == db.Send_Message_Result.EmptyMessage:
		await ws.send(hd, 'remove_reply_container', message_id = mid)
	else:
		_, html_message = html.message(message, message['reply_chain_patriarch'])
		await ws.send_content(hd, 'post_completed_reply', html_message, message_id = mid)
	for each_hd in hd.rq.app['hds']:
		if each_hd != hd:
			await deliver_message(each_hd, message)
	#!!!@hd.state['message_notify'] = NewMessageNotify.inject # go back to normal injection TODO: what if our previous state was something else?

@ws.handler(auth_func = active)
async def delete_draft(hd):
	await db.delete_draft(hd.dbc, hd.payload['message_id']) # TODO: make sure user is author or authorized!


@dataclass(slots = True)
class Active_Reply:
	parent_id: int
	patriarch_id: int | None

@ws.handler(auth_func = active)
async def compose_reply(hd):
	parent_mid = hd.payload['message_id']
	patriarch_id = await db.get_patriarch_message_id(hd.dbc, parent_mid)
	selection = hd.payload.get('selection') # TODO: (int, int) range? or actual text, or...?
	# While replying, allow other replies to the same parent or grandparent message to be injected in real-time:
	#!!!@hd.state['message_notify'] = NewMessageNotify.inject_replies
	#!!!@hd.state['message_notify_inject'] = Active_Reply(parent_mid, patriarch_id)
	new_mid = await db.new_message(hd.dbc, hd.uid, parent_mid, patriarch_id)
	# load (empty) reply-box: (note that send_reply() handles the "send" ► action)
	await ws.send_content(hd, 'inline_reply_box', html.inline_reply_box(new_mid, parent_mid), message_id = new_mid, parent_mid = parent_mid)


async def deliver_message(hd, message):
	'''
	Consider scenarios - 
	1) user is staring at (or staring away from) new-messages screen - new messages can pop up (on top, according to scheme)
		likewise, replies can pop up in-place
		both of these can be achieved by a reload, which will have the added effect (benefit) of limiting the showing messages to the normal #
		SO, for this scenario, we just want a message-list reload!
	2) user is typing a reply - replies to the same thread want to pop "insert" above the active text/typing box; no reload here - just a DOM insert, so that the text/typing doesn't have to re-load (alternately, we COULD reload, as the active reply should be periodically auto-saving, and we could do one more (last) auto-save before the reload, and, of course, re-load with the editing reply still in edit mode and the carat where it belongs, but this could get tricky(?) if the user is precisely in the middle of fast typing; e.g., perhaps a keystroke will be lost?!
	Note that we KNOW this detail (whether a user is typing a reply) here, server-side - we don't have to send to recipients and make decisions client-side.
		SO, for this scenario, we care about the message the user is replying to; if it shares inheritance, we have to DOM-insert; if it does not, we can treat this as if it's scenario 3 (below)
	3) user is doing something else in the application, not looking at messages at all (e.g., in "settings", or typing a completely new message...) but, in any event, NOT looking at (or ignoring) the normal "messages" screen
		SO, for this scenario, we want to send the teaser only!) - next time user goes to messages screen, it'll reload properly
	'''
	if await db.delivery_recipient(hd.dbc, hd.uid, message['id']):
		l.debug(f"!!!!!!!!!!! considering INJECTING into uid ({hd.uid})'s stream; message_notify = {hd.state.get('message_notify')}")
		reference_mid = -1 # init to signal "don't inject"
		match hd.state.get('message_notify'):
			case NewMessageNotify.tease:
				await ws.send(hd, 'deliver_message_teaser', teaser = message['teaser'])
			case NewMessageNotify.reload:
				await messages(hd)
			case NewMessageNotify.inject:
				l.debug(f'!!!!!!!!!!!!! INJECTING! uid: {hd.uid}')
				reference_mid = message['reply_to']
			case NewMessageNotify.inject_replies:
				l.debug(f'!!!!!!!!!!!!! INJECTING REPLY! uid: {hd.uid}')
				active_reply = hd.state['message_notify_inject']
				if active_reply.parent_id == message['reply_to']: # message (to be delivered) shares the same parent...
					reference_mid = 0 # ... so inject this new delivery immediately above the active reply (that's what 0 indicates)
				else:
					reference_mid = message['reply_to'] # just like a normal injection
		if reference_mid == None or reference_mid >= 0:
			_, html_message = html.message(message, message['reply_chain_patriarch'], injection = True)
			reference_mid = -1 if reference_mid == None else reference_mid
			await ws.send_content(hd, 'inject_deliver_new_message', html_message, new_mid = message['id'], reference_mid = reference_mid, placement = 'beforeend')

@ws.handler(auth_func = active)
async def message_tags(hd, reverting = False, resume_sending_on_revert = False):
	hd.task.state['resume_sending_on_revert'] = resume_sending_on_revert # also setting this to PRIOR task, actually (on first entry, before just_started() call) - on purpose, to tell message-sending (e.g.) to send directly after this message-tag-selection operation is complete; no need to pause on (reverting to) that prior task for anything more
	started = task.just_started(hd, message_tags)
	mid = hd.payload.get('message_id') # if 'finished' is in the payload, then this will never be used, and might not even be provided by caller
	if started or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		await ws.send_content(hd, 'dialog', html.message_tags(await message_tags_table(hd, mid)))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await message_tags_table(hd, mid), container = 'message_tags_table_container')

async def message_tags_table(hd, mid):
	utags, otags = await db.get_message_tags(hd.dbc, mid,
													active = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													include_others = True)
	return html.message_tags_table(utags, otags, mid)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def remove_tag_from_message(hd):
	await _remove_or_add_tag_to_message(hd, db.remove_tag_from_message, text.removed_tag_from_message)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def add_tag_to_message(hd):
	await _remove_or_add_tag_to_message(hd, db.add_tag_to_message, text.added_tag_to_message)


@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def archive(hd):
	await db.archive_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def unarchive(hd):
	await db.unarchive_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def pin(hd):
	await db.pin_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def unpin(hd):
	await db.unpin_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)


# -----------------------------------------------------------------------------

async def _get_message_drafts(hd):
	return await db.get_message_drafts(hd.dbc, hd.uid,
										include_trashed = hd.task.state.get('filtersearch_include_extra'),
										like = hd.task.state.get('filtersearch_text'))

async def _send_message_draft_table(hd, drafts):
	await ws.send_content(hd, 'sub_content', html.choose_message_draft_table(drafts), container = 'choose_message_draft_table_container')

async def _remove_or_add_tag_to_message(hd, func, banner_text):
	tid = int(hd.payload['tag_id'])
	mid = int(hd.payload['message_id'])
	await func(hd.dbc, mid, tid)
	await ws.send_content(hd, 'sub_content', await message_tags_table(hd, mid), container = 'message_tags_table_container')
	tag = await db.get_tag(hd.dbc, tid, 'name')
	await ws.send_content(hd, 'detail_banner', html.info(banner_text.format(name = tag['name'])))

