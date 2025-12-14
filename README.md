TODO:
webdav3.client.download_from und download_file Änderungen für alle zugänglich machen (requirements):
total = int(response.headers['content-length'])
zu:
total = int(response.headers.get("content-length", 0))
