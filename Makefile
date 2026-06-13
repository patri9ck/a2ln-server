BIN := a2ln
DESTDIR :=

install:
ifdef DESTDIR
	@python3 -m pip install --no-deps --prefix $(DESTDIR) .

	@install -Dm644 "$(BIN).service" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"
else
	@python3 -m pip install --no-deps .
ifeq ($(shell id -u), 0)
	@install -Dm644 "$(BIN).service" "/usr/lib/systemd/user/$(BIN).service"
else
	@install -Dm644 "$(BIN).service" "${HOME}/.local/share/systemd/user/$(BIN).service"
endif
endif

uninstall:
	@python3 -m pip uninstall -y $(BIN)
ifeq ($(shell id -u), 0)
	@rm -f "/usr/lib/systemd/user/$(BIN).service"
else
	@rm -f "${HOME}/.local/share/systemd/user/$(BIN).service"
endif

clean:
	@rm -rf build src/$(BIN).egg-info