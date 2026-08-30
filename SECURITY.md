# Política de seguridad

## Versiones soportadas

Durante la beta se corrige únicamente la última versión publicada y la rama
activa de desarrollo.

## Informar una vulnerabilidad

No publique claves, datos del comandante ni detalles explotables en un issue
público. Informe el problema de forma privada al responsable del proyecto por el
canal privado desde el que recibió la beta. Cuando el repositorio esté publicado,
se habilitará también **Private vulnerability reporting** de GitHub.

Incluya, si es posible:

- versión y sistema operativo;
- componente afectado;
- pasos mínimos para reproducirlo;
- impacto observado;
- registro anonimizado, sin credenciales ni Journal completos.

## Tratamiento de secretos

ODIN guarda credenciales mediante el almacén seguro del sistema operativo. En
Windows utiliza Credential Manager. No se deben guardar API keys en SQLite sin
cifrado, archivos JSON, archivos TXT, logs, capturas ni informes enviados a un
proveedor de IA.

Si una clave se publica accidentalmente, debe revocarse en el proveedor antes de
limpiar el repositorio; borrar solamente el archivo no invalida la credencial.
