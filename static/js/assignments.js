
// TODO: i18n; see equivalent text. strings
const t_loading_assignments = 'Loading assignments...';


let assignments = {

	send_ws: function(task, fields) {
		ws_send_task('app.assignments', task, fields);
	},

	// ---------------

	filter: function(filt, person_id = 0) {
		assignments.send_ws('main', {filt: filt, person_id: person_id});
		$('assignments_container').innerHTML = t_loading_assignments; // set placeholder, awaiting load...
	},

	show_assignments: function(content) {
		hide_dialog();
		set_sub_content('assignments_container', content);
	},

	show_assignments_print: function(content) {
		document.body.innerHTML = content;
	},

	mark_complete: function(assignment_id, checkbox) {
		assignments.send_ws('mark_complete', {assignment_id: assignment_id, checked: (checkbox.checked == true)});
	},

};
