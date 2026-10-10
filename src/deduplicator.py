import hashlib
import re
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from database.db import get_connection
from src.config import TRACKING_PARAMS, TITLE_SIMILARITY_THRESHOLD

def normalize_url(url: str) -> str:
    """
    Normaliza URLs removendo parâmetros de rastreamento (UTMs, fbclid, etc.)
    enquanto preserva parâmetros estruturais necessários para identificar o post (ex: id, p, v).
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = []
    for key in sorted(query_params.keys()):
        key_lower = key.lower()
        if key_lower not in TRACKING_PARAMS and not key_lower.startswith("utm_"):
            for val in query_params[key]:
                filtered_params.append((key, val))

    new_query = urlencode(filtered_params)
    normalized = urlunparse((scheme, netloc, path, parsed.params, new_query, ""))
    return normalized

def compute_content_hash(titulo: str, resumo: str) -> str:
    """
    Calcula o hash SHA-256 estável baseado na combinação normalizada do título e resumo.
    """
    texto_limpo = f"{titulo.strip().lower()}:{resumo.strip().lower()}"
    return hashlib.sha256(texto_limpo.encode("utf-8")).hexdigest()

def calculate_title_similarity(titulo1: str, titulo2: str) -> float:
    """
    Calcula a similaridade entre dois títulos usando SequenceMatcher e sobreposição de tokens.
    Retorna um valor float de 0.0 a 1.0.
    """
    if not titulo1 or not titulo2:
        return 0.0

    t1_clean = re.sub(r"[^\w\s]", "", titulo1.lower())
    t2_clean = re.sub(r"[^\w\s]", "", titulo2.lower())

    if t1_clean == t2_clean:
        return 1.0

    seq_ratio = SequenceMatcher(None, t1_clean, t2_clean).ratio()

    words1 = set(t1_clean.split())
    words2 = set(t2_clean.split())
    if not words1 or not words2:
        return seq_ratio

    jaccard = len(words1.intersection(words2)) / len(words1.union(words2))
    return round((seq_ratio * 0.6) + (jaccard * 0.4), 4)

def is_duplicate_url(db_path: str, url_normalizada: str) -> bool:
    """
    Verifica se a URL normalizada já existe no banco de dados SQLite.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM noticias WHERE url_normalizada = ?", (url_normalizada,))
        return cursor.fetchone() is not None

def find_similar_noticia(db_path: str, titulo: str, threshold: float = TITLE_SIMILARITY_THRESHOLD, limit_recent: int = 100) -> Optional[Dict[str, Any]]:
    """
    Verifica se existe alguma notícia recente cadastrada com título similar acima do limiar.
    Limita a busca aos últimos 100 registros para garantir alta performance durante grandes lotes RSS.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo, url_normalizada FROM noticias ORDER BY id DESC LIMIT ?", (limit_recent,))
        rows = cursor.fetchall()

    for row in rows:
        sim = calculate_title_similarity(titulo, row["titulo"])
        if sim >= threshold:
            return {
                "id": row["id"],
                "titulo": row["titulo"],
                "url_normalizada": row["url_normalizada"],
                "similarity_score": sim
            }
    return None
