-- AMS Save Panel — shows Apple's own Save window for the Main Hub's backup.
--
-- The Finance engine cannot show a window itself: it runs in the background, detached
-- from the login session, so a dialog it opens has nowhere to appear and just hangs.
-- So the engine launches this tiny app instead (with `open`, which starts it properly
-- in his session). It reads what to suggest from a request file, lets him name the file
-- and browse to any folder, and writes his choice back. It never writes the backup —
-- the engine does that and then reads the file's size back off the disk.
on run
	set supportDir to (POSIX path of (path to home folder)) & "Library/Application Support/AMS Finance/"
	set reqPath to supportDir & "savepanel-request.txt"
	set resPath to supportDir & "savepanel-result.txt"
	set suggested to "ams-mainhub-backup.json"
	set startDir to POSIX path of (path to downloads folder)
	try
		set req to paragraphs of (read (POSIX file reqPath) as «class utf8»)
		if (count of req) ≥ 1 then
			if item 1 of req is not "" then set suggested to item 1 of req
		end if
		if (count of req) ≥ 2 then
			if item 2 of req is not "" then set startDir to item 2 of req
		end if
	end try
	set startFolder to missing value
	try
		set startFolder to (POSIX file startDir) as alias
	on error
		set startFolder to path to downloads folder
	end try
	activate
	try
		set chosen to choose file name with prompt "Save your AMS Main Hub backup" default name suggested default location startFolder
		set answer to POSIX path of chosen
	on error number -128
		set answer to "CANCELLED"
	end try
	set f to open for access (POSIX file resPath) with write permission
	set eof f to 0
	write answer to f as «class utf8»
	close access f
end run
