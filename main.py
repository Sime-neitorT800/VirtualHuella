import customtkinter as ctk
import cv2
import face_recognition
import os
import sqlite3
from datetime import datetime, timedelta

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

conexion = sqlite3.connect("database/vitalhuella.db")
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    fecha TEXT,
    hora TEXT,
    tipo TEXT,
    tardanza_minutos INTEGER DEFAULT 0,
    extra_minutos INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS docentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE,
    ruta_rostro TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS horarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    docente_id INTEGER,
    dia TEXT,
    turno TEXT,
    hora_inicio TEXT,
    hora_fin TEXT,
    horas_academicas REAL,
    FOREIGN KEY (docente_id) REFERENCES docentes(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS jornadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    fecha TEXT,
    hora_entrada TEXT,
    hora_salida TEXT,
    tardanza_minutos INTEGER DEFAULT 0,
    extra_minutos INTEGER DEFAULT 0,
    estado TEXT DEFAULT 'Abierta'
)
""")

conexion.commit()

try:
    cursor.execute("""
    ALTER TABLE asistencias
    ADD COLUMN tardanza_minutos INTEGER DEFAULT 0
    """)
except sqlite3.OperationalError:
    pass

try:
    cursor.execute("""
    ALTER TABLE asistencias
    ADD COLUMN extra_minutos INTEGER DEFAULT 0
    """)
except sqlite3.OperationalError:
    pass

conexion.commit()


def mostrar_mensaje(ventana, texto, color):
    mensaje = ctk.CTkLabel(
        ventana,
        text=texto,
        text_color=color,
        font=("Arial", 15, "bold"),
        wraplength=500
    )
    mensaje.pack(pady=10)


def abrir_camara():
    camara = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camara.isOpened():
        return None

    return camara


def registrar_docente_desde_ventana(nombre, ventana_registro, horarios_temp):
    nombre = nombre.strip()

    if nombre == "":
        mostrar_mensaje(ventana_registro, "Ingrese un nombre válido", "red")
        return

    if len(horarios_temp) == 0:
        mostrar_mensaje(ventana_registro, "Agregue al menos un horario", "red")
        return

    camara = abrir_camara()

    if camara is None:
        mostrar_mensaje(ventana_registro, "No se pudo abrir la cámara", "red")
        return

    cv2.namedWindow("Registro Docente", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Registro Docente", cv2.WND_PROP_TOPMOST, 1)

    while True:
        resultado, frame = camara.read()

        if not resultado:
            mostrar_mensaje(ventana_registro, "No se pudo leer la cámara", "red")
            break

        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        rostros = detector.detectMultiScale(
            gris,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100)
        )

        for (x, y, w, h) in rostros:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

        cv2.imshow("Registro Docente", frame)

        tecla = cv2.waitKey(1)

        if tecla == ord("s"):
            for (x, y, w, h) in rostros:
                rostro = frame[y:y+h, x:x+w]

                rgb_rostro = cv2.cvtColor(rostro, cv2.COLOR_BGR2RGB)
                codificaciones_nuevo = face_recognition.face_encodings(rgb_rostro)

                if len(codificaciones_nuevo) == 0:
                    camara.release()
                    cv2.destroyAllWindows()
                    mostrar_mensaje(ventana_registro, "No se pudo codificar el rostro", "red")
                    return

                codificacion_nueva = codificaciones_nuevo[0]

                for archivo in os.listdir("faces"):
                    if archivo.endswith(".jpg") or archivo.endswith(".png"):
                        ruta_existente = f"faces/{archivo}"
                        imagen_existente = face_recognition.load_image_file(ruta_existente)
                        codificaciones_existente = face_recognition.face_encodings(imagen_existente)

                        if len(codificaciones_existente) > 0:
                            coincidencia = face_recognition.compare_faces(
                                [codificaciones_existente[0]],
                                codificacion_nueva,
                                tolerance=0.5
                            )

                            if coincidencia[0]:
                                nombre_existente = os.path.splitext(archivo)[0]

                                camara.release()
                                cv2.destroyAllWindows()

                                mostrar_mensaje(
                                    ventana_registro,
                                    f"Este rostro ya está registrado como\n{nombre_existente}",
                                    "red"
                                )
                                return

                ruta = f"faces/{nombre}.jpg"
                cv2.imwrite(ruta, rostro)

                try:
                    cursor.execute("""
                    INSERT INTO docentes (
                        nombre,
                        ruta_rostro
                    )
                    VALUES (?, ?)
                    """, (nombre, ruta))

                    conexion.commit()

                except sqlite3.IntegrityError:
                    camara.release()
                    cv2.destroyAllWindows()
                    mostrar_mensaje(ventana_registro, "Ese nombre ya está registrado", "red")
                    return

                cursor.execute("""
                SELECT id FROM docentes
                WHERE nombre = ?
                """, (nombre,))

                docente_id = cursor.fetchone()[0]

                for horario in horarios_temp:
                    cursor.execute("""
                    INSERT INTO horarios (
                        docente_id,
                        dia,
                        turno,
                        hora_inicio,
                        hora_fin,
                        horas_academicas
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        docente_id,
                        horario["dia"],
                        horario["turno"],
                        horario["inicio"],
                        horario["fin"],
                        horario["horas"]
                    ))

                conexion.commit()

                camara.release()
                cv2.destroyAllWindows()

                mostrar_mensaje(
                    ventana_registro,
                    "Docente registrado satisfactoriamente",
                    "green"
                )

                ventana_registro.after(3000, ventana_registro.destroy)
                return

        if tecla == 27:
            break

    camara.release()
    cv2.destroyAllWindows()


# =========================
# CÁLCULO DE TARDANZA Y EXTRA
# =========================

def calcular_tardanza_y_extra(nombre, hora_actual, tipo_registro):
    dias_semana = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"
    ]

    dia_actual = dias_semana[datetime.now().weekday()]

    cursor.execute("""
    SELECT hora_inicio, hora_fin
    FROM horarios
    INNER JOIN docentes
    ON horarios.docente_id = docentes.id
    WHERE docentes.nombre = ?
    AND horarios.dia = ?
    """, (nombre, dia_actual))

    horarios = cursor.fetchall()

    tardanza = 0
    extra = 0

    if len(horarios) == 0:
        return tardanza, extra

    hora_real = datetime.strptime(hora_actual, "%H:%M:%S")

    horario_cercano = None
    menor_diferencia = None

    for inicio, fin in horarios:

        if tipo_registro == "Entrada":
            hora_base = datetime.strptime(inicio, "%H:%M")
        else:
            hora_base = datetime.strptime(fin, "%H:%M")

        diferencia = abs((hora_real - hora_base).total_seconds())

        if menor_diferencia is None or diferencia < menor_diferencia:
            menor_diferencia = diferencia
            horario_cercano = (inicio, fin)

    inicio, fin = horario_cercano

    hora_inicio = datetime.strptime(inicio, "%H:%M")
    hora_fin = datetime.strptime(fin, "%H:%M")

    if tipo_registro == "Entrada":

        tolerancia = hora_inicio + timedelta(minutes=5)

        if hora_real > tolerancia:
            diferencia = hora_real - tolerancia
            tardanza = int(diferencia.total_seconds() / 60)

    elif tipo_registro == "Salida":

        if hora_real > hora_fin:
            diferencia = hora_real - hora_fin
            extra = int(diferencia.total_seconds() / 60)

    return tardanza, extra


# =========================
# EXTRA FUERA DE HORARIO
# =========================

def calcular_extra_fuera_de_horario(nombre, fecha_actual, hora_salida):
    cursor.execute("""
    SELECT hora
    FROM asistencias
    WHERE nombre = ?
    AND fecha = ?
    AND tipo = 'Entrada'
    ORDER BY id DESC
    LIMIT 1
    """, (nombre, fecha_actual))

    entrada = cursor.fetchone()

    if entrada is None:
        return 0

    hora_entrada = datetime.strptime(entrada[0], "%H:%M:%S")
    hora_salida_dt = datetime.strptime(hora_salida, "%H:%M:%S")

    diferencia = hora_salida_dt - hora_entrada
    minutos_trabajados = int(diferencia.total_seconds() / 60)

    if minutos_trabajados < 0:
        return 0

    dias_semana = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"
    ]

    dia_actual = dias_semana[datetime.now().weekday()]

    cursor.execute("""
    SELECT horarios.id
    FROM horarios
    INNER JOIN docentes
    ON horarios.docente_id = docentes.id
    WHERE docentes.nombre = ?
    AND horarios.dia = ?
    """, (nombre, dia_actual))

    horario = cursor.fetchone()

    if horario is None:
        return minutos_trabajados

    return 0


# =========================
# GUARDAR JORNADA
# =========================

def guardar_jornada(nombre, fecha, hora, tipo_registro, tardanza_minutos, extra_minutos):

    if tipo_registro == "Entrada":

        cursor.execute("""
        INSERT INTO jornadas (
            nombre,
            fecha,
            hora_entrada,
            tardanza_minutos,
            extra_minutos,
            estado
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            nombre,
            fecha,
            hora,
            tardanza_minutos,
            0,
            "Abierta"
        ))

        conexion.commit()

    elif tipo_registro == "Salida":

        cursor.execute("""
        SELECT id
        FROM jornadas
        WHERE nombre = ?
        AND fecha = ?
        AND estado = 'Abierta'
        ORDER BY id DESC
        LIMIT 1
        """, (
            nombre,
            fecha
        ))

        jornada = cursor.fetchone()

        if jornada is not None:

            jornada_id = jornada[0]

            cursor.execute("""
            UPDATE jornadas
            SET hora_salida = ?,
                extra_minutos = ?,
                estado = 'Cerrada'
            WHERE id = ?
            """, (
                hora,
                extra_minutos,
                jornada_id
            ))

            conexion.commit()


def reconocer_docente(tipo_registro):
    rostros_conocidos = []
    nombres_conocidos = []

    for archivo in os.listdir("faces"):
        if archivo.endswith(".jpg") or archivo.endswith(".png"):
            ruta = f"faces/{archivo}"
            imagen = face_recognition.load_image_file(ruta)
            codificaciones = face_recognition.face_encodings(imagen)

            if len(codificaciones) > 0:
                rostros_conocidos.append(codificaciones[0])
                nombres_conocidos.append(os.path.splitext(archivo)[0])

    if len(rostros_conocidos) == 0:
        label_estado.configure(text="No hay docentes registrados")
        return

    camara = abrir_camara()

    if camara is None:
        label_estado.configure(text="No se pudo abrir la cámara")
        return

    cv2.namedWindow("Reconocimiento Facial", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Reconocimiento Facial", cv2.WND_PROP_TOPMOST, 1)

    while True:
        resultado, frame = camara.read()

        if not resultado:
            label_estado.configure(text="No se pudo leer la cámara")
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        ubicaciones = face_recognition.face_locations(rgb)
        codificaciones = face_recognition.face_encodings(rgb, ubicaciones)

        for codificacion, ubicacion in zip(codificaciones, ubicaciones):
            coincidencias = face_recognition.compare_faces(
                rostros_conocidos,
                codificacion,
                tolerance=0.5
            )

            nombre = "Desconocido"

            if True in coincidencias:
                indice = coincidencias.index(True)
                nombre = nombres_conocidos[indice]

                ahora = datetime.now()
                fecha = ahora.strftime("%d/%m/%Y")
                hora = ahora.strftime("%H:%M:%S")

                cursor.execute("""
                SELECT tipo FROM asistencias
                WHERE nombre = ?
                AND fecha = ?
                ORDER BY id DESC
                LIMIT 1
                """, (nombre, fecha))

                ultimo_registro = cursor.fetchone()

                if ultimo_registro is not None and ultimo_registro[0] == tipo_registro:
                    label_estado.configure(
                        text=f"No se puede registrar otra {tipo_registro}"
                    )

                    camara.release()
                    cv2.destroyAllWindows()
                    return

                tardanza_minutos, extra_minutos = calcular_tardanza_y_extra(
                    nombre,
                    hora,
                    tipo_registro
                )

                if tipo_registro == "Salida":
                    extra_fuera = calcular_extra_fuera_de_horario(
                        nombre,
                        fecha,
                        hora
                    )

                    if extra_fuera > extra_minutos:
                        extra_minutos = extra_fuera

                cursor.execute("""
                INSERT INTO asistencias (
                    nombre,
                    fecha,
                    hora,
                    tipo,
                    tardanza_minutos,
                    extra_minutos
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    nombre,
                    fecha,
                    hora,
                    tipo_registro,
                    tardanza_minutos,
                    extra_minutos
                ))

                conexion.commit()

                guardar_jornada(
                    nombre,
                    fecha,
                    hora,
                    tipo_registro,
                    tardanza_minutos,
                    extra_minutos
                )

                label_estado.configure(
                    text=f"{tipo_registro} registrada: {nombre} | Tardanza: {tardanza_minutos} min | Extra: {extra_minutos} min"
                )

                top, right, bottom, left = ubicacion

                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 255, 0),
                    3
                )

                cv2.putText(
                    frame,
                    f"{tipo_registro}: {nombre}",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )

                cv2.imshow("Reconocimiento Facial", frame)
                cv2.waitKey(2000)

                camara.release()
                cv2.destroyAllWindows()

                return nombre

            top, right, bottom, left = ubicacion

            cv2.rectangle(
                frame,
                (left, top),
                (right, bottom),
                (0, 0, 255),
                3
            )

            cv2.putText(
                frame,
                nombre,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

        cv2.imshow("Reconocimiento Facial", frame)

        tecla = cv2.waitKey(1)

        if tecla == 27:
            break

    camara.release()
    cv2.destroyAllWindows()


def ver_asistencias():
    ventana = ctk.CTkToplevel(app)

    ventana.title("Registro de Asistencias")
    ventana.geometry("1000x550")
    ventana.attributes("-topmost", True)

    titulo = ctk.CTkLabel(
        ventana,
        text="Registro de Jornadas",
        font=("Arial", 24, "bold")
    )
    titulo.pack(pady=20)

    cursor.execute("""
    SELECT nombre, fecha, hora_entrada, hora_salida, tardanza_minutos, extra_minutos, estado
    FROM jornadas
    ORDER BY id DESC
    """)

    registros = cursor.fetchall()

    if len(registros) == 0:
        mensaje = ctk.CTkLabel(
            ventana,
            text="No hay jornadas registradas",
            font=("Arial", 16)
        )
        mensaje.pack(pady=20)
        return

    encabezado = ctk.CTkLabel(
        ventana,
        text="Docente | Fecha | Entrada | Salida | Tardanza | Extra | Estado",
        font=("Arial", 15, "bold")
    )
    encabezado.pack(pady=10)

    for nombre, fecha, entrada, salida, tardanza, extra, estado in registros:

        if salida is None:
            salida = "--:--"

        texto = f"{nombre} | {fecha} | {entrada} | {salida} | {tardanza} min | {extra} min | {estado}"

        fila = ctk.CTkLabel(
            ventana,
            text=texto,
            font=("Arial", 14)
        )
        fila.pack(pady=5)


def abrir_ventana_registro():
    ventana = ctk.CTkToplevel(app)

    ventana.attributes("-topmost", True)
    ventana.lift()
    ventana.focus_force()

    ventana.title("Registrar Docente")
    ventana.geometry("650x750")

    horarios_temp = []

    titulo_registro = ctk.CTkLabel(
        ventana,
        text="Registrar nuevo docente",
        font=("Arial", 22, "bold")
    )
    titulo_registro.pack(pady=15)

    entrada_nombre_registro = ctk.CTkEntry(
        ventana,
        placeholder_text="Nombre del docente",
        width=350,
        height=40
    )
    entrada_nombre_registro.pack(pady=10)

    dia_opcion = ctk.CTkOptionMenu(
        ventana,
        values=[
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado"
        ]
    )
    dia_opcion.pack(pady=8)

    turno_opcion = ctk.CTkOptionMenu(
        ventana,
        values=[
            "Mañana",
            "Tarde"
        ]
    )
    turno_opcion.pack(pady=8)

    entrada_inicio = ctk.CTkEntry(
        ventana,
        placeholder_text="Hora inicio 00:00",
        width=250
    )
    entrada_inicio.pack(pady=8)

    entrada_fin = ctk.CTkEntry(
        ventana,
        placeholder_text="Hora fin 00:00",
        width=250
    )
    entrada_fin.pack(pady=8)

    label_horas = ctk.CTkLabel(
        ventana,
        text="Horas académicas calculadas: 0h",
        font=("Arial", 14, "bold")
    )
    label_horas.pack(pady=8)

    lista_horarios = ctk.CTkLabel(
        ventana,
        text="Horarios agregados: ninguno",
        font=("Arial", 13),
        wraplength=550
    )
    lista_horarios.pack(pady=10)

    def agregar_horario():
        inicio = entrada_inicio.get().strip()
        fin = entrada_fin.get().strip()

        if inicio == "" or fin == "":
            label_horas.configure(
                text="Complete hora inicio y hora fin"
            )
            return

        try:
            hora_inicio = datetime.strptime(inicio, "%H:%M")
            hora_fin = datetime.strptime(fin, "%H:%M")

            diferencia = hora_fin - hora_inicio
            minutos = diferencia.total_seconds() / 60

            if minutos <= 0:
                label_horas.configure(
                    text="La hora fin debe ser mayor"
                )
                return

            horas_academicas = round(minutos / 45, 2)

        except ValueError:
            label_horas.configure(
                text="Formato inválido. Use 00:00"
            )
            return

        horario = {
            "dia": dia_opcion.get(),
            "turno": turno_opcion.get(),
            "inicio": inicio,
            "fin": fin,
            "horas": horas_academicas
        }

        horarios_temp.append(horario)

        label_horas.configure(
            text=f"Horas académicas calculadas: {horas_academicas}h"
        )

        texto = "\n".join([
            f"{h['dia']} | {h['turno']} | {h['inicio']} - {h['fin']} | {h['horas']}h"
            for h in horarios_temp
        ])

        lista_horarios.configure(text=texto)

        entrada_inicio.delete(0, "end")
        entrada_fin.delete(0, "end")

    btn_agregar_horario = ctk.CTkButton(
        ventana,
        text="Agregar Horario",
        width=220,
        height=40,
        command=agregar_horario
    )
    btn_agregar_horario.pack(pady=10)

    boton_capturar = ctk.CTkButton(
        ventana,
        text="Capturar rostro y guardar docente",
        width=280,
        height=45,
        command=lambda: registrar_docente_desde_ventana(
            entrada_nombre_registro.get(),
            ventana,
            horarios_temp
        )
    )
    boton_capturar.pack(pady=20)


app = ctk.CTk()

app.title("VitalFace")
app.geometry("900x650")

titulo = ctk.CTkLabel(
    app,
    text="VITALFACE",
    font=("Arial", 32, "bold")
)
titulo.pack(pady=20)

btn_registrar = ctk.CTkButton(
    app,
    text="Registrar Docente",
    width=250,
    height=50,
    command=abrir_ventana_registro
)
btn_registrar.pack(pady=15)

btn_entrada = ctk.CTkButton(
    app,
    text="Registrar Entrada",
    width=250,
    height=50,
    command=lambda: reconocer_docente("Entrada")
)
btn_entrada.pack(pady=15)

btn_salida = ctk.CTkButton(
    app,
    text="Registrar Salida",
    width=250,
    height=50,
    command=lambda: reconocer_docente("Salida")
)
btn_salida.pack(pady=15)

btn_asistencias = ctk.CTkButton(
    app,
    text="Ver Asistencias",
    width=250,
    height=50,
    command=ver_asistencias
)
btn_asistencias.pack(pady=15)

label_estado = ctk.CTkLabel(
    app,
    text="Sistema iniciado",
    font=("Arial", 18)
)
label_estado.pack(pady=20)

app.mainloop()
