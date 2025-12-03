# src/assistant_logic.py

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.config import get_llm
from src.prompts import (
    PROMPT_ASSISTENTE_GERACAO_DIRETA,
    PROMPT_ASSISTENTE_BRAINSTORMING,
    PROMPT_ASSISTENTE_EXECUCAO
)

def gerar_prompt_final_direto(diagnostico: dict) -> str:
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_GERACAO_DIRETA)
    geracao_chain = prompt_template | llm | StrOutputParser()
    return geracao_chain.invoke(diagnostico)

def gerar_sugestoes(diagnostico: dict) -> str:
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_BRAINSTORMING)
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke(diagnostico)

def gerar_prompt_final_com_abordagem(diagnostico: dict, diretriz_abordagem: str) -> str:
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_EXECUCAO)
    chain = prompt_template | llm | StrOutputParser()
    input_data = {**diagnostico, "diretriz_abordagem": diretriz_abordagem}
    return chain.invoke(input_data)
