
function handle_message(payload) { // TODO: same as in join.js, currently - develop, or combine into ws.js
	switch(payload.task) {
		case "success":
			set_content(payload.content);
			break;
	}
}

function submit_fields(fields) {
	ws_send({task: "invite", ...fields});
}

