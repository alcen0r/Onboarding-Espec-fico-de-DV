#!/usr/bin/env python3

import os
import pty
import time
import json
import random
import logging
import threading
import select

#Config do Logger
logging.basicConfig(
    level=logging.INFO,
    format='[FakeSender] %(message)s')

#Cria a porta do simulador do arduino
master_fd, slave_fd = pty.openpty()
slave_name = os.ttyname(slave_fd)
with open("/tmp/fake_sender_port", "w") as f:
    f.write(slave_name)

logging.info(f"Serial virtual criada em {slave_name}")
logging.info("Configure esta porta no serial_reader.py")

#Status do Motor
engine_on = True

#Linha para escutar os comandos da Jetson
def serial_listener():
    global engine_on

    while True:
        try:
            # Espera até existirem dados disponíveis para leitura
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if not ready:
                continue
            message = os.read(master_fd, 1024).decode(errors="ignore").strip()
            if not message:
                continue
            logging.info(f"Comando recebido: {message}")
            if message.upper() == "KILL":
                if engine_on:
                    logging.warning("========== KILL RECEBIDO ==========")
                    logging.warning("Motor desligado.")
                    engine_on = False
                else:
                    logging.info("Motor já estava desligado.")
        except Exception as e:
            logging.error(f"Erro ao ler serial: {e}")


# Inicia a thread que escuta comandos
listener = threading.Thread(target=serial_listener, daemon=True)
listener.start()

#Loop de envio de Telemetria
try:
    while True:
        if engine_on:
            speed = random.randint(0, 20)
            acceleration = round(random.uniform(0, 5), 1)
        else:
            speed = 0
            acceleration = 0.0
        telemetry = {
            "speed": speed,
            "acceleration": acceleration,
            "engine": engine_on
        }
        payload = json.dumps(telemetry) + "\n"
        os.write(master_fd, payload.encode())
        logging.info(f"Telemetria enviada: {payload.strip()}")
        time.sleep(0.5)
except KeyboardInterrupt:
    logging.info("Fake sender interrompido pelo usuário.")
finally:
    os.close(master_fd)
    os.close(slave_fd)
    logging.info("Porta serial encerrada.")