import customtkinter as ctk
import cv2
import face_recognition
import os
import sqlite3
from datetime import datetime

# =========================
# CONFIGURACIÓN VISUAL
# =========================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# =========================
# DETECTOR FACIAL
# =========================

detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# =========================
# BASE DE DATOS
# =========================

conexion = sqlite3.connect("database/vitalhuella.db")
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    fecha TEXT,
    hora TEXT,
    tipo TEXT
)
""")

conexion.commit()

# =========================
# FUNCIÓN REGISTRAR DOCENTE
# =========================

def registrar_docente_desde_ventana(nombre, ventana_registro):

    nombre = nombre.strip()

    if nombre == "":
        label_error = ctk.CTkLabel(
            ventana_registro,
            text="Ingrese un nombre válido",
            text_color="red",
            font=("Arial", 16, "bold")
        )
        label_error.pack(pady=10)
        return

    camara = cv2.VideoCapture(0)

    cv2.namedWindow("Registro Docente", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Registro Docente", cv2.WND_PROP_TOPMOST, 1)

    while True:

        resultado, frame = camara.read()

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
                    label_error = ctk.CTkLabel(
                        ventana_registro,
                        text="No se pudo codificar el rostro",
                        text_color="red",
                        font=("Arial", 16, "bold")
                    )
                    label_error.pack(pady=10)

                    camara.release()
                    cv2.destroyAllWindows()
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

                                label_error = ctk.CTkLabel(
                                    ventana_registro,
                                    text=f"Este rostro ya está registrado como {nombre_existente}",
                                    text_color="red",
                                    font=("Arial", 15, "bold"),
                                    wraplength=420
                                    
                                )
                                label_error.pack(pady=10)

                                return

                ruta = f"faces/{nombre}.jpg"

                cv2.imwrite(ruta, rostro)

                print(f"Docente {nombre} registrado")

                camara.release()
                cv2.destroyAllWindows()

                label_exito = ctk.CTkLabel(
                    ventana_registro,
                    text="Rostro capturado satisfactoriamente",
                    text_color="green",
                    font=("Arial", 16, "bold")
                )

                label_exito.pack(pady=10)

                ventana_registro.after(
                    3000,
                    ventana_registro.destroy
                )

                return

        if tecla == 27:
            break

    camara.release()
    cv2.destroyAllWindows()



# =========================
# FUNCIÓN RECONOCER DOCENTE
# =========================

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
        print("No hay docentes registrados")
        return

    camara = cv2.VideoCapture(0)

    while True:

        resultado, frame = camara.read()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        ubicaciones = face_recognition.face_locations(rgb)

        codificaciones = face_recognition.face_encodings(
            rgb,
            ubicaciones
        )

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

                label_estado.configure(
                text=f"Docente reconocido: {nombre}"
                 )

                ahora = datetime.now()
                fecha = ahora.strftime("%d/%m/%Y")
                hora = ahora.strftime("%H:%M:%S")

                cursor.execute("""
                SELECT tipo FROM asistencias
                WHERE nombre = ?
                ORDER BY id DESC
                LIMIT 1
                """, (nombre,))

                ultimo_registro = cursor.fetchone()

                if ultimo_registro is not None and ultimo_registro[0] == tipo_registro:

                    label_estado.configure(
                    text=f"No se puede registrar otra {tipo_registro}"
                    )

                    camara.release()
                    cv2.destroyAllWindows()

                    return

                cursor.execute("""
                INSERT INTO asistencias (
                    nombre,
                    fecha,
                    hora,
                    tipo
                )
                VALUES (?, ?, ?, ?)
                """, (nombre, fecha, hora, tipo_registro))

                conexion.commit()

                label_estado.configure(
                text=f"{tipo_registro} registrada: {nombre}"
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

    # =========================
# FUNCIÓN VER ASISTENCIAS
# =========================

def ver_asistencias():

    ventana = ctk.CTkToplevel(app)

    ventana.title("Registro de Asistencias")

    ventana.geometry("650x500")

    ventana.attributes("-topmost", True)

    titulo = ctk.CTkLabel(
        ventana,
        text="Registro de Asistencias",
        font=("Arial", 24, "bold")
    )

    titulo.pack(pady=20)

    cursor.execute("""

    SELECT nombre, fecha, hora, tipo
    FROM asistencias
    ORDER BY id DESC

    """)

    registros = cursor.fetchall()

    if len(registros) == 0:

        mensaje = ctk.CTkLabel(
            ventana,
            text="No hay asistencias registradas",
            font=("Arial", 16)
        )

        mensaje.pack(pady=20)

        return

    for nombre, fecha, hora, tipo in registros:

        texto = f"{nombre} | {fecha} | {hora} | {tipo}"

        fila = ctk.CTkLabel(
            ventana,
            text=texto,
            font=("Arial", 14)
        )

        fila.pack(pady=5)

# =========================
# VENTANA PRINCIPAL
# =========================

app = ctk.CTk()
app.title("VitalHuella")
app.geometry("900x600")

titulo = ctk.CTkLabel(
    app,
    text="VITALHUELLA",
    font=("Arial", 32, "bold")
)

titulo.pack(pady=20)

def abrir_ventana_registro():

    ventana = ctk.CTkToplevel(app)

    ventana.attributes("-topmost", True)

    ventana.lift()

    ventana.focus_force()

    ventana.title("Registrar Docente")

    ventana.geometry("500x380")

    titulo_registro = ctk.CTkLabel(
        ventana,
        text="Registrar nuevo docente",
        font=("Arial", 22, "bold")
    )

    titulo_registro.pack(pady=20)

    entrada_nombre_registro = ctk.CTkEntry(
        ventana,
        placeholder_text="Ingrese nombre del docente",
        width=300,
        height=40
    )

    entrada_nombre_registro.pack(pady=15)

    boton_capturar = ctk.CTkButton(
        ventana,
        text="Capturar rostro",
        width=220,
        height=45,
        command=lambda: registrar_docente_desde_ventana(
            entrada_nombre_registro.get(),
            ventana
        )
    )

    boton_capturar.pack(pady=20)


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
# =========================
# MENSAJES DEL SISTEMA
# =========================

label_estado = ctk.CTkLabel(
    app,
    text="Sistema iniciado",
    font=("Arial", 18)
)

label_estado.pack(pady=20)

app.mainloop()