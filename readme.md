# Ping Monitor

Aplicação web para monitoramento de conectividade via ICMP (ping),
voltada para uso interno em redes corporativas.

O sistema permite acompanhar múltiplos hosts em tempo real, exibindo
latência, perda de pacotes e status visual (UP / INSTÁVEL / DOWN).

---

## Funcionalidades

- Monitoramento de até **60 IPs/hosts**
- Gráfico de latência em tempo real
- Status automático:
  - 🟢 **UP** – sem perda
  - 🟡 **INSTÁVEL** – perda parcial
  - 🔴 **DOWN** – perda total
- Interface com abas
- Organização manual das abas
- Remoção dinâmica de hosts
- Persistência de hosts (nome + IP)
- Retomada automática do monitoramento após reiniciar o app

---

## Tecnologias utilizadas

- Python 3
- Flask
- pythonping
- Chart.js
- HTML / CSS / JavaScript

---

## Persistência de Hosts

Os hosts monitorados são armazenados no arquivo `hosts.json`.

Esse arquivo **não é versionado** por conter dados internos da rede.
Caso não exista, ele será criado automaticamente ao adicionar o primeiro host.

---

## Como executar

```bash
# criar ambiente virtual
python -m venv .venv

# ativar (Windows)
.venv\Scripts\activate

# ativar (Linux / Mac)
source .venv/bin/activate

# instalar dependências
pip install -r requirements.txt

# executar
python app.py