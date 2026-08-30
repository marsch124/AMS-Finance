on run
	-- AMS Finance Engine: starts the hub server at login, no browser window.
	set appDir to "/Users/martinschabbauer/Documents/01 Leisure/30 App Development/AMS Finance"
	set logFile to (POSIX path of (path to home folder)) & "Library/Logs/AMS-Finance.log"
	try
		do shell script "/usr/bin/curl -s --max-time 1 http://127.0.0.1:7780/health >/dev/null && echo yes"
		return
	end try
	do shell script "/usr/local/bin/node " & quoted form of (appDir & "/server.js") & " >> " & quoted form of logFile & " 2>&1 &"
end run
