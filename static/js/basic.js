
function $(id) {
	return document.getElementById(id);
};


function show_message(message) {
	$('message_container').innerHTML = message;
}

function clear_message(message) {
	$('message_container').innerHTML = "";
}

function set_content(content) {
	$('content_container').innerHTML = content;
	clear_message();
}

function focus_top_input() {
	document.querySelector('input').focus();
}
