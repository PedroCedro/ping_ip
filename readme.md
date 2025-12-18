# Monitor de Ping em Tempo Real

Aplicação web simples para monitoramento de ping em tempo real, com:
- múltiplos IPs
- status visual (UP / INSTÁVEL / DOWN)
- gráfico de latência
- perda de pacotes real
- nomes amigáveis por host

## Tecnologias
- Python
- Flask
- pythonping
- Chart.js
- HTML / CSS / JavaScript

## Como rodar o projeto

```bash
# criar ambiente virtual

python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# instalar dependências
pip install -r requirements.txt

# rodar
python app.py

## Configuração de Hosts

Os hosts monitorados são salvos em um arquivo local (`hosts.json`).

Cada host possui:
- nome amigável
- IP ou hostname

Exemplo:
```json
[
  { "name": "CLOUDFARE", "ip": "1.1.1.1" },
  { "name": "GOOGLE DNS1", "ip": "8.8.8.8" },
  { "name": "GOOGLE DNS2", "ip": "8.8.4.4" }
]

