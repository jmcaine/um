k_video_formats = ('.mp4', '.mov', '.mkv', '.mov')
k_audio_formats = ('.m4a', '.mp3', )
k_image_formats = ('.jpg', '.jpeg', '.png' ) # png?
k_thumbnail_size = 300
k_thumb_appendix = '.small.jpg'
k_upload_path = 'static/uploads/'
k_landscape_video_overlay = 'static/landscape_overlay.png'
k_portrait_video_overlay = 'static/portrait_overlay.png'

k_url_re = r'\[([^][]+)\](\(((?:[^()]+|(?2))+)\))' # thank you https://stackoverflow.com/users/1231450/jan (https://stackoverflow.com/questions/67940820/how-to-extract-markdown-links-with-a-regex)
k_url_replacement = r'<a target="_blank" rel="noopener noreferrer" href="\3">\1</a>'
