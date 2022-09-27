PREFIX := /usr/local/bin/
BIN := a2ln
DESTDIR :=

install: a2ln
	install -Dm777 "$(BIN)" "$(DESTDIR)$(PREFIX)$(BIN)"
	cp a2ln.service /etc/systemd/system/a2ln.service 
uninstall:
	rm -f "$(DESTDIR)$(PREFIX)$(BIN)"
