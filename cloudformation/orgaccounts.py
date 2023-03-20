import boto3
from typing import List


def get_account_org_mapping(org_client: boto3.client) -> List[dict]:
    """
    Retrieves a list of dictionaries containing the mapping between AWS accounts and their respective OUs in an
    AWS Organization.

    Args:
        org_client (boto3.client): The AWS Organizations client.

    Returns:
        List[dict]: A list of dictionaries, where each dictionary represents an account and its respective OU in the
        organization, and contains the following keys: 'AccountId', 'AccountEmail', 'OUId', 'OUName'.

    Raises:
        botocore.exceptions.ClientError: If there is an issue retrieving the mapping.

    Example usage:
        org_client = boto3.client('organizations')
        account_mapping = get_account_org_mapping(org_client)
    """
    account_mapping = []
    accounts = org_client.list_accounts()['Accounts']

    for account in accounts:
        try:
            response = org_client.list_parents(ChildId=account['Id'])
            ou = response['Parents'][0]
            ou_id = ou['Id']
            ou_name = org_client.describe_organizational_unit(OrganizationalUnitId=ou_id)['OrganizationalUnit']['Name']
        except Exception as e:
            ou_id = ''
            ou_name = ''
        account_mapping.append({
            'AccountId': account['Id'],
            'AccountEmail': account['Email'],
            'OUId': ou_id,
            'OUName': ou_name
        })

    return account_mapping


def list_org_ous(org_client: boto3.client) -> List[dict]:
    """
    Lists all the Organizational Units (OUs) in an AWS Organization.

    Args:
        org_client (boto3.client): The AWS Organizations client.

    Returns:
        List[dict]: A list of dictionaries, where each dictionary represents an OU and contains its ID and name.

    Raises:
        botocore.exceptions.ClientError: If there is an issue listing the OUs.

    Example usage:
        org_client = boto3.client('organizations')
        ous = list_org_ous(org_client)
    """
    ous = []

    # Get the root object of the organization
    root = org_client.list_roots()['Roots'][0]

    # List the child OUs of the root
    ou_paginator = org_client.get_paginator('list_children')
    ou_iterator = ou_paginator.paginate(ParentId=root['Id'], ChildType='ORGANIZATIONAL_UNIT')

    for page in ou_iterator:
        for ou in page['Children']:
            ous.append({'Id': ou['Id'], 'Name': ou.get('Name')})

    return ous


def get_all_accounts(org_client: boto3.client, ou_ids: List[str] = None) -> List[dict]:
    """
    Retrieves a list of all accounts in an AWS Organization, including child accounts of the specified OUs.

    Args:
        org_client (boto3.client): The AWS Organizations client.
        ou_ids (List[str], optional): A list of Organizational Unit (OU) IDs. If provided, the function retrieves
            all accounts in the specified OUs and their child OUs. If not provided, the function retrieves all
            accounts in the organization. Defaults to None.

    Returns:
        List[dict]: A list of AWS account objects, where each object contains the account ID, ARN, and email address.

    Raises:
        botocore.exceptions.ClientError: If the specified OU ID or account ID is invalid, or if there is an issue
            retrieving the accounts.

    Example usage:
        org_client = boto3.client('organizations')
        ou_ids = ['ou-xxxx-xxxxxxx', 'ou-yyyy-yyyyyyy']
        accounts = get_all_accounts(org_client, ou_ids)
    """
    accounts = []
    if ou_ids is None:
        # Get all accounts in the organization
        paginator = org_client.get_paginator('list_accounts')
        for page in paginator.paginate():
            accounts += page['Accounts']
    else:
        # Get all accounts in the specified OUs and their child OUs
        for ou_id in ou_ids:
            child_ous = org_client.list_children(ParentId=ou_id)['Children']
            for child_ou in child_ous:
                if child_ou['Type'] == 'ORGANIZATIONAL_UNIT':
                    child_ou_id = child_ou['Id']
                    accounts += get_all_accounts(org_client, [child_ou_id])
            accounts += org_client.list_accounts_for_parent(ParentId=ou_id)['Accounts']
    return accounts


def main():
    org_client = boto3.client('organizations')
    map = get_account_org_mapping(org_client)
    ous = list_org_ous(org_client)
    accounts = get_all_accounts(org_client)
    print(accounts)


if __name__ == '__main__':
    main()