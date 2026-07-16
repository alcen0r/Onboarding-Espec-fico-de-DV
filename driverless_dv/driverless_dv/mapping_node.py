import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import matplotlib.pyplot as plt


class MappingNode(Node):
    def __init__(self):
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
        # Nosso array/vetor chega no formato [x1, y1, x2, y2]
        data = msg.data

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
    rclpy.init(args=args)
    node = MappingNode()

    try:
        rclpy.spin(node)

    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()