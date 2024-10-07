import json
import yaml
import time
import os
import argparse
import requests
import boto
from boto.s3.key import Key
import wizard
from typing import Dict, Optional
import logging
import requests.exceptions
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_config():
    config_path = Path(__file__).parent / 'config.yaml'
    with open(config_path, 'r') as config_file:
        return yaml.full_load(config_file)


class Atlassian:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config['USER_EMAIL'], config['API_TOKEN'])
        self.session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json'})
        self.payload = {"cbAttachments": self.config['INCLUDE_ATTACHMENTS'], "exportToCloud": "true"}
        self.start_confluence_backup = f"https://{self.config['HOST_URL']}/wiki/rest/obm/1.0/runbackup"
        self.start_jira_backup = f"https://{self.config['HOST_URL']}/rest/backup/1/export/runbackup"
        self.backup_status = {}
        self.wait = 10

    def create_confluence_backup(self) -> Optional[str]:
        try:
            response = self.session.post(self.start_confluence_backup, json=self.payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error al iniciar el backup: {e}")
            return None
        else:
            logging.info('-> Backup process successfully started')
            confluence_backup_status = f"https://{self.config['HOST_URL']}/wiki/rest/obm/1.0/getprogress"
            time.sleep(self.wait)
            while 'fileName' not in self.backup_status:
                self.backup_status = self.session.get(confluence_backup_status).json()
                logging.info(f"Current status: {self.backup_status['alternativePercentage']}; {self.backup_status['currentStatus']}")
                time.sleep(self.wait)
            return f"https://{self.config['HOST_URL']}/wiki/download/{self.backup_status['fileName']}"

    def create_jira_backup(self) -> Optional[str]:
        backup = self.session.post(self.start_jira_backup, json=self.payload)
        if backup.status_code != 200:
            raise Exception(backup, backup.text)
        else:
            task_id = backup.json()['taskId']
            logging.info(f'-> Backup process successfully started: taskId={task_id}')
            jira_backup_status = f"https://{self.config['HOST_URL']}/rest/backup/1/export/getProgress?taskId={task_id}"
            time.sleep(self.wait)
            while 'result' not in self.backup_status:
                self.backup_status = self.session.get(jira_backup_status).json()
                logging.info(f"Current status: {self.backup_status['status']} {self.backup_status['progress']}; {self.backup_status['description']}")
                time.sleep(self.wait)
            return f"https://{self.config['HOST_URL']}/plugins/servlet/{self.backup_status['result']}"

    def download_file(self, url, local_filename):
        logging.info(f'-> Downloading file from URL: {url}')
        r = self.session.get(url, stream=True)
        file_path = Path(__file__).parent / 'backups' / local_filename
        with open(file_path, 'wb') as file_:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    file_.write(chunk)
        logging.info(file_path)

    def stream_to_s3(self, url, remote_filename):
        print('-> Streaming to S3')
        
        s3_config = self.config['UPLOAD_TO_S3']
        
        if s3_config['AWS_ACCESS_KEY']:
            session = boto3.Session(
                aws_access_key_id=s3_config['AWS_ACCESS_KEY'],
                aws_secret_access_key=s3_config['AWS_SECRET_KEY'],
                region_name=s3_config['AWS_REGION']
            )
        else:
            session = boto3.Session()
        
        with session.client('s3', endpoint_url=s3_config['AWS_ENDPOINT_URL']) as s3:
            r = self.session.get(url, stream=True)
            if r.status_code == 200:
                s3.put_object(
                    Bucket=s3_config['S3_BUCKET'],
                    Key=f"{s3_config['S3_DIR']}{remote_filename}",
                    Body=r.content,
                    ContentType=r.headers['content-type']
                )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Atlassian backup tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    wizard_parser = subparsers.add_parser('wizard', help='activate config wizard')
    confluence_parser = subparsers.add_parser('confluence', help='activate confluence backup')
    jira_parser = subparsers.add_parser('jira', help='activate jira backup')

    args = parser.parse_args()

    if args.command == 'wizard':
        wizard.create_config()
    else:
        config = read_config()
        if config['HOST_URL'] == 'something.atlassian.net':
            raise ValueError('You forgot to edit config.json or to run the backup script with "wizard" command')

        print(f"-> Starting backup; include attachments: {config['INCLUDE_ATTACHMENTS']}")
        atlass = Atlassian(config)
        
        if args.command == 'confluence':
            backup_url = atlass.create_confluence_backup()
        elif args.command == 'jira':
            backup_url = atlass.create_jira_backup()

        print(f'-> Backup URL: {backup_url}')
        file_name = f"{time.strftime('%d%m%Y_%H%M')}_{backup_url.split('/')[-1].replace('?fileId=', '')}.zip"

        if config['DOWNLOAD_LOCALLY'] == 'true':
            atlass.download_file(backup_url, file_name)

        if config['UPLOAD_TO_S3']['S3_BUCKET'] != '':
            atlass.stream_to_s3(backup_url, file_name)