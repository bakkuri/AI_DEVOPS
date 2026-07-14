"""
AWS Scanner Module

Handles AWS CLI interactions to fetch resource groups and resources.
Parses JSON output and returns structured response with resource details.
"""

import subprocess
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Resource:
    """Represents an AWS resource with cost-relevant details."""
    resource_type: str
    name: str
    region: str
    sku: str
    tags: Dict[str, str]
    arn: str


class AWSError(Exception):
    """Base exception for AWS operations."""
    pass


class AWSCliNotFoundError(AWSError):
    """Raised when AWS CLI is not installed."""
    pass


class AWSAuthenticationError(AWSError):
    """Raised when AWS authentication fails."""
    pass


class AWSResourceGroupError(AWSError):
    """Raised when resource group operation fails."""
    pass


class AWSScanner:
    """Manages AWS CLI commands for resource discovery."""

    @staticmethod
    def _run_aws_command(command: List[str]) -> Dict[str, Any]:
        """
        Execute an AWS CLI command and return parsed JSON output.
        
        Args:
            command: List of command parts (e.g., ['aws', 'resource-groups', 'list-groups', '--output', 'json'])
            
        Returns:
            Parsed JSON output as dictionary
            
        Raises:
            AWSCliNotFoundError: If aws command is not found
            AWSAuthenticationError: If authentication/credentials fail
            AWSResourceGroupError: For other AWS operation errors
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                
                # AWS CLI not found
                if "command not found" in error_msg or "No such file or directory" in error_msg:
                    raise AWSCliNotFoundError(
                        "AWS CLI is not installed. Please install it from https://aws.amazon.com/cli/"
                    )
                
                # Authentication errors
                if any(auth_error in error_msg for auth_error in [
                    "NotAuthorizedException",
                    "AuthorizationException",
                    "InvalidClientId.NotFound",
                    "UnauthorizedOperation",
                    "Signature mismatch",
                    "credentials",
                    "Unable to locate credentials"
                ]):
                    raise AWSAuthenticationError(
                        "AWS authentication failed. Ensure AWS CLI credentials are configured correctly. "
                        "Run 'aws configure' or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
                    )
                
                # Invalid resource group
                if "ResourceGroupNotFoundException" in error_msg or "does not exist" in error_msg:
                    raise AWSResourceGroupError(
                        f"Resource group not found or does not exist: {error_msg}"
                    )
                
                # Generic error
                raise AWSResourceGroupError(f"AWS CLI error: {error_msg}")
            
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as e:
                raise AWSResourceGroupError(f"Failed to parse AWS CLI JSON output: {str(e)}")
                
        except FileNotFoundError:
            raise AWSCliNotFoundError(
                "AWS CLI is not installed. Please install it from https://aws.amazon.com/cli/"
            )
    
    @staticmethod
    def verify_aws_authentication() -> bool:
        """
        Verify AWS authentication by calling get-caller-identity.
        
        Returns:
            True if authenticated, raises AWSAuthenticationError otherwise
            
        Raises:
            AWSCliNotFoundError: If AWS CLI is not installed
            AWSAuthenticationError: If not authenticated
        """
        try:
            AWSScanner._run_aws_command(['aws', 'sts', 'get-caller-identity', '--output', 'json'])
            return True
        except AWSError:
            raise
    
    @staticmethod
    def list_resource_groups() -> List[str]:
        """
        Fetch all AWS Resource Groups.
        
        Returns:
            List of resource group names
            
        Raises:
            AWSCliNotFoundError: If AWS CLI is not installed
            AWSAuthenticationError: If not authenticated
            AWSResourceGroupError: For other errors
        """
        try:
            response = AWSScanner._run_aws_command([
                'aws', 'resource-groups', 'list-groups',
                '--output', 'json'
            ])
            
            group_identifiers = response.get('GroupIdentifiers', [])
            group_names = []
            for group in group_identifiers:
                # Try 'GroupName' first (in GroupIdentifiers), then 'Name' (in Groups)
                name = group.get('GroupName') or group.get('Name')
                if name:
                    group_names.append(name)
            
            logger.info(f"Found {len(group_names)} resource groups: {group_names}")
            return group_names
            
        except AWSError:
            raise
    
    @staticmethod
    def _parse_resource_arn(arn: str) -> tuple[str, str]:
        """
        Parse ARN to extract region and resource type.
        
        Args:
            arn: AWS ARN string
            
        Returns:
            Tuple of (region, resource_type)
        """
        # ARN format: arn:aws:service:region:account-id:resource-type/resource-id
        parts = arn.split(':')
        region = parts[3] if len(parts) > 3 else 'unknown'
        service = parts[2] if len(parts) > 2 else 'unknown'

        # Some services (IAM) are global and do not have a region
        if service.lower() == 'iam':
            region = 'global'
        
        # Extract resource type from the last part
        resource_part = parts[-1] if parts else ''
        resource_type = resource_part.split('/')[0] if '/' in resource_part else resource_part
        if not resource_type:
            resource_type = 'UNKNOWN'
        
        return region, f"AWS::{service.upper()}::{resource_type}"
    
    @staticmethod
    def _get_resource_name_from_arn(arn: str) -> str:
        """
        Extract resource name from ARN (last segment after / or :).
        
        Args:
            arn: AWS ARN string
            
        Returns:
            Resource name
        """
        # Get the last part after : or /
        last_part = arn.split(':')[-1]
        if '/' in last_part:
            return last_part.split('/')[-1]
        return last_part
    
    @staticmethod
    def list_group_resources(group_name: str) -> List[Resource]:
        """
        Fetch all resources in a specific Resource Group.
        
        Args:
            group_name: Name of the AWS Resource Group
            
        Returns:
            List of Resource objects with details
            
        Raises:
            AWSCliNotFoundError: If AWS CLI is not installed
            AWSAuthenticationError: If not authenticated
            AWSResourceGroupError: If resource group is invalid or operation fails
        """
        try:
            # Get resources in the group
            response = AWSScanner._run_aws_command([
                'aws', 'resource-groups', 'list-group-resources',
                '--group-name', group_name,
                '--output', 'json'
            ])
            
            resource_identifiers = response.get('ResourceIdentifiers', [])
            
            if not resource_identifiers:
                logger.info(f"No resources found in group '{group_name}'")
                return []
            
            # Normalize ARNs and fields for tagging API call
            arns = []
            resources = []

            for rid in resource_identifiers:
                # Support different AWS CLI key casing/variants
                arn = rid.get('ResourceARN') or rid.get('ResourceArn') or rid.get('ARN') or rid.get('Arn') or ''
                if arn:
                    arns.append(arn)

            # Fetch tags for all resources
            tags_map = AWSScanner._get_resource_tags(arns) if arns else {}

            # Build resource list with robust field extraction
            for rid in resource_identifiers:
                arn = rid.get('ResourceARN') or rid.get('ResourceArn') or rid.get('ARN') or rid.get('Arn') or ''

                # Resource type may be provided or derivable from ARN
                raw_type = rid.get('ResourceType') or rid.get('Type') or ''
                if not raw_type and arn:
                    # Try to derive from ARN last segment
                    _, derived = AWSScanner._parse_resource_arn(arn)
                    # derived is like 'AWS::SERVICE::resource'
                    raw_type = derived

                # Parse region and normalized resource type
                region, parsed_type = AWSScanner._parse_resource_arn(arn) if arn else ('unknown', f"AWS::UNKNOWN::{raw_type or ''}")

                # Name fields may vary
                name = rid.get('Name') or rid.get('ResourceName') or rid.get('Id') or rid.get('ResourceId') or ''
                if not name and arn:
                    name = AWSScanner._get_resource_name_from_arn(arn)

                # SKU/size
                sku = AWSScanner._extract_sku(raw_type or parsed_type, arn)

                tags = tags_map.get(arn, {}) if arn else {}

                resource = Resource(
                    resource_type=parsed_type,
                    name=name or '',
                    region=region or 'unknown',
                    sku=sku or 'unknown',
                    tags=tags,
                    arn=arn or ''
                )
                resources.append(resource)
            
            logger.info(f"Found {len(resources)} resources in group '{group_name}'")
            return resources
            
        except AWSError:
            raise
    
    @staticmethod
    def _get_resource_tags(arns: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Fetch tags for a list of resource ARNs using the Resource Groups Tagging API.
        
        Args:
            arns: List of AWS ARNs
            
        Returns:
            Dictionary mapping ARN to tags dictionary
        """
        if not arns:
            return {}
        
        try:
            response = AWSScanner._run_aws_command([
                'aws', 'resourcegroupstaggingapi', 'get-resources',
                '--resource-arn-list'] + arns + [
                '--output', 'json'
            ])
            
            tags_map = {}
            for resource in response.get('ResourceTagMappingList', []):
                arn = resource.get('ResourceARN', '')
                tags_list = resource.get('Tags', [])
                tags = {tag['Key']: tag['Value'] for tag in tags_list}
                tags_map[arn] = tags
            
            return tags_map
            
        except AWSError as e:
            logger.warning(f"Failed to fetch tags: {str(e)}. Continuing without tags.")
            return {}
    
    @staticmethod
    def _extract_sku(resource_type: str, arn: str) -> str:
        """
        Extract SKU/size information for the resource.

        This uses AWS CLI describe calls for common compute and database resources
        to give the AI more explicit sizing and state detail.

        Args:
            resource_type: AWS resource type
            arn: AWS ARN of the resource

        Returns:
            SKU or size information
        """
        if not arn:
            return "unknown"

        try:
            if arn.startswith("arn:aws:ec2:"):
                instance_id = arn.split('/')[-1]
                if instance_id.startswith("i-"):
                    response = AWSScanner._run_aws_command([
                        'aws', 'ec2', 'describe-instances',
                        '--instance-ids', instance_id,
                        '--query', 'Reservations[0].Instances[0].{Type:InstanceType,State:State.Name,AZ:Placement.AvailabilityZone}',
                        '--output', 'json'
                    ])
                    if isinstance(response, dict):
                        instance_type = response.get('Type')
                        state = response.get('State')
                        az = response.get('AZ')
                        details = [value for value in [instance_type, state, az] if value]
                        return ' '.join(details) if details else 'ec2-instance'

            if 'rds' in resource_type.lower() or ':rds:' in arn:
                resource_id = arn.split(':')[-1].replace('db:', '')
                if resource_id:
                    response = AWSScanner._run_aws_command([
                        'aws', 'rds', 'describe-db-instances',
                        '--db-instance-identifier', resource_id,
                        '--query', 'DBInstances[0].{Class:DBInstanceClass,Status:DBInstanceStatus,MultiAZ:MultiAZ}',
                        '--output', 'json'
                    ])
                    if isinstance(response, dict):
                        db_class = response.get('Class')
                        status = response.get('Status')
                        multi_az = response.get('MultiAZ')
                        details = [str(value) for value in [db_class, status, f"MultiAZ={multi_az}" if multi_az is not None else None] if value]
                        return ' '.join(details) if details else 'rds-instance'

            if 'elasticache' in resource_type.lower() or ':elasticache:' in arn:
                cache_id = arn.split(':')[-1]
                response = AWSScanner._run_aws_command([
                    'aws', 'elasticache', 'describe-cache-clusters',
                    '--cache-cluster-id', cache_id,
                    '--query', 'CacheClusters[0].{NodeType:CacheNodeType,Engine:Engine,Status:CacheClusterStatus}',
                    '--output', 'json'
                ])
                if isinstance(response, dict):
                    node_type = response.get('NodeType')
                    engine = response.get('Engine')
                    status = response.get('Status')
                    details = [value for value in [node_type, engine, status] if value]
                    return ' '.join(details) if details else 'elasticache-cluster'

        except AWSError as e:
            logger.warning(f"Failed to fetch SKU details for {arn}: {str(e)}. Falling back to unknown.")
        except Exception as e:
            logger.warning(f"Unexpected SKU extraction error for {arn}: {str(e)}")

        return "unknown"
