PREFIX := /usr
BIN := a2ln
DESTDIR :=

dist/*.whl:
	@python -m build --wheel --no-isolation

install: dist/*.whl
ifdef DESTDIR
	@python -m installer -p "$(PREFIX)" -d "$(DESTDIR)" dist/*.whl
else
	@python -m installer -p "$(PREFIX)" dist/*.whl
endif
	@install -Dm644 "$(BIN).service" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"

uninstall:
	@python -m pip uninstall --break-system-packages -y $(BIN)

	@rm -f "/usr/lib/systemd/user/$(BIN).service"

clean:
	@rm -rf build dist src/$(BIN).egg-info