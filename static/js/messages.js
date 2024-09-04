

let messages = {
		
	send: function(task, fields) {
		ws_send({module: 'app.messages', task: task, ...fields});
	},
	
	
	edit_message: function(content, message_content) {
		$('dialog_container').innerHTML = content;
		show_dialog();
		$('message_content').innerHTML = message_content;
		$('message_content').focus();
		messages.start_saving();
	},

	
	draft_saver: null,
	draft_message: null,

	save_draft: function() {
		let new_draft = $('message_content').innerHTML;
		if (new_draft != messages.draft_message) { // only send if there's change...
			messages.draft_message = new_draft;
			messages.send('save_draft', {content: messages.draft_message});
		}
	},

	start_saving: function() {
		draft_saver = setInterval(messages.save_draft, 2000);
	},
	
	stop_saving: function() {
		clearInterval(draft_saver);
		draft_saver = null;
	},

	
	deliver_message: function(content) {
		$('messages_container').insertAdjacentHTML("afterbegin", content);
	},

	finish_draft: function() {
		messages.stop_saving();
		messages.save_draft(); // one last time
		main.send("finish");
	},

	send_message: function() {
		messages.stop_saving();
		messages.save_draft(); // one last time
		messages.send("send_message");
	},
	
};
