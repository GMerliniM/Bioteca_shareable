import serial                              # para ler a porta COM (Bluetooth)
import struct                              # para desempacotar os bytes, convertendo-os nos tipos certo
from collections import deque              # para criar a janela deslizante de dados (deque = lista para adicionar e remover itens)
import matplotlib.pyplot as plt            # para desenhar a janela e os gráficos
import matplotlib.animation as animation   # para atualizar os gráficos em tempo real
from matplotlib.widgets import Button
import numpy as np                         # biblioteca para cálculos com listas
import time                                # biblioteca para a contagem do tempo


MAX_SAMPLES   = 2000
SAMPLING_RATE = 1000


try:
    porta_bt = serial.Serial('COM4', 115200, timeout=0.1) # tenta associar o bluetooth a uma porta serial, limite de espera 0,1s
    print("Conectado")                                    # envia a mensagem em caso de sucesso
except Exception as e:
    print(f"Erro ao abrir a porta: {e}")                  # avisa se não tiver conseguido abrir a porta
    exit()


colecting      = 0                                        # variável para controlar coleta
lost_ids       = []                                       # lista para salvar os IDs perdidos
last_id        = None
start_time     = 0                                        # atribuição de valor para garantir existência na memória

x_data   = deque(maxlen=MAX_SAMPLES)                      # lista para guiar o eixo x, sem alocar memória ainda
ch1_data = deque(maxlen=MAX_SAMPLES)                      # função deque remove dados mais atingos quando entram novos
ch2_data = deque(maxlen=MAX_SAMPLES)
ch3_data = deque(maxlen=MAX_SAMPLES)
ch4_data = deque(maxlen=MAX_SAMPLES)


def start(event):   # event = argumento necessário para a função de clique do botão, mas não é utilizado
    global colecting, last_id, lost_ids, start_time
    x_data.clear()
    ch1_data.clear()
    ch2_data.clear()
    ch3_data.clear()
    ch4_data.clear()

    for g in graphs:
        g.set_xlim(0, MAX_SAMPLES/SAMPLING_RATE)          # reseta o limite horizontal para o início da coleta
    
    last_id  = None
    lost_ids = []
    start_time = time.time()

    porta_bt.reset_input_buffer()                         # limpa os dados antigos antes de começar o gráfico
    porta_bt.write(b'S')                                  # sinal de controle para o ESP. Possui esse formato porque precisa ser byte

    colecting = 1
    print("Coleta iniciada! Sinal S enviado ao ESP")

    ani.resume()                                          # retoma a animação


def end(event):     # event = argumento necessário para a função de clique do botão, mas não é utilizado
    ani.pause()     # pausa a animação
    
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

    last_id  = None   # essa limpeza não é necessária aqui, mas é boa prática para preservar memória
    lost_ids = []

    


def empty_space_if_lost(graph_start_t):
    x_data.append(graph_start_t - 0.001)                         # atualiza o ponto inicial para o espaço vazio
    ch1_data.append(np.nan)                                      # nan = not a number, criando o espaço vazio no gráfico
    ch2_data.append(np.nan)
    ch3_data.append(np.nan)
    ch4_data.append(np.nan)


def unpack_data(current_time):
    global last_id, lost_ids
    if porta_bt.in_waiting >= 8009:                              # verifica se há pelo menos um pacote no buffer
        st_byte = porta_bt.read(1)                               # leitura do primeiro byte enviado

        if (st_byte) and (st_byte[0] == 0x5A):                   # comparação do primeiro byte com o que se espera (envelope e carta)
            nd_byte = porta_bt.read(1)

            if (nd_byte) and (nd_byte[0] == 0xA5):               # comparação do segundo byte com o que se espera
                package_data = porta_bt.read(8007)

                if len(package_data) == 8007:
                    id = struct.unpack('<I', package_data[0:4])[0]    # desempacota o id
                    lost_packet_flag = False                     # cria a variável para controle de perdas
                    if last_id is not None and id > last_id + 1: # checagem de perda de pacotes
                        for lost in range(last_id + 1, id):
                            lost_ids.append(lost)                # adiciona o ID perdido à lista de perdas
                        lost_packet_flag = True                  # altera a flag para indicar perda
                            
                    last_id = id                                 # atualiza o último ID
                                
                    ch_1   = struct.unpack('<1000H', package_data[4:2004])     # < indica que é Little-Endian, 1000 indica que são 1000 conjuntos
                    ch_2   = struct.unpack('<1000H', package_data[2004:4004])  # H indica o tipo de dados (H = unsigned short = 2 bytes)
                    ch_3   = struct.unpack('<1000H', package_data[4004:6004])  # função .unpack() necessária para interpretar os bytes
                    ch_4   = struct.unpack('<1000H', package_data[6004:8004])
                    bat    = package_data[8004]                           # função .unpack() desnecessária por ser valor puro 
                    footer = package_data[8005:8007]

                    if footer == b'\xEE\xEE':
                        graph_start_t = current_time - 1                  # atualiza o começo do gráfico se chegou pacote
                        graph_end_t   = current_time                      # atualiza o final do gráfico
                        t_vector = np.linspace(graph_start_t, graph_end_t, 1000, endpoint=False) # vetor móvel de tempo para gráficos

                        if lost_packet_flag:
                            empty_space_if_lost(graph_start_t)            # chama a função de criação do espaço vazio

                        return(ch_1, ch_2, ch_3, ch_4, bat, t_vector)
        
        return None                    # retorno de segurança para o caso de não chegar pacote


def axes_update(ch_1, ch_2, ch_3, ch_4, t_vector):

    x_data.extend(t_vector)
    ch1_data.extend(ch_1)
    ch2_data.extend(ch_2)
    ch3_data.extend(ch_3)
    ch4_data.extend(ch_4)                 
                            
    quad_1.set_data(x_data, ch1_data)  # atribui a leitura ao gráfico 1 (tamanho, dados)
    quad_2.set_data(x_data, ch2_data)
    quad_3.set_data(x_data, ch3_data)
    quad_4.set_data(x_data, ch4_data)


def bat_update(bat):
    bat_perc = int(100*bat/255)
    txt_bat.set_text(f"Bateria: {bat_perc}%")
    if bat_perc < 20:
        txt_bat.set_color('red')
    else:
        txt_bat.set_color('black')


def update_graph(frame):               # frame = argumento necessário para a função de animação, mas não é utilizado

    if not colecting:
        return quad_1, quad_2, quad_3, quad_4, txt_bat, txt_time # mantém os gráficos congelados se não coletando
    
    current_time = (time.time() - start_time)                    # variável para atualização dos tempos do gráfico
    txt_time.set_text(f"Tempo: {int(current_time)}s")            # atualiza o cronômetro da tela
    window_size = MAX_SAMPLES / SAMPLING_RATE                    # define o tamanho do gráfico em segundos

    if current_time > window_size:                               # atualiza a janela se necessário
        for g in graphs:
                g.set_xlim(current_time - window_size, current_time)   # seta novos limites do gráfico

    result = unpack_data(current_time)                           # recebe os valores de unpack_data

    if result is not None:                                       # atualiza as variáveis se os valores não forem nulos
        ch_1, ch_2, ch_3, ch_4, bat, t_vector = result

        axes_update(ch_1, ch_2, ch_3, ch_4, t_vector)                 
        bat_update(bat)                                          # precisa estar aqui para evitar erros caso result = None

    return quad_1, quad_2, quad_3, quad_4, txt_bat, txt_time


fig, ((graph_1, graph_2), (graph_3, graph_4)) = plt.subplots(2, 2, figsize = (12, 8)) # organização do espaço (fig) em 2 x 2, 12x8 = size(inches)
plt.subplots_adjust(left = 0.1, bottom = 0.2, right = 0.9, top = 0.9, wspace = 0.2, hspace = 0.2) # definição da janela

quad_1, = graph_1.plot([], [], color = 'blue',   linewidth = 1)     # cria objetos vazios para serem preenchidos posteriormente
quad_2, = graph_2.plot([], [], color = 'red',    linewidth = 1)
quad_3, = graph_3.plot([], [], color = 'green',  linewidth = 1)
quad_4, = graph_4.plot([], [], color = 'orange', linewidth = 1)

graphs = [graph_1, graph_2, graph_3, graph_4]      # lista utilizada na função "star()" para resetar os limites dos gráficos

graph_1 .set_ylim(0, 4100)                         # seta o limite vertical
graph_1 .set_xlim(0, MAX_SAMPLES/SAMPLING_RATE)    # seta o limite horizontal
graph_1 .grid(True)                                # coloca grade
graph_1 .set_title(f"Canal {1}")                   # cria título

graph_2 .set_ylim(0, 4100)                         # gráficos foram separados para possibilitar configuração individual
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
                                             

bot_start_region = plt.axes([0.1, 0.05, 0.05, 0.05])                        # configura a região onde estará o botão (left, bottom, width, height)
bot_start        = Button(bot_start_region, 'Start', color = 'lightgreen')  # configura o conteúdo do botão
bot_start.on_clicked(start)                                                 # configura a ação do botão quando clicado

bot_end_region   = plt.axes([0.35, 0.05, 0.05, 0.05])
bot_end          = Button(bot_end_region, 'End', color = 'tomato')
bot_end.on_clicked(end)

bat_region       = plt.axes([0.6, 0.05, 0.05, 0.05])                
bat_region.set_xticks([])                                                   # remove os traços que estariam no eixo x
bat_region.set_yticks([])                                                   # remove os traços que estariam no eixo y
bat_region.set_facecolor('#f0f0f0')                                       # cria uma área de coloração cinza-claro
txt_bat          = bat_region.text(0.5, 0.5, "Bateria: --%",                # define que o texto será anexado no meio da caixa
                                   transform = bat_region.transAxes,        # faz com que o comando de cima funcione, não sendo como gráfico
                                   ha = 'center', va = 'center',            # define que a ancoragem no centro é para o centro do texto
                                   fontsize = 10, fontweight = 'bold')

time_region       = plt.axes([0.8, 0.05, 0.05, 0.05])                
time_region.set_xticks([])                                                  
time_region.set_yticks([])                                                   
time_region.set_facecolor('#f0f0f0')                                       
txt_time          = time_region.text(0.5, 0.5, "Tempo: --s",                
                                   transform = time_region.transAxes,        
                                   ha = 'center', va = 'center',            
                                   fontsize = 10, fontweight = 'bold')


if plt.get_backend() == 'TkAgg':                  # verifica se o backend é o Tkinter (padrão do Windows)
    manager = plt.get_current_fig_manager()       # busca o gerente responsável por exibir a figura na tela
    window = manager.window                       # extrai a janela original do windows e atribui a "window"
    
    window.update_idletasks()                     # força a realização dos cálculos de tamanho de janela (não natural)
    width = window.winfo_width()                  # calcula a largura da janela
    height = window.winfo_height()                # calcula a altura da janela
    
    screen_width = window.winfo_screenwidth()     # lê a resolução horizontal do monitor e armazena em "screen_width"
    screen_height = window.winfo_screenheight()   # lê a resolução vertical do monitor e armazena em "screen_height"
      
    x = (screen_width // 2) - (width // 2)        # calcula a coordenada X e Y exata para o centro
    y = (screen_height // 2) - (height // 2)      # uso de duas barras para retornar um número inteiro
    
    window.geometry(f'{width}x{height}+{x}+{y}')  # aplica o posicionamento na janela do sistema operacional


ani = animation.FuncAnimation(fig, update_graph, interval = 100, cache_frame_data=False) # função para atualizar o gráfico, chamando a função de atualização a cada 100 ms
# (objeto da janela onde vai desenhar, função de atualização, tempo de atualização, desativa o salvamento de dados antigos)
ani.pause()  # começa o programa com o gráfico congelado, esprando o botão "start"

plt.show()   # plota o gráfico apenas uma vez ("ani" atualiza depois)


porta_bt.close()  # fecha a porta serial bluetooth