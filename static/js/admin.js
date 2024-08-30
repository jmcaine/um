

let admin = {
	send: function(task, fields) {
		ws_send_task('app.admin', task, fields);
	}
}
