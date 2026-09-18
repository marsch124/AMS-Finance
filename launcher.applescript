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
	-- Open the AMS Main Hub APP — the front door to everything; the Finance Hub is one
	-- card away on its FINANCE shelf. Never a browser tab: a tab, like any second web app
	-- on the same address, keeps its own EMPTY copy of the hub, and on 2026-09-18 that
	-- looked exactly like his wealth accounts had vanished. The address is only a fallback
	-- for a Mac where the app has not been added yet.
	try
		do shell script "/usr/bin/open -a " & quoted form of "AMS Main Hub"
	on error
		do shell script "/usr/bin/open http://localhost:7780"
	end try
end run
