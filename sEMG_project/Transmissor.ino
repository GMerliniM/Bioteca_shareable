#include "BluetoothSerial.h"               // biblioteca para o funcionamento do bluetooth
#include "freertos/FreeRTOS.h"             // biblioteca com funções essenciais do FreeRTOS
#include "freertos/queue.h"                // biblioteca com funções de gerenciamento de filas
#include "driver/adc.h"                    // biblioteca com função para leitura rápida do ADC

#define SIZE 1000
#define QUEUE_LENGTH 5 // Tamanho da fila: consegue armazenar até 5 pacotes (5000 amostras) em caso de gargalo
#define ADC_CH_EMG1 ADC1_CHANNEL_3         // Pino 39
#define ADC_CH_EMG2 ADC1_CHANNEL_6         // Pino 34
#define ADC_CH_EMG3 ADC1_CHANNEL_7         // Pino 35
#define ADC_CH_EMG4 ADC1_CHANNEL_4         // Pino 32
#define ADC_CH_BAT ADC1_CHANNEL_5          // Pino 33

volatile uint16_t valCh1, valCh2, valCh3, valCh4, valBat;  // variáveis para armazenar os valores lidos do ADC

BluetoothSerial SerialBT;
QueueHandle_t xPacketQueue;                // identificador da fila criada no protocolo do ESP
hw_timer_t * pxTimer = nullptr;            // nullptr é exclusivo para ponteiros e indica que ele aponta para lugar nenhum por enquanto

volatile bool transmitting = false;

typedef struct {
  uint16_t usSyncWord =  0xA55A;           // identificador de início de pacote
  uint32_t ulId = 0;
  uint16_t usV1[SIZE] = {0};               // canal 1 EMG
  uint16_t usV2[SIZE] = {0};               // canal 2 EMG
  uint16_t usV3[SIZE] = {0};               // canal 3 EMG
  uint16_t usV4[SIZE] = {0};               // canal 4 EMG
  uint8_t  ucBattery  =  0;
  uint16_t usPackEnd  =  0xEEEE;           // identificador de fim de pacote
} __attribute__((packed)) Pack;            // o modificador __attribute__((packed)) é para garantir que não sejam adicionados bytes extras para facilitar processamento

static Pack xPackPool [QUEUE_LENGTH + 2];  // um vetor de pacotes que servirá como fila de envio, tem +2 para trabalhar problemas no blueetooth
volatile int lChosenPack = 0;              // indica qual pacote está sendo preenchido
volatile int lCounter = 0;                 // contador para o preenchimento dos vetores do pacote, volatile para garantir a checagem contínua
portMUX_TYPE xCounterLock = portMUX_INITIALIZER_UNLOCKED; // Trava de segurança para a variável 'lCounter', para impedir que seja editada 2x ao mesmo tempo (dual core)


void IRAM_ATTR readAndSend() {
  
  valCh1 = adc1_get_raw(ADC_CH_EMG1);     // função para leitura rápida do ADC
  valCh2 = adc1_get_raw(ADC_CH_EMG2);
  valCh3 = adc1_get_raw(ADC_CH_EMG3);
  valCh4 = adc1_get_raw(ADC_CH_EMG4);
  valBat = adc1_get_raw(ADC_CH_BAT);

  xPackPool[lChosenPack].usV1[lCounter] = valCh1;   // associação da leitura à posição no pacote    
  xPackPool[lChosenPack].usV2[lCounter] = valCh2;    
  xPackPool[lChosenPack].usV3[lCounter] = valCh3;    
  xPackPool[lChosenPack].usV4[lCounter] = valCh4;                        

  lCounter++;

  if (lCounter >= SIZE) { 
    xPackPool[lChosenPack].ucBattery = valBat;             
    
    if(xQueueIsQueueFullFromISR(xPacketQueue) == pdFALSE){
      Pack* pxPackToSend = &xPackPool[lChosenPack];    // o pacote preenchido do vetor de pacotes é atribuído ao endereço pxPackToSend
      
      BaseType_t xHigherPriorityTaskWoken = pdFALSE;   // variável exigida pelo FreeRTOS para saber se precisa acordar uma tarefa mais importante
      xQueueSendFromISR(xPacketQueue, &pxPackToSend, &xHigherPriorityTaskWoken); // faz o envio do pacote para a fila e muda o valor de xHigherPriorityTaskWoken  
      
      uint32_t ulNextId = xPackPool[lChosenPack].ulId + 1;   // calcula o valor do próximo ID de pacote
      lChosenPack = (lChosenPack + 1) % (QUEUE_LENGTH + 2);  // realiza a divisão (apenas inteira) entre o próximo índice e o tamanho da fila + 2 e pega o seu resto
      xPackPool[lChosenPack].ulId = ulNextId;                // sempre se adiciona 1 para ser possível progredir no ID e para usar a operação % corretamente
      
      if (xHigherPriorityTaskWoken) { // agora que xHigherPriorityTaskWoken = 1, retorna o foco do processador para o loop, onde ocorre o envio bluetooth
          portYIELD_FROM_ISR();
      }
    }
    else{
      xPackPool[lChosenPack].ulId++;   // progride no ID se a fila estiver cheia para ser possível calcular as perdas.
    }
    lCounter = 0;                      // Reinicia o índice para encher o próximo pacote
  }
}                                      // os pacotes tem tamanho +2 para forçar o erro do envio para a fila se o bluetooth estiver lento, descartando alguns pacotes.


void LED_action(int val, int pin){
  if (val != 0)
    digitalWrite(pin, 1);
  else
    digitalWrite(pin, 0);
}


void setup() {
  SerialBT.begin("ESP32-BT");
  Serial.begin(115200);
  Serial.println("Bluetooth iniciado. Aguardando o comando do notebook.");
  xPacketQueue = xQueueCreate(QUEUE_LENGTH, sizeof(Pack*));  // criação da fila de ponteiros

  adc1_config_width(ADC_WIDTH_BIT_12);                       // associa a configuração do ADC à capacidade física do ESP
  adc1_config_channel_atten(ADC_CH_EMG1, ADC_ATTEN_DB_12); 
  adc1_config_channel_atten(ADC_CH_EMG2, ADC_ATTEN_DB_12); 
  adc1_config_channel_atten(ADC_CH_EMG3, ADC_ATTEN_DB_12); 
  adc1_config_channel_atten(ADC_CH_EMG4, ADC_ATTEN_DB_12);
  adc1_config_channel_atten(ADC_CH_BAT,  ADC_ATTEN_DB_12);

  pinMode(19, OUTPUT);                               // LED CH1
  pinMode(18, OUTPUT);                               // LED CH2
  pinMode(5 , OUTPUT);                               // LED CH3
  pinMode(17, OUTPUT);                               // LED CH4
  pinMode(16, OUTPUT);                               // LED BT

  digitalWrite(19, LOW);                             // LED CH1
  digitalWrite(18, LOW);                             // LED CH2
  digitalWrite(5, LOW);                              // LED CH3
  digitalWrite(17, LOW);                             // LED CH4
  digitalWrite(16, LOW);                             // LED BT

  pxTimer = timerBegin(1000000);                     // determina qual timer será usado (0) e seta a escala para 1 us
  timerAttachInterrupt(pxTimer, &readAndSend);     // associa a interrupção gerada pelo alarme do timer à função onTimer
  timerAlarm(pxTimer, 1000, true, 0);                  // determina a frequência em que deve ser acionado o alarme
  
  while(!SerialBT.hasClient()) {                         // garante que o alarme não será acionado antes de haver um dispositivo conectado
    delay(50);
  }

  Serial.print("Bluetooth Conectado!");
  timerStart(pxTimer);
}


void loop() {                                                     //Recebe o pacote da fila (retorna pdTRUE) e faz o loop dormir enquanto estiver vazia (portMAX_DELAY)

  if (SerialBT.available()) {
    char cmd = SerialBT.read();
    if (cmd == 'S') transmitting = true;
    if (cmd == 'E') transmitting = false;
  }
  
  LED_action(SerialBT.hasClient(), 16);
  
  LED_action(valCh1, 19);
  LED_action(valCh2, 18);
  LED_action(valCh3, 5);
  LED_action(valCh4, 17);

  Pack* pxPackReceived;                                           // ponteiro que receberá o endereço da fila

  if (xQueueReceive(xPacketQueue, &pxPackReceived, portMAX_DELAY) == pdTRUE) { 

    if (SerialBT.hasClient() && transmitting){                      // envia os pacotes apenas se o bluetooth estiver conectado
      SerialBT.write((const uint8_t*)pxPackReceived, sizeof(Pack)); // faz o envio do pacote via bluetooth. O casting está ali em razão do tipo necessário da função
    }
    else {
      timerStop(pxTimer);                                   // desabilita os alarmes do timer

      while(!SerialBT.hasClient() || !transmitting){        // verifica novamente a conexão
        if(!SerialBT.hasClient()){
           transmitting = false;
        }
        if(SerialBT.hasClient() && SerialBT.available()){
           char cmd = SerialBT.read();
           if (cmd == 'S') transmitting = true;
           if (cmd == 'E') transmitting = false;
        }

        LED_action(SerialBT.hasClient(), 16);       // Atualiza o status do BT em pausa

        int monitorCh1 = adc1_get_raw(ADC_CH_EMG1); // checagem dos ADCs para atualizar os LEDs dos canais mesmo se não houver transmissão.
        int monitorCh2 = adc1_get_raw(ADC_CH_EMG2);
        int monitorCh3 = adc1_get_raw(ADC_CH_EMG3);
        int monitorCh4 = adc1_get_raw(ADC_CH_EMG4);

        LED_action(monitorCh1, 19);
        LED_action(monitorCh2, 18);
        LED_action(monitorCh3, 5);
        LED_action(monitorCh4, 17);

        delay(50);
      }

      Pack* pxTrash;                                                // ponteiro para uma estrutura que servirá como lixeira
      while(xQueueReceive(xPacketQueue, &pxTrash, 0) == pdTRUE){}   // move os endereços dos pacotes da fila para a lixeira, até zerar a fila
    
      portENTER_CRITICAL(&xCounterLock); // essas funções servem para garantir que não haja problemas no processador ao zerar o i - possibilidade de núcleos diferentes
      lCounter = 0;                      // reinicia a contagem de preenchimento dos vetores
      portEXIT_CRITICAL(&xCounterLock); 
     
      timerStart(pxTimer);         // habilita novamente os alarmes do timer

    }
  }
}