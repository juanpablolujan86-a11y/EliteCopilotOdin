from core.command_center import CommandCenter
from core.config import Config
from core.diagnostics import configure_diagnostics, log_fatal_error
from core.single_instance import SingleInstance


def main() -> None:
    config = Config()
    instance = SingleInstance()

    if not instance.acquire():
        print("\nODIN ya está ejecutándose. No se abrirá una segunda copia.")
        return

    try:
        configure_diagnostics(config.data_root)
        odin = CommandCenter()
        odin.start()
    except Exception:
        log_fatal_error()
        print(
            "\nODIN encontró un error inesperado. "
            f"Revisá el registro en: {config.data_root / 'logs' / 'odin.log'}"
        )
        input("Presioná Enter para cerrar...")
    finally:
        instance.close()


if __name__ == "__main__":
    main()
