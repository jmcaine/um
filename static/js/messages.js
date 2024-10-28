

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

	
	deliver_message: function(message, teaser) {
		// TODO: NO LONGER USED!!!!
		let content = message;
		if (content == '') {
			content = teaser;
		}
		messages.deliver_message_alert();
		$('messages').insertAdjacentHTML("afterbegin", content);
	},

	deliver_message_alert: function() {
		// TODO: 'ding' or ...?
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
	
};
