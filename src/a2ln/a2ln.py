"""Android 2 Linux Notifications."""
#  Android 2 Linux Notifications - A way to display Android phone notifications on Linux
#  Copyright (C) 2023  Patrick Zwick and contributors
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
from importlib import metadata
import io
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import time
import traceback
from typing import Any, Optional

import gi
from PIL import Image
import qrcode
import zmq
import zmq.auth
import zmq.auth.thread
import zmq.error

try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
except ValueError as gie:
    print(gie)
    exit(1)


BOLD = "\033[1m"
RESET = "\033[0m"


def main():
    """Main."""
    args = parse_args()
    if args.command == "version":
        print(f"Android 2 Linux Notifications {metadata.version('a2ln')}")
        print("\nFor help, see <https://patri9ck.dev/a2ln/>.")
        return

    main_directory = Path(
        Path.home(), os.environ.get("XDG_CONFIG_HOME") or ".config", "a2ln"
    )
    clients_directory = main_directory / "clients"
    own_directory = main_directory / "server"
    main_directory.mkdir(exist_ok=True)
    clients_directory.mkdir(exist_ok=True)
    if not own_directory.exists():
        own_directory.mkdir()
        zmq.auth.create_certificates(own_directory, "server")
    own_keys_file = own_directory / "server.key_secret"

    try:
        own_public_key, own_secret_key = zmq.auth.load_certificate(own_keys_file)
    except OSError:
        print(f"Own keys file at {own_keys_file} does not exist.")
        exit(1)
    except ValueError:
        print(f"Own keys file at {own_keys_file} is missing the public key.")
        exit(1)

    if args.command == "pair":
        server = PairingServer(clients_directory, own_public_key, args.ip, args.port)
    elif own_secret_key:
        server = NotificationServer(
            clients_directory,
            own_public_key,
            own_secret_key,
            args.ip,
            args.port,
            args.title_format,
            args.body_format,
            args.command,
        )
        def _typed_lambda_fn(*_: Any):
            server.toggle()
        signal.signal(signal.SIGUSR1, _typed_lambda_fn)
    else:
        print(f"Own keys file at {own_keys_file} is missing the private key.")
        exit(1)

    try:
        server.start()
        while server.is_alive():
            time.sleep(1)
        exit(1)
    except KeyboardInterrupt:
        print("\r", end="")


def parse_args():
    """Parse args."""
    argument_parser = argparse.ArgumentParser(
        description="A way to display Android phone notifications on Linux"
    )
    argument_parser.add_argument("--ip", type=str, default="*", help="The IP to listen")
    argument_parser.add_argument(
        "--port", type=int, default=23045, help="The port to listen)"
    )
    argument_parser.add_argument(
        "--title-format",
        type=str,
        default="{title}",
        help="The format of the title. "
        "Available placeholders: {app}, "
        "{title}, {body}",
    )
    argument_parser.add_argument(
        "--body-format",
        type=str,
        default="{body}",
        help="The format of the body. Available "
        "placeholders: {app}, {title}, "
        "{body}",
    )
    argument_parser.add_argument(
        "--command",
        type=str,
        help="A shell command to run whenever a notification arrives. "
        "Available placeholders: {app}, {title}, {body}",
    )

    sub_parser = argument_parser.add_subparsers(title="commands", dest="command")
    sub_parser.add_parser("version", help="Show the version and exit")
    pair_parser = sub_parser.add_parser("pair", help="Run the pairing server")

    pair_parser.add_argument("--ip", type=str, default="*", help="The IP to listen")
    pair_parser.add_argument(
        "--port", type=int, help="The port to listen, random by default"
    )

    return argument_parser.parse_args()


def get_ip():
    """Get IP."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.connect(("8.8.8.8", 80))
        return client.getsockname()[0]


def send_notification(title: str, body: str, picture_file: Optional[Any] = None):
    """Send notification."""
    if picture_file is None:
        Notify.Notification.new(title, body, "dialog-information").show()
    else:
        Notify.Notification.new(title, body, picture_file.name).show()

        picture_file.close()


def handle_error(error: zmq.error.ZMQError):
    """Handle error."""
    if error.errno == zmq.EADDRINUSE:
        print("Port is already used.")
    elif error.errno == 13:
        print("Permission denied (note: use a port > 1023 if you're not root user).")
    elif error.errno == 19:
        print("IP is invalid.")
    else:
        traceback.print_exc()


class NotificationServer(threading.Thread):
    """Notification server."""

    def __init__(
        self,
        clients_directory: Path,
        own_public_key: bytes,
        own_secret_key: bytes,
        ip: str,
        port: int,
        title_format: str,
        body_format: str,
        command: Optional[str],
    ):
        """Initialize notification server."""
        super(NotificationServer, self).__init__(daemon=True)

        self.clients_directory = clients_directory
        self.own_public_key = own_public_key
        self.own_secret_key = own_secret_key
        self.ip = ip
        self.port = port
        self.title_format = title_format
        self.body_format = body_format
        self.command = command

        self.enabled = True

    def run(self):
        """Run notification server."""
        super(NotificationServer, self).run()

        with zmq.Context() as context:
            authenticator = zmq.auth.thread.ThreadAuthenticator(context)
            authenticator.start()
            authenticator.configure_curve(
                domain="*", location=self.clients_directory.as_posix()
            )

            with context.socket(zmq.PULL) as server:
                server.curve_publickey = self.own_public_key
                server.curve_secretkey = self.own_secret_key
                server.curve_server = True

                try:
                    server.bind(f"tcp://{self.ip}:{self.port}")
                except zmq.error.ZMQError as error:
                    authenticator.stop()
                    handle_error(error)
                    return

                print(
                    f"Notification server running on IP {BOLD}{self.ip}{RESET}"
                    + f" and port {BOLD}{self.port}{RESET}."
                )

                Notify.init("Android 2 Linux Notifications")

                while True:
                    request = server.recv_multipart()
                    length = len(request)
                    if length != 3 and length != 4:
                        continue
                    if length == 4:
                        picture_file = tempfile.NamedTemporaryFile(suffix=".png")
                        Image.open(io.BytesIO(request[3])).save(picture_file.name)
                    else:
                        picture_file = None

                    app = request[0].decode("utf-8")
                    title = request[1].decode("utf-8")
                    body = request[2].decode("utf-8")

                    print(
                        f"\nReceived notification (Title: {BOLD}{title}{RESET},"
                        + " Body: {BOLD}{body}{RESET})"
                    )

                    if not self.enabled:
                        continue

                    def replace(text: str):
                        return (
                            text.replace("{app}", app)
                            .replace("{title}", title)
                            .replace("{body}", body)
                        )

                    threading.Thread(
                        target=send_notification,
                        args=(
                            replace(self.title_format),
                            replace(self.body_format),
                            picture_file,
                        ),
                        daemon=True,
                    ).start()

                    if self.command is not None:
                        subprocess.Popen(replace(self.command), shell=False)

    def toggle(self):
        """Toggle notification."""
        self.enabled = not self.enabled
        print("\nNotifications", "enabled." if self.enabled else "disabled.")


class PairingServer(threading.Thread):
    """Pairing server."""

    def __init__(
        self,
        clients_directory: Path,
        own_public_key: bytes,
        ip: str,
        port: Optional[int],
    ):
        """Initialize pairing server."""
        super(PairingServer, self).__init__(daemon=True)

        self.clients_directory = clients_directory
        self.own_public_key = own_public_key
        self.ip = ip
        self.port = port

    def run(self):
        """Run pairing server."""
        super(PairingServer, self).run()

        with zmq.Context() as context, context.socket(zmq.REP) as server:
            try:
                if self.port is None:
                    self.port = server.bind_to_random_port(f"tcp://{self.ip}")
                else:
                    server.bind(f"tcp://{self.ip}:{self.port}")
            except zmq.error.ZMQError as error:
                handle_error(error)

                return

            ip = get_ip()
            qr_code = qrcode.QRCode()
            qr_code.add_data(f"{ip}:{self.port}")
            qr_code.print_ascii()

            print(
                f"Pairing server running on IP {BOLD}{self.ip}{RESET} and"
                + f" port {BOLD}{self.port}{RESET}. To pair a "
                + "new device, open the Android 2 Linux Notifications app"
                + "and scan this QR code or enter the following:"
            )
            print(f"IP: {BOLD}{ip}{RESET}")
            print(f"Port: {BOLD}{self.port}{RESET}")
            print(f"\nPublic Key: {BOLD}{self.own_public_key.decode('utf-8')}{RESET}")
            print("\nAfter pairing, restart the notification server.")

            while True:
                request = server.recv_multipart()
                if len(request) != 2:
                    continue
                client_ip = request[0].decode("utf-8")
                client_public_key = request[1].decode("utf-8")
                print("\nNew pairing request:")
                print(f"\nIP: {BOLD}{client_ip}{RESET}")
                print(f"\nPublic Key: {BOLD}{client_public_key}{RESET}")
                if input("Accept? (Yes/No): ").lower() != "yes":
                    print("Pairing cancelled.")
                    server.send(b"")
                    continue

                with open(
                    (self.clients_directory / client_ip).as_posix() + ".key",
                    "w",
                    encoding="utf-8",
                ) as client_file:
                    client_file.write(
                        f"metadata\ncurve\n    public-key = '{client_public_key}'\n"
                    )

                server.send(self.own_public_key)
                print("Pairing finished.")
