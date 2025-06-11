from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import numpy as np
import tensorflow as tf
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'


modelo = tf.keras.models.load_model('modelo_entrenado_final.h5')

def get_db_connection():
    return psycopg2.connect(os.getenv('DATABASE_URL'))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, tipo 
            FROM usuarios 
            WHERE username = %s AND password = %s
        """, (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['logged_in'] = True
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['user_type'] = user[2]
            flash('Inicio de sesión exitoso', 'success')
            
            # Redirigir según tipo de usuario
            if user[2] == 'medico':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

# Ruta de registro mejorada
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        fecha_nacimiento = request.form.get('fecha_nacimiento')
        genero = request.form.get('genero')
        telefono = request.form.get('telefono')
        direccion = request.form.get('direccion')
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Insertar usuario
            cur.execute("""
                INSERT INTO usuarios (username, password)
                VALUES (%s, %s)
                RETURNING id
            """, (username, password))
            
            usuario_id = cur.fetchone()[0]
            
            # Insertar paciente con todos los datos
            cur.execute("""
                INSERT INTO pacientes (
                    usuario_id, nombre, apellido, fecha_nacimiento, 
                    genero, telefono, direccion
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                usuario_id, nombre, apellido, fecha_nacimiento,
                genero, telefono, direccion
            ))
            
            conn.commit()
            flash('Registro exitoso. Ahora puede iniciar sesión.', 'success')
            return redirect(url_for('login'))
            
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('El nombre de usuario ya existe', 'error')
        except Exception as e:
            conn.rollback()
            flash(f'Error en el registro: {str(e)}', 'error')
        finally:
            cur.close()
            conn.close()
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/diagnostico', methods=['GET', 'POST'])
def diagnostico():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario (todos los campos que necesitas)
            edad = int(request.form['edad'])
            genero = request.form['genero']
            ps = int(request.form['ps'])
            pd = int(request.form['pd'])
            col = float(request.form['colesterol'])
            glu = float(request.form['glucosa'])
            fuma = request.form['fuma']
            alcohol = request.form['alcohol']
            actividad = request.form['actividad']
            peso = float(request.form['peso'])
            estatura = int(request.form['estatura'])

            # Calcular IMC (igual que en tu código)
            imc = peso / ((estatura / 100) ** 2)

            # Transformar a vectores de entrada (EXACTAMENTE IGUAL QUE TU VERSIÓN)
            entrada = [
                0 if edad < 45 else 1 if edad <= 59 else 2,
                0 if 'femenino' in genero.lower() else 1,
                0 if ps < 120 else 1 if ps <= 139 else 2,
                0 if pd < 80 else 1 if pd <= 89 else 2,
                0 if col < 200 else 1 if col <= 239 else 2,
                0 if glu < 100 else 1 if glu <= 125 else 2,
                1 if fuma == 's' else 0,
                1 if alcohol == 's' else 0,
                2 if 'no' in actividad.lower() else 1 if '1' in actividad or '2' in actividad else 0,
                1 if imc == 0 else 1 if imc < 18.5 else 0 if imc < 25 else 1 if imc < 30 else 2
            ]

            # Convertir a array NumPy
            input_array = np.array([entrada], dtype=np.float32)

            # Predicción (igual que tu versión)
            pred = modelo.predict(input_array)[0]

            # Obtener clase y confianza
            riesgo = int(np.argmax(pred))
            confianza = float(np.max(pred))

            # Mapa de descripción
            mapa_riesgo = {0: "Bajo", 1: "Medio", 2: "Alto"}

            # Guardar en base de datos (versión simple)
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO diagnosticos (
                        edad, genero, ps, pd, colesterol, glucosa, fuma, 
                        alcohol, actividad, imc, riesgo, confianza
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    edad, genero, ps, pd, col, glu, fuma, 
                    alcohol, actividad, imc, riesgo, confianza
                ))
                conn.commit()
            except Exception as e:
                print(f"Error al guardar en BD: {str(e)}")
            finally:
                cur.close()
                conn.close()

            # Mostrar resultados
            return jsonify({
                'riesgo': riesgo,
                'confianza': round(confianza * 100, 2),
                'descripcion': f"Riesgo {mapa_riesgo[riesgo]}"
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    return render_template('diagnostico.html')
@app.route('/noticias')
def noticias():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('noticias.html')

@app.route('/admin')
def admin_panel():
    if not session.get('logged_in') or session.get('user_type') != 'medico':
        flash('Acceso no autorizado', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Obtener todos los pacientes con sus diagnósticos
    cur.execute("""
        SELECT p.id, u.username, p.nombre, p.apellido, 
               COUNT(d.id) as total_diagnosticos,
               MAX(d.fecha_diagnostico) as ultimo_diagnostico
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        LEFT JOIN diagnosticos d ON p.id = d.paciente_id
        GROUP BY p.id, u.username, p.nombre, p.apellido
        ORDER BY p.nombre
    """)
    pacientes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('admin_panel.html', pacientes=pacientes)

# Ruta para ver diagnósticos de un paciente específico
@app.route('/admin/diagnosticos/<int:paciente_id>')
def ver_diagnosticos(paciente_id):
    if not session.get('logged_in') or session.get('user_type') != 'medico':
        flash('Acceso no autorizado', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Obtener información del paciente
    cur.execute("""
        SELECT p.*, u.username 
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.id = %s
    """, (paciente_id,))
    paciente = cur.fetchone()
    
    # Obtener sus diagnósticos
    cur.execute("""
        SELECT d.*, u.username as medico_nombre
        FROM diagnosticos d
        JOIN usuarios u ON d.medico_id = u.id
        WHERE d.paciente_id = %s
        ORDER BY d.fecha_diagnostico DESC
    """, (paciente_id,))
    diagnosticos = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('diagnosticos_paciente.html', 
                         paciente=paciente, 
                         diagnosticos=diagnosticos)

@app.route('/configuracion', methods=['GET', 'POST'])
def configuracion():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form['email']
        flash('Configuración actualizada (simulado)', 'success')
    
    return render_template('configuracion.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
