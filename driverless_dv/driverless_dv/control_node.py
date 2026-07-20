# Bibliotecas necessárias para o funcionamento do ROS2
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray

# Bibliotecas necessárias para operações matemáticas, comunicação, paralelismo de tarefas (threading) e 
# escrever na porta serial
import math
import json
import socket
import threading
import time
import serial

# Distância entre os eixos do carrinho, para uso no Pure Pursuit
WHEELBASE = 0.29
# Posição padrão (e inicial) do eixo de esterçamento
STEERING_CENTER = 90 
# Limite mínimo de esterçamento
STEERING_MIN = 45
# Limite máximo de esterçamento
STEERING_MAX = 135 
# Porcentagem da potência enviada para o carrinho. Constante por recomendação.
CONSTANT_THRUST = 75

# Distância até o waypoint para determinar se o carrinho já atingiu a posição média - em prol de estacionar
ARRIVAL_RADIUS = 0.30
# Intervalo de tempo entre envios de waypoint -> um tempo maior gera uma parada por segurança
WAYPOINT_TIMEOUT = 1.0

# Pasta que representa a conexão USB com o arduíno, para enviar as informações de comando
SERIAL_PORT = "/dev/ttyACM0"
# Velocidade de envio de bytes pela porta serial que a jetson e arduíno usam para se comunicar, sincronizados
SERIAL_RATE = 115200

# Informações de IP e portas de comunicação entre controle e a telemetria, para enviar e receber dados e comandos.
NOTEBOOK_IP = "143.106.207.64"
TELEMETRY_PORT = 5006
KILL_LISTEN_PORT = 6000

class ControlNode(Node):
    def __init__(self):
        "Método construtor do nó de Controle"

        # Herda da classe Node padrão do ros2, atribuindo um id 'control_node' para identificação no comando ros2 run
        super().__init__('control_node')

        # O nó de controle se inscreve no tópico waypoint para receber os pontos gerados pelo mapping
        self.subscription = self.create_subscription(Float32MultiArray, "waypoint", self.waypoint_callback, 10)

        try:
            # Inicia a comunicação com a porta serial do arduíno
            self.serial = serial.Serial(SERIAL_PORT, SERIAL_RATE, timeout=1)
            # O Arduino reseta sozinho ao abrir a serial (comportamento do hardware) e 
            # leva um tempo pra ficar pronto de novo.
            # Sem esse sleep, os primeiros comandos mandados logo depois de abrir a 
            # porta podem se perder silenciosamente, sem erro nenhum aparecer.
            time.sleep(2.0)
        except serial.SerialException:
            # Essa parte corresponde a uma exceção em que controle não consegue detectar o arduíno conectado.
            # Utilizamos isso para simular e testar o envio de mensagens sem ter o carrinho em mãos.
            self.serial = None
            self.get_logger().warn(
                f"Nao foi possivel abrir {SERIAL_PORT} -- rodando em modo simulado "
                "(comandos serao logados, nao enviados de verdade)"
            )

        # Criação da comunicação com a telemetria via UDP
        self.telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Booleano para detectar se a parada de emergência está ativada, evitando com que o carrinho ande sem motivo.
        self.emergency_stop = False

        # Tempo do último waypoint detectado, para verificar se o tempo entre um e outro superou o tempo limite,
        # o qual foi definido no WAYPOINT_TIMEOUT.
        self.last_waypoint_time = None

        # Criação do threading para o código conseguir executar duas ações ao mesmo tempo:
        # Ficar escutando comando de kill na porta 6000 e ao mesmo tempo ficar enviando comandos de direção e potência.
        kill_thread = threading.Thread(target=self.kill_listener, daemon=True)
        kill_thread.start()

        # Esse timer roda em paralelo, sem depender de mensagens novas chegarem no topico 'waypoint'. 
        # Se a percepcao parar de publicar, esse timer para o carro sozinho,
        # em vez de deixar o ultimo comando travado pra sempre no Arduino. Isso aqui é uma rede de seguranca por cima.
        self.watchdog_timer = self.create_timer(0.5, self.check_waypoint_timeout)

        # Aviso no terminal de inicialização do nó
        self.get_logger().info("Control node iniciado")

    def waypoint_callback(self, msg):
        "Chamada quando um novo waypoint é recebido, enviando comandos ao arduíno e dados para a telemetria"
        # Coleta dos dados recebidos
        data = msg.data

        # Coleta do waypoint
        xm = data[0]
        ym = data[1]

        # Define que o último waypoint recebido foi agora, para controle de segurança
        self.last_waypoint_time = time.time()

        # caso apertem o kill, nem precisa calcular a potencia, ja freia na hora
        if self.emergency_stop:
            # state = 0 é uma das condições do arquivo v1.ino, correspondente ao freio suave
            self.send_command(STEERING_CENTER, state=0, power=0)
            self.send_telemetry(xm, ym, power = 0, engine = False)
            return

        # calcula a distância ao waypoint
        dist = math.hypot(xm, ym)

        # Sem isso, o carro nunca pararia sozinho ao chegar perto das caixas
        # Essa parte corresponde ao "estacionar no ponto medio" pedido no PDF do onboarding.
        if dist <= ARRIVAL_RADIUS:
            self.get_logger().info("Alvo alcancado, parando.")
            self.send_command(STEERING_CENTER, state=0, power=0)
            self.send_telemetry(xm, ym, power=0, engine=False)
            return

        # caso esteja tranquilo, calcula o angulo, envia o movimento e envia telemetria
        steering_angle = self.calculate_steering_angle(xm, ym)

        self.send_command(steering_angle, state=1, power=CONSTANT_THRUST)
        self.send_telemetry(xm, ym, CONSTANT_THRUST, True)

    def check_waypoint_timeout(self):
        "Função de segurança para detectar se o último waypoint recebido superou o limite"

        # só age se ja recebemos algum waypoint antes e o carro nao esta parado/killed
        if self.last_waypoint_time is None or self.emergency_stop:
            return

        # Caso o tempo passado seja maior que o tempo limite, o carro deve parar, por segurança 
        elapsed = time.time() - self.last_waypoint_time
        if elapsed > WAYPOINT_TIMEOUT:
            self.get_logger().warn(
                f"Nenhum waypoint novo ha {elapsed:.1f}s -- parando por seguranca",
                throttle_duration_sec=2.0,
            )
            self.send_command(STEERING_CENTER, state=0, power=0)
            self.send_telemetry(0.0, 0.0, power=0, engine=False)

    def calculate_steering_angle(self, xm, ym):
        "Calcula o ângulo de esterçamento a partir do Pure Pursuit em modelo bicicleta"
        # coleta do ângulo e distância entre o carrinho e o waypoint
        alpha = math.atan2(ym, xm)
        dist = math.pow((xm ** 2 + ym ** 2), 0.5)

        # Pure pursuit modelo bicicleta aplicado
        delta_pursuitRAD = math.atan2(2 * WHEELBASE * math.sin(alpha), dist)
        delta_pursuitDEG = math.degrees(delta_pursuitRAD)

        # clamp: evitamos passar do limite; se o waypoint estiver na frente, o angulo continua 90 graus
        displacement_angle = max(STEERING_MIN, min(STEERING_MAX, STEERING_CENTER + delta_pursuitDEG))
        return displacement_angle

    def send_command(self, angleDEG, state, power):
        "Recebe os comandos de ângulo de esterçamento, estado e potência e repassa para o arduíno. "
        "Segue o protocolo de 5 caracteres compondo a mensagem, definido pelo código v1.ino."
        "No protocolo, os caracteres recebidos são lidos como 2 caracteres correspondentes ao ângulo"
        "de esterçamento, um de estado (frente, ré ou parado) e os 2 finais de potência enviada aos motores."
        # Clamp para evitar ultrapassagem de limites nos parâmetros recebidos
        angleDEG = max(0, min(180, angleDEG))
        angleDEG = str(format(int(angleDEG), '02X'))
        state = str(state)
        power = max(0, min(100, power))
        power = str(format(int(power), '02X'))
        # Criação da mensagem
        message = angleDEG + state + power + "\n"

        # Envia a mensagem na porta serial
        if self.serial is not None:
            # Parte de envio de fato: quando o arduíno e, consequentemente, o carrinho, estão conectados
            try:
                self.serial.write(message.encode())
                self.get_logger().info(f"[DE VERDADE] mandando pra serial: {message}")
            # Detectamos erro ao escrever na porta serial para ver se há algum erro de permissão ou algo do tipo.
            except serial.SerialException as e:
                self.get_logger().error(f'Erro ao escrever na serial: {e}')
        # Parte de envio simulado: quando estamos testando sem o carrinho
        else:
            self.get_logger().info(f"[SIMULADO] mandaria pra serial: {message}")

    def send_telemetry(self, xm, ym, power, engine):
        "Repassa os dados de movimento para a telemetria exibir na sua página"
        # Apenas uma aproximação, dado que não temos PD/sensor de velocidade
        speed = power
        # Aceleração padronizada em 0 m/s² por estarmos enviando potência constante
        message = {"speed": speed, "acceleration": 0.0, "engine": engine}
        # Conversão de mensagem em formato json, definido pela telemetria como ela seria recebida
        messageToSend = (json.dumps(message)).encode()
        self.telemetry_socket.sendto(messageToSend, (NOTEBOOK_IP, TELEMETRY_PORT))

    def kill_listener(self,):
        "Escuta constantemente se chega algum comando de kill para o carro parar imediatamente"
        # Criação da via de comunicação UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Associa o socket criado a porta de comunicação que a telemetria criou
        sock.bind(("", KILL_LISTEN_PORT))
        self.get_logger().info(f"Kill switch escutando na porta {KILL_LISTEN_PORT}")
        # Loop infinito até receber o kill command. Por isso precisamos de threading, para realizar esta tarefa
        # e não comprometer as demais.
        while True:
            payload, addr = sock.recvfrom(1024)
            if payload == b"KILL":
                self.get_logger().warn("KILL recebido! Parando o carro...")
                self.emergency_stop = True
                # state=0 = freio suave (rampa), unico "parar" que o v1.ino entende.
                self.send_command(STEERING_CENTER, state=0, power=0)
                self.send_telemetry(0.0, 0.0, power=0, engine=False)

    def destroy_node(self):
        "Destrói o nó e ao mesmo tempo mata o carro por segurança"
        # Sem isso, se o no fosse encerrado (Ctrl+C) no meio de uma navegação,
        # o último comando mandado pro Arduino ficaria estagnado e o carro continuaria 
        # andando mesmo com o control_node já fechado.
        if self.serial is not None:
            try:
                self.send_command(STEERING_CENTER, state=0, power=0)
                time.sleep(0.05)
            except Exception:
                pass
        super().destroy_node()


def main(args=None):
    "Controla as ações de inicialização do nó"
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