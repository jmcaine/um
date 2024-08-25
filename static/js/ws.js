

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "new_key":
			identify(true);
			break;
		case "banner":
			show_banner(payload.banner);
			break;
		case "detail_banner":
			show_detail_banner(payload.detail_banner);
			break;
		case "fieldset":
			set_content(payload.fieldset, true);
			if (Object.hasOwn(payload, "banner")) {
				show_banner(payload.banner);
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
			set_dialog(payload.dialog);
			break;
		case "hide_dialog":
			hide_dialog();
			break;
		default:
			handle_task(payload);
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


function pingpong() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "ping"});
}
setInterval(pingpong, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds
