
window.addEventListener('scroll', () => {
	const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
	if (scrollTop + clientHeight >= scrollHeight) {
		messages.send('more_messages');
		console.log('Bottom reached!');
	}
});


let messages = {

	send: function(task, fields) {
		ws_send({module: 'app.messages', task: task, ...fields});
	},
	
	
	edit_message: function(content) {
		$('dialog_container').innerHTML = content;
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

	show_messages: function(content, filtering_message) {
		set_sub_content('messages_container', content);
		if (filtering_message) {
			set_sub_content('banner_container', filtering_message);
		}
		const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
		if (scrollTop + clientHeight >= scrollHeight) {
			console.log('Bottom visible!');
		}
	},

	show_more_messages(content) {
		$('messages_container').insertAdjacentHTML("beforeend", content);
	},

};
