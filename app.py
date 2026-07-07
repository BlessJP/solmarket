from flask import Flask, render_template, request, redirect, url_for
from flask import flash, session, jsonify, send_from_directory

import sqlite3
import json
import io
import os

from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from scraper import noticias_creg, buscar_en_web

from difflib import get_close_matches


from difflib import get_close_matches
from sentence_transformers import SentenceTransformer, util


# ======================================================
# APP CONFIG
# ======================================================

app = Flask(__name__)

app.secret_key = 'solmarket123'

ADMIN_USER = "admin"
ADMIN_PASS = "solmarket123"




# ======================================================
# DB CONNECTION
# ======================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")



def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

    
# ======================================================
# FAQ CHATBOT
# ======================================================
with open('faq_energia.json', 'r', encoding='utf-8') as f:
    faq_data = json.load(f)

# ======================================================
# MODELO IA
# ======================================================

print("Cargando modelo de IA...")

modelo_ia = SentenceTransformer("all-MiniLM-L6-v2")

print("Modelo IA cargado correctamente.")

# Lista de preguntas
preguntas_faq = [item["question"] for item in faq_data]

# Embeddings de todas las preguntas
embeddings_faq = modelo_ia.encode(
    preguntas_faq,
    convert_to_tensor=True
)

print(f"{len(preguntas_faq)} preguntas indexadas con IA.")

# ======================================================
# INIT DB
# ======================================================

def init_db():

    with get_db_connection() as conn:

        c = conn.cursor()

        # USUARIOS
        c.execute('''
        CREATE TABLE IF NOT EXISTS solicitud_registro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            numero_documento TEXT UNIQUE,
            correo TEXT,
            direccion TEXT,
            tipo_usuario TEXT,
            contrasena TEXT
        )
        ''')

        # OFERTAS
        c.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_vendedor TEXT,
            numero_documento TEXT,
            cantidad_horas REAL,
            precioxhora REAL,
            preciototal REAL
        )
        ''')

        # VENTAS REALIZADAS
        c.execute('''
        CREATE TABLE IF NOT EXISTS ventas_realizadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vendedor INTEGER,
            nombre_vendedor TEXT,
            nombre_comprador TEXT,
            energia_vendida REAL,
            preciototal REAL
        )
        ''')

        # FACTURAS
        c.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id TEXT,
            codigo_pago TEXT,
            nombre_comprador TEXT,
            total REAL,
            archivo_pdf TEXT,
            estado TEXT,
            fecha TEXT
        )
        ''')

        conn.commit()

init_db()



# ======================================================
# HOME
# ======================================================

@app.route('/')
def index():

    return render_template('index.html')

# ======================================================
# CHATBOX
# ======================================================

@app.route('/chatbox')
def chatbox():

    return render_template('chatbox.html')




# ======================================================
# CHATBOT API
# ======================================================

def buscar_respuesta_ia(pregunta_usuario, umbral=0.80):

    embedding_usuario = modelo_ia.encode(
        pregunta_usuario,
        convert_to_tensor=True
    )

    similitudes = util.cos_sim(
        embedding_usuario,
        embeddings_faq
    )[0]

    indice = similitudes.argmax().item()
    score = similitudes[indice].item()

    print(f"Similitud IA: {score:.3f}")

    if score >= umbral:
        return faq_data[indice]["answer"]

    return None
    try:

        data = request.get_json()

        pregunta_usuario = data.get('pregunta', '').strip().lower()

        # ============================================
        # 1. Buscar usando IA
        # ============================================

        respuesta = buscar_respuesta_ia(pregunta_usuario)

        # ============================================
        # 2. Si no encuentra, buscar en páginas oficiales
        # ============================================

        if respuesta is None:
            respuesta = buscar_en_web(pregunta_usuario)

        # ============================================
        # 3. Respuesta final
        # ============================================

        if respuesta is None:
            respuesta = (
                "Lo siento, no encontré información relacionada. "
                "Puedes intentar formular la pregunta de otra manera."
            )

        return jsonify({
            "respuesta": respuesta
        })

    except Exception as e:

        print("ERROR CHATBOT:", e)

        return jsonify({
            "respuesta": "Error interno del servidor."
        })
    
    
    #==================================================
    
@app.route('/preguntar', methods=['POST'])
def preguntar():

    try:

        data = request.get_json()

        pregunta_usuario = data.get("pregunta", "").strip()

        if not pregunta_usuario:

            return jsonify({
                "respuesta": "Por favor escribe una pregunta."
            })

        # Buscar en la base de preguntas
        respuesta = buscar_respuesta_ia(pregunta_usuario)

        # Si no encuentra, buscar en páginas oficiales
        if respuesta is None:
            respuesta = buscar_en_web(pregunta_usuario)

        # Si tampoco encuentra
        if respuesta is None:
            respuesta = (
                "Lo siento, no encontré información relacionada con tu consulta."
            )

        return jsonify({
            "respuesta": respuesta
        })

    except Exception as e:

        print("ERROR CHATBOT:", e)

        return jsonify({
            "respuesta": "Error interno del servidor."
        }), 500
# ======================================================
# LOGIN
# ======================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        documento = request.form.get(
            'numero_documento'
        )

        clave = request.form.get('clave')

        # ADMIN
        if (
            documento == ADMIN_USER
            and clave == ADMIN_PASS
        ):

            session['rol'] = 'admin'
            session['nombre'] = 'Administrador'

            return redirect(
                url_for('admin_ventas')
            )

        # USUARIO
        with get_db_connection() as conn:

            user = conn.execute('''
                SELECT *
                FROM solicitud_registro
                WHERE numero_documento = ?
                AND contrasena = ?
            ''', (
                documento,
                clave
            )).fetchone()

        if user:

            session['usuario_id'] = user['id']
            session['nombre'] = user['nombre']
            session['numero_documento'] = user['numero_documento']
            session['tipo_usuario'] = user['tipo_usuario']

            if user['tipo_usuario'] == 'comprador':

                return redirect(
                    url_for('reservas')
                )

            else:

                return redirect(
                    url_for('ventas_vendedor')
                )

        flash('❌ Datos incorrectos')

        return redirect(
            url_for('login')
        )

    return render_template('login.html')

# ======================================================
# LOGOUT
# ======================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect(
        url_for('login')
    )

# ======================================================
# REGISTRO
# ======================================================

@app.route('/registro_form', methods=['GET', 'POST'])
def registro_form():

    if request.method == 'POST':

        nombre = request.form.get('nombre')

        numero_documento = request.form.get(
            'numero_documento'
        )

        correo = request.form.get('correo')

        direccion = request.form.get('direccion')

        tipo_usuario = request.form.get(
            'tipo_usuario'
        )

        contrasena = request.form.get(
            'contrasena'
        )

        try:

            with get_db_connection() as conn:

                conn.execute('''
                    INSERT INTO solicitud_registro
                    (
                        nombre,
                        numero_documento,
                        correo,
                        direccion,
                        tipo_usuario,
                        contrasena
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    nombre,
                    numero_documento,
                    correo,
                    direccion,
                    tipo_usuario,
                    contrasena
                ))

                conn.commit()

            flash('✅ Registro exitoso')

            return redirect(
                url_for('login')
            )

        except Exception as e:

            flash(f'❌ Error: {e}')

            return redirect(
                url_for('registro_form')
            )

    return render_template('registro.html')

# ======================================================
# RESERVAS
# ======================================================
@app.route('/reservas')
def reservas():

    if 'numero_documento' not in session:
        return redirect(url_for('login'))

    with get_db_connection() as conn:

        # Ofertas disponibles
        ventas = conn.execute("""
            SELECT *
            FROM ventas
            ORDER BY precioxhora ASC
        """).fetchall()

        # Facturas del comprador que inició sesión
        facturas = conn.execute("""
            SELECT *
            FROM facturas
            WHERE nombre_comprador = ?
            ORDER BY id DESC
        """, (
            session['nombre'],
        )).fetchall()

    return render_template(
        "reservas.html",
        ventas=ventas,
        facturas=facturas
    )

# ======================================================
# GUARDAR COMPRA
# ======================================================

@app.route('/guardar_venta', methods=['POST'])
def guardar_venta():

    if 'numero_documento' not in session:

        return redirect(
            url_for('login')
        )

    try:

        energia_total = float(
            request.form.get(
                'energia_total',
                0
            )
        )

        if energia_total <= 0:

            flash('❌ Cantidad inválida')

            return redirect(
                url_for('reservas')
            )

        with get_db_connection() as conn:

            ofertas = conn.execute('''
                SELECT *
                FROM ventas
                ORDER BY precioxhora ASC
            ''').fetchall()

            if not ofertas:

                flash('❌ No hay energía disponible')

                return redirect(
                    url_for('reservas')
                )

            energia_restante = energia_total
            total_general = 0
            detalle_factura = []

            for oferta in ofertas:

                if energia_restante <= 0:
                    break

                disponible = oferta['cantidad_horas']

                energia_comprada = min(
                    energia_restante,
                    disponible
                )

                subtotal = (
                    energia_comprada *
                    oferta['precioxhora']
                )

                detalle_factura.append({
                    'vendedor': oferta['nombre_vendedor'],
                    'energia': energia_comprada,
                    'precio': oferta['precioxhora'],
                    'subtotal': subtotal
                })

                total_general += subtotal

                conn.execute('''
                    INSERT INTO ventas_realizadas
                (
        id_vendedor,
        nombre_vendedor,
        nombre_comprador,
        energia_vendida,
        precioxhora,
        preciototal
    )
    VALUES (?, ?, ?, ?, ?, ?)
''', (
    oferta['id'],
    oferta['nombre_vendedor'],
    session['nombre'],
    energia_comprada,
    oferta['precioxhora'],
    subtotal
))

                nueva_cantidad = (
                    disponible -
                    energia_comprada
                )

                if nueva_cantidad > 0:

                    conn.execute('''
                        UPDATE ventas
                        SET cantidad_horas = ?,
                            preciototal = ?
                        WHERE id = ?
                    ''', (
                        nueva_cantidad,
                        nueva_cantidad * oferta['precioxhora'],
                        oferta['id']
                    ))

                else:

                    conn.execute('''
                        DELETE FROM ventas
                        WHERE id = ?
                    ''', (
                        oferta['id'],
                    ))

                energia_restante -= energia_comprada

            conn.commit()

        factura_id = (
            f"SM-"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        codigo_pago = (
            f"PAY-"
            f"{datetime.now().strftime('%H%M%S')}"
        )

        carpeta_facturas = 'static/facturas'

        if not os.path.exists(carpeta_facturas):
            os.makedirs(carpeta_facturas)

        nombre_pdf = f'{factura_id}.pdf'

        ruta_pdf = os.path.join(
            carpeta_facturas,
            nombre_pdf
        )

        buffer = io.BytesIO()

        pdf = canvas.Canvas(
            buffer,
            pagesize=letter
        )

        pdf.setFont(
            "Helvetica-Bold",
            20
        )

        pdf.drawString(
            150,
            750,
            "SOL MARKET S.A.S"
        )

        pdf.setFont(
            "Helvetica",
            12
        )

        pdf.drawString(
            50,
            700,
            f"Factura: {factura_id}"
        )

        pdf.drawString(
            50,
            680,
            f"Cliente: {session['nombre']}"
        )

        pdf.drawString(
            50,
            660,
            f"Codigo Pago: {codigo_pago}"
        )

        y = 620

        pdf.setFont(
            "Helvetica-Bold",
            12
        )

        pdf.drawString(
            50,
            y,
            "DETALLE DE COMPRA"
        )

        y -= 30

        pdf.setFont(
            "Helvetica",
            11
        )

        for item in detalle_factura:

            pdf.drawString(
                50,
                y,
                f"Vendedor: {item['vendedor']}"
            )

            y -= 20

            pdf.drawString(
                70,
                y,
                f"Energia Comprada: {item['energia']} kWh"
            )

            y -= 20

            pdf.drawString(
                70,
                y,
                f"Precio por kWh: ${item['precio']:.2f}"
            )

            y -= 20

            pdf.drawString(
                70,
                y,
                f"Subtotal: ${item['subtotal']:.2f}"
            )

            y -= 35

        pdf.setFont(
            "Helvetica-Bold",
            13
        )

        pdf.drawString(
            50,
            y,
            f"TOTAL GENERAL: ${total_general:.2f}"
        )

        y -= 40

        pdf.setFont(
            "Helvetica-Oblique",
            11
        )

        pdf.drawString(
            50,
            y,
            "Gracias por utilizar Sol Market."
        )

        y -= 20

        pdf.drawString(
            50,
            y,
            "La energia del futuro esta en tus manos."
        )

        pdf.save()

        pdf_bytes = buffer.getvalue()

        with open(ruta_pdf, 'wb') as f:
            f.write(pdf_bytes)

        buffer.close()

        with get_db_connection() as conn:

            conn.execute('''
                INSERT INTO facturas
                (
                    factura_id,
                    codigo_pago,
                    nombre_comprador,
                    total,
                    archivo_pdf,
                    estado,
                    fecha
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                factura_id,
                codigo_pago,
                session['nombre'],
                total_general,
                nombre_pdf,
                'Pendiente',
                datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            ))

            conn.commit()

        return render_template(
            'compra_exitosa.html',
            codigo=codigo_pago,
            factura=nombre_pdf
        )

    except Exception as e:

        print("ERROR:", e)

        flash('❌ Error al procesar la compra')

        return redirect(
            url_for('reservas')
        )


#========================================================

#========================================================

@app.route("/descargar_factura/<nombre_pdf>")
def descargar_factura(nombre_pdf):

    return send_from_directory(
        "static/facturas",
        nombre_pdf,
        as_attachment=True
    )

# ======================================================
# PUBLICAR OFERTA
# ======================================================

@app.route('/guardar_venta_v', methods=['POST'])
def guardar_venta_v():

    if 'numero_documento' not in session:
        return redirect(url_for('login'))

    try:

        nombre = session['nombre']
        documento = session['numero_documento']

        cantidad = float(request.form['cantidad_horas'])
        precio = float(request.form['precioxhora'])

        total = cantidad * precio

        fecha_publicacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with get_db_connection() as conn:

            conn.execute("""
                INSERT INTO ventas
                (
                    nombre_vendedor,
                    numero_documento,
                    cantidad_horas,
                    precioxhora,
                    preciototal,
                    fecha_publicacion
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                nombre,
                documento,
                cantidad,
                precio,
                total,
                fecha_publicacion
            ))

            conn.commit()

        flash("✅ Oferta publicada correctamente.")

    except Exception as e:

        print(e)
        flash("❌ No fue posible publicar la oferta.")

    return redirect(url_for("ventas_vendedor"))


#=============================================================

# Mis Ofertas

#============================================================


@app.route('/mis_ofertas')
def mis_ofertas():            

    if 'numero_documento' not in session:
        return redirect(url_for('login'))

    documento = session['numero_documento']

    conn = get_db_connection()

    ofertas = conn.execute('''
        SELECT *
        FROM ventas
        WHERE numero_documento = ?
        ORDER BY fecha_publicacion DESC
    ''', (documento,)).fetchall()

    conn.close()

    return render_template(
        'mis_ofertas.html',
        ofertas=ofertas
    )
    
    #=========================== VER Y ELIMINAR VENTAS===================
@app.route('/ventas')
def ventas_vendedor():

    if 'numero_documento' not in session:
        return redirect(url_for('login'))

    documento = str(session['numero_documento']).strip()

    with get_db_connection() as conn:

        ofertas = conn.execute("""
            SELECT *
            FROM ventas
            WHERE TRIM(numero_documento) = ?
            ORDER BY id DESC
        """, (documento,)).fetchall()

    return render_template(
        "ventas.html",
        ofertas=ofertas
    )

#================================================================ 


@app.route('/editar_oferta/<int:id>', methods=['GET', 'POST'])
def editar_oferta(id):

    if 'numero_documento' not in session:
        return redirect(url_for('login'))

    with get_db_connection() as conn:

        if request.method == 'POST':

            cantidad = float(request.form['cantidad_horas'])
            precio = float(request.form['precioxhora'])
            total = cantidad * precio

            conn.execute("""
                UPDATE ventas
                SET cantidad_horas = ?,
                    precioxhora = ?,
                    preciototal = ?
                WHERE id = ?
                AND numero_documento = ?
            """, (
                cantidad,
                precio,
                total,
                id,
                session['numero_documento']
            ))

            conn.commit()

            flash("✅ Oferta actualizada correctamente.")

            return redirect(url_for('ventas_vendedor'))

        oferta = conn.execute("""
            SELECT *
            FROM ventas
            WHERE id = ?
            AND numero_documento = ?
        """, (
            id,
            session['numero_documento']
        )).fetchone()

    if oferta is None:

        flash("❌ Oferta no encontrada.")

        return redirect(url_for('ventas_vendedor'))

    return render_template(
        'editar_oferta.html',
        oferta=oferta
    )

#==============================================================

@app.route('/eliminar_oferta/<int:id>')
def eliminar_oferta(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM ventas WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("Oferta eliminada")

    return redirect(
        url_for('ventas_vendedor')
    )



# ======================================================
# ADMIN VENTAS
# ======================================================

@app.route('/admin/ventas')
def admin_ventas():

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    with get_db_connection() as conn:

        ventas = conn.execute('''
            SELECT *
            FROM ventas_realizadas
            ORDER BY id DESC
        ''').fetchall()

    return render_template(
        'admin_ventas.html',
        ventas=ventas
    )

# ======================================================
# ADMIN OFERTAS
# ======================================================

@app.route('/admin/ofertas')
def admin_ofertas():

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    with get_db_connection() as conn:

        ofertas = conn.execute('''
            SELECT *
            FROM ventas
            ORDER BY id DESC
        ''').fetchall()

    return render_template(
        'admin_ofertas.html',
        ofertas=ofertas
    )

# ======================================================
# ADMIN FACTURAS
# ======================================================

@app.route('/admin/facturas')
def admin_facturas():

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    with get_db_connection() as conn:

        facturas = conn.execute('''
            SELECT *
            FROM facturas
            ORDER BY id DESC
        ''').fetchall()

    return render_template(
        'admin_facturas.html',
        facturas=facturas
    )

# ======================================================
# PAGAR FACTURA
# ======================================================

@app.route('/admin/facturas/pagar/<int:id>')
def pagar_factura(id):

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    with get_db_connection() as conn:

        conn.execute('''
            UPDATE facturas
            SET estado = 'Pagada'
            WHERE id = ?
        ''', (
            id,
        ))

        conn.commit()

    flash('✅ Factura marcada como pagada')

    return redirect(
        url_for('admin_facturas')
    )

# ======================================================
# ADMIN SOLICITUDES
# ======================================================

@app.route('/admin/solicitudes')
def admin_solicitudes():

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    with get_db_connection() as conn:

        solicitudes = conn.execute('''
            SELECT *
            FROM solicitud_registro
            ORDER BY id DESC
        ''').fetchall()

    return render_template(
        'admin_solicitudes.html',
        solicitudes=solicitudes
    )

# ======================================================
# EDITAR SOLICITUD
# ======================================================

@app.route(
    '/admin/solicitudes/editar/<int:id>',
    methods=['POST']
)
def editar_solicitud(id):

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    nombre = request.form['nombre']
    correo = request.form['correo']
    direccion = request.form['direccion']
    tipo_usuario = request.form['tipo_usuario']

    with get_db_connection() as conn:

        conn.execute('''
            UPDATE solicitud_registro
            SET nombre = ?,
                correo = ?,
                direccion = ?,
                tipo_usuario = ?
            WHERE id = ?
        ''', (
            nombre,
            correo,
            direccion,
            tipo_usuario,
            id
        ))

        conn.commit()

    flash('✅ Usuario actualizado')

    return redirect(
        url_for('admin_solicitudes')
    )

# ======================================================
# ELIMINAR SOLICITUD
# ======================================================

@app.route(
    '/admin/solicitudes/eliminar/<int:id>'
)
def eliminar_solicitud(id):

    if 'rol' not in session:

        return redirect(
            url_for('login')
        )

    with get_db_connection() as conn:

        conn.execute('''
            DELETE FROM solicitud_registro
            WHERE id = ?
        ''', (
            id,
        ))

        conn.commit()

    flash('✅ Usuario eliminado')

    return redirect(
        url_for('admin_solicitudes')
    )
    
# ==================================================
# Seccion de noticias 
# ==================================================
@app.route('/noticias')
def noticias():

    with get_db_connection() as conn:

        # Mejores compradores
        mejores_compradores = conn.execute("""
            SELECT nombre_comprador,
                   SUM(energia_vendida) AS energia_total,
                   SUM(preciototal) AS total
            FROM ventas_realizadas
            GROUP BY nombre_comprador
            ORDER BY energia_total DESC
            LIMIT 5
        """).fetchall()

        # Mejores vendedores
        mejores_vendedores = conn.execute("""
            SELECT nombre_vendedor,
                   SUM(energia_vendida) AS energia_total,
                   SUM(preciototal) AS total
            FROM ventas_realizadas
            GROUP BY nombre_vendedor
            ORDER BY energia_total DESC
            LIMIT 5
        """).fetchall()

        # Transacción más alta
        transaccion_alta = conn.execute("""
            SELECT *
            FROM ventas_realizadas
            ORDER BY preciototal DESC
            LIMIT 1
        """).fetchone()

        # Transacción más baja
        transaccion_baja = conn.execute("""
    SELECT *
    FROM ventas_realizadas
    WHERE preciototal > 0
    ORDER BY preciototal ASC
    LIMIT 1
""").fetchone()

        # Últimas ofertas
        ultimas_ofertas = conn.execute("""
            SELECT *
            FROM ventas
            ORDER BY id DESC
            LIMIT 5
        """).fetchall()

        # Estadísticas generales
        total_usuarios = conn.execute("""
            SELECT COUNT(*) as total
            FROM solicitud_registro
        """).fetchone()["total"]

        total_ventas = conn.execute("""
            SELECT COUNT(*) as total
            FROM ventas_realizadas
        """).fetchone()["total"]

        ofertas_activas = conn.execute("""
            SELECT COUNT(*) as total
            FROM ventas
        """).fetchone()["total"]

        energia_total = conn.execute("""
            SELECT COALESCE(SUM(energia_vendida),0) as total
            FROM ventas_realizadas
        """).fetchone()["total"]

    noticias_scraping = noticias_creg()

    print("NOTICIAS ENVIADAS AL HTML:")
    print(len(noticias_scraping))
    print(noticias_scraping)

    
    return render_template(
    'noticias.html',
    mejores_compradores=mejores_compradores,
    mejores_vendedores=mejores_vendedores,
    transaccion_alta=transaccion_alta,
    transaccion_baja=transaccion_baja,
    ultimas_ofertas=ultimas_ofertas,
    total_usuarios=total_usuarios,
    total_ventas=total_ventas,
    ofertas_activas=ofertas_activas,
    energia_total=energia_total,
    noticias_scraping=noticias_scraping
)  



# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)