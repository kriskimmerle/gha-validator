#!/usr/bin/env python3
"""
gha-validator - GitHub Actions workflow validator
Catches semantic issues before you push
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple


class ValidationError:
    """Represents a validation error or warning"""
    
    LEVELS = ['error', 'warning', 'info']
    
    def __init__(self, level: str, message: str, file: str, path: str = None):
        self.level = level
        self.message = message
        self.file = file
        self.path = path
    
    def __str__(self):
        emoji = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}
        prefix = f"{emoji.get(self.level, '•')} {self.level.upper()}"
        location = f"{self.file}"
        if self.path:
            location += f" [{self.path}]"
        return f"{prefix}: {location}\n  {self.message}"


def find_workflow_files(directory: str = '.github/workflows') -> List[Path]:
    """Find all GitHub Actions workflow files"""
    workflow_dir = Path(directory)
    if not workflow_dir.exists():
        return []
    
    return list(workflow_dir.glob('*.yml')) + list(workflow_dir.glob('*.yaml'))


def load_workflow(file_path: Path) -> Tuple[Dict[Any, Any], List[ValidationError]]:
    """Load and parse a workflow file"""
    errors = []
    
    try:
        with open(file_path) as f:
            content = yaml.safe_load(f)
        
        if not isinstance(content, dict):
            errors.append(ValidationError(
                'error',
                'Workflow file must contain a YAML mapping',
                str(file_path)
            ))
            return {}, errors
        
        return content, errors
    
    except yaml.YAMLError as e:
        errors.append(ValidationError(
            'error',
            f'YAML syntax error: {e}',
            str(file_path)
        ))
        return {}, errors
    
    except Exception as e:
        errors.append(ValidationError(
            'error',
            f'Failed to read file: {e}',
            str(file_path)
        ))
        return {}, errors


def validate_triggers(workflow: Dict, file_path: str) -> List[ValidationError]:
    """Validate workflow triggers"""
    errors = []
    
    if 'on' not in workflow and True not in workflow:
        errors.append(ValidationError(
            'error',
            'Workflow missing "on" trigger definition',
            file_path
        ))
        return errors
    
    triggers = workflow.get('on', workflow.get(True, {}))
    
    # workflow_dispatch visibility check
    if isinstance(triggers, dict) and 'workflow_dispatch' in triggers:
        errors.append(ValidationError(
            'info',
            'workflow_dispatch requires workflow to exist on default branch to appear in UI',
            file_path,
            'on.workflow_dispatch'
        ))
    
    # pull_request from forks
    if isinstance(triggers, dict) and 'pull_request' in triggers:
        pr_config = triggers.get('pull_request', {})
        if isinstance(pr_config, dict):
            types = pr_config.get('types', [])
            if 'opened' not in types and not types:
                errors.append(ValidationError(
                    'info',
                    'pull_request without types will trigger on opened, synchronize, reopened by default',
                    file_path,
                    'on.pull_request'
                ))
    
    # Check for empty trigger object
    if isinstance(triggers, dict):
        for trigger_name, trigger_config in triggers.items():
            if trigger_config == {} and trigger_name not in ['workflow_dispatch', 'repository_dispatch']:
                errors.append(ValidationError(
                    'warning',
                    f'Empty configuration for trigger "{trigger_name}" - is this intentional?',
                    file_path,
                    f'on.{trigger_name}'
                ))
    
    return errors


def validate_jobs(workflow: Dict, file_path: str) -> List[ValidationError]:
    """Validate workflow jobs"""
    errors = []
    
    if 'jobs' not in workflow:
        errors.append(ValidationError(
            'error',
            'Workflow missing "jobs" section',
            file_path
        ))
        return errors
    
    jobs = workflow.get('jobs', {})
    
    if not jobs:
        errors.append(ValidationError(
            'warning',
            'Workflow has no jobs defined',
            file_path,
            'jobs'
        ))
        return errors
    
    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue
        
        # Check for runs-on
        if 'runs-on' not in job_config and 'uses' not in job_config:
            errors.append(ValidationError(
                'error',
                f'Job "{job_name}" missing "runs-on" (required for normal jobs)',
                file_path,
                f'jobs.{job_name}'
            ))
        
        # Reusable workflow version check
        if 'uses' in job_config:
            uses = job_config['uses']
            if isinstance(uses, str):
                # Check for reusable workflow reference
                if uses.startswith('./.github/workflows/'):
                    errors.append(ValidationError(
                        'info',
                        f'Job "{job_name}" uses local reusable workflow - ensure it exists',
                        file_path,
                        f'jobs.{job_name}.uses'
                    ))
                elif '@' not in uses and '/' in uses:
                    errors.append(ValidationError(
                        'error',
                        f'Job "{job_name}" reusable workflow missing version/ref (should be org/repo/.github/workflows/file.yml@ref)',
                        file_path,
                        f'jobs.{job_name}.uses'
                    ))
        
        # Check steps for actions without versions
        steps = job_config.get('steps', [])
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            
            if 'uses' in step:
                action = step['uses']
                if isinstance(action, str) and '/' in action and '@' not in action:
                    errors.append(ValidationError(
                        'warning',
                        f'Job "{job_name}", step {i+1}: Action "{action}" missing version tag (e.g., @v1)',
                        file_path,
                        f'jobs.{job_name}.steps[{i}].uses'
                    ))
    
    return errors


def validate_permissions(workflow: Dict, file_path: str) -> List[ValidationError]:
    """Validate permissions configuration"""
    errors = []
    
    permissions = workflow.get('permissions')
    
    if permissions is not None:
        if isinstance(permissions, str):
            if permissions not in ['read-all', 'write-all']:
                errors.append(ValidationError(
                    'error',
                    f'Invalid permissions value: "{permissions}" (should be read-all, write-all, or object)',
                    file_path,
                    'permissions'
                ))
        elif isinstance(permissions, dict):
            valid_scopes = {
                'actions', 'checks', 'contents', 'deployments', 'id-token',
                'issues', 'discussions', 'packages', 'pages', 'pull-requests',
                'repository-projects', 'security-events', 'statuses'
            }
            
            for scope, level in permissions.items():
                if scope not in valid_scopes:
                    errors.append(ValidationError(
                        'warning',
                        f'Unknown permission scope: "{scope}"',
                        file_path,
                        f'permissions.{scope}'
                    ))
                
                if level not in ['read', 'write', 'none']:
                    errors.append(ValidationError(
                        'error',
                        f'Invalid permission level for "{scope}": "{level}" (should be read, write, or none)',
                        file_path,
                        f'permissions.{scope}'
                    ))
    
    return errors


def validate_workflow(file_path: Path) -> List[ValidationError]:
    """Run all validations on a workflow file"""
    workflow, load_errors = load_workflow(file_path)
    
    if load_errors:
        return load_errors
    
    errors = []
    errors.extend(validate_triggers(workflow, str(file_path)))
    errors.extend(validate_jobs(workflow, str(file_path)))
    errors.extend(validate_permissions(workflow, str(file_path)))
    
    return errors


def main():
    parser = argparse.ArgumentParser(
        description='Validate GitHub Actions workflows for common issues',
        epilog='Catches semantic problems before you push'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.github/workflows',
        help='Path to workflow file or directory (default: .github/workflows)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Only show errors and warnings, not info'
    )
    
    args = parser.parse_args()
    
    # Find workflow files
    path = Path(args.path)
    
    if path.is_file():
        workflow_files = [path]
    elif path.is_dir():
        workflow_files = find_workflow_files(str(path))
    else:
        print(f"Error: {args.path} not found", file=sys.stderr)
        sys.exit(1)
    
    if not workflow_files:
        print(f"No workflow files found in {args.path}", file=sys.stderr)
        sys.exit(1)
    
    # Validate all workflows
    all_errors = []
    
    for workflow_file in workflow_files:
        errors = validate_workflow(workflow_file)
        all_errors.extend(errors)
    
    # Filter and display
    display_levels = ['error', 'warning']
    if not args.quiet:
        display_levels.append('info')
    
    filtered_errors = [e for e in all_errors if e.level in display_levels]
    
    if filtered_errors:
        print(f"\n🔍 Found {len(filtered_errors)} issue(s) in {len(workflow_files)} workflow file(s):\n")
        
        for error in filtered_errors:
            print(error)
            print()
    else:
        print(f"✅ All {len(workflow_files)} workflow file(s) validated successfully!")
    
    # Determine exit code
    has_errors = any(e.level == 'error' for e in all_errors)
    has_warnings = any(e.level == 'warning' for e in all_errors)
    
    if has_errors or (args.strict and has_warnings):
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()
