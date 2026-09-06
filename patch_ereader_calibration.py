#!/usr/bin/env python3
"""
ereader_calibration_tool.py

Herramienta para inspeccionar y reparar el bloque de calibracion del
e-Reader+ dentro de archivos .sav (dump de 128KB de la flash del e-Reader+).

El bloque de calibracion vive en dos copias identicas (redundancia),
en los offsets 0xD000 y 0xE000, 96 bytes cada una. Contiene:
  - Nombre de producto: "Card-E Reader 2001"
  - Un codigo numerico ofuscado (posible serie/calibracion)
  - Una cola binaria con lo que parecen ser checksum/valores de calibracion

Si ese bloque esta vacio (todo 0xFF) en un e-Reader+ real, el BIOS no
puede validar el sensor y falla al escanear tarjetas.

------------------------------------------------------------------
COMANDOS
------------------------------------------------------------------
  inspect   Muestra el estado del bloque de calibracion de un .sav
  patch     Copia el bloque de calibracion de un .sav sano hacia otro

------------------------------------------------------------------
EJEMPLOS
------------------------------------------------------------------
  # Ver ayuda general
  python3 ereader_calibration_tool.py --help

  # Ver ayuda de un subcomando especifico
  python3 ereader_calibration_tool.py patch --help
  python3 ereader_calibration_tool.py inspect --help

  # Inspeccionar un .sav (ver si tiene calibracion o esta vacio)
  python3 ereader_calibration_tool.py inspect mi_dump.sav

  # Parchear un .sav sin calibracion usando uno que si la tiene
  python3 ereader_calibration_tool.py patch \\
      --source CARDEREADER___PSAJ01_.sav \\
      --target mi_dump.sav \\
      --output mi_dump_patched.sav

  # Forzar sobreescritura aunque el target ya tenga datos distintos
  python3 ereader_calibration_tool.py patch \\
      --source sano.sav --target roto.sav --output resultado.sav --force

  # Ver mas detalle (bytes crudos) al inspeccionar o parchear
  python3 ereader_calibration_tool.py inspect mi_dump.sav --verbose
"""

import argparse
import sys
from pathlib import Path

# Offsets y tamano del bloque de calibracion (encontrados comparando
# un .sav sano contra uno con la calibracion borrada).
CAL_OFFSETS = [0xD000, 0xE000]
CAL_LENGTH = 0x60  # 96 bytes

EXPECTED_SAV_SIZE = 128 * 1024  # 131072 bytes = flash del e-Reader+


# ----------------------------------------------------------------------
# Utilidades comunes
# ----------------------------------------------------------------------

def read_sav(path: Path, quiet: bool = False) -> bytearray:
    if not path.exists():
        sys.exit(f"[ERROR] No existe el archivo: {path}")
    data = bytearray(path.read_bytes())
    if len(data) != EXPECTED_SAV_SIZE and not quiet:
        print(
            f"[!] Aviso: {path.name} mide {len(data)} bytes, "
            f"se esperaban {EXPECTED_SAV_SIZE} (128KB). Continuo de todos modos.",
            file=sys.stderr,
        )
    return data


def extract_calibration(data: bytes) -> dict:
    """Devuelve {offset: bytes} para cada copia del bloque de calibracion."""
    return {off: bytes(data[off:off + CAL_LENGTH]) for off in CAL_OFFSETS}


def is_blank(block: bytes) -> bool:
    return all(b == 0xFF for b in block)


def describe_block(block: bytes) -> str:
    """Intenta extraer el texto legible del bloque para mostrarlo."""
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in block)
    return text


def print_block(offset: int, block: bytes, verbose: bool) -> None:
    status = "VACIO (0xFF)" if is_blank(block) else "con datos"
    print(f"  0x{offset:04X} [{status}]")
    if not is_blank(block) or verbose:
        if verbose:
            print(f"    hex : {block.hex()}")
        print(f"    text: {describe_block(block)}")


# ----------------------------------------------------------------------
# Comando: inspect
# ----------------------------------------------------------------------

def cmd_inspect(args: argparse.Namespace) -> None:
    data = read_sav(args.file)
    blocks = extract_calibration(data)

    print(f"Archivo: {args.file}")
    print(f"Tamano:  {len(data)} bytes")
    print("Bloques de calibracion:")
    for off, block in blocks.items():
        print_block(off, block, args.verbose)

    values = list(blocks.values())
    if all(is_blank(v) for v in values):
        print("\n[RESULTADO] Sin calibracion: ambas copias estan vacias (0xFF).")
        print("            Esto suele causar error al escanear tarjetas.")
    elif values[0] == values[1]:
        print("\n[RESULTADO] Calibracion presente y consistente en ambas copias.")
    else:
        print("\n[RESULTADO] Las dos copias NO coinciden entre si (raro).")


# ----------------------------------------------------------------------
# Comando: patch
# ----------------------------------------------------------------------

def cmd_patch(args: argparse.Namespace) -> None:
    source = read_sav(args.source)
    target = read_sav(args.target)

    source_blocks = extract_calibration(source)
    target_blocks = extract_calibration(target)

    for off, block in source_blocks.items():
        if is_blank(block):
            print(
                f"[!] Aviso: el bloque fuente en 0x{off:04X} tambien esta "
                "vacio. El archivo --source puede no ser una buena fuente "
                "de calibracion.",
                file=sys.stderr,
            )

    for off, block in target_blocks.items():
        if not is_blank(block) and not args.force:
            print(
                f"[ERROR] El destino ya tiene datos (no 0xFF) en 0x{off:04X}:",
                file=sys.stderr,
            )
            print(f"        {block.hex()}", file=sys.stderr)
            print(
                "        Usa --force si de verdad quieres sobreescribirlo.",
                file=sys.stderr,
            )
            sys.exit(1)

    output = args.output or args.target.with_name(
        args.target.stem + "_patched" + args.target.suffix
    )
    if output.resolve() in (args.source.resolve(), args.target.resolve()):
        sys.exit("[ERROR] --output no puede ser igual a --source o --target.")

    patched = bytearray(target)
    for off in CAL_OFFSETS:
        patched[off:off + CAL_LENGTH] = source_blocks[off]

    output.write_bytes(patched)

    print(f"[OK] Calibracion copiada desde: {args.source.name}")
    print(f"[OK] Aplicada sobre:            {args.target.name}")
    print(f"[OK] Guardado en:               {output}")
    print("Bloques resultantes:")
    for off in CAL_OFFSETS:
        block = patched[off:off + CAL_LENGTH]
        print_block(off, block, args.verbose)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ereader_calibration_tool.py",
        description=(
            "SooraPatcher E-reader Any region\n"
            "Inspecciona y repara el bloque de calibracion del e-Reader+ "
            "(offsets 0xD000/0xE000) dentro de archivos .sav de 128KB."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  %(prog)s inspect mi_dump.sav\n"
            "  %(prog)s inspect mi_dump.sav --verbose\n"
            "  %(prog)s patch --source sano.sav --target roto.sav "
            "--output resultado.sav\n"
            "  %(prog)s patch --source sano.sav --target roto.sav "
            "--output resultado.sav --force\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True,
                                 metavar="{inspect,patch}")

    # --- inspect ---
    p_inspect = sub.add_parser(
        "inspect",
        help="Muestra el estado del bloque de calibracion de un .sav",
        description=(
            "Lee un archivo .sav y reporta si el bloque de calibracion "
            "del e-Reader+ (0xD000/0xE000) esta presente o vacio, "
            "y el contenido legible que contiene."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  ereader_calibration_tool.py inspect mi_dump.sav\n"
            "  ereader_calibration_tool.py inspect mi_dump.sav --verbose\n"
        ),
    )
    p_inspect.add_argument(
        "file", type=Path,
        help="Ruta del archivo .sav a inspeccionar"
    )
    p_inspect.add_argument(
        "--verbose", action="store_true",
        help="Muestra los bytes en hexadecimal ademas del texto legible"
    )
    p_inspect.set_defaults(func=cmd_inspect)

    # --- patch ---
    p_patch = sub.add_parser(
        "patch",
        help="Copia el bloque de calibracion de un .sav sano hacia otro",
        description=(
            "SooraPatcher E-reader Any region"
            "Copia los 96 bytes de calibracion en 0xD000 y 0xE000 desde "
            "--source hacia --target, dejando el resto del archivo target "
            "intacto, y guarda el resultado en --output (nunca sobreescribe "
            "los archivos originales)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  ereader_calibration_tool.py patch --source sano.sav "
            "--target roto.sav --output resultado.sav\n"
            "  ereader_calibration_tool.py patch --source sano.sav "
            "--target roto.sav --output resultado.sav --force\n"
        ),
    )
    p_patch.add_argument(
        "--source", required=True, type=Path,
        help="Archivo .sav que SI tiene la calibracion valida "
             "(ej: uno generado por mGBA que si escanea bien)"
    )
    p_patch.add_argument(
        "--target", required=True, type=Path,
        help="Archivo .sav al que le falta la calibracion "
             "(ej: tu dump real del e-Reader+ fisico)"
    )
    p_patch.add_argument(
        "--output", type=Path, default=None,
        help="Ruta del .sav parcheado de salida. Por defecto: "
             "<target>_patched.sav (nunca se sobreescriben los originales)"
    )
    p_patch.add_argument(
        "--force", action="store_true",
        help="Sobreescribe el bloque de calibracion del target aunque ya "
             "tenga datos distintos de 0xFF (por defecto, se detiene para "
             "evitar perder datos)"
    )
    p_patch.add_argument(
        "--verbose", action="store_true",
        help="Muestra los bytes en hexadecimal del resultado, ademas del texto"
    )
    p_patch.set_defaults(func=cmd_patch)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()