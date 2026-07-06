from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import numpy as np
import os

app = FastAPI(title="FAQ Energía - Chatbot ligero")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FAQ_FILE = "faq_energia.json"
if not os.path.exists(FAQ_FILE):
    raise FileNotFoundError(f"No se encontró {FAQ_FILE}.")

with open(FAQ_FILE, "r", encoding="utf-8") as f:
    faq = json.load(f)

questions = [item["question"] for item in faq]
vectorizer = TfidfVectorizer().fit(questions)
question_vectors = vectorizer.transform(questions)

class Pregunta(BaseModel):
    pregunta: str

@app.post("/preguntar")
def preguntar(pregunta: Pregunta):
    texto = pregunta.pregunta.strip()
    if texto == "":
        return {"respuesta": "Escribe una pregunta para que pueda ayudarte."}

    q_vec = vectorizer.transform([texto])
    sims = cosine_similarity(q_vec, question_vectors).flatten()
    best_idx = int(np.argmax(sims))
    best_score = float(sims[best_idx])

    UMBRAL = 0.28

    if best_score >= UMBRAL:
        return {
            "respuesta": faq[best_idx]["answer"],
            "score": best_score,
            "matched_question": faq[best_idx]["question"]
        }
    else:
        top_k = np.argsort(sims)[-3:][::-1]
        sugerencias = [questions[i] for i in top_k if sims[i] > 0.05]
        return {
            "respuesta": (
                "Lo siento, no encontré una respuesta clara. "
                "Intenta preguntar de otra forma o prueba alguna de estas sugerencias:\n- "
                + ("\n- ".join(sugerencias) if sugerencias else "No tengo sugerencias por ahora.")
            ),
            "score": best_score,
            "matched_question": None,
            "suggestions": sugerencias
        }

@app.get("/")
def root():
    return {"status": "FAQ Energía API funcionando. Endpoint /preguntar (POST)."}
