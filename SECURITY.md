# Security

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security → Report a vulnerability** in this repository
(private vulnerability reporting), or by e-mail to [contact@trenify.org](mailto:contact@trenify.org). Do not open a public issue for a vulnerability.

We aim to answer within 7 days.

## Personal data in jerzyk-bench

If you find personal data in the benchmark (for example a name that the anonymisation missed), write to
[contact@trenify.org](mailto:contact@trenify.org) with the document id. Please do not quote the data in public issues or discussions. We will
remove it. The same address handles requests from people the documents concern (GDPR) and copyright requests.

## Running the server

`jerzyk-serve` (`jerzyk/serve.py`) has no authentication. By default it listens only on `127.0.0.1`. Do not expose it to a network
(`--host 0.0.0.0`) unless it runs behind your own access control (a reverse proxy with authentication, a VPN).
The server limits request size (100,000 characters of text, 32 questions) and handles one prediction at a time.

Jerzyk helps sort correspondence. It is not legal advice, and it must not be the only safeguard for statutory deadlines.
