
from __future__ import annotations

from typing import List, Dict, Any
import re
import streamlit as st

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


SHOPWAVE_KB = """
RETURN POLICY
Most products have a 30-day return window from delivery.
Electronics accessories have 60-day return window.
High-value electronics have 15-day return window.
Footwear has 30-day return window and must be unworn.
Sports items non-returnable if used.
Final Sale non-returnable.

DAMAGED OR DEFECTIVE
Damaged item qualifies for refund or replacement.

WRONG ITEM
Wrong item delivered qualifies for free pickup and replacement.

REFUND POLICY
Refund after approval.
5-7 business days.

CUSTOMER TIERS
Standard normal policy.
Premium small exceptions possible.
VIP highest leniency.

CANCELLATION POLICY
Processing orders cancellable.
Shipped orders cannot cancel.
Delivered orders use return flow.

ESCALATION RULES
Refund above $200 escalate.
Fraud escalate.
Low confidence below 0.6 escalate.
"""


def clean_text(text: str):
    return re.sub(r"\s+", " ", text).strip()


def chunk_kb(text: str, chunk_size: int = 220):
    words = clean_text(text).split()

    chunks = []
    current = []

    for word in words:
        current.append(word)

        if len(" ".join(current)) >= chunk_size:
            chunks.append(" ".join(current))
            current = []

    if current:
        chunks.append(" ".join(current))

    return chunks



class KBSearchEngine:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chunks = chunk_kb(SHOPWAVE_KB)

        self.embeddings = self.model.encode(
            self.chunks,
            convert_to_tensor=False
        )

    def search(self, query: str, top_k: int = 3):

        query_emb = self.model.encode(
            [query],
            convert_to_tensor=False
        )

        scores = cosine_similarity(
            query_emb,
            self.embeddings
        )[0]

        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return [
            {
                "chunk_id": idx,
                "score": float(score),
                "text": self.chunks[idx]
            }
            for idx, score in ranked
        ]

    def get_context(self, query: str):
        rows = self.search(query)
        return "\n\n".join([r["text"] for r in rows])



@st.cache_resource
def get_kb():
    return KBSearchEngine()


kb_engine = get_kb()


def search_kb(query: str, top_k: int = 3):
    return kb_engine.search(query, top_k)


def get_kb_context(query: str, top_k: int = 3):
    rows = kb_engine.search(query, top_k)
    return "\n\n".join([r["text"] for r in rows])
