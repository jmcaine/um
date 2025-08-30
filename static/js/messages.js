
// TODO: i18n
const t_message_stashed = 'Message stashed!';
const t_pin = 'Pin this message' // TODO: this has a duplicate in text.py
const t_unpin = 'UNpin this message' // TODO: this has a duplicate in text.py

const h_message_stashed = '<div class="info fadeout_short">' + t_message_stashed + '</div>';

let g_playing = null;

let g_accept_injected_messages_at_bottom = false;
let g_forced_scroll = false;
let g_main_pane = $('main_pane');
g_main_pane.addEventListener('scroll', () => {
	if (!g_forced_scroll) {
		if (g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight) {
			messages.send_ws('more_new_messages');
		}
		else if (g_main_pane.scrollTop == 0){
			messages.send_ws('more_old_messages');
		}
	}
	else {
		g_forced_scroll = false;
	}
});

const g_file_upload = $('file_upload');
g_file_upload.onchange = () => {
	ws_send_files(g_file_upload.files, 'messages', g_file_upload.dataset.message_id);
};


let messages = {

	send_ws: function(task, fields) {
		ws_send_task('app.messages', task, fields);
	},

	// ---------------

	filter: function(id, filt) {
		messages.send_ws('messages', {filt: filt});
		$('messages_container').innerHTML = "Loading messages..."; // set placeholder, awaiting loading... TODO: deport hard string!
	},


	edit_message: function(content, message_id) {
		$('dialog_screen').innerHTML = content;
		show_dialog();
		let mc = $('edit_message_content_' + message_id);
		mc.focus();
		setEndOfContenteditable(mc);
		messages.start_saving(mc, message_id);
	},


	wip_saver: null,
	wip_content: null,

	save_wip: function(element, message_id) {
		const content = element.innerHTML;
		if (content != messages.wip_content) { // only send if there's change...
			messages.wip_content = content;
			messages.send_ws('save_wip', {message_id: message_id, content: messages.wip_content});
		}
	},

	_clear_old_wip_saver(element, message_id) {
		if (messages.wip_saver != null) {
			if (element != null) {
				messages.save_wip(element, message_id); // one last time
			}
			clearInterval(messages.wip_saver);
			messages.wip_saver = null;
		}
	},

	start_saving: function(element, message_id) {
		messages._clear_old_wip_saver(null, 0);
		messages.wip_saver = setInterval(messages.save_wip, 2000, element, message_id);
	},
	
	stop_saving: function(element, message_id) {
		messages._clear_old_wip_saver($('edit_message_content_' + message_id), message_id);
	},

	
	deliver_message_teaser: function(teaser) {
		console.log(teaser);
		// TODO: 'ding' or ...?
	},

	inject_deliver_new_message: function(content, new_mid, reference_mid, placement) {
		// (note that, very nicely, browsers seem to auto-adjust scroll, so, if something is injected above, OFF SCREEN, it does NOT push scroll down!)  (It DOES push stuff down if on-screen)
		// First, see if new_mid is actually already in our DOM (meaning the message was simply edited):
		let existing = $('message_' + new_mid); // (in which case it's not really a "new" message (id), after all....)
		if (existing) {
			// Lift out replies, before removing `existing`:
			let replies = document.querySelectorAll('#message_' + new_mid + ' > div.container');
			if (replies) {
				replies.forEach(function(reply) {
					existing.insertAdjacentElement("afterend", reply);
				});
			}
			// Then set the new replacement content just above the existing, then remove the old existing:
			existing.insertAdjacentHTML("beforebegin", content);
			existing.remove();
			// Note that this does "break" the normal format of replies being contained "within" parents, but this should be fine....
		} else { // all other cases are true injections (of new_mid, heretofore unseen)
			let div = $('message_' + reference_mid); // if reference_mid == 0 (new message), this processes as expected - the div is (properly) not found
			let injected = false;
			if (div) {
				div.insertAdjacentHTML(placement, content);
				injected = true;
				messages._scroll_into_view_if_needed(div);
			}
			// else reference_mid is not (yet) in our set, so there's no place to inject, but...
			else if (g_accept_injected_messages_at_bottom) { // user has scrolled to bottom of NEW messages, and there are no more, OR user is looking at ALL messages, and is at the bottom... so brand new bottom-injections can be placed at the bottom:
				const currently_at_bottom = g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight; // note this FIRST, then do the insertAdjacentHTML (only after!)...
				$('messages_container').insertAdjacentHTML("beforeend", content);
				injected = true;
				if (currently_at_bottom) {
					g_forced_scroll = true;
					g_main_pane.scrollTo(0, g_main_pane.scrollHeight);
				}
			}
			if (injected) {
				messages.send_ws('injected_message', {message_id: new_mid});
			}
			// Note that there is no need to set casual_date; inject-message will come with "just now" as default init date, and this message will automatically get updated with other shortly (in 10 seconds)
		}
	},

	remove_message: function(message_id) {
		let message = $('message_' + message_id);
		if (message) {
			message.remove();
		}
	},

	reply_recipient_all: function(message_id) {
		let d = $('reply_recipient_' + message_id);
		d.dataset.replyrecipient = 'A';
		let rr_all = $('rr_all_' + message_id);
		rr_all.classList.add('show');
		rr_all.classList.remove('hide');
		let rr_one = $('rr_one_' + message_id);
		rr_one.classList.add('hide');
		rr_one.classList.remove('show');
	},

	reply_recipient_one: function(message_id) {
		let d = $('reply_recipient_' + message_id);
		d.dataset.replyrecipient = '1';
		let rr_one = $('rr_one_' + message_id);
		rr_one.classList.add('show');
		rr_one.classList.remove('hide');
		let rr_all = $('rr_all_' + message_id);
		rr_all.classList.add('hide');
		rr_all.classList.remove('show');
	},

	stash: function(message_id) {
		messages.send_ws('stash', {message_id: message_id});
		message_element = $('message_' + message_id);
		let replies = document.querySelectorAll('#message_' + message_id + ' > div.container');
		if (replies) {
			message_element.insertAdjacentHTML("beforebegin", '<hr>'); // the "extractions" of the message_elements contained within will want a hard line above them, to keep the reply chain visibly sparate from messages above (which may not be the same patriarch at all, and, even if it is, it's better to have a slightly misleading solid hr than a soft hr separating completely different threads of conversation)
			replies.forEach(function(reply) {
				message_element.insertAdjacentElement("afterend", reply);
			});
		}
		message_element.innerHTML = h_message_stashed;
		setTimeout(messages._remove_element, 1800, message_element); // slightly less than the 2-second fadeout_short (see common.css), so the thing doesn't pop back into view before disappearing entirely

		if (g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight) {
			messages.send_ws('more_new_messages');
		}
	},

	pin: function(message_id, button) {
		messages.send_ws('pin', {message_id: message_id});
		button.classList.add('selected');
		button.setAttribute('title', t_unpin);
		button.setAttribute('onclick', "messages.unpin(" + message_id + ", this)");
	},

	unpin: function(message_id, button) {
		messages.send_ws('unpin', {message_id: message_id});
		button.classList.remove('selected');
		button.setAttribute('title', t_pin);
		button.setAttribute('onclick', "messages.pin(" + message_id + ", this)");
	},


	_remove_element: function(element) { // note that inlining this results in failures when multiple stashes are started in started in quick succession; seems one obliterates the other
		element.remove();
	},

	save_draft: function() {
		messages.stop_saving();
		main.send_ws("finish");
	},

	_scroll_into_view_if_needed: function(div) {
		let bound = div.getBoundingClientRect();
		if (bound.bottom > (window.innerHeight || document.documentElement.clientHeight)) {
		//if (bound.bottom > (g_main_pane.scrollTop + g_main_pane.clientHeight)) {
			g_forced_scroll = true;
			div.scrollIntoView({block: "end"});
			//g_main_pane.scrollTo(0, bound.bottom);
		}
	},
	
	inline_reply_box: function(content, message_id, parent_mid) {
		$('message_' + parent_mid).insertAdjacentHTML("beforeend", content);
		let new_reply_box = $('edit_message_content_' + message_id); // could use message_<message_id>, but for the call to focus(), below - need to do that on the editable-content area
		new_reply_box.addEventListener('paste', (e) => {
			const items = (e.clipboardData || e.originalEvent.clipboardData).items; // note that just using e.clipboardData.files is ONLY sufficient for actual files, not BLOBs normally copied when user copies image itself from some gallary app or something; this re-casting (below) is necessary
			let files = [];
			for (const item of items) {
				if (item.kind === 'file') {
					e.preventDefault();
					files.push(item.getAsFile());
				} else if (item.kind === 'string') {
					e.preventDefault();
					item.getAsString((s) => { messages._paste(new_reply_box, s); });
				}
			}
			if (files.length > 0) {
				$('attachments_for_message_' + message_id).insertAdjacentHTML("beforeend", "Uploading your files... loading thumbnails..."); // TODO: replace this with a spinner (that doesn't allow user to interact until finished!!)
				//NO! Can't just do: set_dialog("<div>Uploading your files... loading thumbnails... please wait....</div>");
				// because our dialog may be in use already (message edit!)
				// SO: use html dialog, instead, or make another layer dialog (z-level)....
				ws_send_files(files, 'messages', message_id);
			}
		});
		messages._scroll_into_view_if_needed(new_reply_box.parentElement);
		new_reply_box.focus();
	},

	_paste: function(element, text) {
		const text2 = text.startsWith("http") ? "[the link (click here)](" + text + ") " : text;
		element.focus(); // apparently important, though should be impossible for it not to have focus
		const selection = window.getSelection();
		if (selection.rangeCount > 0) {
			const range = selection.getRangeAt(0);
			range.deleteContents();
			const node = document.createTextNode(text2);
			range.insertNode(node);
			// collapse range and move cursor to end of new node
			range.setStartAfter(node);
			range.collapse(true);
			selection.removeAllRanges();
			selection.addRange(range);
		}
	},

	remove_reply_container: function(message_id) {
		$('edit_message_content_' + message_id).parentElement.remove(); // parent is always the main message_id outer container
	},

	post_completed_reply: function(content, message_id) {
		let edit_div = $('message_' + message_id); // assume this contained edit_message_content - edit-box that we're now replacing with final, submitted content
		edit_div.insertAdjacentHTML("beforebegin", content);
		edit_div.remove();
	},

	send_message: function(message_id) {
		messages.stop_saving(message_id);
		messages.send_ws("send_message", {message_id: message_id});
	},

	send_reply: function(message_id, parent_mid, to_sender_only) {
		messages.stop_saving(message_id);
		messages.send_ws("send_reply", {message_id: message_id, parent_mid: parent_mid, to_sender_only: to_sender_only});
	},

	delete_draft_in_list: function(message_id, delete_confirmation) {
		if (window.confirm(delete_confirmation)) {
			messages.send_ws('delete_draft_in_list', {message_id: message_id});
		}
	},

	delete_unsent_reply_draft: function(message_id, delete_confirmation) {
		if (window.confirm(delete_confirmation)) {
			messages.send_ws('delete_draft', {message_id: message_id});
			let edit_div = $('edit_message_content_' + message_id).parentElement; // parent is always the message_id outer container; could have grabbed that div (message_<message_id>), instead, but this ensures that the message within is actually edit_message_content, and not (somehow) a completed (sent) message.
			// TODO: put a temporary (timeout) "undo" button in place (insertAdjacentHTML()), to allow undo within a few seconds
			edit_div.remove();
		}
	},

	delete_message: function(message_id, finish = false) {
		if (window.confirm("Are you sure you want to delete this message?")) {
			messages.send_ws('delete_message', {message_id: message_id});
			if (finish) {
				main.send_ws('finish'); // closes task and dialog box
			}
		}
	},


	change_recipients: function(message_id) {
		messages.send_ws('message_tags', {message_id: message_id, send_after: true});
	},

	time_updater: null,
	show_messages: function(content, scroll_to_bottom, filtering_banner) {
		set_sub_content('messages_container', content);
		if (filtering_banner) {
			set_sub_content('banner_container', filtering_banner);
		}
		
		//TODO: DEPRECATE (unused?!?): const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
		if (g_main_pane.scrollTop + g_main_pane.clientHeight >= g_main_pane.scrollHeight) {
			// the bottom is visible!  
			if (scroll_to_bottom == 1) {
				messages.send_ws('more_old_messages')
			}
			else {
				messages.send_ws('more_new_messages');
			}
		}
		if (scroll_to_bottom == 1) {
			g_accept_injected_messages_at_bottom = true;
			g_forced_scroll = true;
			g_main_pane.scrollTo(0, g_main_pane.scrollHeight);
		}
		else {
			g_accept_injected_messages_at_bottom = false; // the "bottom" is a false bottom - when you scroll there, more messages will be loaded.  So, "brand new" injections should not be injected there; they'll just get loaded later when fetched on a future scroll-down
		}

		messages._update_times();
		messages.time_updater ??= setInterval(messages._update_times, 10000); // AND, if not already set for 10-second intervals, do so...
	},

	_update_times: function() {
		let elements = document.querySelectorAll('.time_updater');
		elements.forEach(function(element) {
			element.innerHTML = messages.casual_date(new Date(element.dataset.isodate));
		});
	},

	show_more_old_messages: function(content) {
		let old_scroll_height = g_main_pane.scrollHeight;
		$('messages_container').insertAdjacentHTML("afterbegin", content);
		g_main_pane.scrollTo(0, g_main_pane.scrollHeight - old_scroll_height); // scroll back to where user was before the inserted (which also caused a scroll-up)
		messages._update_times();
	},

	show_more_new_messages: function(content) {
		g_accept_injected_messages_at_bottom = false; // often redundant, to re-set every scroll-down, but may be a useful safeguard
		$('messages_container').insertAdjacentHTML("beforeend", content);
		messages._update_times();
	},

	no_more_new_messages: function(content) {
		g_accept_injected_messages_at_bottom = true;
	},

	show_whole_thread: function(content, message_id) {
		let msg = $('message_' + message_id);
		msg.insertAdjacentHTML("beforebegin", content);
		msg.remove(); // we "replaced" it with the whole thread
	},

	attach_upload: function(message_id) {
		g_file_upload.dataset.message_id = message_id;
		g_file_upload.click(); // see g_file_upload.onchange()
		$('attachments_for_message_' + message_id).insertAdjacentHTML("beforeend", "Uploading your files... loading thumbnails...");
	},

	files_uploaded: function(content, message_id) {
		$('attachments_for_message_' + message_id).insertAdjacentHTML("beforeend", content);
	},

	play_video: function(path, poster_path) {
		g_playing = path;
		$('dialog_contents').innerHTML = '<video controls id="dialog_video" class="media_container" poster="' + poster_path + '" width="' + Math.floor(parent.innerWidth*8/9) + '"><source src="' + path + '" type="video/mp4" /></video>';
		$('dialog').showModal();
	},

	play_image: function(path) {
		g_playing = path;
		$('dialog_contents').innerHTML = '<img src="' + path + '" width ="' + Math.floor(parent.innerWidth*8/9) + '" />';
		$('dialog').showModal();
	},

	play_pdf: function(path) {
		g_playing = path;
		const width = Math.floor(parent.innerWidth*8/9);
		const height = Math.floor(parent.innerHeight*8/9);
		$('dialog_contents').innerHTML = '<object data="' + path + '" type="application/pdf" width="' + width + '" height="' + height + '"><embed src="' + path + '" width ="' + width + '" height = "' + height + '" /> <p>This browser does not support PDFs. Please download the PDF to view it: <a href="' + path + '">Download (click) here</a></p></object>';
		// thanks http://jsgyan.blogspot.com/2017/12/how-to-display-pdf-in-html-web-page.html
		$('dialog').showModal();
	},

	download: function() {
		if (g_playing != null) {
			const anchor = document.createElement('a');
			console.log(g_playing);
			anchor.href = g_playing;
			const last_slash = g_playing.lastIndexOf('/');
			anchor.download = g_playing.substring(last_slash + 1);
			document.body.appendChild(anchor);
			anchor.click();
			document.body.removeChild(anchor);
		}
	},

	casual_date: function(reference_date) {
		const now = new Date();
		const diff = now - reference_date;
		let hours = reference_date.getHours();
		let ampm = "AM"
		if (hours > 12) {
			ampm = "PM"
			hours -= 12;
		}
		if (diff < 10000) {
			return "just now"
		} else if (diff < 60 * 1000) {
			return Math.floor(diff/1000).toString() + " seconds ago";
		} else if (diff < 60 * 60 * 1000) {
			const minutes = Math.floor(diff/60000)
			return minutes == 1 ? "1 minute ago" : minutes.toString() + " minutes ago";
		} else {
			if (reference_date.getFullYear() === now.getFullYear() && reference_date.getMonth() === now.getMonth() && reference_date.getDate() === now.getDate()) { // today!
				return hours.toString() + ":" + reference_date.getMinutes().toString().padStart(2, '0') + " " + ampm;
			} //else:
			let yesterday = new Date(); // wait for it...
			yesterday.setDate(yesterday.getDate() - 1);
			if (reference_date.getFullYear() === yesterday.getFullYear() && yesterday.getMonth() === now.getMonth() && yesterday.getDate() === now.getDate()) { // yesterday!
				return "yesterday @ " + hours.toString() + ":" + reference_date.getMinutes().toString().padStart(2, '0') + " " + ampm;
			} // else:
			const days_ago = Math.floor(diff / 1000 / 60 / 60 / 24 ) + 1;
			if (days_ago <= 4) {
				return days_ago == 1 ? "yesterday" : days_ago.toString() + " days ago";
			} // else, this year:
			if (reference_date.getFullYear() === now.getFullYear()) {
				return (reference_date.getMonth() + 1).toString() + "/" + reference_date.getDate();
			} else { // else, some year in the past:
				return (reference_date.getMonth() + 1).toString() + "/" + reference_date.getDate() + "/" + reference_date.getFullYear();
			}
		}
	},

};
