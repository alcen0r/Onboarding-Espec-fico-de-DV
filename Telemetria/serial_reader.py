#!/usr/bin/env python3
import serial
import socket
import json
import threading
import logging
import sys

# Configura o formato das mensagens exibidas no terminal.
logging.basicConfig(level=logging.INFO, format='[SerialReader] %(message)s')

# Porta serial criada pelo fake_sender.py.
with open("/tmp/fake_sender_port") as f:
    SERIAL_PORT = f.read().strip()

# Baudrate utilizado na comunicação serial.
BAUDRATE = 9600

# Endereço IP do computador que executa o backend.
NOTEBOOK_IP = "127.0.0.1"

# Porta UDP usada para enviar a telemetria.
TELEMETRY_PORT = 5006

# Porta UDP usada para receber o comando KILL.
KILL_PORT = 6000

# Tenta abrir a porta serial para receber a telemetria.
try:
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    logging.info(f"Porta serial aberta: {SERIAL_PORT}")
except serial.SerialException as e:
    logging.error(f"Não foi possível abrir a porta serial: {e}")
    sys.exit(1)

# Escuta continuamente comandos KILL enviados pelo backend.
def udp_kill_listener():

    # Cria um socket UDP para receber comandos.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Associa o socket à porta de escuta.
    sock.bind(("", KILL_PORT))

    logging.info(f"Escutando comandos KILL na porta {KILL_PORT}")

    while True:
        try:
            # Aguarda o recebimento de um pacote UDP.
            msg, addr = sock.recvfrom(1024)
            # Converte os bytes recebidos em texto.
            command = msg.decode().strip().upper()
            # Processa apenas o comando KILL.
            if command == "KILL":
                logging.warning(f"Comando KILL recebido de {addr}")
                # Encaminha o comando para o Arduino simulado.
                ser.write(b"KILL\n")
                # Garante o envio imediato pela serial.
                ser.flush()
                logging.info("Comando enviado para a serial.")
        except Exception as e:
            logging.error(f"Erro no listener UDP: {e}")


# Inicia a thread responsável por receber comandos KILL.
threading.Thread(target=udp_kill_listener, daemon=True).start()

# Cria o socket UDP que enviará a telemetria ao backend.
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

try:
    # Lê continuamente os dados enviados pela serial.
    while True:
        # Lê uma linha completa da porta serial.
        raw = ser.readline().decode(errors="ignore").strip()
        # Ignora leituras vazias.
        if not raw:
            continue
        try:
            # Converte o JSON recebido para um dicionário Python.
            data = json.loads(raw)
        except json.JSONDecodeError:
            logging.error(f"JSON inválido: {raw}")
            continue
        logging.info(f"Recebido da serial: {data}")
        # Encaminha a telemetria para o backend via UDP.
        udp_sock.sendto(raw.encode(), (NOTEBOOK_IP, TELEMETRY_PORT))
        logging.info("Telemetria enviada ao notebook.")

# Permite finalizar o programa com Ctrl + C.
except KeyboardInterrupt:
    logging.info("Serial Reader interrompido pelo usuário.")
finally:
    # Fecha a conexão serial.
    ser.close()
    # Fecha o socket UDP.
    udp_sock.close()
    logging.info("Conexões encerradas.")