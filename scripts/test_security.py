import importlib.util
from pathlib import Path
import tempfile
import unittest


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


environment = module('environment', 'check-environment.py')
infra = module('infra', 'infra-run.py')


class SecurityBoundaries(unittest.TestCase):
    def fixture(self):
        return ({'deployment_branch_policy': {'custom_branch_policies': True},
                 'protection_rules': [{'type': 'required_reviewers', 'prevent_self_review': False,
                                       'reviewers': [{'type': 'User', 'reviewer': {'login': 'PedroMatos'}}]}]},
                {'branch_policies': [{'name': 'main', 'type': 'branch'}]})

    def test_infra_requires_pedro_review(self):
        data, policies = self.fixture()
        environment.validate_environment(data, policies, True)
        data['protection_rules'] = []
        with self.assertRaises(AssertionError):
            environment.validate_environment(data, policies, True)

    def test_denies_tag_and_wildcard_deployments(self):
        for policy in [{'name': 'main', 'type': 'tag'}, {'name': '*', 'type': 'branch'}]:
            data, policies = self.fixture()
            policies['branch_policies'] = [policy]
            with self.assertRaises(AssertionError):
                environment.validate_environment(data, policies, True)

    def test_content_must_remain_automatic(self):
        data, policies = self.fixture()
        with self.assertRaises(AssertionError):
            environment.validate_environment(data, policies, False)
        data['protection_rules'] = []
        environment.validate_environment(data, policies, False)

    def test_changed_binary_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan'
            path.write_bytes(b'approved-plan')
            expected = infra.digest(path)
            infra.verify_file(path, expected)
            path.write_bytes(b'replaced-plan')
            with self.assertRaises(AssertionError):
                infra.verify_file(path, expected)

    def test_generation_injection_rejected(self):
        for value in ['123#456', '123\n456', 'latest', '']:
            with self.assertRaises(AssertionError):
                infra.checked(value, r'[0-9]+')


if __name__ == '__main__':
    unittest.main()

class DNSPreservation(unittest.TestCase):
    def test_mail_omission_and_txt_replacement_are_visible(self):
        dns = module('dns_compare', 'compare-dns.py')
        old = dns.normalize([
            {'name': 'devcirrus.com.', 'type': 'MX', 'ttl': 300, 'rrdatas': ['10 mail.example.invalid.']},
            {'name': 'devcirrus.com.', 'type': 'TXT', 'ttl': 300, 'rrdatas': ['"v=spf1 -all"', '"old-verification"']},
        ])
        new = dns.normalize([
            {'name': 'devcirrus.com.', 'type': 'TXT', 'ttl': 300, 'rrdatas': ['"new-challenge"']},
        ])
        self.assertEqual(dns.differences(old, new), {'devcirrus.com.|MX', 'devcirrus.com.|TXT'})
