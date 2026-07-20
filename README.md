# Onboarding Específico DV — E-Racing

Sistema completo do desafio de onboarding da divisão Driverless: um carrinho que identifica dois cones (um laranja, um azul), calcula o ponto médio entre eles, dirige até lá e "estaciona" — com telemetria ao vivo num dashboard web e um kill switch de emergência.

---

## 1. Visão geral da arquitetura

O sistema roda em **duas máquinas diferentes ao mesmo tempo**, conversando pela rede:

```
                    JETSON                                    NOTEBOOK
┌──────────────────────────────────────────┐       ┌────────────────────────────┐
│  perception_node                          │      │                            │
│  (câmera ZED 2i -> YOLO -> coordenadas)   │      │  Telemetria/backend/app.py │
│         │ tópico ROS2 "coordinates"       │      │  (dashboard web, Flask)    │
│         v                                 │      │            ^               │
│  mapping_node                             │      │            │ UDP :5006     │
│  (calcula o ponto médio -> waypoint)      │      │            │ (telemetria)  │
│         │ tópico ROS2 "waypoint"          │      │            │               │
│         v                                 │      │            │ UDP :6000     │
│  control_node          <───────────────── │──────│────────────┘ (kill switch) │
│  (pure pursuit + serial p/ Arduino)       │      │                            │
│         │ USB (5 bytes, protocolo hex)    │      └────────────────────────────┘
│         v                                 │
│      Arduino (v1_corrigido.ino)           │
│      -> servo de direção + motor          │
└──────────────────────────────────────────┘
```

- **Percepção, Mapeamento e Controle** são 3 nós ROS2 (pacote `driverless_dv`), todos rodando **na Jetson**, porque é ela que tem a câmera ZED e o Arduino fisicamente plugados.
- **A Telemetria** (dashboard + servidor Flask) roda **no notebook**, só pra visualização — não depende do ROS2, comunica com a Jetson via UDP puro pela rede.
- O `control_node` é o único que fala com o Arduino (decisão documentada em `Telemetria/DECISOES.md`).

---

## 2. Estrutura do repositório

```
driverless_dv/          -> pacote ROS2 (percepção, mapeamento, controle)
  driverless_dv/
    perception_node.py  -> lê a ZED, roda o YOLO, publica coordenadas dos cones
    mapping_node.py     -> calcula o ponto médio entre os 2 cones (waypoint)
    control_node.py     -> pure pursuit, fala com o Arduino, manda telemetria, kill switch
  weights/best.pt        -> modelo YOLO treinado
  setup.py, package.xml  -> configuração do pacote ROS2

Arduino/
  v1_corrigido.ino       -> firmware que roda no Arduino (é ESTE que deve estar gravado nele)
  v1.ino                 -> versão antiga, mantida só de referência histórica

Telemetria/
  backend/app.py         -> servidor Flask + dashboard web
  backend/templates/     -> HTML do dashboard
  backend/static/app.js  -> lógica do frontend (WebSocket)
  fake_sender.py          -> ferramenta pra testar o backend sem nenhum hardware
  requirements.txt        -> dependências Python da telemetria
  DECISOES.md              -> histórico de decisões de arquitetura, leia se tiver dúvida "por que foi feito assim"
```

**Nota:** as pastas `driverless_dv/build/`, `driverless_dv/install/` e `driverless_dv/log/` são geradas automaticamente pelo `colcon build` — **nunca edite nada dentro delas manualmente**, e nunca as copie de uma máquina pra outra (ver seção 5).

---

## 3. Pré-requisitos

### Sistemas operacionais testados

| Máquina | SO | Distro ROS2 |
|---|---|---|
| Notebook (dev/dashboard) | Ubuntu 22.04 LTS | ROS2 **Humble** |
| Jetson (embarcado) | Ubuntu 20.04 LTS | ROS2 **Foxy** |

**Atenção:** são versões de ROS2 **diferentes** em cada máquina — isso é esperado, não é erro. Cada distribuição do ROS2 é atrelada a uma versão específica do Ubuntu (Humble → 22.04, Foxy → 20.04). O pacote `driverless_dv` precisa ser compilado (`colcon build`) **separadamente em cada máquina** — o resultado de um `colcon build` não é portável entre elas.

### Software necessário, por máquina

**No notebook:**
- Ubuntu 22.04
- ROS2 Humble ([guia oficial](https://docs.ros.org/en/humble/Installation.html))
- Python 3.10
- Python: `flask`, `flask-socketio` (ver `Telemetria/requirements.txt` — se estiver vazio, rode `pip install flask flask-socketio` e depois `pip freeze | grep -iE "flask|socketio|engineio" > Telemetria/requirements.txt` pra deixar o arquivo correto)

**Na Jetson:**
- Ubuntu 20.04 (JetPack)
- ROS2 Foxy
- `colcon` (`sudo apt install python3-colcon-common-extensions`)
- ZED SDK — **versão para Jetson/L4T**, baixada especificamente pra plataforma Jetson no site da Stereolabs (não é o mesmo instalador do notebook)
- Python: `pyserial`, `ultralytics`, `opencv-python`, `numpy`, `torch` (`pip install pyserial ultralytics opencv-python numpy`; o `torch` geralmente já vem com o JetPack)

**Hardware:**
- Jetson (AGX Xavier ou Nano)
- Câmera ZED 2i, conectada via USB 3.0 na Jetson
- Arduino Uno, conectado via USB na Jetson
- Driver de motor (ponte H), servo de direção, motor de tração com bateria de força **separada** (o USB nunca alimenta o motor, só manda o sinal)
- Dois cones (um laranja, um azul) pro teste da tarefa

**Arduino IDE ou `arduino-cli`**, pra fazer upload do firmware (qualquer um dos dois funciona — este README usa `arduino-cli` nos exemplos, por ser mais confiável em scripts).

---

## 4. Configuração de rede

Jetson e notebook precisam se enxergar na rede pra telemetria e kill switch funcionarem (o controle do carro em si, via USB/serial, **não depende disso** — só a telemetria e o kill switch dependem de rede).

### Passo 1 — Colocar os dois na mesma rede

Recomendado: **cabo Ethernet na Jetson** + **Wi-Fi no notebook**, ambos na mesma rede física para testes sem andar com o carrinho. Para andar de fato, ambos precisam estar em Wi-Fi. Nisso, precisamos adicionar um componente extra de hardware: um módulo/conector Wi-Fi pra Jetson, que não possui Wi-Fi próprio.

### Passo 2 — Descobrir o IP da Jetson

Direto no terminal da Jetson (via monitor + teclado plugados nela, ou SSH se a rede já estiver configurada):
```bash
hostname -I
```
ou, preferencialmente,
```bash
ip addr show
```
Anote o IP que aparecer na interface conectada (ex: `143.106.207.93`).

### Passo 3 — Descobrir o IP do notebook

No notebook:
```bash
ip addr show
```
Procure a interface Wi-Fi ativa (`UP`, `LOWER_UP`, com um `inet` listado) — geralmente algo como `wlp...`.

### Passo 4 — Onde configurar cada IP no projeto

| Variável | Arquivo | Roda em | Deve apontar pra |
|---|---|---|---|
| `NOTEBOOK_IP` | `driverless_dv/driverless_dv/control_node.py` | Jetson | IP do **notebook** |
| `JETSON_IP` | `Telemetria/backend/app.py` | Notebook | IP da **Jetson** |

Cada variável aponta pra **máquina oposta** de onde o arquivo roda — é fácil confundir isso, revise com calma. Precisamos disso para a comunicação entre controle e telemetria.

### Passo 5 — Recompilar depois de editar

Depois de editar `control_node.py`, recompile **na Jetson**:
```bash
cd ~/ros2_ws && colcon build && source install/setup.bash
```

### Se o IP mudar

Redes com DHCP podem reatribuir um IP diferente a cada vez que um dispositivo conecta. **Refaça os passos 2–5 sempre que os testes de rede (`ping`) começarem a falhar do nada**, antes de suspeitar de qualquer outra coisa.

---

## 5. Como rodar do zero

### 5.1 — Compilar o pacote ROS2 (uma vez em cada máquina nova)

```bash
mkdir -p ~/ros2_ws/src
cp -r driverless_dv ~/ros2_ws/src/
cd ~/ros2_ws
colcon build
source install/setup.bash
```

### 5.2 — Upload do firmware no Arduino (uma vez, ou sempre que o firmware mudar)

```bash
arduino-cli core install arduino:avr
arduino-cli lib install Servo
arduino-cli compile --fqbn arduino:avr:uno Arduino/
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno Arduino/
```
(o `Arduino/` deve conter só o `v1_corrigido.ino` — se os dois `.ino` estiverem na mesma pasta, a compilação falha por função duplicada; mantenha cada versão em pastas separadas se for guardar as duas)

Preferencialmente, faça o download do Arduino IDE no site oficial (https://www.arduino.cc/en/software/) e abra o arquivo .ino por lá. Ao fazer isso, para subir o código ao arduíno, clique no botão de 'check' para compilar e, com a compilação confirmada, clique na seta de upload para enviar o arquivo ao arduíno. Certifique-se de que a placa associada é o modelo certo (aqui, UNO) e que a porta correspondente é /dev/tty/ACM0 ou semelhante.

### 5.3 — Ordem de inicialização

**Por que a ordem importa:** no ROS2, um nó que assina um tópico só recebe mensagens publicadas **depois** dele existir — mensagens anteriores são perdidas para ele. Se a percepção começar a publicar antes do mapeamento/controle estarem prontos, as primeiras detecções se perdem. A telemetria via UDP também perde os primeiros pacotes se o backend ainda não estiver escutando (não é grave, mas evita ruído no log).

Ordem recomendada:

1. **Arduino** já com o firmware certo, conectado na Jetson
2. **No notebook** — sobe o dashboard primeiro, pra não perder telemetria:
   ```bash
   cd Telemetria/backend
   python3 app.py
   ```
3. **Na Jetson** — `control_node` primeiro (assim você já confirma que a serial abriu, antes de mais nada):
   ```bash
   source /opt/ros/foxy/setup.bash && source ~/ros2_ws/install/setup.bash
   ros2 run driverless_dv control_node
   ```
4. **Na Jetson** — `mapping_node`:
   ```bash
   source /opt/ros/foxy/setup.bash && source ~/ros2_ws/install/setup.bash
   ros2 run driverless_dv mapping_node
   ```
5. **Na Jetson**, por último — `perception_node` (assim, quando ele começar a detectar, mapping/control já estão prontos pra usar o dado):
   ```bash
   source /opt/ros/foxy/setup.bash && source ~/ros2_ws/install/setup.bash
   ros2 run driverless_dv perception_node
   ```

**Segurança: rodas fora do chão / carrinho apoiado até confirmar que tudo está se comportando corretamente.**

---

## 6. Como testar sem o carro (localmente, sem hardware nenhum)

Útil pra desenvolver de casa, fora da oficina, sem Jetson/ZED/Arduino.

### 6.1 — Testar só o dashboard (sem ROS2)

```bash
cd Telemetria
python3 fake_sender.py
```
Isso cria uma porta serial virtual e simula um Arduino mandando telemetria e recebendo `KILL`. Rode `Telemetria/backend/app.py` num outro terminal e abra `http://127.0.0.1:5000` — os valores devem aparecer se mexendo sozinhos.

### 6.2 — Testar a pipeline ROS2 inteira (percepção simulada)

Com `control_node` rodando (ele detecta sozinho a ausência do Arduino e cai em **modo simulado** — loga o que mandaria pra serial, sem precisar de hardware) e `mapping_node` rodando, simule uma detecção manualmente:
```bash
ros2 topic pub /coordinates std_msgs/msg/Float32MultiArray "{data: [1.5, 0.5, 1.5, -0.5]}" --once
```
Isso simula 2 cones detectados, dispara o cálculo do waypoint e o pure pursuit, tudo sem câmera nenhuma. Pra simular continuamente (em vez de um pulso único):
```bash
ros2 topic pub /coordinates std_msgs/msg/Float32MultiArray "{data: [1.5, 0.5, 1.5, -0.5]}" -r 5
```

### 6.3 — Testar o kill switch sem navegador

```bash
python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b'KILL', ('127.0.0.1', 6000))
"
```

---

## 7. Segurança

- **`control_node` tem um watchdog**: se ficar mais de 1 segundo sem receber um waypoint novo (câmera perdeu os cones de vista, nó de percepção travou, etc.), o carro **para sozinho**.
- **Parada automática por chegada**: o carro para sozinho ao chegar a 30cm do waypoint (`ARRIVAL_RADIUS`, em `control_node.py`) — é o que implementa o "estacionar" pedido na tarefa.
- **Kill switch**: botão no dashboard (ou UDP manual, ver 6.3) manda o carro parar imediatamente. Fica travado (`emergency_stop = True`) até o `control_node` ser reiniciado.
- **Sempre teste com as rodas fora do chão primeiro**, em qualquer mudança de código que toque em `control_node.py` ou no firmware do Arduino (não se esqueça de sempre recompilar com colcon build caso haja uma mudança de código).

---

## 8. Protocolo Arduino ↔ control_node

5 caracteres ASCII, sempre nessa ordem, sem separador:

| Posição | Significado |
|---|---|
| `[0:2]` | Ângulo de direção, em hexadecimal (0–180, ex: `5A` = 90°) |
| `[2]` | Estado: `0`=parar (rampa suave), `1`=frente, `2`=ré, outro=freio brusco |
| `[3:5]` | Potência do motor, em hexadecimal (0–100%) |

Exemplo: `"5A114"` = ângulo 90°, frente, potência `0x14` = 20%.

Baudrate: **115200** — precisa bater entre `control_node.py` (`SERIAL_RATE`) e o `Serial.begin()` do `.ino`.

---

## 9. Decisões de arquitetura e histórico

Ver `Telemetria/DECISOES.md` — documenta, entre outras coisas, por que `control_node.py` é o único dono da conexão serial (e não um processo separado), e as correções aplicadas ao firmware do Arduino.

---

## 10. Troubleshooting

Caso tenha problemas com a porta serial, verifique ls /dev/tty* antes e depois de plugar o arduíno. Verifique qual arquivo é adicionado. Esta porta é a serial correta do arduíno. Normalmente aparece como /dev/ttyACM0 ou /dev/ttyACM1.

---
## 11. Telemetria

A Telemetria tem função de monitorar de forma remota o estado do carro durante a execução do desafio, obtendo dados como velocidade, aceleração e estado do motor. Além disso, tem como objetivo a transmissão de dados e o **Kill Switch**, mecanismo que manda um sinal  pro arduino que força uma parada de emergência. 

### 11.1 Fluxo de dados

```
Telemetria/
  control_node.py        -> envia dados do veículo via UDP (:5006)
      │
      ▼
  backend/app.py         -> recebe telemetria da Jetson e retransmite via Socket.IO
      │
      ▼
  Dashboard Web          -> exibe velocidade, direção e estado do sistema

Kill Switch:
  Dashboard Web          -> botão de parada de emergência
      │
      ▼
  backend/app.py         -> recebe evento Socket.IO e envia UDP (:6000)
      │
      ▼
  control_node.py        -> interrompe imediatamente o movimento do veículo
```
O nó de controle envia as informações sobre o estado do veículo para o backFlask utilizando UDP. O back recebe os dados e retransmite em tempo real para o dashboard web, utilizando Socket.IO

```
Kill Switch
Fluxo de Kill Switch:

  Dashboard Web          -> operador aciona o botão de emergência
      │ Socket.IO
      ▼
  backend/app.py         -> recebe o evento "kill" e encaminha o comando para a Jetson
      │ UDP :6000
      ▼
  control_node.py        -> ativa a parada de emergência e interrompe imediatamente o veículo
```
Ao pressionar o botão de kill no dashboard, o backend envia um comando UDP para a Jetson, que interrompe o movimento e desliga o motor

### 11.2 Teste sem Hardware

Para facilidar o desenvolvimento e validar partes da telemetria, foi criado o arquivo `fake_sender.py` que simula o envio de dados para o backend sem necessidade do ROS2, arduino, ZED e da Jetson. Tem como função validar a transmissão de dados, o acionamento do Kill Switch e a recepção de dados no dashboard

---