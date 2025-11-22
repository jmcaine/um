
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

	subject_filter: function(subj_id) {
		assignments.send_ws('main', {subj_id: subj_id});
		$('assignments_container').innerHTML = t_loading_assignments; // set placeholder, awaiting load...
	},

	show_dropdown_options: function(id, btn) {
		let e = $(id);
		e.classList.remove("hide");
		e.classList.add("show");
		btn.addEventListener('focusout', function(event) { // NOTE: can't addEventListener to e, itself, for some reason! (even if that element has tabindex set!)
			//assignments.hide_dropdown_options(e); // nope, must delay!  See below!
			setTimeout(assignments.hide_dropdown_options, 200, e); // must delay a bit, so that, if the lose-focus was a selection in the list of options, that selection has a chance to onclick() process!
		});
	},

	hide_dropdown_options: function(element) {
		element.classList.remove("show");
		element.classList.add("hide");
	},

	// From server side:

	show_assignments: function(content) {
		hide_dialog();
		set_sub_content('assignments_container', content);
	},

	show_assignments_print: function(content) {
		document.body.innerHTML = content;
	},

	// From client side:

	mark_complete: function(assignment_id, enrollment_id, checkbox) {
		assignments.send_ws('mark_complete', {assignment_id: assignment_id, enrollment_id: enrollment_id, checked: (checkbox.checked == true)});
	},

};
