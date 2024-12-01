__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import re

from dataclasses import dataclass, field as dataclass_field
from enum import Enum

from . import db
from . import html
from . import task
from . import text
from . import ws

from .admin import authorize as is_admin

l = logging.getLogger(__name__)

NewMessageNotify = Enum('NewMessageNotify', ['Reload', 'InjectReplies', 'Tease'])

async def active(hd, user_id):
	return (await db.get_user(hd.dbc, user_id, 'active'))['active']


@ws.handler
async def enter_module(hd):
	hd.state['message_notify'] = NewMessageNotify.Tease # probably unnecessary, except perhaps the first time ever, such that this is just an initializer

@ws.handler
async def exit_module(hd):
	hd.state['message_notify'] = NewMessageNotify.Tease


k_limit = 15 # TODO: parameterize to user prefs(?!!!)

@ws.handler(auth_func = active)
async def messages(hd, reverting = False):
	if task.just_started(hd, messages):
		hd.state['message_notify'] = NewMessageNotify.Reload
		hd.task.state['filt'] = 'new' # default to viewing new messages (only)
		hd.task.state['skip'] = 0
		await ws.send_content(hd, 'content', html.messages_page(await is_admin(hd, hd.uid)))
		# sending the above can happen almost immediately; as message lookup might take a moment longer, we'll do it only subsequently (below), even for the very first load, so that the user at least has the framework of the page to see, and the "loading messages..." to see (or, hopefully not, if things are fast enough!)
	filt = hd.payload.get('filt')
	if filt != hd.task.state['filt']: # if it's changed (from before)...
		hd.task.state['filt'] = filt
		if filt != 'new':
			hd.state['message_notify'] = NewMessageNotify.Tease # send alerts/teasers only, since user is looking at non-new messages
			hd.task.state['skip'] = -1 # start at "last page" - with most recent messages (but still in ascending order)
	ms = await _get_messages(hd)
	await ws.send_content(hd, 'messages', html.messages(ms))

@ws.handler(auth_func = active)
async def more_messages(hd):
	hd.task.state['skip'] += k_limit
	ms = await _get_messages(hd)
	await ws.send_content(hd, 'more_messages', html.messages(ms))

async def _get_messages(hd):
	return await db.get_messages(hd.dbc, hd.uid,
													deep = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													filt = hd.task.state['filt'],
													skip = hd.task.state['skip'],
													limit = k_limit)


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
	elif not await task.finished(hd): # dialog-box could have been "canceled"
		# user did something like filtersearch update, and we're back here with a new set of drafts to present:
		await _send_message_draft_table(hd, drafts)

@ws.handler(auth_func = active)
async def brand_new_message(hd):
	await edit_message(hd, False, await db.new_message(hd.dbc, hd.uid))

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def edit_message(hd, reverting = False, message_id = None):
	if reverting and hd.task.state['resume_sending_on_revert']:
		await send_message(hd) # just go straight (back) to sending the message
		return # finished here
	#else:
	if first := task.just_started(hd, edit_message):
		hd.task.state['message_id'] = message_id or hd.payload.get('message_id') or hd.task.state.get('message_id')
	elif not reverting and await task.finished(hd): # user pushed ▼, to save draft for later
		await ws.send_content(hd, 'banner', html.info(text.message_draft_saved)) # send banner to prior-task
		return # finished
	#else:
	if first or reverting:
		# load message: (note that send_message() handles the "send" ► action)
		message = await db.get_message(hd.dbc, hd.task.state['message_id'])
		await ws.send_content(hd, 'edit_message', html.edit_message(message["message"]))

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

@ws.handler(auth_func = active)
async def save_wip(hd):
	await db.save_message(hd.dbc, hd.task.state['message_id'], hd.payload['content'])


@ws.handler(auth_func = active)
async def send_message(hd):
	mid = hd.task.state['message_id']
	match hd.payload.get('to_sender_only', -1): # versus "to all original recipients"; only really applies to replies...
		case 1: # yup, replier wishes to send only to the original (parent_mid) sender, and leave others out of it...
			await db.add_tag_to_message(hd.dbc, mid, (await db.get_author_tag(hd.dbc, hd.task.state['parent_mid']))['id'])
		case 0: # nope, rather, replier wishes to send "to all original recipients", instead...
			await db.set_reply_message_tags(hd.dbc, mid)
		#else, this isn't a "reply", and the message tags are already set by user (or they aren't and the next call will fail gracefully
	message = await db.send_message(hd.dbc, mid)
	match message:
		case db.Send_Message_Result.NoTags:
			await message_tags(hd, resume_sending_on_revert = True) # note: revert is to edit_message task; send_message isn't actually a task, it's just a helper-handler!
			return # finished here
		case db.Send_Message_Result.EmptyMessage:
			await ws.send_content(hd, 'detail_banner', html.error(text.cant_send_empty_message))
			return # finished here
	# otherwise it's a real message...
	await task.finish(hd) # actually finishing the edit_message task, here!
	if hd.state['message_notify'] == NewMessageNotify.InjectReplies:
		hd.state['message_notify'] = NewMessageNotify.Reload # finished authoring reply (about to send it), so go back to "Reload" notify-state (do this before deliver_message() calls so that message will be delivered to sender with a proper reload)
	for other_hd in hd.rq.app['hds']:
		await deliver_message(other_hd, message)
	await ws.send_content(hd, 'banner', html.info(text.message_sent)) # TODO: if this was a reply scenario, make the banner text (to the sender!) indicate that the message is now at the bottom of the chain


@dataclass(slots = True)
class Active_Reply:
	parent_id: int
	patriarch_id: int | None

@ws.handler(auth_func = active)
async def compose_reply(hd):
	started = task.just_started(hd, compose_reply)
	parent_mid = hd.task.state['parent_mid'] = hd.payload['message_id']
	patriarch_id = await db.get_patriarch_message_id(hd.dbc, parent_mid)
	selection = hd.payload.get('selection') # TODO: (int, int) range? or actual text, or...?
	# While replying, allow other replies to the same parent or grandparent message to be injected in real-time:
	hd.state['message_notify'] = NewMessageNotify.InjectReplies
	hd.state['message_notify_inject'] = Active_Reply(parent_mid, patriarch_id)
	new_mid = hd.task.state['message_id'] = await db.new_message(hd.dbc, hd.uid, parent_mid, patriarch_id)
	# load (empty) reply-box: (note that send_message() handles the "send" ► action)
	await ws.send_content(hd, 'inline_reply_box', html.inline_reply_box(hd.payload.get('to_sender_only', 1)), message_id = parent_mid)


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
		match hd.state.get('message_notify'):
			case NewMessageNotify.Tease:
				await ws.send(hd, 'deliver_message_teaser', teaser = message['teaser'])
			case NewMessageNotify.Reload:
				await messages(hd)
			case NewMessageNotify.InjectReplies:
				active_reply = hd.state['message_notify_inject']
				# The following seem like meaningful locations in the tree to inject-show the new message now, even while the active-replier is typing
				placement = -1 # default: don't inject at all (just let the new message show next time a reload happens)
				if active_reply.parent_id == message['reply_to']: # message (to be delivered) shares the same parent...
					placement = 0 # ... so inject this new delivery immediately above the active reply (that's what 0 indicates)
				elif active_reply.patriarch_id == message['reply_to']: # (to be delivered) message's parent is active-reply's grandparent (first descendent)...
					placement = message['id'] # ... so inject this new delivery just ABOVE active-reply's parent message
				if placement != -1:
					await ws.send(hd, 'inject_deliver_new_message', content = html.message(message['message']).render(), placement = placement)
				# else don't show now, just let it show next time a reload happens

@ws.handler(auth_func = active)
async def message_tags(hd, reverting = False, resume_sending_on_revert = False):
	mid = hd.task.state['message_id'] # possibly (intentionally) stealing from prior task (BEFORE calling task.started())!
	hd.task.state['resume_sending_on_revert'] = resume_sending_on_revert # also setting this to PRIOR task, actually (on first entry, before just_started() call) - on purpose, to tell message-sending (e.g.) to send directly after this message-tag-selection operation is complete; no need to pause on (reverting to) that prior task for anything more
	if started := task.just_started(hd, message_tags):
		hd.task.state['message_id'] = mid # stolen from prior task; now a part of our task TODO: make this technique a PART of task.started(args)?!
	if started or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		await ws.send_content(hd, 'dialog', html.message_tags(await message_tags_table(hd)))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await message_tags_table(hd), container = 'message_tags_table_container')

async def message_tags_table(hd):
	utags, otags = await db.get_message_tags(hd.dbc, hd.task.state['message_id'],
													active = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													include_others = True)
	return html.message_tags_table(utags, otags)

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
	await func(hd.dbc, hd.task.state['message_id'], tid)
	await ws.send_content(hd, 'sub_content', await message_tags_table(hd), container = 'message_tags_table_container')
	tag = await db.get_tag(hd.dbc, tid, 'name')
	await ws.send_content(hd, 'detail_banner', html.info(banner_text.format(name = tag['name'])))

