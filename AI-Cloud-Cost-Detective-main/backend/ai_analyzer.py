"""
AI Analyzer Module

Uses OpenAI API to perform cost analysis on AWS resources.
Identifies cost optimization opportunities and provides actionable recommendations.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import os
from dotenv import load_dotenv
from openai import OpenAI, APIError

from aws_scanner import Resource

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


@dataclass
class CostIssue:
    """Represents a single cost issue identified by AI analysis."""
    title: str
    description: str
    severity: str  # "high", "medium", "low"
    resource_name: str
    resource_type: str
    estimated_savings: str  # e.g., "$500/month", "20%"
    fix_command: Optional[str] = None


@dataclass
class CostAnalysis:
    """Complete cost analysis result."""
    summary: str
    total_estimated_savings: str
    issues: List[CostIssue]
    recommendations: List[str]


class AIAnalyzerError(Exception):
    """Base exception for AI analysis operations."""
    pass


class OpenAIConfigError(AIAnalyzerError):
    """Raised when OpenAI configuration is missing or invalid."""
    pass


class OpenAIAPIError(AIAnalyzerError):
    """Raised when OpenAI API call fails."""
    pass


class AIAnalyzer:
    """Performs AI-powered cost analysis on AWS resources."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI Analyzer.
        
        Args:
            api_key: OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
            
        Raises:
            OpenAIConfigError: If API key is not available
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            raise OpenAIConfigError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY environment variable or pass it as a parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
    
    @staticmethod
    def _format_resources_for_prompt(resources: List[Resource]) -> str:
        """
        Format resources into a readable format for the AI prompt.
        
        Args:
            resources: List of Resource objects
            
        Returns:
            Formatted string representation of resources
        """
        if not resources:
            return "No resources found."
        
        lines = []
        for i, resource in enumerate(resources, 1):
            lines.append(f"{i}. {resource.name}")
            lines.append(f"   Type: {resource.resource_type}")
            lines.append(f"   Region: {resource.region}")
            lines.append(f"   SKU: {resource.sku}")
            if resource.tags:
                tags_str = ", ".join([f"{k}={v}" for k, v in resource.tags.items()])
                lines.append(f"   Tags: {tags_str}")
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _build_analysis_prompt(resources: List[Resource]) -> str:
        """
        Build the prompt for cost analysis.
        
        Args:
            resources: List of AWS resources to analyze
            
        Returns:
            Formatted prompt string
        """
        resources_str = AIAnalyzer._format_resources_for_prompt(resources)
        
        prompt = f"""You are an AWS cost optimization expert. Analyze the following AWS resources and identify cost optimization opportunities.

AWS RESOURCES:
{resources_str}

Please provide a structured cost analysis in JSON format with the following structure:
{{
    "summary": "Overall summary of findings (2-3 sentences)",
    "total_estimated_savings": "Estimated total monthly or annual savings (e.g., '$1,500/month' or '15%')",
    "issues": [
        {{
            "title": "Issue title",
            "description": "Detailed description of the issue",
            "severity": "high/medium/low",
            "resource_name": "Name of affected resource",
            "resource_type": "AWS resource type",
            "estimated_savings": "Estimated savings for this issue (e.g., '$250/month')",
            "fix_command": "AWS CLI command to fix the issue (optional, omit if not applicable)"
        }}
    ],
    "recommendations": [
        "General recommendation 1",
        "General recommendation 2"
    ]
}}

Focus on these areas of cost optimization:
1. Over-provisioned resources (EC2, RDS, ElastiCache instances larger than workload needs)
2. Unused or idle resources (unattached EBS volumes, unused Elastic IPs, idle load balancers, stopped instances)
3. Misconfigurations (wrong instance families, missing Savings Plans, no auto-scaling, oversized storage)
4. Storage and logging waste (S3 without lifecycle policies, excessive CloudWatch log retention)
5. Reserved Instances and Savings Plans opportunities

Return ONLY valid JSON, no additional text."""
        
        return prompt
    
    def analyze(self, resources: List[Resource]) -> CostAnalysis:
        """
        Perform AI-powered cost analysis on resources.
        
        Args:
            resources: List of AWS resources to analyze
            
        Returns:
            CostAnalysis object with findings
            
        Raises:
            OpenAIAPIError: If OpenAI API call fails
        """
        if not resources:
            logger.warning("No resources provided for analysis")
            return CostAnalysis(
                summary="No resources provided for analysis.",
                total_estimated_savings="$0",
                issues=[],
                recommendations=[]
            )
        
        prompt = self._build_analysis_prompt(resources)
        
        try:
            logger.info(f"Calling OpenAI API for cost analysis of {len(resources)} resources")
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AWS cost optimization expert. Respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Extract the response text
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            try:
                analysis_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {response_text}")
                raise OpenAIAPIError(
                    f"OpenAI returned invalid JSON: {str(e)}"
                )
            
            # Parse issues with validation
            issues = []
            for issue_data in analysis_data.get('issues', []):
                issue = CostIssue(
                    title=issue_data.get('title', 'Unknown issue'),
                    description=issue_data.get('description', ''),
                    severity=issue_data.get('severity', 'medium'),
                    resource_name=issue_data.get('resource_name', ''),
                    resource_type=issue_data.get('resource_type', ''),
                    estimated_savings=issue_data.get('estimated_savings', 'Unknown'),
                    fix_command=issue_data.get('fix_command')
                )
                issues.append(issue)
            
            # Build and return CostAnalysis
            analysis = CostAnalysis(
                summary=analysis_data.get('summary', ''),
                total_estimated_savings=analysis_data.get('total_estimated_savings', 'Unknown'),
                issues=issues,
                recommendations=analysis_data.get('recommendations', [])
            )
            
            logger.info(f"Cost analysis complete: {len(issues)} issues found")
            return analysis
        
        except APIError as e:
            error_msg = f"OpenAI API error: {str(e)}"
            logger.error(error_msg)
            raise OpenAIAPIError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during AI analysis: {str(e)}"
            logger.exception(error_msg)
            raise OpenAIAPIError(error_msg)
