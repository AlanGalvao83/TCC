# Stack Tecnológico — PosturaRun
**TCC · Análise biomecânica de corrida com Inteligência Artificial**
*Desenvolvido por Alan Galvão*

---

## 1. Visão Geral do Sistema

O PosturaRun é uma aplicação web que recebe um vídeo de corrida, extrai poses humanas quadro a quadro com visão computacional, calcula ângulos articulares via trigonometria vetorial e compara com limiares biomecânicos para gerar um laudo automático.

```
Vídeo → OpenCV (frames) → MediaPipe Pose (landmarks) → Cálculo de ângulos → Avaliação biomecânica → JSON → Frontend
```

---

## 2. Stack Tecnológico

### 2.1 Back-end — FastAPI (Python)

| Componente | Versão | Função |
|---|---|---|
| **FastAPI** | 0.115.4 | Framework HTTP assíncrono para a API REST |
| **Uvicorn** | 0.32.0 | Servidor ASGI (ASGI = Python async web interface) |
| **python-multipart** | 0.0.22 | Recebimento do upload de vídeo via `multipart/form-data` |

A rota principal é `POST /analyze`, que recebe o vídeo, processa e retorna um JSON com ângulos, problemas e URLs das visualizações.

### 2.2 Visão Computacional — OpenCV

**OpenCV** (Open Source Computer Vision Library) é usada para:

- Abrir e iterar quadro a quadro com `cv2.VideoCapture`
- Converter espaço de cor BGR → RGB para o MediaPipe
- Desenhar linhas e círculos de anotação sobre os frames
- Exportar o vídeo anotado com `cv2.VideoWriter`

```python
cap = cv2.VideoCapture(video_path)
while True:
    ret, frame = cap.read()       # lê próximo frame
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # converte para RGB
    result = pose.process(image)  # passa para o MediaPipe
```

### 2.3 Estimação de Pose — MediaPipe Pose

**MediaPipe Pose** é um modelo de deep learning desenvolvido pelo Google que detecta **33 pontos de referência** (landmarks) do esqueleto humano em imagens 2D.

Cada landmark retorna coordenadas normalizadas:
- **x** — posição horizontal (0.0 a 1.0)
- **y** — posição vertical (0.0 a 1.0)
- **z** — profundidade estimada (relativa ao quadril)
- **visibility** — confiança da detecção (0.0 a 1.0)

Os pontos utilizados na análise:

| Landmark | Índice | Articulação |
|---|---|---|
| LEFT_SHOULDER | 11 | Ombro esquerdo |
| LEFT_HIP | 23 | Quadril esquerdo |
| LEFT_KNEE | 25 | Joelho esquerdo |
| LEFT_ANKLE | 27 | Tornozelo esquerdo |
| LEFT_FOOT_INDEX | 31 | Ponta do pé esquerdo |
| RIGHT_SHOULDER | 12 | Ombro direito |
| RIGHT_HIP | 24 | Quadril direito |
| RIGHT_KNEE | 26 | Joelho direito |
| RIGHT_ANKLE | 28 | Tornozelo direito |
| RIGHT_FOOT_INDEX | 32 | Ponta do pé direito |

### 2.4 Processamento de Vídeo — imageio + ffmpeg

**imageio** com back-end **ffmpeg** gera o vídeo anotado em MP4 (codec H.264) e o GIF de prévia. O ffmpeg é instalado como dependência de sistema no Dockerfile.

### 2.5 Front-end

Interface web sem framework, servida estaticamente pelo FastAPI (`StaticFiles`):

- **HTML5** — estrutura semântica, drag-and-drop nativo
- **CSS3** — variáveis, grid, media queries, animações
- **JavaScript (ES2020)** — Fetch API, FormData, renderização dinâmica

### 2.6 Infraestrutura — Railway + Docker

O sistema roda em container Docker (Debian Slim + Python 3.11) hospedado no Railway. A porta de serviço é injetada via variável de ambiente `$PORT`.

---

## 3. A Matemática das Decisões

### 3.1 Representação vetorial de articulações

Para calcular o ângulo em uma articulação B formada pelos pontos A–B–C, define-se dois vetores saindo de B:

$$\vec{u} = A - B = (A_x - B_x,\; A_y - B_y)$$
$$\vec{v} = C - B = (C_x - B_x,\; C_y - B_y)$$

### 3.2 Fórmula do ângulo articular

O ângulo θ entre os vetores é obtido pelo **produto escalar** dividido pelo produto das normas (magnitudes):

$$\theta = \arccos\!\left(\frac{\vec{u} \cdot \vec{v}}{|\vec{u}|\;|\vec{v}|}\right)$$

Onde:
- $\vec{u} \cdot \vec{v} = u_x v_x + u_y v_y$ — produto escalar
- $|\vec{u}| = \sqrt{u_x^2 + u_y^2}$ — norma (comprimento) do vetor

O resultado é dado em radianos, convertido para graus com $\theta° = \theta \times \frac{180}{\pi}$.

### 3.3 Implementação em Python (NumPy)

```python
def _angle(a, b, c):
    """Calcula o ângulo na articulação b, formado pelos pontos a-b-c."""
    ab = np.array([a[0] - b[0], a[1] - b[1]])   # vetor u
    cb = np.array([c[0] - b[0], c[1] - b[1]])   # vetor v

    # Normaliza para vetores unitários (evita divisão por zero)
    nab = ab / (np.linalg.norm(ab) + 1e-8)
    ncb = cb / (np.linalg.norm(cb) + 1e-8)

    # Produto escalar → clamped para [-1, 1] por segurança numérica
    cos_ang = np.clip(np.dot(nab, ncb), -1.0, 1.0)

    return float(np.degrees(np.arccos(cos_ang)))  # converte para graus
```

### 3.4 Ângulo de inclinação do tronco

Para medir a inclinação do tronco em relação à vertical, usa-se o vetor **quadril → ombro** comparado com o vetor vertical $(0, -1)$:

```python
def _angle_to_vertical(p1, p2):
    """Ângulo entre o segmento p1→p2 e o eixo vertical."""
    v  = np.array([p2[0] - p1[0], p2[1] - p1[1]])
    nv = v / (np.linalg.norm(v) + 1e-8)
    vertical = np.array([0.0, -1.0])       # eixo Y invertido (imagem)
    cos_ang  = np.clip(np.dot(nv, vertical), -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_ang)))
```

> **Nota:** Em imagens digitais o eixo Y cresce para baixo, por isso o vetor vertical é [(0, -1)](file:///c:/Users/ALAN/Documents/PROJETOS/TCC/public/app.js#86-90) e não [(0, 1)](file:///c:/Users/ALAN/Documents/PROJETOS/TCC/public/app.js#86-90).

---

## 4. Limiares Biomecânicos e Tomada de Decisão

Os ângulos calculados são comparados com intervalos obtidos da literatura biomecânica de corrida:

| Articulação | Mínimo ideal | Máximo ideal | Ideal central |
|---|---|---|---|
| Inclinação do tronco | 4° | 8° | 6° |
| Extensão do joelho | 150° | 170° | 160° |
| Ângulo do quadril | 165° | 175° | 170° |
| Ângulo do tornozelo | 80° | 100° | 90° |

A lógica de avaliação para cada ângulo:

```python
if val < t["min"]:
    # abaixo do ideal → sugerir AUMENTAR
    issue = f"{t['label']} abaixo do ideal"
    correction = {"valor": val, "corrigir": t["min"] - val, "direção": "aumentar"}

elif val > t["max"]:
    # acima do ideal → sugerir REDUZIR
    issue = f"{t['label']} acima do ideal"
    correction = {"valor": val, "corrigir": val - t["max"], "direção": "reduzir"}

else:
    # dentro do intervalo → adequado
    correction = {"valor": val, "corrigir": 0.0, "direção": "adequado"}
```

### Agregação temporal

Como o vídeo tem múltiplos quadros, os ângulos de todos os frames com pose detectada são agregados usando a **mediana**, que é mais robusta a outliers do que a média:

```python
def _aggregate(metrics_list):
    for k in ["trunk", "knee", "hip", "ankle"]:
        vals = [m[side][k] for m in metrics_list]
        agg[side][k] = float(np.median(vals))   # mediana dos quadros
```

---

## 5. Fluxo Completo de Processamento

```
1. Upload do vídeo (multipart/form-data) → FastAPI
       ↓
2. Salva temporariamente em /uploads/<uuid>.mp4
       ↓
3. OpenCV abre o vídeo e itera quadro a quadro
       ↓
4. MediaPipe Pose detecta os 33 landmarks (x, y, z) em cada frame
       ↓
5. _compute_frame_metrics() calcula 4 ângulos por lado (8 no total)
   usando _angle() e _angle_to_vertical() com produto escalar
       ↓
6. Acumula métricas dos frames com pose detectada
       ↓
7. _aggregate() aplica mediana sobre todos os frames
       ↓
8. _evaluate() compara com limiares biomecânicos → gera issues e correções
       ↓
9. OpenCV desenha esqueleto + linhas de postura ideal no vídeo
       ↓
10. imageio salva MP4 anotado + GIF de prévia
        ↓
11. JSON de resposta enviado ao front-end
        ↓
12. JavaScript renderiza cards de ângulos, issues e visualizações
```

---

## 6. Limitações e Considerações

> [!NOTE]
> O sistema usa coordenadas 2D (x, y) extraídas da projeção frontal da câmera. A coordenada z do MediaPipe é uma estimativa de profundidade relativa, não usada nos cálculos angulares para maior estabilidade.

> [!WARNING]
> Os limiares biomecânicos são referências gerais da literatura. Variações individuais (biotipo, tipo de corrida, velocidade) podem alterar os valores ideais para cada atleta.

> [!TIP]
> Para maior precisão, o vídeo deve ser filmado em plano sagital (de lado) com boa iluminação e câmera estável, evitando ângulos oblíquos que distorcem os landmarks.
