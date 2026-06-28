# CSVMapper

Aplicación de escritorio (Windows / Linux / Mac) para mapear registros de un CSV de trabajo contra una tabla de referencia, con autocompletado dinámico multi-término.

---

## Instalación

```bash
pip install -r requirements.txt
python main.py
```

**Requisitos:** Python 3.11+ · PySide6 >= 6.5 · chardet >= 5.0

---

## Estructura del proyecto

```
csvmapper/
├── main.py                          ← Punto de entrada
├── requirements.txt
├── sample_referencia.csv            ← Datos de ejemplo
├── sample_trabajo.csv
│
├── core/                            ← Lógica pura, sin UI
│   ├── csv_loader.py                ← Lectura/escritura CSV (auto-encoding, auto-delimitador)
│   ├── config_manager.py            ← Persistencia de sesión con QSettings
│   └── theme.py                     ← Paletas claro/oscuro
│
├── ui/                              ← Ventanas y pestañas
│   ├── main_window.py               ← Ventana principal, toggle de tema, sesión
│   ├── work_tab.py                  ← Pestaña de Trabajo
│   └── ref_tab.py                   ← Pestaña de Referencia
│
└── widgets/                         ← Componentes reutilizables
    ├── autocomplete_delegate.py     ← Delegate + popup de búsqueda
    ├── import_dialog.py             ← Asistente de importación CSV
    └── export_dialog.py             ← Asistente de exportación CSV
```

---

## Flujo de trabajo

### 1. Pestaña Referencia

- Abrí tu archivo maestro (lista de productos, clientes, etc.)
- El **asistente de importación** detecta automáticamente el encoding y el separador; podés ajustarlo y ver una preview antes de confirmar
- Elegí qué columna es el **ID** (se copiará al archivo de trabajo)
- Tildá los **campos para buscar** — la búsqueda opera solo sobre esos campos
- Tildá las **columnas a copiar al trabajo** — al seleccionar un registro, esos valores se copian automáticamente a las columnas correspondientes del archivo de trabajo
- Activá **"Solo copiar el ID"** si no necesitás columnas extra

Cada grupo de checkboxes tiene botones **Todos / Ninguno / Invertir**.

### 2. Pestaña Trabajo

- Abrí el CSV que querés enriquecer (cualquier cantidad de columnas, cualquier separador)
- La tabla agrega dos columnas al final:
  - 🟡 **Coincidencia** — donde escribís para buscar
  - 🟢 **ID Referencia** — se rellena automáticamente al seleccionar

#### Búsqueda con autocompletado

- Doble clic (o F2) en la columna **Coincidencia** para activar el editor
- Escribí cualquier parte de cualquier palabra — la búsqueda es **multi-término**: `anca aña` encuentra `Azúcar blanca | Azúcar refinada de caña`
- El popup muestra todos los campos del registro de referencia
- Navegación: `↓ / ↑` para moverse, `Enter` para seleccionar, `Esc` para cerrar, clic directo también funciona
- Al confirmar: se rellena **Coincidencia**, **ID Referencia**, y las columnas extra tildadas en Referencia
- El cursor avanza automáticamente a la siguiente fila, lista para escribir

#### Modo edición

- **Solo mapeo** (por defecto): solo se pueden editar las columnas Coincidencia e ID. Los datos originales no se tocan.
- **Edición libre**: cualquier celda es editable + botones para agregar filas y columnas.

#### Ordenar

Clic en cualquier encabezado de columna para ordenar ascendente / descendente.

### 3. Exportar

El botón **💾 Exportar** abre el asistente de exportación:

- Seleccioná qué **columnas** incluir (checkboxes con Todos / Ninguno / Invertir)
- Elegí el **separador de salida**: coma, punto y coma, tab, pipe, o personalizado
- Opción **entrecomillar cada campo**
- Opción **exportar solo filas con coincidencia o modificación**
- El archivo se guarda en UTF-8 con BOM (compatible con Excel)

---

## Características generales

| Feature | Detalle |
|---|---|
| Formatos de entrada | CSV, TSV, TXT — detección automática de encoding y delimitador |
| Separadores soportados | `,` `;` `\t` `\|` y personalizado; con o sin comillas en los campos |
| Primera fila | Configurable: encabezado o dato |
| Múltiples archivos | Varios archivos abiertos a la vez en cada pestaña |
| Sesión persistente | Se guarda automáticamente cada 30 s y al cerrar |
| Archivos grandes | Límite de 200.000 filas con aviso; exportación por chunks |
| Tema | Claro / Oscuro, persiste entre sesiones |
| Teclado | Navegación completa sin mouse |

---

## Archivos de ejemplo

| Archivo | Descripción |
|---|---|
| `sample_referencia.csv` | 8 productos con ID, Nombre, Descripción, Categoría |
| `sample_trabajo.csv` | 5 pedidos sin mapear |

**Prueba rápida:**
1. Abrí `sample_referencia.csv` en la pestaña Referencia → ID = `ID`, buscar en `Nombre`
2. Abrí `sample_trabajo.csv` en la pestaña Trabajo
3. Doble clic en la columna Coincidencia de la primera fila → escribí `azu` → seleccioná con Enter o clic
