from core.command_center import CommandCenter
from core.config import Config
from core.diagnostics import configure_diagnostics, log_fatal_error


def main() -> None:
    config = Config()
    configure_diagnostics(config.data_root)

    try:
        odin = CommandCenter()
        odin.start()
    except Exception:
        log_fatal_error()
        print(
            "\nODIN encontró un error inesperado. "
            f"Revisá el registro en: {config.data_root / 'logs' / 'odin.log'}"
        )
        input("Presioná Enter para cerrar...")


if __name__ == "__main__":
    main()
