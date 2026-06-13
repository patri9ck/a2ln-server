PREFIX := /usr/bin/
BIN := a2ln
DESTDIR :=

install: $(BIN) $(BIN).service
	install -Dm777 "$(BIN)" "$(DESTDIR)$(PREFIX)$(BIN)"
	install -Dm644 "$(BIN).service" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)$(BIN)" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"
