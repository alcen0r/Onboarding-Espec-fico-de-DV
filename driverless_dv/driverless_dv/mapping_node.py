# Bibliotecas necessárias para o funcionamento do ROS2
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray

# Biblioteca necessária para plotar os pontos recebidos e o waypoint resultante
import matplotlib.pyplot as plt

class MappingNode(Node):
    def __init__(self):
        "Método construtor do nó de Mapeamento"

        # Herda da classe Node padrão do ros2, atribuindo um id 'control_node' para identificação no comando ros2 run
        super().__init__("mapping_node")

        # Subscriber que recebe o tópico "coordinates"
        self.subscription = self.create_subscription(Float32MultiArray, "coordinates", self.coordinates_callback, 10)

        # Publisher que publica no tópico "waypoint"
        self.publisher_ = self.create_publisher(Float32MultiArray, "waypoint", 10)

        # Configurações do gráfico
        plt.ion()
        self.fig, self.ax = plt.subplots()

        self.get_logger().info("Mapping node iniciado")

    def coordinates_callback(self, msg):
        "Chamada quando uma coordenada é recebida, calculando um novo waypoint e o publicando em seu próprio tópico"

        # Nosso array/vetor chega no formato [x1, y1, x2, y2]
        data = msg.data

        # Proteção contra uma mensagem em formato incorreto de quebrar o unpack abaixo
        if len(data) != 4:
            self.get_logger().warn( f"Esperava 4 valores [x1,y1,x2,y2], recebi {len(data)}. Ignorando.")
            return

        # ========== PEGAR COORDENADAS ==========

        # 1 - Aqui precisamos extrair x1, y1, x2, y2

        x1 = data[0]
        y1 = data[1]
        x2 = data[2]
        y2 = data[3]

        # =======================================


        # ========== CÁLCULO DO WAYPOINT ==========

        # 2 - Precisamos calcular x_wp e y_wp
        x_wp = (x1 + x2) / 2
        y_wp = (y1 + y2) / 2

        # =========================================


        # ========== PUBLICAÇÃO DO WAYPOINT ==========

        # 3 - Como fazer para publicar o waypoint?
        waypoint_msg = Float32MultiArray()
        waypoint_msg.data = [x_wp, y_wp]
        self.publisher_.publish(waypoint_msg)

        # ============================================

        # Atualizar plot
        self.update_plot(x1, y1, x2, y2, x_wp, y_wp)

    def update_plot(self, x1, y1, x2, y2, x_wp, y_wp):
        # Limpar gráfico
        self.ax.clear()

        # Plotar caixa esquerda
        self.ax.scatter(x1, y1, label = "Esquerda")

        # ========== PLOT DA CAIXA DIREITA ==========

        # 4 - Como plotar a caixa direita?
        self.ax.scatter(x2, y2, label = 'Direita')

        # ===========================================

        # Plotar waypoint
        self.ax.scatter(x_wp, y_wp, label = "Waypoint")

        # Plotar carro na origem
        self.ax.scatter(0, 0, marker = "x", s = 100, label = "Carro")

        # Configurações usadas
        self.ax.set_xlabel("X [m]")
        self.ax.set_ylabel("Y [m]")
        self.ax.set_title("Mapa Local")
        self.ax.legend()
        self.ax.grid(True)
        self.ax.axis("equal")

        plt.draw()
        plt.pause(0.001)


def main(args=None):
    "Controla as ações de inicialização do nó"
    rclpy.init(args=args)
    node = MappingNode()

    try:
        rclpy.spin(node)

    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass

    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()