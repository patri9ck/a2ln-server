PREFIX := /usr/bin/
BIN := a2ln
DESTDIR :=

install:
	install -Dm777 "src/a2ln/$(BIN).py" "$(DESTDIR)$(PREFIX)$(BIN)"
	install -Dm644 "$(BIN).service" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)$(BIN)" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"