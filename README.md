# 🧠 Analisador de Laudos Psicológicos

Ferramenta de extração automática de dados estruturados a partir de imagens de laudos psicológicos, utilizando o modelo **Gemini** (Google AI) via Vision API. Os dados extraídos são exportados para uma planilha Excel (`.xlsx`).

---

## 📋 O que o programa faz

- Lê imagens de laudos psicológicos (`.jpg`, `.jpeg`, `.png`) de uma pasta
- Envia cada imagem para o modelo Gemini e extrai campos como nome, data de nascimento, parecer, profissão, entre outros
- Salva checkpoints automáticos para retomar execuções interrompidas
- Exporta todos os dados extraídos em uma planilha Excel ordenada por número de laudo

---

## 📁 Estrutura esperada do projeto

```
seu-projeto/
├── analisador.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
└── imagens/          ← coloque aqui os laudos em .jpg/.jpeg/.png
```

---

## 🔑 Pré-requisito: obter a API Key do Gemini

1. Acesse [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Faça login com sua conta Google
3. Clique em **"Create API Key"** e copie a chave gerada

---

## 🐍 Opção 1 — Rodar localmente com Python

### 1. Pré-requisitos

- Python **3.10+** instalado ([python.org](https://www.python.org/downloads/))
- `pip` disponível no terminal

Verifique sua versão:

```bash
python --version
pip --version
```

### 2. Clone ou baixe o projeto

```bash
git clone https://github.com/Kaneka4850/Analisador-de-documentos.git
cd Analisador-de-documentos
```

### 3. Crie e ative um ambiente virtual (recomendado)

**Linux / macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 4. Instale as dependências

```bash
pip install -r requirements.txt
```

### 5. Configure a API Key

**Linux / macOS:**
```bash
export GEMINI_API_KEY="sua_chave_aqui"
```

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="sua_chave_aqui"
```

> ⚠️ Essa variável precisa ser definida toda vez que abrir um novo terminal. Para torná-la permanente, adicione a linha ao seu `.bashrc`, `.zshrc` ou às variáveis de ambiente do sistema.

### 6. Prepare a pasta de imagens

Crie uma pasta chamada `imagens` na raiz do projeto e mova seus laudos para dentro:

```bash
mkdir imagens
# Copie seus arquivos .jpg/.jpeg/.png para a pasta imagens/
```

### 7. Execute o programa

```bash
python analisador.py --pasta ./imagens
```

O arquivo Excel será gerado dentro da própria pasta de imagens como `Planilha_Laudos_Final.xlsx`.

#### Parâmetros opcionais

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `--pasta` | Caminho para a pasta com as imagens | `./imagens` |
| `--saida` | Nome do arquivo Excel de saída | `Planilha_Laudos_Final.xlsx` |
| `--checkpoint` | Nome do arquivo de checkpoint CSV | `resultados_parciais.csv` |

Exemplo com parâmetros personalizados:

```bash
python analisador.py --pasta ./meus_laudos --saida resultado_junho.xlsx
```

---

## 🐳 Opção 2 — Rodar com Docker

### 1. Pré-requisitos

- Docker instalado ([docs.docker.com/get-docker](https://docs.docker.com/get-docker/))
- Docker Compose (já incluído no Docker Desktop; no Linux, verifique com `docker compose version`)

Verifique a instalação:

```bash
docker --version
docker compose version
```

### 2. Clone ou baixe o projeto

```bash
git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio
```

### 3. Crie o arquivo `.env`

Na raiz do projeto, crie um arquivo chamado `.env` com sua API Key:

```bash
echo 'GEMINI_API_KEY=sua_chave_aqui' > .env
```

> 🔒 Nunca envie o arquivo `.env` para o GitHub. Ele já deve estar no `.gitignore`.

### 4. Prepare a pasta de imagens

```bash
mkdir imagens
# Copie seus arquivos .jpg/.jpeg/.png para a pasta imagens/
```

### 5. Build da imagem Docker

```bash
docker compose build
```

### 6. Execute o programa

```bash
docker compose up
```

O programa vai processar todas as imagens dentro de `./imagens/` e gerar o Excel na mesma pasta ao finalizar.

Para rodar em segundo plano (sem travar o terminal):

```bash
docker compose up -d
```

Para acompanhar os logs enquanto roda em segundo plano:

```bash
docker compose logs -f
```

---

## ⚙️ Variáveis de ambiente disponíveis

Todas as configurações do programa podem ser ajustadas via variáveis de ambiente, seja no `.env` ou diretamente no terminal.

| Variável | Descrição | Padrão |
|---|---|---|
| `GEMINI_API_KEY` | Chave de autenticação da API Google AI | *(obrigatória)* |
| `GEMINI_MODEL` | Modelo Gemini a ser utilizado | `gemini-2.5-flash` |
| `PASTA_IMAGENS` | Caminho da pasta com as imagens | `./imagens` |
| `ARQUIVO_SAIDA` | Nome do Excel de saída | `Planilha_Laudos_Final.xlsx` |
| `ARQUIVO_CHECKPOINT` | Nome do CSV de checkpoint | `resultados_parciais.csv` |
| `DELAY_SECONDS` | Intervalo entre requisições (segundos) | `4.0` |
| `TAMANHO_LOTE` | Intervalo de salvamento de checkpoint | `10` |
| `MAX_RETRIES` | Tentativas em caso de erro recuperável | `5` |

---

## 📊 Campos extraídos

| Campo | Descrição |
|---|---|
| `numero_laudo` | Número do laudo clínico |
| `nome_cliente` | Nome completo do paciente |
| `indicacao` | Indicação do exame |
| `tipo_exame` | Tipo: PF, CR ou CR/PF |
| `telefone` | Apenas os dígitos do telefone |
| `data_nascimento` | Data no formato DD/MM/AAAA |
| `email` | Endereço de e-mail |
| `data_laudo` | Data do laudo no formato DD/MM/AAAA |
| `parecer` | `APTO`, `INAPTO` ou `NAO_INFORMADO` |
| `profissao` | Profissão declarada |

---

## 🔄 Retomada automática

Se a execução for interrompida por qualquer motivo, basta rodar o comando novamente. O programa detecta automaticamente o arquivo `resultados_parciais.csv` e retoma do ponto onde parou, sem reprocessar arquivos já concluídos.

---

## ❗ Solução de problemas comuns

**`API key não encontrada`**
Verifique se a variável `GEMINI_API_KEY` está definida corretamente no terminal ou no arquivo `.env`.

**`Pasta não encontrada ou inválida`**
Confirme que a pasta `imagens/` existe e que o caminho passado no `--pasta` está correto.

**`PermissionError` ao salvar o Excel**
O arquivo `.xlsx` de saída está aberto no Excel ou outro programa. Feche-o e execute novamente. O programa salvará automaticamente uma versão com sufixo `_RECUPERADO.xlsx`.

**Erros 429 / 503 (Rate limit)**
O programa tenta novamente automaticamente com backoff. Se os erros persistirem, aumente o valor de `DELAY_SECONDS`.
