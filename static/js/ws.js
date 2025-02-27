

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "new_key":
			identify(true);
			break;
		case "banner":
			set_sub_content('banner_container', payload.content, false);
			break;
		case "detail_banner":
			set_sub_content('detail_banner_container', payload.content, false);
			break;
		case "fieldset":
			set_content(payload.fieldset, true);
			if (Object.hasOwn(payload, "banner")) {
				set_sub_content('banner_container', payload.banner, false);
			}
			focus_top_input();
			break;
		case "content":
			set_content(payload.content, true);
			break;
		case "sub_content":
			set_sub_content(payload.container, payload.content);
			break;
		case "dialog":
			set_dialog(payload.content);
			break;
		case "hide_dialog":
			hide_dialog();
			break;
		case "edit_message":
			messages.edit_message(payload.content, payload.message_id);
			break;
		case "messages":
			messages.show_messages(payload.content, payload.scroll_to_bottom, payload.filt, payload.filtering_banner);
			break;
		case "more_old_messages":
			messages.show_more_old_messages(payload.content);
			break;
		case "more_new_messages":
			messages.show_more_new_messages(payload.content);
			break;
		case "no_more_new_messages":
			messages.no_more_new_messages();
			break;
		case "deliver_message_teaser":
			messages.deliver_message_teaser(payload.teaser);
			break;
		case "inject_deliver_new_message":
			messages.inject_deliver_new_message(payload.content, payload.new_mid, payload.reference_mid, payload.placement);
			break;
		case "inline_reply_box":
			messages.inline_reply_box(payload.content, payload.message_id, payload.parent_mid);
			break;
		case "remove_reply_container":
			messages.remove_reply_container(payload.message_id);
			break;
		case "post_completed_reply":
			messages.post_completed_reply(payload.content, payload.message_id)
			break;
		default:
			console.log("ERROR - unknown payload task: " + payload.task);
	}
};


function ws_send(message) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		//console.log("SENDING ws message: " + JSON.stringify(message));
		ws.send(JSON.stringify(message));
	}
}

function ws_send_task(module, task, fields) {
	ws_send({module: module, task: task, ...fields});
}


function pingpong() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "ping"});
}
setInterval(pingpong, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
