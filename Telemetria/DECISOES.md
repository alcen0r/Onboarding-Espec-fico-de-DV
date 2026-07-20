# Decisões de arquitetura (Feito por: Gabriel)

## Dono da conexão serial com o Arduino

**Data:** 15/07/2026
**Decisão:** `control_node.py` (nó ROS2) é o único responsável pela porta serial com o Arduino.

### Esclarecimentos

- `control_node.py` abre a serial diretamente (`serial.Serial(...)`) e escreve os comandos de movimento no protocolo de 5 caracteres hex (2 ângulo + 1 estado + 2 potência), que o `v1.ino` já lê.
- `control_node.py` manda a telemetria diretamente via UDP pro `backend.py` (porta 5006), sem intermediário.
- `control_node.py` escuta o comando `KILL` diretamente via UDP (porta 6000), sem intermediário.
- `serial_reader.py` **não faz parte do pipeline ativo** por enquanto.
- `fake_sender.py` deixa de ser necessário pro fluxo principal (já que o `control_node` manda telemetria real), mas pode continuar sendo útil como ferramenta de teste isolado do `backend.py`, se quiserem.

### Razões

- `control_node.py` já integra leitura do waypoint (ROS2), cálculo (pure pursuit), comando pro Arduino e telemetria num só lugar — criar um processo extra (`serial_reader.py`) só duplicaria a posse da porta serial sem necessidade.
- O `v1.ino` atual só **recebe** comandos, nunca **escreve** telemetria de volta pela serial — o design do `serial_reader.py` (ler JSON da serial) exigiria mudar o firmware do Arduino também, o que não é necessário nesse momento.
- Menos processos rodando ao mesmo tempo = menos coisa pra debugar na oficina.

#### Se no futuro fizer sentido separar essas responsabilidades (por exemplo, se o Arduino precisar reportar sensores próprios via serial), essa decisão pode ser revisitada.


# Decisões de arquitetura - Parte 2 (Feito por: Gabriel)

## Dono da conexão serial com o Arduino

**Data:** 20/07/2026
**Decisão:** `v1.ino` ->  `v1_corrigido.ino` passa a ter algumas verificações de segurança no envio de comandos para os motores, além de evitar perda de mensagens incompletas

### Esclarecimentos

- `v1.ino` estava enviando alguns comandos que poderiam fazer com que freios bruscos fossem sobrescritos por freios suaves, interrompendo comportamentos desejados de parada total do carrinho, além de não possuir verificações de potência enviada
- `v1.ino` estava tirando mensagens incompletas, o que estava dificultando debuggs de controle e acreditamos que não tinha grande impacto no sistema

# DECISÕES DE TELEMETRIA - Feito por: Alcenor

## Transmissão de Dados UDP:

**Data** 13/07/2026
**Decisão** Preferência do uso de `UDP` em relação à `TCP` na comunição de telemetria

### Esclarecimentos

Em comparação ao TCP, o formato escolhido tem uma menor latência e é mais leve, já que não precisa do protocolo de _handshake_. Pontos negativos é a possível perda/desordem dos dados, mas mostrou-se baixa a probalidade, não atrapalhando a telemetria em tempo real.

## Implementação do Backend:

**Data** 13/07/2026
**Decisão** Uso do `Flask` e `Flask-SocketIO` 

### Esclarecimentos

A responsabilidade do Socket.IO é ser uma "ponte", um canal bidirecional que passa os dados do back pro front, atualizando instantaneamente e passando comandos como o `KILL`. Portanto, por ser de fácil uso e atuando como transmissor de comandos e dados entre back e front, foi escolhido. Já o Flask foi escolhido por ser simples, fácil de manusear e tem uma integração direta com o Socket.IO

## Telemetria não ser implementada como nó ROS2.

**Data** 13/07/2026
**Decisão** Telemetria desenvolvida como serviço em paralelo ao sistema ROS2

### Esclarecimentos

Os nós ROS2 são responsáveis pelo mapeamento, controle e pela percepção, já a telemetria é responsável pelo monitoramento remoto, acionamento do kill e pela interface com o usuário. Manter a telemetria fora é uma forma de simplificar o projeto e reduzir a carga computacional destinada à Jetson. Além disso, é uma forma de manter o carro ativo, caso dê alguma falha na transmissão de dados, perda de UDP ou falha no dashboard.