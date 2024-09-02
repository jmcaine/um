
let admin = {
	send: function(task, fields) {
		ws_send_task('app.admin', task, fields);
	}
}

function _delete_mpd(table, id) {
	if (window.confirm("Are you sure you want to delete that record?")) {
		ws_send_task('app.admin', 'delete_mpd', {table: table, id: id});
	}
}

function delete_email(email_id) {
	_delete_mpd("email", email_id);
}

function delete_phone(phone_id) {
	_delete_mpd("phone", phone_id);
}
