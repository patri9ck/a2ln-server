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
import io
import os
import signal
import socket
import subprocess
import tempfile
import threading
import time
import traceback
from argparse import Namespace
from pathlib import Path
from typing import Optional

import gi
import qrcode  # type: ignore
import zmq
import zmq.auth
import zmq.auth.thread
import zmq.error
from PIL import Image

gi.require_version('Notify', '0.7')

from gi.repository import Notify  # type: ignore # noqa: E402

BOLD = "\033[1m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
RESET = "\033[0m"

PREFIX = "==> "
GREEN_PREFIX = f"{GREEN}{PREFIX}{RESET}"
RED_PREFIX = f"{RED}{PREFIX}{RESET}"


def main():
    try:
        main_directory = Path(Path.home(), os.environ.get("XDG_CONFIG_HOME") or ".config", "a2ln")

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
            print(f"{RED_PREFIX}Own keys file at {own_keys_file} does not exist.")

            exit(1)
        except ValueError:
            print(f"{RED_PREFIX}Own keys file at {own_keys_file} is missing the public key.")

            exit(1)

        args = parse_args()

        notification_server, pairing_server = None, None

        if not args.no_notification_server:
            if own_secret_key:
                notification_server = NotificationServer(clients_directory, own_public_key, own_secret_key,
                                                         args.notification_ip, args.notification_port, args.command,
                                                         args.title_format, args.body_format)

                notification_server.start()

                signal.signal(signal.SIGUSR1, lambda *_: notification_server.toggle())
            else:
                inform("notification", error_text=f"Own keys file at {own_keys_file} is missing the private key.")

        time.sleep(1)

        if not args.no_pairing_server:
            pairing_server = PairingServer(clients_directory, own_public_key, args.pairing_ip,
                                           args.pairing_port, args.notification_port, notification_server)

            pairing_server.start()

        while notification_server is not None and notification_server.is_alive() or pairing_server is not None and pairing_server.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\r", end="")

        exit()


def parse_args() -> Namespace:
    argument_parser = argparse.ArgumentParser(description="A way to display Android phone notifications on Linux")

    argument_parser.add_argument("--no-notification-server", action="store_true", default=False,
                                 help="Do not start the notification server")
    argument_parser.add_argument("--notification-ip", type=str, default="*",
                                 help="The IP to listen for notifications (by default *)")
    argument_parser.add_argument("--notification-port", type=int, default=23045,
                                 help="The port to listen for notifications (by default 23045)")
    argument_parser.add_argument("--no-pairing-server", action="store_true", default=False,
                                 help="Do not start the pairing server")
    argument_parser.add_argument("--pairing-ip", type=str, default="*",
                                 help="The IP to listen for pairing requests (by default *)")
    argument_parser.add_argument("--pairing-port", type=int,
                                 help="The port to listen for pairing requests (by default random)")
    argument_parser.add_argument("--title-format", type=str, default="{title}",
                                 help="The format of the title. Available placeholders: {app}, {title}, {body} (by default {title})")
    argument_parser.add_argument("--body-format", type=str, default="{body}",
                                 help="The format of the body. Available placeholders: {app}, {title}, {body} (by default {body})")
    argument_parser.add_argument("--command", type=str,
                                 help="A shell command to run whenever a notification arrives. Available placeholders: {app}, {title}, {body} (by default none)")

    return argument_parser.parse_args()


def get_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.connect(("8.8.8.8", 80))

        return client.getsockname()[0]


def send_notification(title: str, body: str, picture_file=None) -> None:
    if picture_file is None:
        Notify.Notification.new(title, body, "dialog-information").show()
    else:
        Notify.Notification.new(title, body, picture_file.name).show()

        picture_file.close()


def inform(name: str, ip: Optional[str] = None, port: Optional[int] = None,
           error: Optional[zmq.error.ZMQError] = None, error_text: Optional[str] = None) -> None:
    if error is None and error_text is None:
        print(
            f"{GREEN_PREFIX}{name.capitalize()} server running on IP {BOLD}{ip}{RESET} and port {BOLD}{port}{RESET}.")

        return

    print(f"{RED_PREFIX}Cannot start {name.lower()} server:", end=" ")

    if error_text is not None:
        print(error_text)
    elif error.errno == zmq.EADDRINUSE:  # type: ignore
        print("Port already used")
    elif error.errno == 13:  # type: ignore
        print("No permission (note that you must use a port higher than 1023 if you are not root)")
    elif error.errno == 19:  # type: ignore
        print("Invalid IP")
    else:
        traceback.print_exc()


class NotificationServer(threading.Thread):
    def __init__(self, clients_directory: Path, own_public_key: bytes, own_secret_key: bytes, ip: str,
                 port: int, command: Optional[str], title_format: Optional[str], body_format: Optional[str]):
        super(NotificationServer, self).__init__(daemon=True)

        self.clients_directory = clients_directory
        self.own_public_key = own_public_key
        self.own_secret_key = own_secret_key
        self.ip = ip
        self.port = port
        self.command = command
        self.enabled = True
        self.title_format = "{title}" if title_format is None else title_format
        self.body_format = "{body}" if body_format is None else body_format

        self.authenticator: Optional[zmq.auth.thread.ThreadAuthenticator] = None

    def run(self) -> None:
        super(NotificationServer, self).run()

        with zmq.Context() as context:
            self.authenticator = zmq.auth.thread.ThreadAuthenticator(context)

            self.authenticator.start()

            self.update_client_public_keys()

            with context.socket(zmq.PULL) as server:
                server.curve_publickey = self.own_public_key
                server.curve_secretkey = self.own_secret_key

                server.curve_server = True

                try:
                    server.bind(f"tcp://{self.ip}:{self.port}")
                except zmq.error.ZMQError as error:
                    self.authenticator.stop()

                    inform("notification", error=error)

                    return

                inform("notification", ip=self.ip, port=self.port)

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
                        f"{GREEN_PREFIX}Received notification (Title: {BOLD}{title}{RESET}, Body: {BOLD}{body}{RESET})")

                    if not self.enabled:
                        continue

                    def replace(text: str) -> str:
                        return text.replace("{app}", app).replace("{title}", title).replace("{body}", body)

                    threading.Thread(target=send_notification,
                                     args=(replace(self.title_format), replace(self.body_format), picture_file),
                                     daemon=True).start()

                    if self.command is not None:
                        subprocess.Popen(replace(self.command), shell=True)

    def update_client_public_keys(self) -> None:
        if self.authenticator is not None and self.authenticator.is_alive():
            self.authenticator.configure_curve(domain="*", location=self.clients_directory.as_posix())

    def toggle(self) -> None:
        self.enabled = not self.enabled

        if self.enabled:
            print(f"{GREEN_PREFIX}Notification server is enabled")
        else:
            print(f"{GREEN_PREFIX}Notification server is disabled")


class PairingServer(threading.Thread):
    def __init__(self, clients_directory: Path, own_public_key: bytes, ip: str, port: Optional[int],
                 notification_port: int, notification_server: Optional[NotificationServer]):
        super(PairingServer, self).__init__(daemon=True)

        self.clients_directory = clients_directory
        self.own_public_key = own_public_key
        self.ip = ip
        self.port = port
        self.notification_port = notification_port
        self.notification_server = notification_server

    def run(self) -> None:
        super(PairingServer, self).run()

        with zmq.Context() as context, context.socket(zmq.REP) as server:
            try:
                if self.port is None:
                    self.port = server.bind_to_random_port(f"tcp://{self.ip}")
                else:
                    server.bind(f"tcp://{self.ip}:{self.port}")
            except zmq.error.ZMQError as error:
                inform("pairing", error=error)

                return

            ip = get_ip()

            qr_code = qrcode.QRCode()

            qr_code.add_data(f"{ip}:{self.port}")
            qr_code.print_ascii()

            inform("pairing", ip=self.ip, port=self.port)

            print(
                "To pair a new device, open the Android 2 Linux Notifications app and scan this QR code or enter the following:")
            print(f"IP: {BOLD}{ip}{RESET}")
            print(f"Port: {BOLD}{self.port}{RESET}")
            print(f"{GREEN_PREFIX}Public Key: {BOLD}{self.own_public_key.decode('utf-8')}{RESET}")

            while True:
                request = server.recv_multipart()

                if len(request) != 2:
                    continue

                client_ip = request[0].decode("utf-8")
                client_public_key = request[1].decode("utf-8")

                print(f"{GREEN_PREFIX}New pairing request")
                print(f"IP: {BOLD}{client_ip}{RESET}")
                print(f"Public Key: {BOLD}{client_public_key}{RESET}")

                if input("Accept? (Yes/No): ").lower() != "yes":
                    print("Pairing cancelled.")

                    server.send_multipart([b""])

                    continue

                with open((self.clients_directory / client_ip).as_posix() + ".key", "w",
                          encoding="utf-8") as client_file:
                    client_file.write("metadata\n"
                                      "curve\n"
                                      f"    public-key = \"{client_public_key}\"\n")

                server.send_multipart([str(self.notification_port).encode("utf-8"), self.own_public_key])

                if self.notification_server is not None:
                    self.notification_server.update_client_public_keys()

                print("Pairing finished.")
