import os
import time
import json
import logging
import re
import io
import argparse
from typing import Optional

import pandas as pd
from PIL import Image
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==============================
# CONFIGURAÇÕES DA API
# ==============================
API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DELAY = float(os.environ.get("DELAY_SECONDS", "4.0"))
TAMANHO_LOTE = int(os.environ.get("TAMANHO_LOTE", "10"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
EXTENSOES_VALIDAS = (".jpg", ".jpeg", ".png")

# ==============================
# SCHEMA DO MODELO
# ==============================
class LaudoPsicologico(BaseModel):
    numero_laudo: Optional[str] = Field(description="Número do laudo clínico")
    nome_cliente: Optional[str] = Field(description="Nome completo do paciente/cliente")
    indicacao: Optional[str] = Field(description="Indicação do exame")
    tipo_exame: Optional[str] = Field(description="Tipo: PF, CR ou CR/PF")
    telefone: Optional[str] = Field(description="Apenas os números de telefone")
    data_nascimento: Optional[str] = Field(description="Data no formato DD/MM/AAAA")
    email: Optional[str] = Field(description="Endereço de email")
    data_laudo: Optional[str] = Field(description="Data do laudo no formato DD/MM/AAAA")
    parecer: Optional[str] = Field(description="Apenas APTO, INAPTO ou NAO_INFORMADO")
    profissao: Optional[str] = Field(description="Profissão declarada")

CAMPOS_JSON = list(LaudoPsicologico.model_fields.keys())
COLUNAS_SAIDA = ["arquivo", "status"] + CAMPOS_JSON

# ==============================
# PROMPT
# ==============================
PROMPT = """
Você é um sistema de extração de dados clínicos altamente preciso.
Analise a imagem de um laudo psicológico e extraia os dados solicitados com máxima fidelidade ao conteúdo visível.

REGRAS CRÍTICAS:
- NÃO invente informações.
- NÃO deduza dados que não estejam claramente visíveis.
- Se um campo estiver ausente, ilegível ou ambíguo, retorne null.
"""

# ==============================
# UTILITÁRIOS
# ==============================

def comprimir_imagem(caminho: str) -> bytes:
    """Abre, converte para RGB, redimensiona e retorna JPEG."""
    try:
        with Image.open(caminho) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((1600, 1600))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=95)
            return buffer.getvalue()
    except Exception as e:
        raise ValueError(f"Imagem inválida ou corrompida: '{os.path.basename(caminho)}'") from e


def limpar_dados(dados: dict) -> dict:
    """Padroniza e valida campos do JSON extraído."""
    def apenas_numeros(valor: Optional[str]) -> Optional[str]:
        return re.sub(r"\D", "", valor) if valor else None

    def validar_email(valor: Optional[str]) -> Optional[str]:
        return valor if valor and "@" in valor else None

    def extrair_data(valor: Optional[str]) -> Optional[str]:
        if not valor:
            return None
        match = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", str(valor))
        return match.group(0).replace("-", "/") if match else None

    dados["telefone"] = apenas_numeros(dados.get("telefone"))
    dados["email"] = validar_email(dados.get("email"))
    dados["data_nascimento"] = extrair_data(dados.get("data_nascimento"))
    dados["data_laudo"] = extrair_data(dados.get("data_laudo"))

    return dados


def garantir_campos(dados: dict) -> dict:
    """Garante que todos os campos esperados existam no dicionário."""
    for campo in CAMPOS_JSON:
        dados.setdefault(campo, None)
    return dados


def montar_erro(nome_arquivo: str, mensagem: str) -> dict:
    """Retorna um registro de erro padronizado."""
    base = {campo: None for campo in CAMPOS_JSON}
    base["arquivo"] = nome_arquivo
    base["status"] = f"ERRO: {mensagem}"
    return base


# ==============================
# EXTRAÇÃO COM RETRY
# ==============================

def extrair_dados(client: genai.Client, caminho_imagem: str) -> dict:
    """Envia a imagem para o modelo e retorna os dados extraídos."""
    nome_arquivo = os.path.basename(caminho_imagem)

    for tentativa in range(MAX_RETRIES):
        try:
            imagem = comprimir_imagem(caminho_imagem)

            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=imagem, mime_type="image/jpeg"),
                    PROMPT
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LaudoPsicologico,
                )
            )

            if not response.text:
                logger.warning("Resposta vazia ou bloqueada pelo modelo para '%s'.", nome_arquivo)
                return montar_erro(nome_arquivo, "Resposta vazia ou bloqueada pelo modelo")

            try:
                dados = json.loads(response.text.strip())
            except json.JSONDecodeError:
                return montar_erro(nome_arquivo, "JSON inválido retornado pelo modelo")

            dados = garantir_campos(dados)
            dados = limpar_dados(dados)
            dados["arquivo"] = nome_arquivo
            dados["status"] = "OK"

            return dados

        except Exception as e:
            msg = str(e).lower()
            recuperavel = any(x in msg for x in ["429", "503", "quota", "unavailable"])

            if recuperavel:
                espera = 10 * (tentativa + 1)
                logger.warning("Rate limit. Tentativa %d/%d. Aguardando %ds...", tentativa + 1, MAX_RETRIES, espera)
                time.sleep(espera)
            else:
                logger.error("Erro não recuperável em '%s': %s", nome_arquivo, e)
                return montar_erro(nome_arquivo, str(e))

    return montar_erro(nome_arquivo, f"falha após {MAX_RETRIES} tentativas")


# ==============================
# PERSISTÊNCIA
# ==============================

def salvar_checkpoint(resultados: list, arquivo_parcial: str) -> None:
    pd.DataFrame(resultados).to_csv(arquivo_parcial, index=False)
    logger.info("Checkpoint salvo (%d registros).", len(resultados))


def carregar_checkpoint(arquivo_parcial: str) -> tuple:
    if not os.path.exists(arquivo_parcial):
        return [], set()

    try:
        logger.info("Retomando execução anterior...")
        df = pd.read_csv(arquivo_parcial)
        if "arquivo" not in df.columns:
            raise ValueError("Coluna 'arquivo' ausente no checkpoint.")
        return df.to_dict("records"), set(df["arquivo"].tolist())

    except Exception as e:
        logger.warning("Checkpoint corrompido ou inválido. Detalhes: %s", e)
        backup = arquivo_parcial + ".corrompido"
        try:
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(arquivo_parcial, backup)
            logger.info("Checkpoint corrompido salvo como backup em: %s", backup)
        except Exception as err_renomear:
            logger.error("Aviso: Falha ao tentar renomear o arquivo corrompido: %s", err_renomear)

        return [], set()


# ==============================
# EXPORTAÇÃO FINAL
# ==============================

def exportar_resultados(resultados: list, arquivo_saida: str, arquivo_parcial: str) -> None:
    df = pd.DataFrame(resultados)

    for col in COLUNAS_SAIDA:
        if col not in df.columns:
            df[col] = None

    df = df[COLUNAS_SAIDA]
    df["_numero_temp"] = pd.to_numeric(df["numero_laudo"], errors="coerce")
    df = df.sort_values(by="_numero_temp", na_position="last").drop(columns=["_numero_temp"])

    try:
        df.to_excel(arquivo_saida, index=False)
        logger.info("Exportação concluída → %s", arquivo_saida)
    except PermissionError:
        arquivo_alternativo = arquivo_saida.replace(".xlsx", "_RECUPERADO.xlsx")
        logger.error("ATENÇÃO: O Excel '%s' estava aberto e não pôde ser sobrescrito!", arquivo_saida)
        df.to_excel(arquivo_alternativo, index=False)
        logger.info("Dados salvos no arquivo alternativo → %s", arquivo_alternativo)

    df.to_csv(arquivo_parcial, index=False)


# ==============================
# MAIN
# ==============================

def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai dados de laudos usando Gemini.")
    parser.add_argument(
        "--pasta",
        default=os.environ.get("PASTA_IMAGENS", "./imagens"),
        help="Caminho para a pasta de imagens (padrão: ./imagens ou env PASTA_IMAGENS)"
    )
    parser.add_argument(
        "--saida",
        default=os.environ.get("ARQUIVO_SAIDA", "Planilha_Laudos_Final.xlsx"),
        help="Nome do arquivo de saída Excel (padrão: Planilha_Laudos_Final.xlsx ou env ARQUIVO_SAIDA)"
    )
    parser.add_argument(
        "--checkpoint",
        default=os.environ.get("ARQUIVO_CHECKPOINT", "resultados_parciais.csv"),
        help="Nome do arquivo de checkpoint CSV (padrão: resultados_parciais.csv ou env ARQUIVO_CHECKPOINT)"
    )
    args = parser.parse_args()

    pasta_alvo = args.pasta
    arquivo_saida = os.path.join(pasta_alvo, args.saida)
    arquivo_parcial = os.path.join(pasta_alvo, args.checkpoint)

    if not API_KEY:
        logger.error("API key não encontrada. Defina a variável de ambiente GEMINI_API_KEY.")
        return

    if not os.path.isdir(pasta_alvo):
        logger.error("Pasta não encontrada ou inválida: %s", pasta_alvo)
        return

    logger.info("Iniciando extração na pasta: %s", pasta_alvo)

    arquivos = sorted([
        f for f in os.listdir(pasta_alvo)
        if f.lower().endswith(EXTENSOES_VALIDAS)
    ])

    resultados, processados = carregar_checkpoint(arquivo_parcial)
    pendentes = [f for f in arquivos if f not in processados]

    logger.info("Total: %d | Já processados: %d | Pendentes: %d", len(arquivos), len(processados), len(pendentes))

    if not pendentes:
        if resultados:
            exportar_resultados(resultados, arquivo_saida, arquivo_parcial)
        logger.info("Nenhum arquivo pendente. Encerrando.")
        return

    client = genai.Client(api_key=API_KEY)

    for i, arq in enumerate(pendentes, start=1):
        caminho = os.path.join(pasta_alvo, arq)
        logger.info("[%d/%d] Processando: %s", i, len(pendentes), arq)

        resultado = extrair_dados(client, caminho)
        resultados.append(resultado)
        logger.info("Status: %s", resultado["status"])

        if i % TAMANHO_LOTE == 0:
            salvar_checkpoint(resultados, arquivo_parcial)

        time.sleep(DELAY)

    salvar_checkpoint(resultados, arquivo_parcial)
    exportar_resultados(resultados, arquivo_saida, arquivo_parcial)
    logger.info("Processamento finalizado.")


if __name__ == "__main__":
    main()
