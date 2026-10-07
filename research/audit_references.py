"""Collect bibliographic metadata from DOI registration records and arXiv source pages."""
import asyncio
import html
import json
import re
from pathlib import Path

import httpx

SOURCES = [
    ('R01', 'doi', '10.1109/WCNC61545.2025.10978723'),
    ('R02', 'doi', '10.1109/ICASSP49660.2025.10890330'),
    ('R03', 'doi', '10.1109/ICCCAS62034.2024.10652649'),
    ('R04', 'arxiv', '2604.06900'), ('R05', 'arxiv', '2602.19087'),
    ('R06', 'arxiv', '2409.11276'), ('R07', 'doi', '10.1145/3704413.3764429'),
    ('R08', 'arxiv', '2601.22159'), ('R09', 'doi', '10.1109/FMEC62297.2024.10710218'),
    ('R10', 'doi', '10.1109/TCSS.2024.3496746'), ('R11', 'arxiv', '2603.25334'),
    ('R12', 'arxiv', '2512.10341'), ('R13', 'arxiv', '2603.17717'),
    ('R14', 'doi', '10.1109/ACCESS.2024.3386631'), ('R15', 'arxiv', '2502.13256'),
    ('R16', 'arxiv', '2606.12075'), ('R17', 'arxiv', '2502.15561'),
    ('R18', 'web', 'https://www.usenix.org/conference/atc23/presentation/vaswani'),
    ('R19', 'doi', '10.1109/SRDS69199.2025.00022'),
    ('R20', 'doi', '10.1109/IPCCC66453.2025.11304649'),
    ('S02', 'web', 'https://cloud.google.com/discover/what-is-federated-learning'),
    ('S04', 'doi', '10.1038/s41598-026-40122-4'),
    ('S05', 'web', 'https://www.infosecinstitute.com/resources/management-compliance-auditing/overview-understanding-soc-compliance-soc-1-vs-soc-2-vs-soc-3/'),
    ('S06', 'web', 'https://www.ibm.com/think/topics/cybersecurity'),
    ('S07', 'web', 'https://evoailabs.medium.com/cybersecurity-llms-new-locally-deployable-models-for-agentic-ai-54908c3f621b'),
    ('S08', 'web', 'https://docs.snowflake.com/en/user-guide/ml-functions/anomaly-detection'),
    ('S14', 'web', 'https://assets.anthropic.com/m/c52125297b85a42/original/Confidential_Inference_Paper.pdf'),
    ('S15', 'web', 'https://panther.com/blog/python-for-cybersecurity-key-use-cases-and-tools'),
    ('S16', 'web', 'https://infosecwriteups.com/building-an-integrated-threat-intelligence-platform-using-python-and-kibana-84503afe6251'),
]
DUPLICATES = {'S01': 'R11', 'S03': 'R12', 'S09': 'R15', 'S10': 'R04', 'S11': 'R05', 'S12': 'R07', 'S13': 'R06'}


async def main():
    output = Path(__file__).with_name('reference-metadata.json')
    records = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=40, headers={'User-Agent': 'ThreatScope-Bibliography-Verification/1.0'}) as client:
        for key, kind, identifier in SOURCES:
            url = f'https://api.crossref.org/works/{identifier}' if kind == 'doi' else (
                f'https://arxiv.org/abs/{identifier}' if kind == 'arxiv' else identifier)
            record = {'kind': kind, 'identifier': identifier, 'source': url}
            try:
                response = await client.get(url)
                record['status'] = response.status_code
                if response.status_code == 200 and kind == 'doi':
                    message = response.json()['message']
                    record.update({k: message.get(k) for k in ('title', 'author', 'published', 'container-title', 'volume', 'page', 'type', 'URL')})
                elif response.status_code == 200 and kind == 'arxiv':
                    pairs = re.findall(r'<meta\s+name="(citation_[^"]+)"\s+content="([^"]*)"', response.text)
                    for name, value in pairs:
                        record.setdefault(name, []).append(html.unescape(value))
                elif 'pdf' in response.headers.get('content-type', ''):
                    target = Path(__file__).parents[1] / '.runtime/references' / (key + '.pdf')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(response.content)
                    record['downloaded'] = True
                else:
                    match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.S)
                    record['page_title'] = html.unescape(match.group(1).strip()) if match else None
            except httpx.HTTPError as exc:
                record['error'] = type(exc).__name__
            records[key] = record
            output.write_text(json.dumps({'entries': records, 'duplicates': DUPLICATES}, indent=2), encoding='utf-8')
            print(key, record.get('status', record.get('error')), flush=True)
            await asyncio.sleep(0.5)


if __name__ == '__main__':
    asyncio.run(main())
