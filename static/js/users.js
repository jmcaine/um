
function handle_task(payload) {
		switch(payload.task) {
			// no special tasks for here, at present....
			default:
				console.log("ERROR - unknown payload task: " + payload.task);
		}
}


function _delete_mpd(table, id) {
	if (window.confirm("Are you sure you want to delete that record?")) {
		ws_send({task: "delete_mpd", table: table, id: id});
	}
}

function delete_email(email_id) {
	_delete_mpd("email", email_id);
}

function delete_phone(phone_id) {
	_delete_mpd("phone", phone_id);
}
