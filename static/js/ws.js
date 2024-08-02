
ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "init":
			ws_send({task: "init"});
			break;
		case "pong": // currently, this is never called; we receive pings (from pingpong() in ws.js), but our server doesn't send pongs (since it's not really helpful to do so.  If it did, here we'd catch them.
			break;
		case "internal_error":
			show_message(payload.reference);
			break;
		case "show_message":
			show_message(payload.message);
			break;
		case "show_fieldset":
			set_content(payload.fieldset);
			focus_top_input();
			break;
		default:
			handle_message(payload);
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
