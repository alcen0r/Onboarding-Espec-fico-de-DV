# Decisões de arquitetura (Feito por: Gabriel)

## Dono da conexão serial com o Arduino

**Data:** 15/07/2026
**Decisão:** `control_node.py` (nó ROS2) é o único responsável pela porta serial com o Arduino.

### O que isso significa na prática

- `control_node.py` abre a serial diretamente (`serial.Serial(...)`) e escreve os comandos de movimento no protocolo de 5 caracteres hex (2 ângulo + 1 estado + 2 potência), que o `v1.ino` já lê.
- `control_node.py` manda a telemetria diretamente via UDP pro `backend.py` (porta 5006), sem intermediário.
- `control_node.py` escuta o comando `KILL` diretamente via UDP (porta 6000), sem intermediário.
- `serial_reader.py` **não faz parte do pipeline ativo** por enquanto.
- `fake_sender.py` deixa de ser necessário pro fluxo principal (já que o `control_node` manda telemetria real), mas pode continuar sendo útil como ferramenta de teste isolado do `backend.py`, se quiserem.

### Por que

- `control_node.py` já integra leitura do waypoint (ROS2), cálculo (pure pursuit), comando pro Arduino e telemetria num só lugar — criar um processo extra (`serial_reader.py`) só duplicaria a posse da porta serial sem necessidade.
- O `v1.ino` atual só **recebe** comandos, nunca **escreve** telemetria de volta pela serial — o design do `serial_reader.py` (ler JSON da serial) exigiria mudar o firmware do Arduino também, o que não é necessário nesse momento.
- Menos processos rodando ao mesmo tempo = menos coisa pra debugar na oficina.

#### Se no futuro fizer sentido separar essas responsabilidades (por exemplo, se o Arduino precisar reportar sensores próprios via serial), essa decisão pode ser revisitada.