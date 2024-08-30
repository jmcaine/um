

let messages = {
	send: function(task, fields) {
		ws_send({module: 'app.messages', task: task, ...fields});
	}
}
