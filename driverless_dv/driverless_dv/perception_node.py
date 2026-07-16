import cv2
import numpy as np
import pyzed.sl as sl # biblioteca da zed
from ultralytics import YOLO

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from ament_index_python.packages import get_package_share_directory
import os

class PerceptionNode ( Node ) :
    def __init__ (self) :
        super().__init__('perception_node')

        self.publisher_ = self.create_publisher(Float32MultiArray, 'coordinates', 10)

        weights_path = os.path.join(get_package_share_directory('driverless_dv'), 'weights', 'best.pt')
        self.model = YOLO(weights_path)

        self.zed = sl.Camera()

        init_params = sl . InitParameters ()
        init_params.camera_resolution = sl.RESOLUTION.HD720
        init_params.depth_mode = sl.DEPTH_MODE.ULTRA
        init_params.coordinate_units = sl.UNIT.METER # unidade em metros

        if self.zed.open(init_params) != sl.ERROR_CODE.SUCCESS :
            self.get_logger().error("Deu ruim")
            exit()

        self.image_zed = sl.Mat()
        self.point_cloud = sl.Mat()
        self.runtime_params = sl.RuntimeParameters()

        self.get_logger().info("Iniciando loop")

        self.timer = self.create_timer(0.05, self.detection_loop) #de 0.00 para 0.05 para nao ficar tao agressivo

    def detection_loop (self) :
        if self.zed.grab(self.runtime_params) == sl.ERROR_CODE.SUCCESS:
            
            self.zed.retrieve_image(self.image_zed, sl.VIEW.LEFT)
            self.zed.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
            
            frame = self.image_zed.get_data()
            img_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            results = self.model.predict(source = img_bgr, conf = 0.5, verbose = True) #true para verificar como ta a deteccao
            
            lista_detections = []
            
            for result in results:
                for bbox in result.boxes:
                    #conversao para float para lidar melhor com comparacoes
                    conf = float(bbox.conf[0])
                    
                    if bbox.conf < 0.5:
                        continue
                    
                    x1, y1, x2, y2 = bbox.xyxy[0].tolist()
                    
                    cx = int((x1+x2)/2)
                    cy = int((y1+y2)/2)
                    
                    erro, pontos = self.point_cloud.get_value(cx, cy)
                    
                    if erro != sl.ERROR_CODE.SUCCESS:
                        continue
                    
                    x_zed = float(pontos[0])
                    y_zed = float(pontos[1])
                    z_zed = float(pontos[2])
                    
                    x_mapa = z_zed
                    y_mapa = x_zed
                    
                    lista_detections.append({"x_mapa": x_mapa,"y_mapa": y_mapa,"dist": z_zed,"conf": conf})
                    
            if len(lista_detections) >= 2:
                #ordenacao de distancia para a camera
                lista_detections.sort(key = lambda d:d["dist"])
                
                caixa1 = lista_detections[0]
                caixa2 = lista_detections[1]
                
                msg = Float32MultiArray()
                msg.data = [caixa1["x_mapa"], caixa1["y_mapa"], caixa2["x_mapa"], caixa2["y_mapa"]]
                self.publisher_.publish(msg)
                
                # uma especie de debugging:
                self.get_logger().info(f"Publicado: [{msg.data[0]:.2f}, {msg.data[1]:.2f}, {msg.data[2]:.2f}, {msg.data[3]:.2f}]")
            

def main (args = None) :
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
        rclpy.shutdown()
        
if __name__ == '__main__':
    main()