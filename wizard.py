import os
from pathlib import Path
import json
from typing import Dict, Any

def create_config() -> None:
    custom_config: Dict[str, Any] = {
        'JIRA_HOST': input("¿Cuál es el nombre de tu host de Jira? "),
        'JIRA_EMAIL': input("¿Cuál es tu dirección de correo electrónico de la cuenta Jira? "),
        'API_TOKEN': input("Pega tu token API de Jira: "),
        'INCLUDE_ATTACHMENTS': input("¿Quieres incluir archivos adjuntos? (true / false) ").lower(),
        'DOWNLOAD_LOCALLY': input("¿Quieres descargar el archivo de respaldo localmente? (true / false) ").lower(),
        'UPLOAD_TO_S3': {
            'S3_BUCKET': "",
            'AWS_ACCESS_KEY': "",
            'AWS_SECRET_KEY': ""
        }
    }

    if input("¿Quieres subir el archivo de respaldo a S3? (true / false) ").lower() == 'true':
        custom_config['UPLOAD_TO_S3'].update({
            'S3_BUCKET': input("¿Cuál es el nombre del bucket S3? "),
            'AWS_ACCESS_KEY': input("¿Cuál es tu clave de acceso AWS? "),
            'AWS_SECRET_KEY': input("¿Cuál es tu clave secreta AWS? ")
        })

    config_path = Path(__file__).parent / 'config.json'
    with config_path.open('w') as config_file:
        json.dump(custom_config, config_file, indent=4)

    print(f"Configuración guardada en {config_path}")

if __name__ == "__main__":
    create_config()
