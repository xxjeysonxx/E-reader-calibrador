# calibrador.py

Herramienta de línea de comandos para **inspeccionar y reparar el bloque de
calibración del Nintendo e-Reader+** dentro de archivos `.sav` (dump de
128KB de la flash del e-Reader+).

Si tu e-Reader+ da **error al intentar escanear tarjetas**, puede deberse a
que el bloque de calibración de su flash quedó vacío (todo `0xFF`) —por
ejemplo, si nunca completó su primer proceso de calibración, o si ese
sector se perdió al hacer el dump. Este script te permite diagnosticarlo y
trasplantar la calibración desde otro `.sav` que sí la tenga.

## ¿Cómo se descubrió esto?

Comparando byte a byte un dump real de un e-Reader+ (con error de escaneo)
contra un `.sav` sano generado en mGBA, se encontró que ambos difieren
únicamente en dos bloques idénticos de 96 bytes, en los offsets `0xD000` y
`0xE000` (duplicados por redundancia). En el `.sav` sano ese bloque
contiene:

- El texto `"Card-E Reader 2001"` (nombre de producto)
- Un código numérico ofuscado (posible serie/calibración)
- Una cola de bytes binarios (posible checksum/valores de calibración)

En el `.sav` con error, ese mismo bloque estaba completamente vacío
(`0xFF`) en ambas copias.

No se conoce documentación oficial que describa este bloque campo por
campo — esto es una conclusión obtenida por ingeniería inversa comparando
archivos, no un dato confirmado por Nintendo ni por la escena de
homebrew del e-Reader.

## Requisitos

- Python 3.7 o superior (sin dependencias externas)

## Instalación

Solo descarga `calibrador.py`, no requiere instalación:

```bash
git clone https://github.com/tu-usuario/tu-repo.git
cd tu-repo
python3 calibrador.py -help
```

## Uso

### Ver la ayuda completa

```bash
python3 calibrador.py -help
```

También responde a `--help`, `/?`, `-?`, `-h` y `help`.

### Inspeccionar un `.sav`

Revisa si el bloque de calibración está presente o vacío, sin modificar
el archivo:

```bash
python3 calibrador.py inspect mi_dump.sav
python3 calibrador.py inspect mi_dump.sav /verbose
```

Salida de ejemplo:

```
Archivo: mi_dump.sav
Tamano:  131072 bytes
Bloques de calibracion:
  0xD000 [VACIO (0xFF)]
  0xE000 [VACIO (0xFF)]

[RESULTADO] Sin calibracion: ambas copias estan vacias (0xFF).
            Esto suele causar error al escanear tarjetas.
```

### Parchear la calibración

Copia el bloque de calibración de un `.sav` sano (`--source`) hacia uno
sin calibrar (`--target`), y guarda el resultado en un archivo nuevo sin
tocar los originales:

```bash
python3 calibrador.py patch --source sano.sav --target roto.sav --output resultado.sav
```

O con la sintaxis estilo MS-DOS, si la prefieres:

```bash
python3 calibrador.py patch /source:sano.sav /target:roto.sav /output:resultado.sav
```

Si `--output` / `/output` se omite, se genera automáticamente
`<target>_patched.sav` junto al archivo target.

Si el `.sav` destino ya tiene datos distintos de `0xFF` en ese bloque, el
script se detiene para evitar sobreescribir algo por accidente. Para
forzarlo de todas formas:

```bash
python3 calibrador.py patch --source sano.sav --target roto.sav --output resultado.sav --force
```

Agrega `--verbose` / `/verbose` a cualquier comando para ver los bytes en
hexadecimal, además del texto legible.

## Parámetros de `patch`

| Parámetro           | Obligatorio | Descripción                                                                 |
|----------------------|:-----------:|------------------------------------------------------------------------------|
| `--source` / `/source:` | Sí | `.sav` que sí tiene la calibración válida (ej: uno generado por mGBA que escanea bien) |
| `--target` / `/target:` | Sí | `.sav` al que le falta la calibración (ej: tu dump real del e-Reader+ físico) |
| `--output` / `/output:` | No | Ruta del `.sav` parcheado de salida. Por defecto: `<target>_patched.sav` |
| `--force` / `/force`   | No | Sobreescribe la calibración del target aunque ya tenga datos distintos de `0xFF` |
| `--verbose` / `/verbose` | No | Muestra los bytes en hexadecimal, además del texto legible |

## Cómo probar el resultado

1. Genera el `.sav` parcheado con el comando `patch`.
2. Renómbralo exactamente igual al `.sav` que ya usa tu ROM del e-Reader+
   en tu emulador (por ejemplo mGBA), reemplazando al original.
3. Carga la ROM del e-Reader+ y prueba escanear una tarjeta.

## Advertencias

- Esto se probó y confirmó funcional en un caso real, pero el bloque no
  está documentado oficialmente — úsalo bajo tu propio riesgo.
- El script nunca modifica los archivos `--source` / `--target` originales,
  siempre escribe en un archivo de salida distinto.
- El código numérico dentro del bloque de calibración podría estar
  asociado a la unidad física específica que lo generó. Si tu e-Reader+
  sigue sin escanear después de parchear, es posible que necesites la
  calibración de tu propia unidad y no la de un `.sav` genérico.

## Licencia

MIT (o la que prefieras usar en tu repo).
