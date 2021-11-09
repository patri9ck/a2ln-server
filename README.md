# Android 2 Linux Notifications Server
**Android 2 Linux Notifications** (**A2LN**) is a way to show your Android notifications on Linux with libnotify. It creates a direct socket connection from your phone to your computer whenever a notification arrives. Both devices must be in the same network.

This repository contains the server part of A2LN.
## Installation
The recommended way to install A2LN is through your package manager.
Distribution | Maintainer
------------ | ----------
[Arch Linux / Manjaro (AUR)](https://aur.archlinux.org/packages/a2ln/) | patri9ck
### Manually
Alternatively, you can clone this repository and install/uninstall A2LN manually.
```
$ git clone https://github.com/patri9ck/a2ln-server.git
$ cd a2ln-server
```
Runtime dependencies:
- Python 3
- Pillow
- PyGObject
- PyZMQ
- setproctitle
#### Installation
```
# make install
```
#### Uninstallation
```
# make uninstall
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
