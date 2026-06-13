PREFIX := /usr/local/bin/
BIN := a2ln
SRCDIR :=
DESTDIR :=

install: a2ln
	install -Dm777 "$(SRCDIR)$(BIN)" "$(DESTDIR)$(PREFIX)$(BIN)"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)$(BIN)"
