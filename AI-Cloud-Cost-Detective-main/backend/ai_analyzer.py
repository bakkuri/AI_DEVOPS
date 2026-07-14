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
from pathlib import Path
from dotenv import load_dotenv
import httpx

from aws_scanner import Resource

logger = logging.getLogger(__name__)

# Load environment variables from the backend directory .env file
dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)


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
        
        self.base_url = "https://api.openai.com/v1"
    
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
            lines.append(f"{i}. Resource Name: {resource.name}")
            lines.append(f"   Resource Type: {resource.resource_type}")
            lines.append(f"   Region: {resource.region}")
            lines.append(f"   SKU/Size: {resource.sku}")
            lines.append(f"   ARN: {resource.arn}")
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

Provide a structured cost analysis in valid JSON format. If a specific resource lacks enough detail to make a confident recommendation, note that explicitly in the issue description and still provide the best possible guidance based on the available data.

Use this exact JSON structure:
{{
    "summary": "Overall summary of findings (2-3 sentences)",
    "total_estimated_savings": "Estimated total monthly or annual savings (e.g., '$1,500/month', '$0', or 'unknown')",
    "issues": [
        {{
            "title": "Issue title",
            "description": "Detailed description of the issue",
            "severity": "high/medium/low",
            "resource_name": "Name of affected resource",
            "resource_type": "AWS resource type",
            "estimated_savings": "Estimated savings for this issue (e.g., '$250/month' or '$0')",
            "fix_command": "AWS CLI command to fix the issue (optional, omit if not applicable)"
        }}
    ],
    "recommendations": [
        "General recommendation 1",
        "General recommendation 2"
    ]
}}

Focus on concrete cost optimization items:
1. Over-provisioned compute and database instances.
2. Unused, idle, or orphaned resources.
3. Resource configuration issues and missing optimizations.
4. Storage, backup, and logging configuration waste.
5. Reserved Instance, Savings Plan, and right-sizing opportunities.

Do not return any explanation outside the JSON object. If there are no actionable cost savings, still return valid JSON with total_estimated_savings "$0" and an empty issues array."""

        return prompt
    
    @staticmethod
    def _parse_json_response(response_text: str) -> Dict[str, Any]:
        """
        Parse the model response and extract a JSON object.

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: If JSON cannot be parsed
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to recover by extracting the first JSON object block
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = response_text[start:end + 1]
                return json.loads(candidate)
            raise

    @staticmethod
    def _normalize_severity(value: Optional[str]) -> str:
        if not value:
            return 'medium'
        normalized = value.strip().lower()
        if normalized in {'high', 'medium', 'low'}:
            return normalized
        if normalized.startswith('h'):
            return 'high'
        if normalized.startswith('l'):
            return 'low'
        return 'medium'

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

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an AWS cost optimization expert. Respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }

            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0
                )
            except httpx.HTTPError as e:
                raise OpenAIAPIError(f"OpenAI API request failed: {str(e)}")

            if response.status_code != 200:
                response_text = response.text
                if response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        error_body = response.json()
                        error_message = error_body.get("error", {}).get("message") or response_text
                    except json.JSONDecodeError:
                        error_message = response_text
                else:
                    error_message = response_text

                if response.status_code == 429:
                    raise OpenAIAPIError(
                        f"OpenAI quota exceeded or rate-limited: {error_message}"
                    )
                if response.status_code == 401:
                    raise OpenAIAPIError(
                        f"OpenAI API authorization failed: {error_message}"
                    )

                raise OpenAIAPIError(
                    f"OpenAI API request failed: {response.status_code} {error_message}"
                )

            try:
                response_body = response.json()
            except json.JSONDecodeError as e:
                raise OpenAIAPIError(
                    f"OpenAI response JSON decode failed: {str(e)}"
                )

            response_text = response_body['choices'][0]['message']['content']
            analysis_data = self._parse_json_response(response_text)

            issues = []
            for issue_data in analysis_data.get('issues', []) or []:
                issue = CostIssue(
                    title=issue_data.get('title', 'Unknown issue'),
                    description=issue_data.get('description', ''),
                    severity=self._normalize_severity(issue_data.get('severity', 'medium')),
                    resource_name=issue_data.get('resource_name', ''),
                    resource_type=issue_data.get('resource_type', ''),
                    estimated_savings=issue_data.get('estimated_savings', '$0'),
                    fix_command=issue_data.get('fix_command')
                )
                issues.append(issue)

            total_estimated_savings = analysis_data.get('total_estimated_savings') or '$0'
            summary = analysis_data.get('summary', '').strip() or (
                'No cost issues were identified for the scanned resources.' if issues == [] else 'Cost analysis completed.'
            )
            recommendations = analysis_data.get('recommendations') or []

            analysis = CostAnalysis(
                summary=summary,
                total_estimated_savings=total_estimated_savings,
                issues=issues,
                recommendations=recommendations
            )

            logger.info(f"Cost analysis complete: {len(issues)} issues found")
            return analysis

        except httpx.HTTPError as e:
            error_msg = f"OpenAI API request failed: {str(e)}"
            logger.error(error_msg)
            raise OpenAIAPIError(error_msg)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {response_text}")
            raise OpenAIAPIError(
                f"OpenAI returned invalid JSON: {str(e)}"
            )
        except OpenAIAPIError as e:
            # Return a safe fallback analysis when OpenAI is unavailable (quota/rate-limit/auth)
            logger.warning(f"OpenAI unavailable: {str(e)}. Returning fallback analysis.")
            fallback_summary = (
                "AI analysis unavailable: " + str(e) +
                "\nThe system returned a fallback analysis. Please check OpenAI billing, quota, or API key."
            )
            return CostAnalysis(
                summary=fallback_summary,
                total_estimated_savings="$0",
                issues=[],
                recommendations=[
                    "Enable billing or increase quota on the OpenAI account.",
                    "Verify OPENAI_API_KEY is valid and has remaining quota.",
                    "Retry the analysis after resolving the OpenAI issue."
                ]
            )
        except Exception as e:
            error_msg = f"Unexpected error during AI analysis: {str(e)}"
            logger.exception(error_msg)
            raise OpenAIAPIError(error_msg)
