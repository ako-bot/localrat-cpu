# localrat-cpu

**Navegación de código sin gastar tokens para agentes de programación.** Un servidor MCP con dos herramientas que permiten a un agente (Claude Code, Cursor, Codex…) encontrar código sin leer archivos enteros. Funciona solo con CPU y la biblioteca estándar de Python: sin modelo, sin índice y sin gastar tokens en cada consulta.

[Read in English](README.md)

## Para qué sirve

Cada archivo que abre un agente cuesta tokens. La mayoría de las lecturas exploratorias solo sirven para responder «¿dónde está X?» o «¿qué hay en este archivo?». `find` y `outline` responden a eso con unas pocas líneas, y así el agente lee solo el trozo que necesita.

## Herramientas

### `find`
Busca texto o una expresión regular en el repo. Devuelve `ruta:línea: texto`.

| Parámetro | Por defecto | Significado |
|---|---|---|
| `query` | — | Texto (o regex) que se busca |
| `root` | `.` | Carpeta donde buscar |
| `glob` | `*` | Filtro de archivos, p. ej. `*.py` |
| `regex` | `false` | Interpretar `query` como expresión regular |
| `context` | `0` | Líneas de contexto alrededor de cada acierto |
| `max_hits` | `30` | Límite de resultados |
| `case` | `smart` | `smart` (no distingue mayúsculas salvo que la búsqueda tenga alguna), `sensitive` o `insensitive` |
| `word` | `false` | Solo palabras completas |

Dentro de un repo git se saltan los archivos ignorados por `.gitignore`. Las carpetas típicas de dependencias y compilación (`node_modules`, `.venv`, `dist`…) se saltan siempre.

### `outline`
Estructura de un archivo con números de línea.

- **Python**: funciones y clases con rango `inicio-fin` (desde el primer decorador) y métodos anidados. Usa `ast`.
- **JS/TS**: funciones, clases, funciones flecha y `export default`.
- **Shell / PowerShell**: definiciones de funciones (los comentarios no se listan).
- **Markdown**: encabezados (ignorando los bloques de código).

## Instalación

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/ako-bot/localrat-cpu.git
cd localrat-cpu
pip install -r requirements.txt
```

Registrarlo en Claude Code:

```bash
claude mcp add localrat-cpu -- python /ruta/absoluta/a/localrat-cpu/server.py
```

Y añade una línea así a tu `CLAUDE.md` para que el agente lo use de verdad:

```
Para localizar código, usa las herramientas MCP `find` (ruta:línea) y `outline` (funciones con rangos de líneas) antes de abrir archivos; lee solo los rangos que necesites.
```

## Límites

- Solo busca en archivos con extensiones de texto habituales (`.py`, `.js`, `.ts`, `.md`, `.json`, `.toml`, `.yml`, `.sh`, `.ps1`…); se saltan los de más de 1 MB.
- Fuera de Python, `outline` usa expresiones regulares: suficiente para navegar, pero no es un analizador completo y no da la línea final.
- La búsqueda es Python puro. Va bien en repos pequeños y medianos; en monorepos muy grandes `ripgrep` será más rápido.

## Tests

```bash
python -m unittest discover tests
```

## Licencia

MIT
