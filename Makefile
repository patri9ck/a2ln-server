PREFIX := /usr/local/bin/
BIN := a2ln
PORT := 8880
DESTDIR :=

install: a2ln
	install -Dm777 "$(BIN)" "$(DESTDIR)$(PREFIX)$(BIN)"
	cp a2ln.service /etc/systemd/system/$(BIN).service
	sed -i 's/PORT/$(PORT)/g' /etc/systemd/system/$(BIN).service
	systemctl daemon-reload

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)$(BIN)"
	rm -f /etc/systemd/system/$(BIN).service
