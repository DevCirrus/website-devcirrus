"""Read-only acceptance against production after the approved release and DNS cutover.

Run with default TLS verification. Store the resulting evidence privately.
Path/query redirect behaviour is observed and reported, not silently assumed.
"""
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    try:
        response = build_opener(NoRedirect).open(url, timeout=30)
    except HTTPError as error:
        response = error
    with response:
        return {'url': url, 'status': response.status, 'location': response.headers.get('Location'),
                'headers': dict(response.headers.items()), 'body': response.read().decode('utf-8')}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    apex = fetch('https://devcirrus.com/')
    require(apex['status'] == 200, 'Canonical HTTPS must return 200')
    for text in ['Hello world', 'DevCirrus', 'A brand by Augmen', 'lang="pt-PT"', 'lang="en-GB"',
                 'Projetos, experiências e conhecimento de cloud e DevOps.',
                 'Cloud and DevOps projects, experiments and knowledge.']:
        require(text in apex['body'], 'Required bilingual content missing')
    www = fetch('https://www.devcirrus.com/')
    require(www['status'] == 301 and www['location'] == 'https://devcirrus.com/', 'www must 301 to canonical HTTPS')
    observations = []
    for host in ['devcirrus.com', 'www.devcirrus.com']:
        first = fetch('http://' + host + '/')
        require(first['status'] in [301, 302, 307, 308], 'HTTP must redirect')
        location = urlsplit(first['location'] or '')
        require(location.scheme == 'https' and location.hostname in ['devcirrus.com', 'www.devcirrus.com'], 'HTTP must upgrade to the intended HTTPS hosts')
        # Follow the HTTPS chain with a bound; both certificates are validated.
        with build_opener().open('https://' + host + '/', timeout=30) as response:
            require(response.geturl() == 'https://devcirrus.com/' and response.status == 200, 'Redirect must converge without loops')
        observations.append({'url': first['url'], 'status': first['status'], 'location': first['location']})
    probe = fetch('https://www.devcirrus.com/__devcirrus_probe__?probe=1')
    require(probe['status'] == 301, 'www path/query probe must return 301')
    target = urlsplit(probe['location'] or '')
    require(target.scheme == 'https' and target.netloc == 'devcirrus.com', 'Path/query probe must target canonical host')
    observations.append({'url': probe['url'], 'status': probe['status'], 'location': probe['location'],
                         'path_preserved': target.path == '/__devcirrus_probe__', 'query_preserved': target.query == 'probe=1'})
    print(json.dumps({'https_and_content': 'passed', 'www_301': 'passed', 'redirect_observations': observations}, indent=2))


if __name__ == '__main__':
    main()
