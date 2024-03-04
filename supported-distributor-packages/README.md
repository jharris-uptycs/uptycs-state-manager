# Uptycs Distributor Package Sharing Script

Uptycs now provides a managed distributor package in us-east-1 and us-east-2.  This folder 
contains a script `share_uptycs_package.py` which will make an api call to Uptycs to request 
that the packages are shared in the given account.

The folder also includes a template `Uptycs-Managed-Package-State-Manager.yaml` which can be 
applied after the script is run. The template creates a Stackset that can be applied to multiple 
regions 

## Requesting that the Uptycs Package is Shared

Run the `share_uptycs_package.py` script.

This script allows you to share an Uptycs Distributor package to an AWS account in specified regions.

The script requires three inputs:

1. `account_id` - The AWS account ID.
2. `regions_file` - A JSON file containing the regions where the package should be shared.
3. `api_key_file` - A file containing the API keys for Uptycs.

### Dependencies

The script requires the following packages:
- `argparse`
- `datetime`
- `json`
- `logging`
- `os`
- `time`
- `jwt`
- `requests`

If necessary, these can be installed using pip by running 
```pip install -r requirements.txt```

### Usage

First, clone and navigate into the directory:

To run the script, use the following command:

```python share_uptycs_package.py -a <account_id> -r <regions.json> -k <apikey.json>```

Replace `<account_id>`, `<regions.json>`, and `<api_keys.json>` with your AWS account ID, path to the JSON file containing the regions and path to the API key file, respectively.

## Create the State Manager Association

Load the Cloudformation template `Uptycs-Managed-Package-State-Manager.yaml`