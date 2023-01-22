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
import socket
import subprocess
import tempfile
import threading
import time
import traceback
from argparse import Namespace
from pathlib import Path

import gi
import qrcode
import setproctitle
import zmq
import zmq.auth
import zmq.auth.thread
import zmq.error
from PIL import Image

gi.require_version('Notify', '0.7')

from gi.repository import Notify

BOLD = "\033[1m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
RESET = "\033[0m"

PREFIX = "==> "
GREEN_PREFIX = f"{GREEN}{PREFIX}{RESET}"
RED_PREFIX = f"{RED}{PREFIX}{RESET}"


def main():
    try:
        setproctitle.setproctitle("a2ln")

        main_directory = Path(Path.home(), os.environ.get("XDG_CONFIG_HOME") or ".config", "a2ln")

        client_public_keys_directory = main_directory / "clients"
        own_keys_directory = main_directory / "server"

        main_directory.mkdir(exist_ok=True)

        client_public_keys_directory.mkdir(exist_ok=True)

        if not own_keys_directory.exists():
            own_keys_directory.mkdir()

            zmq.auth.create_certificates(own_keys_directory, "server")

        args = parse_args()

        own_public_key, own_secret_key = zmq.auth.load_certificate(own_keys_directory / "server.key_secret")

        notification_server = None
        pairing_server = None

        if not args.no_notification_server:
            notification_server = NotificationServer(client_public_keys_directory, own_public_key, own_secret_key,
                                                     args.notification_ip, args.notification_port, args.title_format,
                                                     args.body_format,
                                                     args.command)

            notification_server.start()

        if not args.no_pairing_server:
            if notification_server is not None and notification_server.is_alive():
                time.sleep(1)

            pairing_server = PairingServer(client_public_keys_directory, own_public_key, args.pairing_ip,
                                           args.pairing_port, notification_server)

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


def send_notification(title: str, text: str, picture_file: tempfile = None) -> None:
    if picture_file is None:
        Notify.Notification.new(title, text, "dialog-information").show()
    else:
        Notify.Notification.new(title, text, picture_file.name).show()

        picture_file.close()

    print(f"{GREEN_PREFIX}Sent notification (Title: {BOLD}{title}{RESET}, Text: {BOLD}{text}{RESET})")


def inform(name: str, ip: str = None, port: int = None, error: zmq.error.ZMQError = None) -> None:
    if error is None:
        print(
            f"{GREEN_PREFIX}{name.capitalize()} server running on IP {BOLD}{ip}{RESET} and port {BOLD}{port}{RESET}.")

        return

    print(f"{RED_PREFIX}Cannot start {name.lower()} server:", end=" ")

    if error.errno == zmq.EADDRINUSE:
        print("Port already used")
    elif error.errno == 13:
        print("No permission (note that you must use a port higher than 1023 if you are not root)")
    elif error.errno == 19:
        print("Invalid IP")
    else:
        traceback.print_exc()


class NotificationServer(threading.Thread):
    def __init__(self, client_public_keys_directory: Path, own_public_key: bytes, own_secret_key: bytes, ip: str,
                 port: int, title_format: str, body_format: str, command: str):
        super(NotificationServer, self).__init__(daemon=True)

        self.client_public_keys_directory = client_public_keys_directory
        self.own_public_key = own_public_key
        self.own_secret_key = own_secret_key
        self.ip = ip
        self.port = port
        self.title_format = title_format
        self.body_format = body_format
        self.command = command
        self.authenticator = None

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

                print(
                    "Do not forget to autostart the notification server. More information can be found at https://patri9ck.dev/a2ln/server.html#autostarting.")

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

                    def replace(text: str) -> str:
                        return text.replace("{app}", app).replace("{title}", title).replace("{body}", body)

                    threading.Thread(target=send_notification,
                                     args=(replace(self.title_format), replace(self.body_format), picture_file),
                                     daemon=True).start()

                    if self.command is not None:
                        subprocess.Popen(replace(self.command), shell=True)

    def update_client_public_keys(self) -> None:
        if self.authenticator is not None and self.authenticator.is_alive():
            self.authenticator.configure_curve(domain="*", location=self.client_public_keys_directory.as_posix())


class PairingServer(threading.Thread):
    def __init__(self, client_public_keys_directory: Path, own_public_key: bytes, ip: str, port: int,
                 notification_server: NotificationServer):
        super(PairingServer, self).__init__(daemon=True)

        self.client_public_keys_directory = client_public_keys_directory
        self.own_public_key = own_public_key
        self.ip = ip
        self.port = port
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

                with open((self.client_public_keys_directory / client_ip).as_posix() + ".key", "w",
                          encoding="utf-8") as client_key_file:
                    client_key_file.write("metadata\n"
                                          "curve\n"
                                          f"    public-key = \"{client_public_key}\"\n")

                server.send_multipart([str(self.notification_server.port).encode("utf-8"), self.own_public_key])

                if self.notification_server is not None:
                    self.notification_server.update_client_public_keys()

                print("Pairing finished.")
