# CSVMapper

Aplicación de escritorio (Windows/Linux/Mac) para mapear registros de un CSV de trabajo contra una tabla de referencia, con autocompletado dinámico.

## Estructura del proyecto

```
csvmapper/
├── main.py                  ← Punto de entrada
├── ui_main.py               ← Ventana principal + pestañas
├── work_tab.py              ← Pestaña "Trabajo"
├── ref_tab.py               ← Pestaña "Referencia"
├── autocomplete_delegate.py ← Lógica de autocompletado
├── csv_loader.py            ← Lectura/escritura de archivos
├── config_manager.py        ← Persistencia de sesión (QSettings)
└── requirements.txt
```

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

### Flujo típico

1. **Pestaña Referencia**  
   - Abrí tu CSV maestro (ej. lista de clientes, productos, etc.)  
   - Elegí qué columna es el **ID** y qué columna contiene el **texto a buscar**

2. **Pestaña Trabajo**  
   - Abrí el CSV que querés enriquecer  
   - En la columna **Coincidencia** (anteúltima, amarilla), tipea cualquier parte de cualquier palabra de la referencia  
   - Seleccioná con Enter o clic el registro que querés  
   - La columna **ID Referencia** (última, verde) se rellena automáticamente

3. **Exportar**: botón "💾 Exportar CSV" → guarda el archivo completo con las columnas nuevas

### Características

- Soporte CSV, TSV y TXT (detección automática de encoding y delimitador)
- Múltiples archivos abiertos simultáneamente en cada pestaña
- La sesión se guarda automáticamente cada 30 segundos y al cerrar
- Búsqueda fuzzy: encuentra coincidencias en cualquier campo del registro de referencia
- Navegación con teclado en el popup (↓ para bajar, Enter para seleccionar, Esc para cerrar)
