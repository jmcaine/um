
// listen for ENTER key press - invoke the submit button's click():
document.addEventListener("keydown", (event) => {
	if (event.keyCode === 13) {
		let submit = $('submit')
		if (submit && event.target != submit) { // if the submit button is the target, then it'll already click (avoid double-click!)
			submit.click();
		}
	}
});

// TODO! - not sure this does what we want!
window.history.forward();

function submit_fields(fields) {
	ws_send({task: "submit_fields", ...fields});
}
