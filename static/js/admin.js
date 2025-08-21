
let admin = {
	send_ws: function(task, fields) {
		ws_send_task('app.admin', task, fields);
	},



	_delete_mpd: function(table, id) {
		if (window.confirm("Are you sure you want to delete that record?")) {
			admin.send_ws('delete_mpd', {table: table, id: id});
		}
	},

	delete_email: function(email_id) {
		_delete_mpd("email", email_id);
	},

	delete_phone: function(phone_id) {
		_delete_mpd("phone", phone_id);
	},

	orphan_child: function(child_person_id, guardian_person_id) {
		if (window.confirm("Are you sure you want to delete that record?")) { // NOTE: duplicates window.confirm above; DRY consolidate?!
			admin.send_ws('orphan_child', {child_person_id: child_person_id, guardian_person_id: guardian_person_id});
		}
	},

};
