
// TODO: i18n; see equivalent text. strings
const t_loading_assignments = 'Loading assignments...';


let assignments = {

	send_ws: function(task, fields) {
		ws_send_task('app.assignments', task, fields);
	},

	// ---------------

	_placehold: function() {
		$('content_container').innerHTML = t_loading_assignments; // set placeholder, awaiting load...
	},

	filter: function(filt, person_id = 0) {
		assignments.send_ws('main', {filt: filt, person_id: person_id});
		assignments._placehold();
	},

	subject_filter: function(subj_id) {
		assignments.send_ws('main', {subj_id: subj_id});
		assignments._placehold();
	},

	_teachers_subs_filter: function(id, vals) {
		assignments.send_ws('teachers_subs', vals);
		setTimeout(assignments.hide_dropdown_options, 100, $(id)); // must delay a bit, so that a selection click (which brings us to this function we're in) doesn't subsequently result in a show_... immediately after we hide_...
		assignments._placehold();
	},

	teachers_subs_week_filter: function(id, week) {
		assignments._teachers_subs_filter(id, {week: week});
	},

	teachers_subs_program_filter: function(id, program) {
		assignments._teachers_subs_filter(id, {program: program});
	},

	show_dropdown_options: function(id, btn) {
		let e = $(id);
		if (e.classList.contains("hide")) {
			e.classList.remove("hide");
			e.classList.add("show");
			btn.addEventListener('focusout', function(event) { // NOTE: can't addEventListener to e, itself, for some reason! (even if that element has tabindex set!)
				//assignments.hide_dropdown_options(e); // nope, must delay!  See below!
				setTimeout(assignments.hide_dropdown_options, 200, e); // must delay a bit, so that, if the lose-focus was a selection in the list of options, that selection has a chance to onclick() process!
			});
		} // else, it's already showing'
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

	add_person_to_class: function(adder_task, person_id) {
		clear_filtersearch();
		assignments.send_ws(adder_task, {person_id: person_id});
	},

};
