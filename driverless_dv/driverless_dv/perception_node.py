import cv2
import numpy as np
import pyzed.sl as sl # biblioteca da zed
from ultralytics import YOLO

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from ament_index_python.packages import get_package_share_directory
import os

class PerceptionNode (Node):
    def __init__ (self):
        "Método construtor do nó de Percepção"
        # Herda da classe Node padrão do ros2, atribuindo um id 'control_node' para identificação no comando ros2 run
        super().__init__('perception_node')

        # O nó de perception atua como publisher do tópico coordinates, em que mapeamento fica aguardando publicações
        self.publisher_ = self.create_publisher(Float32MultiArray, 'coordinates', 10)

        # Inicialização do modelo de detecção dos cones, acessando o caminho do arquivo e iniciando o modelo.
        weights_path = os.path.join(get_package_share_directory('driverless_dv'), 'weights', 'best.pt')
        self.model = YOLO(weights_path)

        # Atribuição das qualidades da câmera, criando configurações de resolução, profunidade e unidade de medida
        self.zed = sl.Camera()
        init_params = sl.InitParameters ()
        init_params.camera_resolution = sl.RESOLUTION.HD720
        init_params.depth_mode = sl.DEPTH_MODE.ULTRA
        init_params.coordinate_units = sl.UNIT.METER # unidade em metros
        # Sem isso abaixo, a ZED usa o sistema padrao dela (x = direita, z = frente),
        # que exigia remapear os eixos na mao e tinha um risco real de inverter o
        # sinal do "esquerda/direita" (o carro virando pro lado errado). Com isso
        # aqui, pontos[0] ja vem como "pra frente" e pontos[1] como "pra esquerda",
        # que e exatamente a convencao que o mapping/controle esperam.
        init_params.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Z_UP_X_FWD

        # Verificação de sucesos em abertura da câmera, útil também para debuggar
        if self.zed.open(init_params) != sl.ERROR_CODE.SUCCESS :
            self.get_logger().error("Deu ruim")
            exit()

        # Criação e atribuição de matrizes para futuramente receber a imagem e a nuvem de pontos detectada pela zed
        self.image_zed = sl.Mat()
        self.point_cloud = sl.Mat()
        self.runtime_params = sl.RuntimeParameters()

        self.get_logger().info("Iniciando loop")

        self.timer = self.create_timer(0.05, self.detection_loop) # de 0.00 para 0.05 para nao ficar tao agressivo

    def detection_loop (self) :
        "Realiza o loop de detecções de cones frame a frame."
        "Baseia-se no modelo e dataset criados com YOLO e CVAT, respectivamente."
        # Se a abertura com os parâmetros não apresentou problemas, inicia-se o loop
        if self.zed.grab(self.runtime_params) == sl.ERROR_CODE.SUCCESS:
            # Coletamos a mensagem a partir do "olho esquerdo" para facilitar (padrão) e atribuímos ao atributo de imagem
            self.zed.retrieve_image(self.image_zed, sl.VIEW.LEFT)
            # Coletamos a nuvem de pontos correspondente e atribuímos ao atributo de point cloud, no padrão de 4 entradas
            self.zed.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
            
            # Coletamos frame a frame para detectar os cones neste
            frame = self.image_zed.get_data()
            # Conversão do formato de imagem de 4 entradas para 3, que é o padrão suportado pela YOLO
            img_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Identificação dos cones no frame pelo modelo criado a partir do dataset desenvolvido pelo grupo
            results = self.model.predict(source = img_bgr, conf = 0.5, verbose = True) #true para verificar como ta a deteccao
            
            lista_detections = []
            
            # Iteramos pelas detecções a fim de detectar as posições do cones e enviar suas mensagens.
            # Aqui, chamamos os cones de 'caixas' pois generalizamos para o contexto do PDF do onboarding.
            for result in results:
                for bbox in result.boxes:
                    # Conversao para float para lidar melhor com comparacoes
                    conf = float(bbox.conf[0])
                    
                    if bbox.conf < 0.5:
                        continue
                    
                    # Unpack das informações detectadas na bounding box
                    x1, y1, x2, y2 = bbox.xyxy[0].tolist()
                    
                    # Coleta do ponto médio do OBJETO, identificando seu centro
                    cx = int((x1+x2)/2)
                    cy = int((y1+y2)/2)
                    
                    erro, pontos = self.point_cloud.get_value(cx, cy)
                    
                    if erro != sl.ERROR_CODE.SUCCESS:
                        continue

                    # com coordinate_system = RIGHT_HANDED_Z_UP_X_FWD, a propria ZED
                    # ja devolve pontos[0] = pra frente, pontos[1] = pra esquerda
                    x_mapa = float(pontos[0])
                    y_mapa = float(pontos[1])

                    if not (np.isfinite(x_mapa) and np.isfinite(y_mapa)):
                        continue  # profundidade invalida (sem textura/iluminacao, etc.)

                    lista_detections.append({"x_mapa": x_mapa,"y_mapa": y_mapa,"dist": x_mapa,"conf": conf})

            # Se foram detectados 2 cones para realizar o movimento, criamos a coordenada para ser publicada       
            if len(lista_detections) == 2:
                #ordenacao de distancia para a camera
                lista_detections.sort(key = lambda d:d["dist"])
                
                caixa1 = lista_detections[0]
                caixa2 = lista_detections[1]
                
                # Criação da mensagem no formato do ros2, publicando-a
                msg = Float32MultiArray()
                msg.data = [caixa1["x_mapa"], caixa1["y_mapa"], caixa2["x_mapa"], caixa2["y_mapa"]]
                self.publisher_.publish(msg)
                
                # uma especie de debugging:
                self.get_logger().info(f"Publicado: [{msg.data[0]:.2f}, {msg.data[1]:.2f}, {msg.data[2]:.2f}, {msg.data[3]:.2f}]")
            elif len(lista_detections) > 2:
                # Para evitar um falso positivo (ex: "2 cones laranjas" detectados por engano) faria o código
                # publicar um waypoint calculado a partir de 2 deteccoes erradas, sem nenhum aviso. 
                # Assim, esse frame é descartado e avisado no log, em vez de virar um waypoint ruim.
                self.get_logger().warn(
                    f"Detectei {len(lista_detections)} objetos em vez de 2 -- descartando este frame"
                )
            

def main (args = None):
    "Controla as ações de inicialização do nó"
    rclpy.init (args = args)
    node = PerceptionNode()
    try:
        rclpy.spin(node)
    except(KeyboardInterrupt , rclpy . executors . ExternalShutdownException ) :
        pass
    finally :
        node.destroy_node()
        #adicoes:
        node.zed.close()
        if rclpy.ok():
            rclpy.shutdown()
        
if __name__ == '__main__':
    main()