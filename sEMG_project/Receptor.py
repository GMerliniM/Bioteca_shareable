import serial                              # para ler a porta COM (Bluetooth)
import struct                              # para desempacotar os bytes, convertendo-os nos tipos certo
from collections import deque              # para criar a janela deslizante de dados (deque = lista para adicionar e remover itens)
import matplotlib.pyplot as plt            # para desenhar a janela e os gráficos
import matplotlib.animation as animation   # para atualizar os gráficos em tempo real
from matplotlib.widgets import Button
import numpy as np                         # biblioteca para cálculos com listas grandes
import time                                # biblioteca para a contagem do tempo

MAX_SAMPLES   = 5000
SAMPLING_RATE = 1000

try:
    porta_bt = serial.Serial('COM4', 115200, timeout=0.1) # tenta associar o bluetooth a uma porta serial
    print("Conectado")                                    # envia a mensagem em caso de sucesso
except Exception as e:
    print(f"Erro ao abrir a porta: {e}")                  # avisa se não tiver conseguido abrir a porta
    exit()


colecting      = 0                                        # variável para controlar coleta
lost_ids       = []                                       # lista para salvar os IDs perdidos
last_id        = None
start_time = 0

x_data   = deque(maxlen=MAX_SAMPLES)
ch1_data = deque(maxlen=MAX_SAMPLES)
ch2_data = deque(maxlen=MAX_SAMPLES)
ch3_data = deque(maxlen=MAX_SAMPLES)
ch4_data = deque(maxlen=MAX_SAMPLES)


def start(colect):
    global colecting, last_id, lost_ids, start_time
    x_data.clear()
    ch1_data.clear()
    ch2_data.clear()
    ch3_data.clear()
    ch4_data.clear()
    last_id  = None
    lost_ids = []
    start_time = time.time()

    porta_bt.reset_input_buffer()                         # limpa os dados antigos antes de começar o gráfico
    porta_bt.write(b'S')                                  # sinal de controle para o ESP

    colecting = 1
    print("Coleta iniciada! Sinal S enviado ao ESP")

def end(colect):
    global colecting, last_id, lost_ids
    colecting = 0

    porta_bt.write(b'E')

    print("Coleta encerrada. Sinal E enviado ao ESP")
    print("\nRelatório de coleta:\n")
    
    if len(lost_ids) == 0:
        print("Concluído sem perdas!")
    else:
        print("Concluído com perdas!\n")
        print(f"Total de pacotes perdidos: {len(lost_ids)}\n")
        print(f"IDs perdidos: {lost_ids}\n")

    last_id  = None
    lost_ids = []


fig, ((graph_1, graph_2), (graph_3, graph_4)) = plt.subplots(2, 2, figsize = (12, 8)) # organização do espaço (fig) em 2 x 2, 12x8 = size(inches)
plt.subplots_adjust(left = 0.1, bottom = 0.2, right = 0.9, top = 0.9, wspace = 0.2, hspace = 0.2) # definição da janela

quad_1, = graph_1.plot([], [], color = 'blue',   linewidth = 1)     # cria objetos vazios para serem preenchidos posteriormente
quad_2, = graph_2.plot([], [], color = 'red',    linewidth = 1)
quad_3, = graph_3.plot([], [], color = 'green',  linewidth = 1)
quad_4, = graph_4.plot([], [], color = 'orange', linewidth = 1)

graphs = [graph_1, graph_2, graph_3, graph_4]

graph_1 .set_ylim(0, 4100)                         # seta o limite vertical
graph_1 .set_xlim(0, MAX_SAMPLES/SAMPLING_RATE)                         # seta o limite horizontal
graph_1 .grid(True)                                # coloca grade
graph_1 .set_title(f"Canal {1}")                   # cria título

graph_2 .set_ylim(0, 4100)                         
graph_2 .set_xlim(0, MAX_SAMPLES/SAMPLING_RATE)                         
graph_2 .grid(True)                                
graph_2 .set_title(f"Canal {2}")

graph_3 .set_ylim(0, 4100)                         
graph_3 .set_xlim(0, MAX_SAMPLES/SAMPLING_RATE)                         
graph_3 .grid(True)                                
graph_3 .set_title(f"Canal {3}")

graph_4 .set_ylim(0, 4100)                         
graph_4 .set_xlim(0, MAX_SAMPLES/SAMPLING_RATE)                         
graph_4 .grid(True)                                
graph_4 .set_title(f"Canal {4}")
                                             

bot_start_region = plt.axes([0.1, 0.05, 0.1, 0.1])                          # configura a região onde estará o botão
bot_start        = Button(bot_start_region, 'Start', color = 'lightgreen')  # configura o conteúdo do botão
bot_start.on_clicked(start)                                                 # configura a ação do botão quando clicado

bot_end_region   = plt.axes([0.3, 0.05, 0.1, 0.1])
bot_end          = Button(bot_end_region, 'End', color = 'tomato')
bot_end.on_clicked(end)

bat_region       = plt.axes([0.6, 0.05, 0.1, 0.1])                
bat_region.set_xticks([])                                                   # remove os traços que estariam no eixo x
bat_region.set_yticks([])                                                   # remove os traços que estariam no eixo y
bat_region.set_facecolor('#f0f0f0')                                       # cria uma área de coloração cinza-claro
txt_bat          = bat_region.text(0.5, 0.5, "Bateria: --%",                # define que o texto será anexado no meio da caixa
                                   transform = bat_region.transAxes,        # faz com que o comando de cima funcione, não sendo como gráfico
                                   ha = 'center', va = 'center',            # define que a ancoragem no centro é para o centro do texto
                                   fontsize = 10, fontweight = 'bold')

time_region       = plt.axes([0.8, 0.05, 0.1, 0.1])                
time_region.set_xticks([])                                                  
time_region.set_yticks([])                                                   
time_region.set_facecolor('#f0f0f0')                                       
txt_time          = time_region.text(0.5, 0.5, "Tempo: --s",                
                                   transform = time_region.transAxes,        
                                   ha = 'center', va = 'center',            
                                   fontsize = 10, fontweight = 'bold')


while plt.fignum_exists(fig.number):                                 #loop para a continuidade do processo, checa a existência do espaço

    if colecting:

        current_time = (time.time() - start_time)
        txt_time.set_text(f"Tempo: {int(current_time)}s")
        
        if current_time > 5:
            for g in graphs:
                    g.set_xlim(current_time - 5, current_time)

        if porta_bt.in_waiting >= 8009:                              # verifica se há pelo menos um pacote no buffer
            st_byte = porta_bt.read(1)                               # leitura do primeiro byte enviado

            if (st_byte) and (st_byte[0] == 0x5A):                   # comparação do primeiro byte com o que se espera (envelope e carta)
                nd_byte = porta_bt.read(1)

                if (nd_byte) and (nd_byte[0] == 0xA5):               # comparação do segundo byte com o que se espera
                    payload = porta_bt.read(8007)

                    if len(payload) == 8007:
                        id = struct.unpack('<I', payload[0:4])[0]
                        lost_packet_flag = False

                        if last_id is not None and id > last_id + 1:    # checagem de perda de pacotes
                                for lost in range(last_id + 1, id):
                                    lost_ids.append(lost)
                                lost_packet_flag = True
                        
                        last_id = id
                            
                        ch_1   = struct.unpack('<1000H', payload[4:2004])     # < indica que é Little-Endian, 1000 indica que são 1000 conjuntos
                        ch_2   = struct.unpack('<1000H', payload[2004:4004])  # H indica o tipo de dados (H = unsigned short = 2 bytes)
                        ch_3   = struct.unpack('<1000H', payload[4004:6004])
                        ch_4   = struct.unpack('<1000H', payload[6004:8004])
                        bat    = payload[8004]
                        footer = payload[8005:8007]


                        if footer == b'\xEE\xEE':
                            start_t = current_time - 1
                            end_t   = current_time
                            t_vector = np.linspace(start_t, end_t, 1000, endpoint=False)


                            if lost_packet_flag:
                                x_data.append(start_t - 0.001)
                                ch1_data.append(np.nan)
                                ch2_data.append(np.nan)
                                ch3_data.append(np.nan)
                                ch4_data.append(np.nan)


                            x_data.extend(t_vector)
                            ch1_data.extend(ch_1)
                            ch2_data.extend(ch_2)
                            ch3_data.extend(ch_3)
                            ch4_data.extend(ch_4)
                            
                           
                            quad_1.set_data(x_data, ch1_data)               # atribui a leitura ao gráfico 1
                            quad_2.set_data(x_data, ch2_data)
                            quad_3.set_data(x_data, ch3_data)
                            quad_4.set_data(x_data, ch4_data)
                            

                            bat_perc = int(100*bat/255)
                            txt_bat.set_text(f"Bateria: {bat_perc}%")
                            if bat_perc < 20:
                                txt_bat.set_color('red')
                            else:
                                txt_bat.set_color('black')

    plt.pause(0.001)                                              # delay para atualização da interface

porta_bt.close()