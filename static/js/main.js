function login() {
	ws_send({task: "login"});
}

function logout() {
	ws_send({task: "logout"});
}

function join() {
	ws_send({task: "join"});
}

function invite() {
	ws_send({task: "invite"});
}

function join_or_invite(fields) {
	ws_send({task: "join_or_invite", ...fields});
}

function forgot_password() {
	ws_send({task: "forgot_password"});
}

function show_banner(banner) {
	$('banner_container').innerHTML = banner;
}

function show_detail_banner(banner) {
	$('detail_banner_container').innerHTML = banner;
}

function clear_banner() {
	$('banner_container').innerHTML = "";
}

function set_content(content, clear_msg = true) {
	_set_content($('content_container'), content, clear_msg);
}

function set_sub_content(container_id, content, clear_msg = true) {
	_set_content($(container_id), content, clear_msg);
}

function _set_content(container, content, clear_msg) {
	hide_dialog();
	container.innerHTML = content;
	if (clear_msg) {
		clear_banner();
	}
	focus_top_input(container);
}

function set_dialog(dialog) {
	let dialog_container = $('dialog_container');
	dialog_container.innerHTML = dialog;
	show_dialog();
	focus_top_input(dialog_container);
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
	ws_send({task: "revert_to_priortask"});
}

function focus_top_input(container) {
	inp = container.querySelector('input');
	if (inp) {
		inp.focus();
	}
}


function admin_screen() {
	ws_send({task: "admin_screen"});
}

function filtersearch(text, include_extra = false) {
	ws_send({task: "filtersearch", searchtext: text, include_extra: include_extra});
}

function detail(table, id) {
	ws_send({task: "detail", table: table, id: id});
}


