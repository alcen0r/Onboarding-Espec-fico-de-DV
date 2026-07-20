#include <Servo.h>

#define steeringPin 4
#define RPWM 5
#define LPWM 6
#define REN 7
#define LEN 8
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
    
    for(int k=0;k<5;k++){
      comandos[k]=Serial.read();
    }

    int steerUp = charToHexa(comandos[0]);
    int steerDown = charToHexa(comandos[1]);
    steeringAngle = (16*steerUp)+steerDown;

    state = comandos[2]-48;

    if(state != 0){
      int powerUp = charToHexa(comandos[3]);
      int powerDown = charToHexa(comandos[4]);

      thrustPower = (16*powerUp)+powerDown;
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

      }

      steering.write(steeringAngle);
      
    }else{ //Estado =0 -> parar normal.
        for(int k=lastPwm;k>=0;k--){
          analogWrite(RPWM,k);
          delay(5);
        }
           steering.write(steeringAngle);


      

    }
    
  }
  else if(Serial.available()>0){ //Significa mensagem incompleta.
    digitalWrite(LED,HIGH);
    while(Serial.available()){
      Serial.read();
    }

    delay(50);
    digitalWrite(LED,LOW);

  }
}