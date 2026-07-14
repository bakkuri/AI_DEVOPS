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
            group_names = [group['Name'] for group in group_identifiers if 'Name' in group]
            
            logger.info(f"Found {len(group_names)} resource groups")
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
        
        # Extract resource type from the last part
        resource_part = parts[-1] if parts else ''
        resource_type = resource_part.split('/')[0] if '/' in resource_part else resource_part
        
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
            
            # Extract ARNs for tagging API call
            arns = [rid.get('ResourceARN') for rid in resource_identifiers if 'ResourceARN' in rid]
            
            # Fetch tags for all resources
            tags_map = AWSScanner._get_resource_tags(arns) if arns else {}
            
            # Build resource list
            resources = []
            for rid in resource_identifiers:
                arn = rid.get('ResourceARN', '')
                resource_type = rid.get('ResourceType', '')
                
                region, parsed_type = AWSScanner._parse_resource_arn(arn)
                name = rid.get('Name') or AWSScanner._get_resource_name_from_arn(arn)
                sku = AWSScanner._extract_sku(resource_type, arn)
                tags = tags_map.get(arn, {})
                
                resource = Resource(
                    resource_type=parsed_type,
                    name=name,
                    region=region,
                    sku=sku,
                    tags=tags,
                    arn=arn
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
        
        For now, returns a placeholder. Can be extended to call describe-* APIs.
        
        Args:
            resource_type: AWS resource type
            arn: AWS ARN of the resource
            
        Returns:
            SKU or size information
        """
        # Placeholder - can be extended to call describe-* APIs for specific resource types
        # e.g., for EC2: describe-instances, for RDS: describe-db-instances
        return "standard"  # Default SKU
