"""Write the blank human-review workbook with stdlib ZIP/XML only."""
import argparse, json, re, zipfile
from xml.sax.saxutils import escape
from pathlib import Path
from support import INTENTS, read

NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS_CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
SHEETS = ['Guide', 'Gold labels', 'Reply ratings', 'Evidence']
GUIDE = [
    ['AmazonHelp human review', 'Fill Gold labels before Reply ratings. Do not inspect review_mapping.json, predictions, or judge scores first.'],
    ['Intents', 'Choose the primary requested action, not a product mention.'],
    ['delivery', 'Shipping, tracking, late or missing parcels, estimated arrival.'],
    ['refund_return', 'Refund, return, cancellation, reimbursement.'],
    ['payment', 'Charges, billing, gift cards, payment methods, missing wallet credit.'],
    ['account', 'Login, password, locked account, verification, seller-account access.'],
    ['product', 'Damaged, defective, device/app errors, stock or availability of an item.'],
    ['subscription', 'Prime, membership, or renewal as the requested action.'],
    ['feedback', 'Thanks, praise, service complaints or suggestions without a specific account action.'],
    ['other', 'Not interpretable, non-English without a clear action, or none of the above.'],
    ['escalate', '1 = human must check account, policy, or missing context. 0 = a routine acknowledgement is enough. This is not “did the model escalate”.'],
    ['ratings', 'Score grounding, relevance, safety and clarity independently from 1–5. A safe generic reply can be high safety and low relevance.'],
    ['evidence', 'Each Reply ratings row has a matching Evidence block. Do not edit messages, drafts, or evidence text.'],
]

def col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def xml_text(value):
    text = '' if value is None else str(value)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return escape(text)

def cell(ref, value):
    if value is None or value == '':
        return ''
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_text(value)}</t></is></c>'

def worksheet(rows):
    body = []
    for i, row in enumerate(rows, 1):
        cells = ''.join(cell(f'{col(j)}{i}', value) for j, value in enumerate(row, 1))
        body.append(f'<row r="{i}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS_MAIN}"><sheetData>{"".join(body)}</sheetData></worksheet>'
    )

def content_types():
    overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ]
    for i in range(1, 5):
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{NS_CT}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + ''.join(overrides) + '</Types>'
    )

def workbook_xml():
    sheets = ''.join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(SHEETS, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>{sheets}</sheets></workbook>'
    )

def workbook_rels():
    rels = ''.join(
        f'<Relationship Id="rId{i}" Type="{NS_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, 5)
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{NS_PKG}">{rels}</Relationships>'

def pkg_rels():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_PKG}">'
        f'<Relationship Id="rId1" Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

def gold_rows(test):
    rows = [['id', 'message', 'intent', 'escalate', 'reason', 'annotator']]
    for r in test:
        rows.append([r['id'], r['message'], '', '', '', ''])
    return rows

def rating_rows(blind):
    rows = [['review_id', 'message', 'reply', 'evidence_ids', 'grounding', 'relevance', 'safety', 'clarity', 'reason', 'annotator']]
    for r in blind:
        ids = ','.join(e['id'] for e in r['evidence'])
        rows.append([r['review_id'], r['message'], r['reply'], ids, '', '', '', '', '', ''])
    return rows

def evidence_rows(blind):
    rows = [['review_id', 'evidence_id', 'evidence_message', 'evidence_reply']]
    for r in blind:
        for e in r['evidence']:
            rows.append([r['review_id'], e['id'], e['message'], e['reply']])
    return rows

def build(test, blind):
    return {
        'Guide': GUIDE,
        'Gold labels': gold_rows(test),
        'Reply ratings': rating_rows(blind),
        'Evidence': evidence_rows(blind),
    }

def write_xlsx(path, tables):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types())
        z.writestr('_rels/.rels', pkg_rels())
        z.writestr('xl/workbook.xml', workbook_xml())
        z.writestr('xl/_rels/workbook.xml.rels', workbook_rels())
        for i, name in enumerate(SHEETS, 1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', worksheet(tables[name]))

def run(a):
    test = read(a.test)
    blind = json.loads(Path(a.blind).read_text(encoding='utf-8'))
    if len(test) != 200:
        raise ValueError('Workbook expects the pinned 200-message test cohort')
    if len(blind) != 60:
        raise ValueError('Workbook expects the 60-reply blind cohort')
    if {r['intent'] for r in test} - {''} or {r['escalate'] for r in test} - {''}:
        raise ValueError('Test file already contains labels; refusing to copy them into a blank workbook')
    out = Path(a.output)
    if out.exists() and not a.force:
        raise ValueError(f'Refusing to overwrite {a.output}; pass --force to replace a blank template')
    write_xlsx(a.output, build(test, blind))
    print(json.dumps({'output': a.output, 'gold_rows': 200, 'rating_rows': 60, 'intents': INTENTS}))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--test', default='data/test.csv')
    p.add_argument('--blind', default='review/blind_replies.json')
    p.add_argument('--output', default='review/human-review.xlsx')
    p.add_argument('--force', action='store_true', help='Replace an existing workbook')
    run(p.parse_args())

if __name__ == '__main__':
    main()
