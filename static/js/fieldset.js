
// listen for ENTER key press - invoke the submit button's click():
document.addEventListener("keydown", (event) => {
	if (event.keyCode === 13) {
		if (event.target != $('submit')) { // if the submit button is the target, then it'll already click (avoid double-click!)
			$('submit').click();
		}
	}
});

// focus on the top input right off the bat (there is a chance load-order trouble here; consider a more robust place for this)
focus_top_input();

window.history.forward();
