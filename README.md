# um
"unremarkable messenger" - an asyncio aiohttp message management app that prioritizes:

	* centralized management (invite/disinvite participants)
	* tags (as rooms); tag subscriptions (also centrally manageable)
	* linear processing ("inbox" style default; tag/room organization alternate/searchability)

## Installation and Configuration

	$ python3 -m venv ve
	$ . ve/bin/activate
	$ pip install --upgrade pip
	$ git clone git@github.com:jmcaine/um.git

Install Requirements.
(If adev is wanted, install aiohttp-devtools -- see below, also)

	$ cd um
	$ pip install -r requirements.txt

(Note, the pip install may rely on apt-installs like build-essential, libffi-dev, python3-dev, ...)

Create the database ('apt install sqlite3' will be required for this, of course):

	$ cat main.sql | sqlite3 main.db

And run your app:

	$ python -m aiohttp.web -H localhost -P 8080 app.main:init

(Note that you may want your 'port' variable in settings.py to be 8080; or, that is, to match the above.  See elsewhere for setting up nginx / supervisor (or uwsgi...))

(Or, with [aiohttp-devtools](https://github.com/aio-libs/aiohttp-devtools)

	$ adev runserver -s static --livereload app

The adev server will run on port 8000 by default.  Other adev options may be
desirable, and additions like [aiohttp-debugtoolbar](https://github.com/aio-libs/aiohttp-debugtoolbar)
might be useful.

