#include <Servo.h>

#define steeringPin 4
#define RPWM 5
#define LPWM 6
#define REN 8
#define LEN 9
#define LED 13 


char comandos[5];
int steeringAngle, state, thrustPower;
int lastPwm=0;

Servo steering;


void setup() {
  steering.attach(steeringPin);
  steering.write(90);

  pinMode(RPWM,OUTPUT);
  pinMode(LPWM,OUTPUT);
  pinMode(REN,OUTPUT);
  pinMode(LEN,OUTPUT);
  pinMode(LED,OUTPUT);

  digitalWrite(REN,HIGH);
  digitalWrite(LEN,HIGH);
  digitalWrite(LED,LOW);



  Serial.begin(115200);


}



int charToHexa(char input){
  //Função que retorna o valor hexadecimal respectivo a um char.
  if(input >= 48 && input <= 57){
    return input-48;
  }
  else if(input>=65 && input <=70){
    return input-55;
  }
  else{
    return -1; //Retorna -1 em caso de erro.
  }
}


void loop() {
  if(Serial.available()>=5){
    digitalWrite(LED, HIGH);
    delay(20);
    digitalWrite(LED, LOW);
    
    for(int k=0;k<5;k++){
      comandos[k]=Serial.read();
    }

    int steerUp = charToHexa(comandos[0]);
    int steerDown = charToHexa(comandos[1]);
    steeringAngle = (16*steerUp)+steerDown;
    // CORRECAO: sem isso, um byte corrompido/fora da faixa podia mandar um valor
    // acima de ~200 pro servo, que a biblioteca Servo interpreta como microsegundos
    // de pulso em vez de graus -- comportamento sem sentido nenhum pro servo.
    steeringAngle = constrain(steeringAngle, 0, 180);

    state = comandos[2]-48;

    if(state != 0){
      int powerUp = charToHexa(comandos[3]);
      int powerDown = charToHexa(comandos[4]);

      thrustPower = (16*powerUp)+powerDown;
      // CORRECAO: mesma ideia -- garante 0-100% antes do map(), evitando um valor
      // corrompido virar um PWM fora de 0-255 depois do map().
      thrustPower = constrain(thrustPower, 0, 100);
      thrustPower = map (thrustPower, 0,100,0,255);

      if(state == 1){ //Frente.
        analogWrite(RPWM,thrustPower);
        analogWrite(LPWM,0);
        lastPwm=thrustPower;


      }else if (state==2){ //Estado = 2 (ré)
        analogWrite(RPWM,0);
        analogWrite(LPWM,thrustPower);
        lastPwm=thrustPower;

      }else{ //Estado = 1 -> freio brusco.
        analogWrite(RPWM,0);
        analogWrite(LPWM,0);
        // CORRECAO: sem isso, um proximo comando de "parar normal" (estado=0)
        // rampeava a partir desse valor antigo, dando um solavanco de potencia
        // no motor antes de parar de vez.
        lastPwm=0;

      }

      steering.write(steeringAngle);
    }else{ //Estado =0 -> parar normal.
        for(int k=lastPwm;k>=0;k--){
          analogWrite(RPWM,k);
          delay(5);
        }
        // CORRECAO: mesma razao do freio brusco -- zera pra evitar rampa fantasma
        // na proxima parada.
        lastPwm=0;
        steering.write(steeringAngle);



    }
    
  }
  // Removemos a parte de descarte de mensagens incompletas
}
