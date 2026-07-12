#!/usr/bin/env python3

from flask import Flask, render_template
from flask_socketio import SocketIO
import socket
import threading
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[Backend] %(message)s"
)

app = Flask(__name__)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

NOTEBOOK_IP = "127.0.0.1"

TELEMETRY_PORT = 5006
KILL_PORT = 6000


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def on_connect():
    logging.info("Frontend conectado.")


@socketio.on("disconnect")
def on_disconnect():
    logging.info("Frontend desconectado.")


@socketio.on("kill")
def on_kill():

    logging.warning("Comando KILL recebido do frontend.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.sendto(
        b"KILL",
        (NOTEBOOK_IP, KILL_PORT)
    )

    sock.close()

    logging.warning("Comando KILL enviado ao Serial Reader.")


def telemetry_listener():

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.bind(("", TELEMETRY_PORT))

    logging.info(
        f"Escutando telemetria UDP na porta {TELEMETRY_PORT}"
    )

    while True:

        payload, addr = sock.recvfrom(1024)

        try:

            data = json.loads(payload.decode())

            logging.info(
                f"Telemetria recebida de {addr}: {data}"
            )

            socketio.emit("telemetry", data)

        except json.JSONDecodeError:

            logging.warning("Pacote JSON inválido.")


if __name__ == "__main__":

    telemetry_thread = threading.Thread(
        target=telemetry_listener,
        daemon=True
    )

    telemetry_thread.start()

    logging.info("Servidor iniciado.")

    socketio.run(
        app,
        host="127.0.0.1",
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )