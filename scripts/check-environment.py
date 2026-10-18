"""Fail closed before cloud auth if main or the configured review gate changed."""
import json
import os
import subprocess
import sys
import urllib.request


def validate_environment(data, policies, approval):
    assert data['deployment_branch_policy']['custom_branch_policies'], 'Use custom main-only deployment policy'
    rules = policies['branch_policies']
    assert len(rules) == 1 and rules[0]['name'] == 'main' and rules[0]['type'] == 'branch', 'Allow main branch only, no tags or patterns'
    reviews = [r for r in data['protection_rules'] if r['type'] == 'required_reviewers']
    if approval:
        assert len(reviews) == 1, 'Infrastructure requires a reviewer gate'
        assert reviews[0].get('prevent_self_review') is False, 'Pedro must be able to approve his own manual run'
        reviewers = reviews[0]['reviewers']
        assert len(reviewers) == 1 and reviewers[0]['type'] == 'User' and reviewers[0]['reviewer']['login'] == 'PedroMatos', 'Require Pedro as reviewer'
    else:
        assert not reviews, 'Content publication must stay automatic after merge'


def current_head():
    assert os.environ['GITHUB_REF'] == 'refs/heads/main', 'Use main only'
    sha = os.environ['GITHUB_SHA']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == sha
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/main'], text=True).split()[0]
    assert remote == sha, 'Stale run: main advanced; start a new run'


def api(path):
    req = urllib.request.Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + path,
                                 headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                                          'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


if __name__ == '__main__':
    current_head()
    name = sys.argv[1]
    if name != '--head-only':
        names = ['infrastructure', 'infrastructure-plan'] if name == 'infrastructure' else [name]
        for env in names:
            data = api('/environments/' + env)
            policies = api('/environments/' + env + '/deployment-branch-policies')
            validate_environment(data, policies, env == 'infrastructure')
    print('Main revision and required environment policies verified.')
