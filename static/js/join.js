
function handle_task(payload) {
	switch(payload.task) {
		case "success":
			set_content(payload.success);
			break;
	}
}

function submit_fields(fields) {
	ws_send({task: "join", ...fields});
}

