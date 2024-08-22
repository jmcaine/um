
function handle_task(payload) {
		switch(payload.task) {
			// no special tasks for here, at present....
			default:
				console.log("ERROR - unknown payload task: " + payload.task);
		}
}

function invite() {
	ws_send({task: "invite"})
}

function more_person_detail() {
	ws_send({task: "more_person_detail"});
}

function email_detail(email_id = 0) {
	ws_send({task: "mpd_detail", table: "email", id: email_id});
}

function phone_detail(phone_id = 0) {
	ws_send({task: "mpd_detail", table: "phone", id: phone_id});
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
