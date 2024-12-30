
let g_forced_scroll = false;
let g_main_pane = $('main_pane');
g_main_pane.addEventListener('scroll', () => {
	if (!g_forced_scroll) {
		if (g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight) {
			messages.send('more_new_messages');
		}
		else if (g_main_pane.scrollTop == 0){
			messages.send('more_old_messages');
		}
	}
	else {
		g_forced_scroll = false;
	}
});


let messages = {

	send: function(task, fields) {
		ws_send({module: 'app.messages', task: task, ...fields});
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
			messages.send('save_wip', {content: messages.wip_message});
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


	send_message: function(to_sender_only = -1) {
		messages.stop_saving();
		messages.save_wip(); // one last time
		messages.send("send_message", {to_sender_only: to_sender_only});
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
				messages.send('more_old_messages')
			}
			else {
				messages.send('more_new_messages_forward_only');
			}
		}
		if (scroll_to_bottom == 1) {
			g_forced_scroll = true;
			g_main_pane.scrollTo(0, g_main_pane.scrollHeight);
		}
	},

	show_more_old_messages(content) {
		$('messages_container').insertAdjacentHTML("afterbegin", content);
	},
	show_more_new_messages(content) {
		$('messages_container').insertAdjacentHTML("beforeend", content);
	},

};
