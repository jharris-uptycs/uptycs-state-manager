"""
Creates Uptycs distributor package
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import random
import re
import string
import sys
import time
import zipfile
from typing import Dict, List, Optional, Any
from botocore.exceptions import BotoCoreError, ClientError
import boto3
import jwt
import requests
import urllib3

urllib3.disable_warnings()
S3PREFIX = 'uptycs'
TIMEOUT = 9000
ASSET_GRP_NAME = 'assets'
PATH_TO_BUCKET_FOLDER = '../s3-bucket/'
PACKAGE_NAME = 'UptycsAgent'
INSTALLER_VERSION = '1.0'
OS_LIST = ['windows', 'linux']
MAP_FILE = 'uptycs-agent-mapping.json'
AUTHFILE = 'apikey.json'
PACKAGE_DESCRIPTION = \
    'The Uptycs platform provides you with osquery installation packages for ' \
    'all supported operating systems, configures it for optimal data collection, ' \
    'and automatically schedules the queries necessary to track the historical ' \
    'state and activity of all of your assets. '

class DistributorFilePackager:
    """
    Class to represent a AWS Distributor package.
    """
    OSQUERY_PACKAGE_NAME_TEMPLATE = '{dir}-{version}.zip'

    def __init__(self, installer_version: str, with_remediation: bool):
        """
        Initializes an instance of the DistributorFilePackager class.

        Args:
            installer_version (str): The version of the installer package.
            with_remediation (bool): Whether or not to include the remediation package.
        """
        self.logger = LogHandler(str(self.__class__))
        self.manifest_dict: Dict = {}
        self.with_remediation: bool = with_remediation
        self.dirs: set = set()
        self.zip_file_list: set = set()
        self.build_configs: Dict = self._parse_mappings(MAP_FILE)
        self.dir_list: List[str] = os.listdir()
        self.installer_version: str = installer_version
        for os_type in OS_LIST:
            for installer in self.build_configs[os_type]:
                self.dirs.add(installer['dir'])
                self.zip_file_list.add(
                    self.OSQUERY_PACKAGE_NAME_TEMPLATE.format(dir=installer["dir"],
                                                              version=self.installer_version))

    def download_osquery_files(self) -> None:
        """Download the osquery files for each operating system type and architecture."""
        for os_type in OS_LIST:
            for installer in self.build_configs[os_type]:
                self._add_binary_to_dir(installer)

    def create_staging_dir(self) -> None:
        """Create a staging directory and zip files from each directory in self.dirs."""
        for _dir in self.dirs:
            self._create_zip_files(_dir)
        self._generate_manifest()

    def add_files_to_bucket(self, bucket_name: str, aws_region: str) -> None:
        """
        Upload the zip files in self.zip_file_list to the specified S3 bucket.

        Args:
            bucket_name (str): The name of the S3 bucket.
            aws_region (str): The name of the AWS region.
        """
        bucket = ManagePackageBucket(aws_region)
        bucket.update(bucket_name, self.zip_file_list)

    def _add_binary_to_dir(self, dir_config: Dict) -> None:
        """
        Download the osquery binary for the specified directory configuration.
        Args:
             dir_config (Dict): A dictionary containing the directory configuration information.
            The dictionary should contain the following keys:
                - dir: The directory to download the osquery binary to.
                - arch_type: The architecture of the OS, e.g. "x64", "arm64", etc.
                - upt_package: The name of the OS, as expected by the UptApi.
        """
        working_dir = dir_config.get('dir')
        upt_arch = dir_config.get('arch_type')
        upt_os_name = dir_config.get('upt_package')
        upt_protection_query_params = {
            'remediationPackage': 'true'
        }
        arm64_query_params = {
            'gravitonPackage': 'true'
        }
        query_params = {
            'osqVersion': self.installer_version
        }
        if upt_arch == 'arm64':
            query_params.update(arm64_query_params)
        if self.with_remediation:
            query_params.update(upt_protection_query_params)
        package_download_api = PackageDownloadsApi()
        print(f'Downloading {upt_os_name} for {upt_arch} to folder {working_dir}')
        package_download_api.package_downloads_osquery_os_asset_group_id_get(
            upt_os_name,
            working_dir,
            query_params
        )

    @staticmethod
    def _parse_mappings(filename: str) -> Dict:
        """
        Parses the specified file and returns the configuration data.

        Args:
            filename (str): The name of the file to parse.

        Returns:
            dict: The configuration data.
        """
        with open(filename, 'rb') as file_handle:
            json_data = json.loads(file_handle.read())
        return json_data

    def _generate_manifest(self) -> None:
        """
        Generates the manifest.json file required to create the ssm document.
        """
        # Create an empty dictionary to hold the instance information for each OS type and version.
        manifest_instance_info = {}

        # Initialize the manifest dictionary with the required fields.
        self.manifest_dict = {
            "schemaVersion": "2.0",
            "publisher": "Uptycs.",
            "description": PACKAGE_DESCRIPTION,
            "version": self.installer_version
        }

        # Iterate through each OS type and configuration and add its information to the manifest.
        for os_type in OS_LIST:
            for config in self.build_configs[os_type]:
                name = config['name']
                arch_type = config['arch_type']
                version = config['major_version']
                if not len(config['minor_version']) == 0:
                    version = version + "." + config['minor_version']
                if name in manifest_instance_info:
                    pass
                else:
                    manifest_instance_info[name] = {}

                if version in manifest_instance_info[name]:
                    pass
                else:
                    manifest_instance_info[name][version] = {}

                if arch_type in manifest_instance_info[name][version]:
                    pass
                else:
                    manifest_instance_info[name][version][arch_type] = {}

                zip_file_name = self.OSQUERY_PACKAGE_NAME_TEMPLATE.format(
                    dir=config["dir"],
                    version=self.installer_version)
                manifest_instance_info[name][version][arch_type] = {'file': zip_file_name}

        # Generate a SHA256 digest for each file in the zip file list and add its information to
        # the manifest.
        try:
            hashes = self._generate_digest(self.zip_file_list)
            self.manifest_dict["packages"] = manifest_instance_info
            obj = {}
            for hash_val in hashes:
                for key, val in hash_val.items():
                    obj.update({key: {'checksums': {"sha256": val}}})
            file_list = {"files": obj}
            self.manifest_dict.update(file_list)

            # Write the manifest file to the S3 bucket folder and add it to the zip file list.
            manifest_file_path = PATH_TO_BUCKET_FOLDER + 'manifest.json'
            self._write_manifest_file(manifest_file_path, self.manifest_dict)
            self.zip_file_list.add('manifest.json')

        # Log an error message if there are any exceptions while generating the manifest.
        except (KeyError, ValueError) as err:
            self.logger.error(f'Exception {err}')

    @staticmethod
    def _write_manifest_file(file: str, json_data: Dict) -> None:
        """
        Write the given JSON data to the specified file.

        Args:
            file (str): The file to write the data to.
            json_data (Dict): The JSON data to write.
        """
        try:
            with open(file, 'w', encoding="utf-8") as file_handle:
                file_handle.write(json.dumps(json_data))
                print('Writing manifest file')
        except (FileNotFoundError, FileExistsError, OSError) as err:
            print(err)

    def _create_zip_files(self, directory: str) -> None:
        """
        Creates a zip file from the contents of the specified directory
        and saves it to the specified path.

        Args:
            directory (str): The directory to create a zip file from.
        """
        # Generate the path to the zip file
        zip_path = os.path.join(PATH_TO_BUCKET_FOLDER, f"{directory}-{self.installer_version}.zip")

        # Create any necessary directories for the zip file
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        # Create the zip file and write the contents of the directory to it
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, file_list in os.walk(f"{directory}/"):
                for file in file_list:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))

        # Output a message to indicate that the zip file was successfully created
        print(f'Successfully created zip file: {zip_path}')

    @staticmethod
    def _generate_digest(zip_file_list: set) -> List[Dict[str, str]]:
        """
        Generate a SHA-256 digest for each file in the provided list.

        Args:
            zip_file_list (set): A set of file names to generate the digests for.

        Returns:
            List[Dict[str, str]]: A list of dictionaries,
            each containing a file name and its corresponding SHA-256 digest.
        """
        hashes = []
        for filename in zip_file_list:
            file_path = os.path.join(PATH_TO_BUCKET_FOLDER, filename)
            with open(file_path, 'rb') as file_handle:
                read_bytes = file_handle.read()  # read entire file as bytes
                readable_hash = hashlib.sha256(read_bytes).hexdigest()
                hashes.append({filename: readable_hash})

        return hashes


class LogHandler:
    """Class for handling logging to file and console"""

    def __init__(self, logger_name):
        """
        Initializes a new LogHandler object.

        Args:
            logger_name (str): The name of the logger.

        Attributes:
            logger (logging.Logger): The logger instance.
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        log_format = '%(asctime)s: %(levelname)s: %(name)s: %(message)s'
        filename = os.path.splitext(os.path.basename(__file__))[0] + '.log'
        file_handler = logging.FileHandler(filename)
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(log_format)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def debug(self, msg):
        """
        Log a debug message.

        Args:
            msg (str): The debug message
        """
        self.logger.debug(msg)

    def info(self, msg):
        """
        Log an info message.

        Args:
            msg (str): The info message
        """
        self.logger.info(msg)

    def warning(self, msg):
        """
        Log a warning message.

        Args:
            msg (str): The warning message
        """
        self.logger.warning(msg)

    def error(self, msg):
        """
        Log an error message.

        Args:
            msg (str): The error message
        """
        self.logger.error(msg)

    def critical(self, msg):
        """
        Log a critical message.

        Args:
            msg (str): The critical message
        """
        self.logger.critical(msg)


class UptApiAuthError(Exception):
    """Base class for exceptions raised by UptApiAuth."""


class ApiConfigFileNotFoundError(UptApiAuthError):
    """Exception raised when an API config file is not found."""


class InvalidApiConfigFileError(UptApiAuthError):
    """Exception raised when an API config file is invalid."""


class InvalidApiAuthParametersError(UptApiAuthError):
    """Exception raised when one or more API authentication parameters are missing or invalid."""


class UptApiAuth:
    """Class for creating Uptycs API authorization objects from API key files or parameters."""

    def __init__(self, api_config_file=None, key=None, secret=None, domain=None, customer_id=None,
                 silent=True):
        # pylint: disable=too-many-arguments
        """Initialize a new UptApiAuth object.

        Args:
            api_config_file (str): Path to an API key file (default: None)
            key (str): Uptycs API key (default: None)
            secret (str): Uptycs API secret (default: None)
            domain (str): Uptycs API domain (default: None)
            customer_id (str): Uptycs customer ID (default: None)
            silent (bool): Whether to suppress console output (default: True)
        """
        self.base_url = None
        self.header = None

        if api_config_file is not None:
            try:
                if not silent:
                    print(
                        f'Reading Uptycs API connection & authorization details from '
                        f'{api_config_file}')
                with open(api_config_file, encoding='utf-8') as file_handle:
                    data = json.load(file_handle)
                key = data['key']
                secret = data['secret']
                domain = data['domain']
                customer_id = data['customerId']
            except FileNotFoundError as error:
                raise ApiConfigFileNotFoundError(
                    f"API config file not found: {error.filename}") from error
            except (json.JSONDecodeError, KeyError) as error:
                raise InvalidApiConfigFileError(
                    f"Invalid API config file: {api_config_file}") from error
        elif key is None or secret is None or domain is None or customer_id is None:
            raise InvalidApiAuthParametersError(
                "Please provide either an API key file or all of the following parameters: key, "
                "secret, domain, customerId")

        if domain is None:
            raise InvalidApiAuthParametersError("Please provide the Uptycs API domain.")
        if customer_id is None:
            raise InvalidApiAuthParametersError("Please provide the Uptycs customer ID.")

        self.base_url = f"https://{domain}.uptycs.io/public/api/customers/{customer_id}"
        try:
            exp_time = time.time() + TIMEOUT
            authvar: str = jwt.encode({'iss': key, 'exp': exp_time}, secret)
            authorization: str = f"Bearer {authvar}"
        except jwt.exceptions.PyJWTError as error:
            raise UptApiAuthError("Error encoding key and secret with jwt module") from error

        self.header = {
            'authorization': authorization,
            'date': datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            'Content-type': "application/json"
        }


class UptApiCall:
    """ Class to call any Uptycs API
        Future enhancement could add support for /url?param=value filters
        self.rc = 0 on success, 1 on error
    """

    def __init__(self, api_endpoint, method, payload=None, **kwargs):
        """

        Args:
            api_endpoint (str): The Uptycs api endpoint eg '/objectGroups'
            method (str): The HTTP Method
            payload (dict): The api payloat
            **kwargs (dict): Additional parameters
        """
        self.logger = LogHandler(str(self.__class__))
        try:
            self.api_auth = UptApiAuth(AUTHFILE)
        except Exception as error:
            self.logger.error(error)
            sys.exit(1)

        self.items = []  # this can be set by calling get_items() (if method = GET)

        if method == 'GET':
            response = requests.get(self.api_auth.base_url + api_endpoint,
                                    headers=self.api_auth.header, verify=False,
                                    timeout=TIMEOUT,
                                    **kwargs)
        elif method == 'POST':
            payload_json = json.dumps(payload)
            response = requests.post(self.api_auth.base_url + api_endpoint,
                                     headers=self.api_auth.header,
                                     data=payload_json, verify=False,
                                     timeout=TIMEOUT, **kwargs)
        elif method == 'PUT':
            payload_json = json.dumps(payload)
            response = requests.put(self.api_auth.base_url + api_endpoint,
                                    headers=self.api_auth.header,
                                    data=payload_json, verify=False,
                                    timeout=TIMEOUT, **kwargs)
        elif method == 'DELETE':
            payload_json = json.dumps(payload)
            response = requests.delete(self.api_auth.base_url + api_endpoint,
                                       headers=self.api_auth.header,
                                       data=payload_json,
                                       verify=False, timeout=TIMEOUT, **kwargs)
        else:
            self.logger.error(
                "Error! Method must be 'GET', 'POST', 'PUT', or 'DELETE'. Supplied method was: "
                + method)
            sys.exit(1)

        # check response status code, 200 is success
        if response.status_code != 200:
            self.logger.error(
                "Error during " + method + " on " + api_endpoint + ", base url: " +
                self.api_auth.base_url)
            self.logger.error(json.dumps(response.json(), indent=4))

        else:
            self.logger.debug(
                "Success with " + method + " on " + api_endpoint + ", base url: " +
                self.api_auth.base_url)

        content_type = response.headers.get('Content-Type', '')
        stream_types = ['application/octet-stream', 'application/x-redhat-package-manager']
        if any([x in content_type for x in stream_types]):
            self.response_stream = response
        else:
            self.response_json = response.json()

    def get_items(self):
        """store each JSON item in a collection"""
        for i in self.response_json['items']:
            self.items.append(i)


class ObjectGroupsApi:
    """
    ObjectGroupsApi Class
    """

    def __init__(self):
        """
        Class init function setting up logger instance
        """
        self.logger = LogHandler(str(self.__class__))

    def object_groups_get(self):
        """
        Get the list of objectGroups.
        """

        try:
            resp = UptApiCall('/objectGroups', 'GET', {})
            return resp.response_json
        except Exception as error:
            self.logger.error(error)
            sys.exit(1)

    def object_groups_object_group_id_delete(self, object_group_id, **kwargs):
        """
        Delete object group.
        """
        path = f'/objectGroups/{object_group_id}'
        headers = kwargs.pop('headers', {})
        query_params = kwargs.pop('query_params', {})
        resp = UptApiCall(path, 'DELETE', headers=headers, query_params=query_params, **kwargs)
        return resp.response_json


class PackageDownloadsApi:
    """
    Class to handle the download of osquery agents and stage them in local directories.
    """

    def __init__(self):
        """
        Initializes an instance of PackageDownloadsApi.
        """
        self.logger = LogHandler(str(self.__class__))
        self.asset_group_id = self._get_asset_group_id()

    def _get_asset_group_id(self):
        """
        Retrieves the asset group ID from the Uptrends API.
        """
        obj_grp_list = ObjectGroupsApi().object_groups_get().get('items')
        for obj_grp in obj_grp_list:
            if obj_grp.get('name') == ASSET_GRP_NAME:
                return obj_grp.get('id')
        return None

    def osquery_packages_get_version(self):
        """
        Retrieves the version number of the current osquery packages.
        """
        path = '/osqueryPackages'
        response = UptApiCall(path, 'GET')

        # for os_target, arch, version, is_remediation in result:
        #     print(os_target, arch, version, is_remediation)
        return response.response_json['items'][0]['version'].split('-')[0]

    def package_downloads_osquery_os_asset_group_id_get(self, os_name: str, dir_name: str,
                                                        query_params: Optional[
                                                            Dict[str, str]] = None) -> None:
        # TODO: Optimise downloads. At present we often download the same file multiple times.

        """
        Downloads an osquery package for the given os and asset
        group ID and saves it to the specified directory.

        Args:
            os_name (str): The name of the OS, e.g. "debian".
            dir_name (str): The name of the directory to save the package in.
            query_params (Dict[str, str], optional): Additional query parameters for the API call.
        """

        # Construct the API path for the osquery package download
        path = f'/packageDownloads/osquery/{os_name}/{self.asset_group_id}'

        try:
            # Append any query parameters to the path, if provided
            if query_params:
                query_params_str = '&'.join([f'{k}={v}' for k, v in query_params.items()])
                path += f'?{query_params_str}'

            # Make the API call to download the osquery package
            self.logger.debug(f'Calling API with {path}')
            response = UptApiCall(path, 'GET')
            self.logger.debug(f'Got response {response.response_stream.status_code}')

            # Extract the filename from the content disposition header
            content_disp_str = response.response_stream.headers.get('content-disposition', '')
            file_name = re.findall(r'filename="(.+?)"', content_disp_str)[0]

            # Download and save the osquery package to the specified directory
            self.logger.debug(f'Downloading file {file_name}')
            relative_path = f'./{dir_name}/{file_name}'
            os.makedirs(os.path.dirname(relative_path), exist_ok=True)
            if response.response_stream.status_code == 200:
                with open(relative_path, 'wb') as file_handle:
                    for chunk in response.response_stream.iter_content(1024):
                        file_handle.write(chunk)
            print(f'Successfully wrote to folder {relative_path}')

            # Replace the filename in the install script with the downloaded package filename
            install_file_name = 'install.ps1' if os_name == 'windows' else 'install.sh'
            install_file_path = f'./{dir_name}/{install_file_name}'
            with open(install_file_path, "r", encoding="utf-8") as file:
                content = file.read()
            content = re.sub(r"(filename=|\$filename=)[^\n]+", r"\g<1>" + file_name, content)
            with open(install_file_path, "w", encoding="utf-8") as file:
                file.write(content)

        except Exception as error:
            # Log and raise any errors encountered during the osquery package download
            self.logger.error(f'Error during GET on {path}')
            self.logger.error(str(error))
            raise error


class ManagePackageBucket:
    """
    Class to handle all interactions with the S3 Bucket used for the distributor package
    """

    def __init__(self, region_name: str) -> None:
        """
        Initializes an instance of the ManagePackageBucket class.

        Args:
            region_name (str): The name of the AWS region.
        """
        self.logger = LogHandler(str(self.__class__))
        self.region = region_name
        self.s3_client = boto3.client('s3', region_name=self.region)

    def update(self, bucket_name: str, file_list: set) -> bool:
        """
        Updates the bucket contents.

        Args:
            bucket_name (str): The name of the S3 bucket.
            file_list (list[str]): A list of file names to be uploaded.

        Returns:
            bool: True if the update was successful, else False.
        """
        if not self._bucket_exists(bucket_name):
            self._create_bucket(bucket_name)
        for file in file_list:
            file_path = os.path.join(PATH_TO_BUCKET_FOLDER, file)
            object_key = f"{S3PREFIX}/{file}"
            self._upload_file(file_path, bucket_name, object_key)
        return True

    def _bucket_exists(self, bucket_name: str) -> bool:
        """
        Checks that the S3 bucket exists in the region.

        Args:
            bucket_name (str): The name of the S3 bucket.

        Returns:
            bool: True if the bucket exists, else False.
        """
        try:
            response = self.s3_client.list_buckets()
            for bucket in response['Buckets']:
                if bucket_name == bucket["Name"]:
                    print('Bucket already exists -Skipping Creation:')
                    return True
            return False
        except ClientError as err:
            self.logger.error(f'Error listing buckets {err}')
            return False

    def _create_bucket(self, bucket_name: str) -> bool:
        """
        Creates an S3 bucket.

        Args:
            bucket_name (str): The name of the bucket to create.

        Returns:
            bool: True if the bucket was created, else False.
        """
        print(f'Creating bucket: {bucket_name}')
        try:
            if self.region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': self.region
                    }
                )
            return True
        except ClientError as err:
            self.logger.error(f'Error creating bucket {err}')
            return False

    def _upload_file(self, file_path: str, bucket_name: str, object_key: str) -> bool:
        """Upload a file to an S3 bucket

        :param file_path: File to upload
        :param bucket_name: Bucket to upload to
        :param object_key: S3 object key
        :return: True if file was uploaded, else False
        """
        try:
            start_time = time.time()
            print(f'Uploading file {file_path}:')
            with open(file_path, "rb") as content:
                self.s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=content
                )
            time_taken = time.time() - start_time
            print(f"Successfully finished uploading files to s3 bucket. in {time_taken}s")
            return True
        except (BotoCoreError, ClientError) as err:
            self.logger.error(f'Upload error {err}')
            return False


def main():
    """

    Main function

    """
    global AUTHFILE
    parser = argparse.ArgumentParser(
        description='Create and upload Distributor packages to the AWS SSM'
    )
    parser.add_argument('-c', '--config', required=True,
                        help='REQUIRED: The path to your auth config file downloaded from Uptycs '
                             'console')
    parser.add_argument('-b', '--s3bucket', default=None,
                        help='OPTIONAL: Name of the S3 bucket used to stage the zip files. '
                             'If not set the bucket will have the name format '
                             'uptycs-dist- + random_string')
    parser.add_argument('-p', '--package_name', default='UptycsAgent',
                        help='OPTIONAL: Use with -d to specify the name of the Distributor '
                             'Package that you will create using files .rpm and .deb files that '
                             'you have added manually')
    parser.add_argument('-r', '--aws_region', default='us-east-1',
                        help='OPTIONAL: The AWS Region that the Bucket will be created in')
    parser.add_argument('-v', '--package_version', default=None,
                        help='OPTIONAL: Use with -d to specify set the Osquery Version if you have '
                             'added the files manually in the format eg 5.7.0.23')
    parser.add_argument('-d', '--download', action='store_false',
                        default=True,
                        help='OPTIONAL: DISABLE the download install files via API. Use if you are '
                             'adding the .rpm and .deb files to the directories manually')

    parser.add_argument('-o', '--sensor_only', dest='sensor_only', action='store_true',
                        default=False,
                        help='OPTIONAL: Setup package without Uptycs protect.  By default the '
                             'Uptycs Protect agent will be used')
    args = parser.parse_args()
    if args.download is False and (args.package_version is None or args.package_name is None):
        parser.error('-v/--package_version and -p/--package_name are mandatory with -d/--download '
                     'flag')

    region = args.aws_region
    package_version: Optional[Any] = args.package_version
    AUTHFILE = args.config
    download_files = args.download
    random_string = ''.join(random.sample(string.ascii_lowercase, 6))

    if args.sensor_only:
        upt_protection = 'false'
    else:
        upt_protection = 'true'

    if args.s3bucket is None:
        s3_bucket = 'uptycs-dist-' + random_string
    else:
        s3_bucket = args.s3bucket

    if package_version:
        #
        # Get the osquery version available via the Uptycs API
        #
        version = args.package_version
    else:
        version = PackageDownloadsApi().osquery_packages_get_version()
    #
    # Initialise the Distributor package object for this version
    #
    uptycs_packager = DistributorFilePackager(version, upt_protection)
    #
    # (Optional) Download the osquery binaries from the Uptycs API
    # You can add older versions of the files manually.
    if download_files:
        uptycs_packager.download_osquery_files()
    #
    # Generate the zip file and manifest and add them to the local staging folder
    #
    uptycs_packager.create_staging_dir()
    uptycs_packager.add_files_to_bucket(s3_bucket, region)


if __name__ == '__main__':
    main()
