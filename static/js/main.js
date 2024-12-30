
let main = {
	send: function(task, fields) {
		ws_send_task('app.main', task, fields);
	}
}


function set_header_content(content) {
	$('header_pane').innerHTML = content;
}

function set_content(content, clear_banner = true, focus_top_inp = true) {
	_set_content($('content_container'), content, clear_banner, focus_top_inp);
}

function set_sub_content(container_id, content, clear_banner = true, focus_top_inp = false) {
	_set_content($(container_id), content, clear_banner, focus_top_inp);
}

function _set_content(container, content, clear_banner, focus_top_inp = true) {
	container.innerHTML = content;
	if (clear_banner) {
		$('banner_container').innerHTML = "";
	}
	if (focus_top_inp) {
		focus_top_input(container);
	}
}

function set_dialog(content) {
	let dialog_screen = $('dialog_screen');
	dialog_screen.innerHTML = content;
	show_dialog();
	focus_top_input(dialog_screen);
}

function show_dialog() {
	$("dialog_screen").classList.remove("hide");
	$("dialog_screen").classList.add("show");
	$('gray_screen').classList.remove("hide");
	$('gray_screen').classList.add("show");
}

function hide_dialog() {
	$("dialog_screen").classList.remove("show");
	$("dialog_screen").classList.add("hide");
	$('gray_screen').classList.remove("show");
	$('gray_screen').classList.add("hide");
}

function focus_top_input(container) {
	try {
		container.querySelector('input').focus();
	} catch (e) {} // We don't care; if 'input' doesn't exist, then there's nothing to set focus to, and we move on quietly
}
