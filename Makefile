PYTHON = python3.exe
SCRIPT = tieba.py
SQLITE3 = sqlite3.exe
DB = tieba.sqlite3
EDITOR = "C:\Program Files\Notepad++\notepad++.exe"
LIST = tieba.list

all:
	$(PYTHON) $(SCRIPT)

list:
	$(EDITOR) $(LIST)

clean:
	rm -rf *.log

sql:
	$(SQLITE3) $(DB)

backup:
	cp $(DB) $(DB).bak

query:
	$(SQLITE3) $(DB) "SELECT COUNT(*) FROM Image GROUP BY status;"