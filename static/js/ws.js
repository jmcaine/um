

ws.onmessage = function(event) {
	var payload = JSON.parse(event.data);
	//console.log("payload.task = " + payload.task);
	switch(payload.task) {
		case "new_key":
			identify(true);
			break;
		case "banner":
			set_sub_content('banner_container', payload.content, false);
			setTimeout(() => {
				$("banner_container").innerHTML = '';
			}, 9800); // slightly less than the 10-second fadeout_short (see common.css), so the thing doesn't pop back into view before disappearing entirely
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
		case "page":
			set_page(payload.content);
			break;
		case "content":
			set_content(payload.content, true); // TODO: rename set_content to set_main_content() or something, to keep it separate from the concept of payload.content; set_content really means: set the contents of 'content_container'
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
		case "show_more_old_messages":
			messages.show_more_old_messages(payload.content);
			break;
		case "show_more_new_messages":
			messages.show_more_new_messages(payload.content);
			break;
		case "no_more_new_messages":
			messages.no_more_new_messages();
			break;
		case "show_whole_thread":
			messages.show_whole_thread(payload.content, payload.message_id);
			break;
		case "deliver_message_teaser":
			messages.deliver_message_teaser(payload.teaser);
			break;
		case "inject_deliver_new_message":
			messages.inject_deliver_new_message(payload.content, payload.new_mid, payload.reference_mid, payload.placement);
			break;
		case "remove_message":
			messages.remove_message(payload.message_id);
			break;
		case "inline_reply_box":
			messages.inline_reply_box(payload.content, payload.message_id, payload.parent_mid);
			break;
		case "remove_reply_container":
			messages.remove_reply_container(payload.message_id);
			break;
		case "post_completed_reply":
			messages.post_completed_reply(payload.content, payload.message_id);
			break;
		case "files_uploaded":
			messages.files_uploaded(payload.content, payload.message_id);
			break;
		case "reload":
			window.location.href = '/';
		default:
			console.log("ERROR - unknown payload task: " + payload.task);
	}
};


function ws_send(message) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		//alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		//console.log("SENDING ws message: " + JSON.stringify(message));
		ws.send(JSON.stringify(message));
	}
}

function ws_send_task(module, task, fields) {
	ws_send({module: module, task: task, ...fields});
}

function ws_send_files(files, module, partition_id) {
	if (!ws || ws.readyState == WebSocket.CLOSING || ws.readyState == WebSocket.CLOSED) {
		alert("Lost connection... going to reload page....");
		location.reload();
	} else {
		let msg = {module: module, task: "upload_files", partition_id: partition_id, files: []};
		let contents = {};
		let total_bytelength = 0;
		let finish_counter = 0;
		const finish_count = files.length
		for (const file of files) {
			msg['files'].push({name: file.name, size: file.size});

			const reader = new FileReader();
			reader.onabort = function(e) { /* TODO */ }
			reader.onerror = function(e) { /* TODO */ }
			reader.onloadstart = function(e) { /* TODO */ }
			reader.onprogress = function(e) { /* TODO */ }
			reader.onload = function(e) { // only triggered if successful; note that this callback will be triggered asynchronously; there's no guarantee that files will load in order...
				total_bytelength += e.target.result.byteLength;
				contents[file.name] = new Uint8Array(e.target.result); // ... thus the dict storage, rather than array - above, the msg['files'] array stores the order, as that processes synchronously
				//assert(e.target.result.byteLength == file.size);
				finish_counter += 1;
				if (finish_counter == finish_count) {
					finish(); // since these are triggered asynchronously, we must finish processing only after every file is loaded into contents
				}
			}
			reader.readAsArrayBuffer(file);
		}
		function finish() {
			let tmp_files = msg['files']; // have to grab tmp_files here, before stringifying it for its own serialization; need it in-tact later
			msg['files'] = JSON.stringify(msg['files']);

			const encoder = new TextEncoder(); // always utf-8, Uint8Array()
			const buf1 = encoder.encode('!');
			const buf2 = encoder.encode(JSON.stringify(msg));
			const buf3 = encoder.encode("\r\n\r\n");
			let bytes = new Uint8Array(buf1.byteLength + buf2.byteLength + buf3.byteLength + total_bytelength);
			bytes.set(new Uint8Array(buf1), 0);
			bytes.set(new Uint8Array(buf2), buf1.byteLength);
			bytes.set(new Uint8Array(buf3), buf1.byteLength + buf2.byteLength);
			let pos = buf1.byteLength + buf2.byteLength + buf3.byteLength;
			for (const file of tmp_files) { // had to grab tmp_files at top of finish(), before stringifying it for its own serialization
				bytes.set(contents[file['name']], pos);
				pos += file['size'];
			}

			let oldBt = ws.binaryType;
			ws.binaryType = "arraybuffer";
			ws.send(bytes);
			ws.binaryType = oldBt;
		}
	}
}


function pingpong() {
	if (!ws) return;
	if (ws.readyState !== WebSocket.OPEN) return;
	// else:
	ws_send({task: "ping"});
}
setInterval(pingpong, 10000); // 10-second heartbeat; default timeouts (like nginx) are usually set to 60-seconds

