from flask import Flask, render_template, request, redirect, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "clave_secreta_super_segura_123"

DATABASE = "database.db"
# =====================================================
#                     BASE DE DATOS
# =====================================================

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # -------- Tabla Productos --------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL NOT NULL,
            stock_actual INTEGER NOT NULL,
            stock_minimo INTEGER NOT NULL
        )
    """)

    # -------- Tabla Ventas --------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total REAL,
            ganancia REAL
        )
    """)

    # -------- Tabla Detalle Ventas --------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER,
            id_producto INTEGER,
            cantidad INTEGER,
            subtotal REAL,
            FOREIGN KEY (id_venta) REFERENCES ventas(id),
            FOREIGN KEY (id_producto) REFERENCES productos(id)
        )
    """)

    conn.commit()
    conn.close()


# =====================================================
#                         HOME
# =====================================================

@app.route("/")
def home():
    return render_template("index.html")


# =====================================================
#                     PRODUCTOS
# =====================================================

@app.route("/productos")
def ver_productos():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)


@app.route("/agregar_producto", methods=["POST"])
def agregar_producto():
    try:
        nombre = request.form["nombre"]
        precio = float(request.form["precio"])
        costo = float(request.form["costo"])
        stock_actual = int(request.form["stock_actual"])
        stock_minimo = int(request.form["stock_minimo"])

        if precio < 0 or costo < 0 or stock_actual < 0 or stock_minimo < 0:
            flash("No se permiten valores negativos.", "danger")
            return redirect("/productos")

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO productos (nombre, precio, costo, stock_actual, stock_minimo)
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, precio, costo, stock_actual, stock_minimo))
        conn.commit()
        conn.close()

        flash(f"Producto '{nombre}' agregado correctamente.", "success")
    except ValueError:
        flash("Datos inválidos, revisa los campos.", "danger")
    return redirect("/productos")


# =====================================================
#                       VENTAS
# =====================================================

@app.route("/ventas")
def ventas():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return render_template("ventas.html", productos=productos)


@app.route("/registrar_venta", methods=["POST"])
def registrar_venta():
    try:
        id_producto = int(request.form["id_producto"])
        cantidad = int(request.form["cantidad"])

        if cantidad <= 0:
            flash("La cantidad debe ser mayor a cero.", "danger")
            return redirect("/ventas")

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nombre, precio, costo, stock_actual FROM productos WHERE id = ?",
            (id_producto,)
        )
        producto = cursor.fetchone()

        if not producto:
            conn.close()
            flash("Producto no encontrado.", "danger")
            return redirect("/ventas")

        nombre, precio, costo, stock_actual = producto

        if cantidad > stock_actual:
            conn.close()
            flash("Stock insuficiente.", "danger")
            return redirect("/ventas")

        subtotal = precio * cantidad
        ganancia = (precio - costo) * cantidad

        # Insertar venta
        cursor.execute(
            "INSERT INTO ventas (total, ganancia) VALUES (?, ?)",
            (subtotal, ganancia)
        )
        id_venta = cursor.lastrowid

        # Insertar detalle
        cursor.execute("""
            INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, subtotal)
            VALUES (?, ?, ?, ?)
        """, (id_venta, id_producto, cantidad, subtotal))

        # Actualizar stock
        nuevo_stock = stock_actual - cantidad
        cursor.execute(
            "UPDATE productos SET stock_actual = ? WHERE id = ?",
            (nuevo_stock, id_producto)
        )

        conn.commit()
        conn.close()

        flash(f"Venta de '{nombre}' registrada correctamente.", "success")
    except ValueError:
        flash("Datos inválidos, revisa los campos.", "danger")

    return redirect("/ventas")

# =====================================================
#                       REPORTES
# =====================================================

@app.route("/reportes")
def reportes():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Total facturado
    cursor.execute("SELECT SUM(total) FROM ventas")
    total_facturado = cursor.fetchone()[0] or 0

    # Cantidad de ventas
    cursor.execute("SELECT COUNT(*) FROM ventas")
    cantidad_ventas = cursor.fetchone()[0]

    # Ganancia total
    cursor.execute("SELECT SUM(ganancia) FROM ventas")
    ganancia_total = cursor.fetchone()[0] or 0

    # Producto más vendido
    cursor.execute("""
        SELECT p.nombre, SUM(d.cantidad) AS total_vendido
        FROM detalle_ventas d
        JOIN productos p ON d.id_producto = p.id
        GROUP BY p.nombre
        ORDER BY total_vendido DESC
        LIMIT 1
    """)
    producto_top = cursor.fetchone()

    # Producto más rentable
    cursor.execute("""
        SELECT p.nombre,
               SUM((p.precio - p.costo) * d.cantidad) AS ganancia_producto
        FROM detalle_ventas d
        JOIN productos p ON d.id_producto = p.id
        GROUP BY p.nombre
        ORDER BY ganancia_producto DESC
        LIMIT 1
    """)
    producto_rentable = cursor.fetchone()

    # Datos para gráfico
    cursor.execute("""
        SELECT p.nombre, SUM(d.cantidad)
        FROM detalle_ventas d
        JOIN productos p ON d.id_producto = p.id
        GROUP BY p.nombre
    """)
    ventas_por_producto = cursor.fetchall()

    conn.close()

    return render_template(
        "reportes.html",
        total_facturado=total_facturado,
        cantidad_ventas=cantidad_ventas,
        ganancia_total=ganancia_total,
        producto_top=producto_top,
        producto_rentable=producto_rentable,
        ventas_por_producto=ventas_por_producto
    )
# =====================================================
#                  HISTORIAL DE VENTAS
# =====================================================

@app.route("/historial")
def historial():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.fecha,
               p.nombre,
               d.cantidad,
               d.subtotal,
               (p.precio - p.costo) * d.cantidad AS ganancia
        FROM detalle_ventas d
        JOIN ventas v ON d.id_venta = v.id
        JOIN productos p ON d.id_producto = p.id
        ORDER BY v.fecha DESC
    """)

    historial = cursor.fetchall()
    conn.close()

    return render_template("historial.html", historial=historial)

# =====================================================
#                       MAIN
# =====================================================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)