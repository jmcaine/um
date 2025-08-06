# um
"unremarkable messenger" - an asyncio aiohttp message management app that prioritizes:

	* centralized management (invite/disinvite participants)
	* tags (as rooms); tag subscriptions (also centrally manageable)
	* linear processing ("inbox" style default; tag/room organization alternate/searchability)

## Installation and Configuration

	$ python3 -m venv ve
	$ . ve/bin/activate
	$ pip install --upgrade pip
	$ git clone https://github.com/jmcaine/um.git
		OR???
		$ git clone git@github.com:jmcaine/um.git

System level needs:

	$ apt install libgl1-mesa-glx sqlite3

(Note, the pip installs below may rely on other apt-installs like build-essential, libffi-dev, python3-dev, ..., but the most recent install from scratch seemed to call out libgl and sqlite3 only)

Install Requirements.

	$ cd um
	$ pip install aiohttp aiohttp-session aiosqlite cryptography dominate pillow bcrypt opencv-python

OR consider pip-installing from requirements.txt, but this adds dependencies and specifies versions... not sure if that's wanted, as it can get out of date...

	$ (?!) pip install -r requirements.txt

(If adev is wanted, install aiohttp-devtools -- see below, also)

Create the database ('apt install sqlite3' will be required for this, of course):

	$ cat um.sql | sqlite3 um.db

And run your app:

	$ python -m aiohttp.web -H localhost -P 8080 app.main:init

(Or, with [aiohttp-devtools](https://github.com/aio-libs/aiohttp-devtools)

	$ adev runserver -s static --livereload app

The adev server will run on port 8000 by default.  Other adev options may be
desirable, and additions like [aiohttp-debugtoolbar](https://github.com/aio-libs/aiohttp-debugtoolbar)
might be useful.

