PREFIX := /usr/local/bin/
BIN := a2ln
DESTDIR :=

install: a2ln
	install -Dm777 "$(BIN)" "$(DESTDIR)$(PREFIX)$(BIN)"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)$(BIN)"
