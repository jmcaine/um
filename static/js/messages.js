

let messages = {
		
	send: function(task, fields) {
		ws_send({module: 'app.messages', task: task, ...fields});
	},
	
	
	edit_message: function(content) {
		$('dialog_container').innerHTML = content;
		show_dialog();
		$('message_content').focus();
		setEndOfContenteditable($('message_content'));
		messages.start_saving();
	},

	
	wip_saver: null,
	wip_message: null,

	save_wip: function() {
		let new_wip = $('message_content').innerHTML;
		if (new_wip != messages.wip_message) { // only send if there's change...
			messages.wip_message = new_wip;
			messages.send('save_wip', {content: messages.wip_message});
		}
	},

	start_saving: function() {
		wip_saver = setInterval(messages.save_wip, 2000);
	},
	
	stop_saving: function() {
		clearInterval(wip_saver);
		wip_saver = null;
	},

	
	deliver_message: function(message, teaser) {
		let content = message;
		if (content == '') {
			content = teaser;
		}
		messages.deliver_message_alert();
		$('messages_container').insertAdjacentHTML("afterbegin", content);
	},

	deliver_message_alert: function() {
		// TODO: 'ding' or ...?
	},
	
	save_draft: function() {
		messages.stop_saving();
		messages.save_wip(); // one last time
		main.send("finish");
	},

	send_message: function() {
		messages.stop_saving();
		messages.save_wip(); // one last time
		messages.send("send_message");
	},
	
};
