PREFIX := /usr
BIN := a2ln
FLAGS :=
DESTDIR :=

install:
ifeq ($(shell [ "$(shell id -u)" = 0 ] || [ -n "$(DESTDIR)" ] && echo 0), 0)
	@python3 -m pip install $(FLAGS) -I --prefix $(DESTDIR)/$(PREFIX) .

	@install -Dm644 "$(BIN).service" "$(DESTDIR)/$(PREFIX)/lib/systemd/user/$(BIN).service"
else
	@python3 -m pip install $(FLAGS) .

	@install -Dm644 "$(BIN).service" "${HOME}/.local/share/systemd/user/$(BIN).service"
	@sed -i 's/ExecStart=.*/ExecStart=%h\/.local\/bin\/a2ln --no-pairing-server/' "${HOME}/.local/share/systemd/user/$(BIN).service"
endif

uninstall:
	@python3 -m pip uninstall -y $(BIN)

ifeq ($(shell id -u), 0)
	@rm -f "$(PREFIX)/lib/systemd/user/$(BIN).service"
else
	@rm -f "${HOME}/.local/share/systemd/user/$(BIN).service"
endif

clean:
	@rm -rf build dist src/$(BIN).egg-info