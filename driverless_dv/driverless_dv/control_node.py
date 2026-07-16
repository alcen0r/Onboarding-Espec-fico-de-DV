import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray

import math
import json
import socket
import threading
import serial

WHEELBASE = 0.0 #a medir: distância entre os eixos do carro
STEERING_CENTER = 90 #posicao padrão inicial
STEERING_MIN = 45 #a medir: esterçamento mínimo
STEERING_MAX = 135 #a medir: esterçamento máximo
CONSTANT_THRUST = 20 #porcentagem da potencia constante pra velocidade constante (recomendada)

SERIAL_PORT = "/dev/ttyACM0" #checar: corresponde ao arquivo que representa a conexao USB com o arduino
SERIAL_RATE = 115200 #velocidade do codigo v1.ino

TELEMETRY_IP = "127.0.0.1" #ip registrado no codigo de telemetria
TELEMETRY_PORT = 5006 #porta que vem do codigo de telemetria
KILL_LISTEN_PORT = 6000 #mesma coisa que o anterior


class ControlNode(Node):
    def __init__(self):
        super().__init__('control_node')

        self.subscription = self.create_subscription(
            Float32MultiArray,
            "waypoint",
            self.waypoint_callback,
            10
        )

        try:
            self.serial = serial.Serial(SERIAL_PORT, SERIAL_RATE, timeout=1)
        except serial.SerialException:
            self.serial = None
            self.get_logger().warn(
                f"Nao foi possivel abrir {SERIAL_PORT} -- rodando em modo simulado "
                "(comandos serao logados, nao enviados de verdade)"
            )

        self.telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.emergency_stop = False

        kill_thread = threading.Thread(target=self.kill_listener, daemon=True)
        kill_thread.start()

        self.get_logger().info("Control node iniciado")

    def waypoint_callback(self, msg):
        data = msg.data

        xm = data[0]
        ym = data[1]

        # caso apertem o kill, nem precisa calcular a potencia, ja freia na hora
        if self.emergency_stop:
            # state = 0 é uma das condições do arquivo v1.ino, correspondente ao freio suave
            self.send_command(STEERING_CENTER, state=0, power=0)
            self.send_telemetry(xm, ym, power = 0, engine = False)
            return

        # caso esteja tranquilo, calcula o angulo, envia o movimento e envia telemetria
        steering_angle = self.calculate_steering_angle(xm, ym)

        self.send_command(steering_angle, state=1, power=CONSTANT_THRUST)
        self.send_telemetry(xm, ym, CONSTANT_THRUST, True)

    def calculate_steering_angle(self, xm, ym):
        alpha = math.atan2(ym, xm)
        dist = math.pow((xm ** 2 + ym ** 2), 0.5)
        delta_pursuitRAD = math.atan2(2 * WHEELBASE * math.sin(alpha), dist)
        delta_pursuitDEG = math.degrees(delta_pursuitRAD)
        # evitamos passar do limite; se o waypoint estiver na frente, o angulo continua 90 graus
        displacement_angle = max(STEERING_MIN, min(STEERING_MAX, STEERING_CENTER + delta_pursuitDEG))
        # SE O CARRO VIRAR PRO LADO ERRADO: trocar o sinal de ym ou de alpha
        return displacement_angle

    def send_command(self, angleDEG, state, power):
        angleDEG = max(0, min(180, angleDEG))
        angleDEG = str(format(int(angleDEG), '02X'))
        state = str(state)
        power = max(0, min(100, power))
        power = str(format(int(power), '02X'))
        message = angleDEG + state + power

        if self.serial is not None:
            self.serial.write(message.encode())
        else:
            self.get_logger().info(f"[SIMULADO] mandaria pra serial: {message}")

    def send_telemetry(self, xm, ym, power, engine):
        # apenas uma aproximação, dado que ainda não temos PD/sensor de velocidade
        speed = power
        message = {"speed": speed, "acceleration": 0.0, "engine": engine}
        messageToSend = (json.dumps(message)).encode()
        self.telemetry_socket.sendto(messageToSend, (TELEMETRY_IP, TELEMETRY_PORT))

    def kill_listener(self,):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", KILL_LISTEN_PORT))
        self.get_logger().info(f"Kill switch escutando na porta {KILL_LISTEN_PORT}")
        while True:
            payload, addr = sock.recvfrom(1024)
            if payload == b"KILL":
                self.get_logger().warn("KILL recebido! Parando o carro...")
                self.emergency_stop = True
                self.send_command(STEERING_CENTER, state=0, power=0)
                self.send_telemetry(0.0, 0.0, power=0, engine=False)


def main(args=None):
    rclpy.init(args=args)
    node = ControlNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()