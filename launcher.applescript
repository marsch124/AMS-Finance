on run
	set appDir to "/Users/martinschabbauer/Documents/01 Leisure/30 App Development/AMS Finance"
	set logFile to (POSIX path of (path to home folder)) & "Library/Logs/AMS-Finance.log"
	-- Touch the Documents folder first so the macOS permission question
	-- appears on the very first launch (user clicks Allow once).
	try
		do shell script "/bin/ls " & quoted form of appDir & " >/dev/null"
	end try
	set isRunning to "no"
	try
		do shell script "/usr/bin/curl -s --max-time 1 http://127.0.0.1:7780/health >/dev/null && echo yes"
		set isRunning to "yes"
	end try
	if isRunning is not "yes" then
		do shell script "/usr/local/bin/node " & quoted form of (appDir & "/server.js") & " >> " & quoted form of logFile & " 2>&1 & for i in $(seq 1 40); do /usr/bin/curl -s --max-time 1 http://127.0.0.1:7780/health >/dev/null && exit 0; sleep 0.25; done; exit 0"
	end if
	-- The Dock app lands on AMS Main Hub, the front door to everything; the
	-- Finance Hub itself is one card away, on the hub's FINANCE shelf.
	do shell script "/usr/bin/open http://localhost:7780/hub/"
end run
