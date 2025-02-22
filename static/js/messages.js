
let g_accept_injected_messages_at_bottom = false;
let g_forced_scroll = false;
let g_main_pane = $('main_pane');
g_main_pane.addEventListener('scroll', () => {
	if (!g_forced_scroll) {
		if (g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight) {
			messages.send_ws('more_new_messages');
		}
		else if (g_main_pane.scrollTop == 0){
			messages.send_ws('more_old_messages');
		}
	}
	else {
		g_forced_scroll = false;
	}
});


let messages = {

	send_ws: function(task, fields) {
		ws_send_task('app.messages', task, fields);
	},

	// ---------------

	filter: function(id, filt) {
		messages.send_ws('messages', {filt: filt});
		$('messages_container').innerHTML = "Loading messages..."; // set placeholder, awaiting loading... TODO: deport hard string!
	},


	edit_message: function(content, message_id) {
		$('dialog_screen').innerHTML = content;
		show_dialog();
		let mc = $('edit_message_content_' + message_id);
		mc.focus();
		setEndOfContenteditable(mc);
		messages.start_saving(mc, message_id);
	},


	wip_saver: null,
	wip_content: null,

	save_wip: function(element, message_id) {
		const content = element.innerHTML;
		if (content != messages.wip_content) { // only send if there's change...
			messages.wip_content = content;
			messages.send_ws('save_wip', {message_id: message_id, content: messages.wip_content});
		}
	},

	_clear_old_wip_saver(element, message_id) {
		if (messages.wip_saver != null) {
			if (element != null) {
				messages.save_wip(element, message_id); // one last time
			}
			clearInterval(messages.wip_saver);
			messages.wip_saver = null;
		}
	},

	start_saving: function(element, message_id) {
		messages._clear_old_wip_saver(null, 0);
		messages.wip_saver = setInterval(messages.save_wip, 2000, element, message_id);
	},
	
	stop_saving: function(element, message_id) {
		messages._clear_old_wip_saver($('edit_message_content_' + message_id), message_id);
	},

	
	deliver_message_teaser: function(teaser) {
		console.log(teaser);
		// TODO: 'ding' or ...?
	},

	inject_deliver_new_message: function(content, new_mid, reference_mid, placement) {
		let rc = $('reply_container');
		if (reference_mid == 0 && rc) {
			// inject immediately above the active reply:
			rc.insertAdjacentHTML("beforebegin", content);
			messages._scroll_into_view_if_needed(rc);
			//OLD: g_main_pane.scrollBy(0, $('message_' + new_mid).clientHeight)
		} else {
			// inject above or below reference message:
			// (note that, very nicely, browsers seem to auto-adjust scroll, so, if something is injected above, OFF SCREEN, it does NOT push scroll down!)  (It DOES push stuff down if on-screen)
			let div = $('message_' + reference_mid);
			if (div) {
				div.insertAdjacentHTML(placement, content);
				if (rc) {
					messages._scroll_into_view_if_needed(rc);
				}
			}
			// else reference_mid is not (yet) in our set, so there's no way to inject, but...
			else if (g_accept_injected_messages_at_bottom) { // user has scrolled to bottom of UNARCHIVED messages, and there are no more, OR user is looking at ALL messages, and is at the bottom... so brand new bottom-injections can be injected!  NOTE/TODO: this results in a SECOND loading of the same message later upon another scroll-down that causes a "load-more"
				// place it at the very bottom:
				const currently_at_bottom = g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight; // note this first, then do the insertAdjacentHTML...
				$('messages_container').insertAdjacentHTML("beforeend", content);
				if (currently_at_bottom) {
					g_forced_scroll = true;
					g_main_pane.scrollTo(0, g_main_pane.scrollHeight);
				}
			}
		}
	},

	reply_recipient_all: function(message_id) {
		let d = $('reply_recipient_' + message_id);
		d.dataset.replyrecipient = 'A';
		let rr_all = $('rr_all_' + message_id);
		rr_all.classList.add('show');
		rr_all.classList.remove('hide');
		let rr_one = $('rr_one_' + message_id);
		rr_one.classList.add('hide');
		rr_one.classList.remove('show');
	},

	reply_recipient_one: function(message_id) {
		let d = $('reply_recipient_' + message_id);
		d.dataset.replyrecipient = '1';
		let rr_one = $('rr_one_' + message_id);
		rr_one.classList.add('show');
		rr_one.classList.remove('hide');
		let rr_all = $('rr_all_' + message_id);
		rr_all.classList.add('hide');
		rr_all.classList.remove('show');
	},

	save_draft: function() {
		messages.stop_saving();
		main.send_ws("finish");
	},

	_scroll_into_view_if_needed: function(div) {
		let bound = div.getBoundingClientRect();
		if (bound.bottom > (window.innerHeight || document.documentElement.clientHeight)) {
		//if (bound.bottom > (g_main_pane.scrollTop + g_main_pane.clientHeight)) {
			g_forced_scroll = true;
			div.scrollIntoView({block: "end"});
			//g_main_pane.scrollTo(0, bound.bottom);
		}
	},
	
	inline_reply_box: function(content, message_id, parent_mid) {
		$('message_' + parent_mid).insertAdjacentHTML("beforeend", content);
		let new_reply_box = $('edit_message_content_' + message_id);
		messages._scroll_into_view_if_needed(new_reply_box.parentElement);
		new_reply_box.focus();
	},

	remove_reply_container: function(message_id) {
		$('edit_message_content_' + message_id).parentElement.remove();
	},

	post_completed_reply: function(content, message_id) {
		let edit_div = $('edit_message_content_' + message_id).parentElement;
		edit_div.insertAdjacentHTML("beforebegin", content);
		edit_div.remove();
	},

	send_message: function(message_id) {
		messages.stop_saving(message_id);
		messages.send_ws("send_message", {message_id: message_id});
	},

	send_reply: function(message_id, parent_mid, to_sender_only) {
		messages.stop_saving(message_id);
		messages.send_ws("send_reply", {message_id: message_id, parent_mid: parent_mid, to_sender_only: to_sender_only});
	},

	delete_draft: function(message_id) {
		messages.send_ws('delete_draft', {message_id: message_id});
		let edit_div = $('edit_message_content_' + message_id).parentElement;
		// TODO: put a temporary (timeout) "undo" button in place (insertAdjacentHTML()), to allow undo within a few seconds
		edit_div.remove();
	},

	show_messages: function(content, scroll_to_bottom, filtering_banner) {
		set_sub_content('messages_container', content);
		if (filtering_banner) {
			set_sub_content('banner_container', filtering_banner);
		}
		
		const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
		if (g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight) {
			// the bottom is visible!  
			if (scroll_to_bottom == 1) {
				messages.send_ws('more_old_messages')
			}
			else {
				messages.send_ws('more_new_messages_forward_only');
			}
		}
		if (scroll_to_bottom == 1) {
			g_accept_injected_messages_at_bottom = true;
			g_forced_scroll = true;
			g_main_pane.scrollTo(0, g_main_pane.scrollHeight);
		}
		else {
			g_accept_injected_messages_at_bottom = false; // the "bottom" is a false bottom - when you scroll there, more messages will be loaded.  So, "brand new" injections should not be injected there; they'll just get loaded later when fetched on a future scroll-down
		}
	},

	show_more_old_messages(content) {
		let old_scroll_height = g_main_pane.scrollHeight;
		$('messages_container').insertAdjacentHTML("afterbegin", content);
		g_main_pane.scrollTo(0, g_main_pane.scrollHeight - old_scroll_height); // scroll back to where user was before the inserted (which also caused a scroll-up)
	},

	show_more_new_messages(content) {
		g_accept_injected_messages_at_bottom = false; // often redundant, to re-set every scroll-down, but may be a useful safeguard
		$('messages_container').insertAdjacentHTML("beforeend", content);
	},

	no_more_new_messages(content) {
		g_accept_injected_messages_at_bottom = true;
	},

};
