
function $(id) {
	return document.getElementById(id);
};


function show_message(message) {
	$('message_container').innerHTML = message;
}

function show_detail_message(message) {
	$('detail_message_container').innerHTML = message;
}

function clear_message() {
	$('message_container').innerHTML = "";
}

function set_content(content, clear_msg = true) {
	$('content_container').innerHTML = content;
	if (clear_msg) {
		clear_message();
	}
}

function set_dialog(dialog) {
	$('dialog_container').innerHTML = dialog;
	show_dialog();
	focus_top_input();
}

function show_dialog() {
	$("dialog_container").classList.remove("hide");
	$("dialog_container").classList.add("show");
	$('gray_screen').classList.remove("hide");
	$('gray_screen').classList.add("show");
}

function hide_dialog() {
	$("dialog_container").classList.remove("show");
	$("dialog_container").classList.add("hide");
	$('gray_screen').classList.remove("show");
	$('gray_screen').classList.add("hide");
}

function cancel() {
	clear_message();
	hide_dialog();
}

function focus_top_input() {
	document.querySelector('input').focus();
}
