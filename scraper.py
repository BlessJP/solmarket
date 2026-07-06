from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
import re


def buscar_en_web(pregunta):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/126 Safari/537.36"
        )
    }

    pregunta = pregunta.lower().strip()

    # -------------------------
    # Detectar entidad
    # -------------------------

    dominio = None
    nombre_fuente = "Fuente oficial"

    if "fenoge" in pregunta:
        dominio = "fenoge.gov.co"
        nombre_fuente = "FENOGE"

    elif "creg" in pregunta:
        dominio = "creg.gov.co"
        nombre_fuente = "CREG"

    elif "ministerio" in pregunta or "minenergia" in pregunta:
        dominio = "minenergia.gov.co"
        nombre_fuente = "Ministerio de Minas y Energía"

    elif "xm" in pregunta:
        dominio = "xm.com.co"
        nombre_fuente = "XM"

    elif "upme" in pregunta:
        dominio = "upme.gov.co"
        nombre_fuente = "UPME"

    elif "ipse" in pregunta:
        dominio = "ipse.gov.co"
        nombre_fuente = "IPSE"

    # -------------------------
    # Consulta
    # -------------------------

    if dominio:

        consulta = f"site:{dominio} {pregunta}"

    else:

        consulta = (
            pregunta +
            " energía solar Colombia"
        )

    print("Buscando:", consulta)

    try:

        with DDGS() as buscador:

            resultados = list(

                buscador.text(

                    consulta,

                    max_results=8

                )

            )

    except Exception as e:

        print("Error búsqueda:", e)

        return None

    # -------------------------
    # Palabras importantes
    # -------------------------

    stopwords = {

        "que","qué","cual","cuál","como","cómo","para",
        "los","las","del","de","el","la","un","una",
        "es","son","en","por","con","y","o","a",
        "programas","programa"

    }

    palabras = [

        p

        for p in re.findall(r"\w+", pregunta)

        if len(p) > 2 and p not in stopwords

    ]

    # -------------------------
    # Recorrer resultados
    # -------------------------

    mejor_texto = None
    mejor_score = 0
    mejor_url = None

    for resultado in resultados:

        url = resultado["href"]

        print("Leyendo:", url)

        try:

            r = requests.get(

                url,

                headers=headers,

                timeout=10

            )

            if r.status_code != 200:
                continue

            soup = BeautifulSoup(

                r.text,

                "html.parser"

            )

            for tag in soup([

                "script",
                "style",
                "header",
                "footer",
                "nav",
                "svg",
                "noscript",
                "aside"

            ]):

                tag.decompose()

            texto = soup.get_text("\n")

            texto = re.sub(r"\n+", "\n", texto)

            parrafos = [

                p.strip()

                for p in texto.split("\n")

                if len(p.strip()) > 80

            ]

            for parrafo in parrafos:

                texto_parrafo = parrafo.lower()

                score = 0

                for palabra in palabras:

                    if palabra in texto_parrafo:
                        score += 2

                if pregunta in texto_parrafo:
                    score += 5

                if score > mejor_score:

                    mejor_score = score
                    mejor_texto = parrafo
                    mejor_url = url

        except Exception as e:

            print(e)

            continue

    # -------------------------
    # Respuesta
    # -------------------------

    if mejor_texto and mejor_score >= 4:

        mejor_texto = re.sub(r"\s+", " ", mejor_texto)

        if len(mejor_texto) > 700:

            mejor_texto = mejor_texto[:700] + "..."

        return (

            f"📄 Según {nombre_fuente}:\n\n"
            f"{mejor_texto}\n\n"
            f"🔗 Fuente oficial:\n{mejor_url}"

        )

    return (
        "Lo siento, no encontré información relacionada. "
        "Puedes intentar formular la pregunta de otra manera."
    )
    
def noticias_creg():

    noticias = []

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(
            "https://www.creg.gov.co",
            headers=headers,
            timeout=10
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        textos = soup.get_text("\n")

        lineas = [
            linea.strip()
            for linea in textos.split("\n")
            if linea.strip()
        ]

        capturar = False

        for linea in lineas:

            if "Últimos documentos publicados" in linea:
                capturar = True
                continue

            if capturar and "Sectores que regulamos" in linea:
                break

            if capturar:

                if (
                    "RESOLUCIÓN" in linea.upper()
                    or "PROYECTO DE RESOLUCIÓN" in linea.upper()
                    or "CIRCULAR" in linea.upper()
                    or "AUTO" in linea.upper()
                ):

                    noticias.append({
                        "fuente": "CREG",
                        "titulo": linea
                    })

        return noticias

    except Exception as e:

        print("Error:", e)
        return []
    
