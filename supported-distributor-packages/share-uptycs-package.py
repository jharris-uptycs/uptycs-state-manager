import argparse
import datetime
import json
import logging
import os
import time

import jwt
import requests


class LogHandler:
    """A class to encapsulate logging setup and methods for serialization."""

    def __init__(self, logger_name):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)  # sets the threshold for this logger to level.

        # File handler for the log messages
        file_handler = logging.FileHandler(os.path.join(os.getcwd(), 'my_log.log'))
        file_handler.setLevel(logging.DEBUG)  # sets the threshold for this handler to level.
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log_message(self, level, message):
        if level.lower() == 'debug':
            self.logger.debug(message)
        elif level.lower() == 'info':
            self.logger.info(message)
        elif level.lower() == 'warning':
            self.logger.warning(message)
        elif level.lower() == 'error':
            self.logger.error(message)
        elif level.lower() == 'critical':
            self.logger.critical(message)


class UptApiAuth:

    def __init__(self, api_config_file=None, key=None, secret=None, domain=None,
                 customer_id=None, domain_suffix='', silent=True, logger=None):
        self.base_url = None
        self.header = None
        self.logger = logger

        if api_config_file is not None:
            try:
                if not silent:
                    self.logger.log_message(
                        'info',
                        f'Reading Uptycs API connection & authorization details from '
                        f'{api_config_file}')
                with open(api_config_file, encoding='utf-8') as file_handle:
                    data = json.load(file_handle)
                key = data.get('key', key)
                secret = data.get('secret', secret)
                domain = data.get('domain', domain)
                customer_id = data.get('customerId', customer_id)
                domain_suffix = data.get('domainSuffix', domain_suffix)
            except FileNotFoundError as error:
                self.logger.log_message('error', f"API config file not found: {error.filename}")
                raise FileNotFoundError(f"API config file not found: {error.filename}") from error
            except (json.JSONDecodeError, KeyError) as error:
                self.logger.log_message('error', f"Invalid API config file: {api_config_file}")
                raise ValueError(f"Invalid API config file: {api_config_file}") from error

        if not all([key, secret, domain, customer_id, domain_suffix]):
            self.logger.log_message('error',
                                    "Please provide either an API key file or all "
                                    "parameters: key, secret, domain, customerId, "
                                    "domainSuffix")
            raise ValueError(
                "Please provide either an API key file or all parameters: "
                "key, secret, domain, customerId, domainSuffix")

        self.base_url = f'https://{domain}{domain_suffix}/public/api/customers/{customer_id}'
        try:
            exp_time = time.time() + 60
            auth_var: str = jwt.encode({'iss': key, 'exp': exp_time}, secret)
            authorization: str = f'Bearer {auth_var}'
        except jwt.exceptions.PyJWTError as error:
            self.logger.log_message('error', "Error encoding key and secret with jwt module")
            raise jwt.PyJWTError("Error encoding key and secret with jwt module") from error

        self.header = {
            'authorization': authorization,
            'date': datetime.datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"),
            'Content-type': "application/json"}


def main():
    logger = LogHandler('auth_logger')
    parser = argparse.ArgumentParser(description='Parse account_id and regions from input')
    parser.add_argument('-a', '--account_id', type=str, required=True, help='The Account ID')
    parser.add_argument('-r', '--regions_file', type=str, required=True,
                        help='The JSON file containing regions')
    parser.add_argument('-k', '--api_key_file', type=str, required=True,
                        help='The JSON file containing regions')
    parser.add_argument('-l', '--log', default='info', type=str, choices=['debug', 'info'],
                        help='Set the log level (default: info)')
    args = parser.parse_args()
    level = logging.DEBUG if args.log == 'debug' else logging.INFO
    logger.logger.setLevel(level)

    # Get account_id from arguments
    account_id = args.account_id

    # Read regions from JSON file
    with open(args.regions_file, "r") as read_file:
        data = json.load(read_file)
    regions = ",".join(data['regions'])

    auth_token = UptApiAuth(args.api_key_file, logger=logger)
    params = {"regions": regions}
    url = f'{auth_token.base_url}/packagedownloads/osqueryssm/terraform/{account_id}'
    response = requests.get(url, headers=auth_token.header, params=params)

    if response.status_code == 200:
        logger.log_message('critical', f"Success! Server responded with: {response.status_code}")
        print("Successfully shared packages")
    else:
        logger.log_message('critical', f"Failure! Server responded with: {response.status_code}")
        print("Failed to share packages")


if __name__ == '__main__':
    main()
