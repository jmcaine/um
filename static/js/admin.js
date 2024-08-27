

let admin = {
	send: function(task, fields) {
		ws_send({module: 'app.admin', task: task, ...fields});
	}
}
