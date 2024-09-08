
function $(id) {
	return document.getElementById(id);
};

function setEndOfContenteditable(contentEditableElement)
{
	// THANK YOU https://stackoverflow.com/users/140293/nico-burns !
	let range = document.createRange();
	range.selectNodeContents(contentEditableElement);
	range.collapse(false);
	let selection = window.getSelection();
	selection.removeAllRanges();
	selection.addRange(range);
}
