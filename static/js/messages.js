
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


	edit_message: function(content) {
		$('dialog_screen').innerHTML = content;
		show_dialog();
		$('edit_message_content').focus();
		setEndOfContenteditable($('edit_message_content'));
		messages.start_saving();
	},


	wip_saver: null,
	wip_message: null,

	save_wip: function() {
		let new_wip = $('edit_message_content').innerHTML;
		if (new_wip != messages.wip_message) { // only send if there's change...
			messages.wip_message = new_wip;
			messages.send_ws('save_wip', {content: messages.wip_message});
		}
	},

	start_saving: function() {
		messages.wip_saver = setInterval(messages.save_wip, 2000);
	},
	
	stop_saving: function() {
		clearInterval(messages.wip_saver);
		messages.wip_saver = null;
	},

	
	deliver_message_teaser: function(teaser) {
		console.log(teaser);
		// TODO: 'ding' or ...?
	},

	inject_deliver_new_message: function(content, placement) {
		if (placement != 0) {
			// inject above parent message-id, which is what 'placement' is, in this case:
			$('message_' + placement).insertAdjacentHTML("beforebegin", content);
		} else {
			// inject immediately above the active reply:
			$('edit_message_content').insertAdjacentHTML("beforebegin", content);
		}
	},
	
	save_draft: function() {
		messages.stop_saving();
		messages.save_wip(); // one last time
		main.send("finish");
	},
	
	inline_reply_box: function(content, message_id) {
		$('message_' + message_id).insertAdjacentHTML("afterend", content);
		$('edit_message_content').focus();
		messages.start_saving();
	},

	remove_reply_container: function() {
		$('reply_container').remove();
	},

	post_completed_reply: function(content) {
		$('reply_container').insertAdjacentHTML("beforebegin", content);
		$('reply_container').remove();
	},

	send_message: function() {
		messages.stop_saving();
		messages.save_wip(); // one last time
		messages.send_ws("send_message");
	},

	send_reply: function(to_sender_only) {
		messages.stop_saving();
		messages.save_wip(); // one last time
		messages.send_ws("send_reply", {to_sender_only: to_sender_only});
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
			g_forced_scroll = true;
			g_main_pane.scrollTo(0, g_main_pane.scrollHeight);
		}
	},

	show_more_old_messages(content) {
		let old_scroll_height = g_main_pane.scrollHeight;
		$('messages_container').insertAdjacentHTML("afterbegin", content);
		g_main_pane.scrollTo(0, g_main_pane.scrollHeight - old_scroll_height); // scroll back to where user was before the inserted (which also caused a scroll-up)
	},
	show_more_new_messages(content) {
		$('messages_container').insertAdjacentHTML("beforeend", content);
	},

};
