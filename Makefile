PREFIX := /usr/bin/
BIN := a2ln
DESTDIR :=

all: clean
	python3 -m build -s -n

	mv dist/$(BIN)-*.tar.gz dist/$(BIN).tar.gz

install:
ifdef DESTDIR
	python3 -m pip install --no-deps -t $(DESTDIR) -U dist/$(BIN).tar.gz
else
	python3 -m pip install --no-deps dist/$(BIN).tar.gz
endif

	install -Dm644 "$(BIN).service" "$(DESTDIR)/usr/lib/systemd/user/$(BIN).service"

uninstall:
	python3 -m pip uninstall -y $(BIN)

clean:
	rm -rf dist src/$(BIN).egg-info