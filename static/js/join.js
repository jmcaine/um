
function handle_message(payload) {
	switch(payload.task) {
		case "success":
			set_content(payload.content);
			break;
	}
}

function submit_fields(fields) {
	ws_send({task: "join", ...fields});
}

