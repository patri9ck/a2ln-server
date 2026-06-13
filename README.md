# Android 2 Linux Notifications Server
This is the server part of **Android 2 Linux Notifications**. It consists of a simple Python script.
## Installation
The recommended way to install A2LN is through your package manager.
Distribution | Maintainer
------------ | ----------
[Arch Linux / Manjaro](https://aur.archlinux.org/packages/a2ln/) | patri9ck
### Manual Installation
Alternatively, you can clone this repository and place the `a2ln` Python script somewhere into your `PATH` variable:
```
$ git clone https://github.com/patri9ck/a2ln-server.git
$ mv a2ln-server
# mv a2ln-server/a2ln /usr/local/bin
```
## Usage
After the installation, simply run A2LN like this:
```
$ a2ln <PORT>
```
Replace `<PORT>` with the port you want to use. **You must use a port higher than 1023 if you are not root**.

If A2LN started correctly, it should show a message like this:
```
Address: 192.168.178.41:6000
```
This is the address you have to enter in the [A2LN app](https://github.com/patri9ck/a2ln-app).
### Auto-starting
Common options to auto-start A2LN are:
- `~/.bash_profile`, `~/.zprofile`, ...
- `~/.xinitrc` or `~/.xprofile`
- Systemd user units
- Auto-start functions of your desktop environment or window manager

Make sure to launch it in the background:
```
a2ln <PORT> &
```
## License
A2LN is licensed under the [GPL3](LICENSE).
