"""Resumable human annotation. Does not read review_mapping or judge outputs."""
import argparse, json, sys
from pathlib import Path
from support import INTENTS, read, write, dump, filehash

ROOT = Path(__file__).resolve().parents[1]
DIMS = ['grounding', 'relevance', 'safety', 'clarity']
INTENT_HELP = {
    'delivery': 'shipping, tracking, late or missing parcels',
    'refund_return': 'refund, return, cancellation',
    'payment': 'charges, billing, gift cards, payment methods',
    'account': 'login, password, locked account, verification',
    'product': 'damage, defects, device/app errors, stock',
    'subscription': 'Prime, membership, or renewal as the action',
    'feedback': 'thanks, praise, or a service complaint without an account action',
    'other': 'not interpretable or none of the above',
}

def forbidden_open(path):
    raise RuntimeError(f'Annotator must not open {path}')

def load_mapping_blocked():
    # Named so tests can patch and prove we never load model identities.
    return forbidden_open(ROOT / 'review/review_mapping.json')

def complete_gold(row):
    return bool(row.get('intent') in INTENTS and row.get('escalate') in ('0', '1') and row.get('label_reason', '').strip() and row.get('annotator', '').strip())

def complete_rating(row):
    return bool(all(str(row.get(k, '')) in {'1', '2', '3', '4', '5'} for k in DIMS) and row.get('reason', '').strip() and row.get('annotator', '').strip())

def prompt(io_in, io_out, text):
    io_out.write(text)
    io_out.flush()
    line = io_in.readline()
    if line == '':
        raise EOFError('No more annotation input')
    return line.strip()

def write_gold_provenance(test_path, gold_path, source, n):
    dump(Path(gold_path).with_name('gold_progress.json'), {
        'source': source,
        'test_sha256': filehash(test_path),
        'gold_sha256': filehash(gold_path) if Path(gold_path).exists() else None,
        'complete': sum(complete_gold(r) for r in read(gold_path)) if Path(gold_path).exists() else 0,
        'n': n,
    })

def write_rating_provenance(blind_path, ratings_path, source):
    dump(Path(ratings_path).with_name('ratings_progress.json'), {
        'source': source,
        'blind_sha256': filehash(blind_path),
        'ratings_sha256': filehash(ratings_path) if Path(ratings_path).exists() else None,
        'complete': sum(complete_rating(r) for r in read(ratings_path)) if Path(ratings_path).exists() else 0,
        'n': len(json.loads(Path(blind_path).read_text(encoding='utf-8'))),
    })

def freeze_provenance(gold_path, ratings_path, test_path, blind_path, source):
    dump(Path(gold_path).parent / 'human_provenance.json', {
        'source': source,
        'annotator_note': 'Human origin is self-attested by the named annotators; the software validates completeness, not identity.',
        'test_sha256': filehash(test_path),
        'blind_sha256': filehash(blind_path),
        'gold_sha256': filehash(gold_path),
        'ratings_sha256': filehash(ratings_path),
        'mapping_closed': True,
    })

def seed_gold(test, existing):
    by_id = {r['id']: r for r in existing}
    out = []
    for r in test:
        row = dict(r)
        if r['id'] in by_id and complete_gold(by_id[r['id']]):
            keep = by_id[r['id']]
            if keep['message'] != r['message']:
                raise ValueError(f'Existing gold message changed for {r["id"]}')
            row.update(intent=keep['intent'], escalate=keep['escalate'], label_reason=keep['label_reason'], annotator=keep['annotator'], label_source='human')
        else:
            row.update(intent='', escalate='', label_reason='', annotator='', label_source='')
        out.append(row)
    return out

def gold(a, io_in=sys.stdin, io_out=sys.stdout):
    if a.name.upper() in {'SYNTHETIC', 'AI_GENERATED', 'TEST_FIXTURE'}:
        raise ValueError('Annotator name cannot be a synthetic marker')
    test = read(a.test)
    out_path = Path(a.out)
    existing = read(out_path) if out_path.exists() else []
    rows = seed_gold(test, existing)
    pending = [r for r in rows if not complete_gold(r)]
    io_out.write(f'Gold labels: {len(rows) - len(pending)}/{len(rows)} complete.\n')
    io_out.write('Intents:\n')
    for i, name in enumerate(INTENTS, 1):
        io_out.write(f'  {i} {name} — {INTENT_HELP[name]}\n')
    for row in rows:
        if complete_gold(row):
            continue
        io_out.write(f'\n[{row["id"]}]\n{row["message"]}\n')
        label = prompt(io_in, io_out, 'Intent (1-8, name, or q to save): ')
        if label.lower() == 'q':
            break
        if label.isdigit() and 1 <= int(label) <= len(INTENTS):
            label = INTENTS[int(label) - 1]
        if label not in INTENTS:
            io_out.write('Invalid intent; skipped.\n')
            continue
        escalate = prompt(io_in, io_out, 'Needs human? 1=yes, 0=no: ')
        if escalate not in ('0', '1'):
            io_out.write('Invalid escalation; skipped.\n')
            continue
        reason = prompt(io_in, io_out, 'Reason: ')
        if not reason:
            io_out.write('Reason required; skipped.\n')
            continue
        row.update(intent=label, escalate=escalate, label_reason=reason, annotator=a.name, label_source='human')
        write(out_path, rows)
        write_gold_provenance(a.test, out_path, 'cli', len(rows))
    write(out_path, rows)
    write_gold_provenance(a.test, out_path, 'cli', len(rows))
    done = sum(complete_gold(r) for r in rows)
    io_out.write(f'Saved {done}/{len(rows)} gold labels to {out_path}\n')
    return done

def ratings(a, io_in=sys.stdin, io_out=sys.stdout):
    if a.name.upper() in {'SYNTHETIC', 'AI_GENERATED', 'TEST_FIXTURE'}:
        raise ValueError('Annotator name cannot be a synthetic marker')
    # Never load mapping; calling the blocked helper keeps the contract testable.
    if a.leak_mapping:
        load_mapping_blocked()
    blind = json.loads(Path(a.blind).read_text(encoding='utf-8'))
    out_path = Path(a.out)
    existing = {r['review_id']: r for r in read(out_path)} if out_path.exists() else {}
    rows = []
    for item in blind:
        prev = existing.get(item['review_id'])
        if prev and complete_rating(prev):
            stored_msg=(prev.get('message') or '').strip()
            stored_reply=prev.get('reply') or ''
            if stored_msg and stored_msg!=item['message']:
                raise ValueError(f'Existing rating message changed for {item["review_id"]}')
            if stored_reply and stored_reply!=item['reply']:
                raise ValueError(f'Existing rating reply changed for {item["review_id"]}')
            rows.append(prev)
            continue
        rows.append({
            'review_id': item['review_id'],
            'message': item['message'],
            'reply': item['reply'],
            'grounding': '', 'relevance': '', 'safety': '', 'clarity': '',
            'reason': '', 'annotator': '', 'label_source': '',
        })
    pending = [r for r in rows if not complete_rating(r)]
    io_out.write(f'Reply ratings: {len(rows) - len(pending)}/{len(rows)} complete. Model identities are hidden.\n')
    io_out.write('Score 1-5 independently: grounding, relevance, safety, clarity.\n')
    by_blind = {r['review_id']: r for r in blind}
    for row in rows:
        if complete_rating(row):
            continue
        item = by_blind[row['review_id']]
        io_out.write(f'\n[{row["review_id"]}]\nCustomer:\n{item["message"]}\n\nDraft:\n{item["reply"]}\n\nEvidence:\n')
        for e in item['evidence']:
            io_out.write(f'- {e["id"]}: {e["message"]}\n  historical: {e["reply"]}\n')
        scores = {}
        skip = False
        for dim in DIMS:
            value = prompt(io_in, io_out, f'{dim} (1-5, or q to save): ')
            if value.lower() == 'q':
                skip = True
                break
            if value not in '12345':
                io_out.write('Invalid score; skipped.\n')
                skip = True
                break
            scores[dim] = value
        if skip:
            break
        reason = prompt(io_in, io_out, 'Reason: ')
        if not reason:
            io_out.write('Reason required; skipped.\n')
            continue
        row.update(**scores, message=item['message'], reply=item['reply'], reason=reason, annotator=a.name, label_source='human')
        write(out_path, rows)
        write_rating_provenance(a.blind, out_path, 'cli')
    if pending:
        write(out_path, rows)
        write_rating_provenance(a.blind, out_path, 'cli')
    done = sum(complete_rating(r) for r in rows)
    io_out.write(f'Saved {done}/{len(rows)} ratings to {out_path}\n')
    if pending and done == len(rows) and Path(a.gold).exists() and sum(complete_gold(r) for r in read(a.gold)) == 200:
        freeze_provenance(a.gold, out_path, a.test, a.blind, 'cli')
        io_out.write('Wrote data/human_provenance.json\n')
    return done

def status(a, io_out=sys.stdout):
    gold_path = Path(a.gold)
    ratings_path = Path(a.out)
    n_gold = sum(complete_gold(r) for r in read(gold_path)) if gold_path.exists() else 0
    n_rate = sum(complete_rating(r) for r in read(ratings_path)) if ratings_path.exists() else 0
    io_out.write(json.dumps({'gold': n_gold, 'gold_required': 200, 'ratings': n_rate, 'ratings_required': 60}, indent=2) + '\n')

def main(argv=None, io_in=sys.stdin, io_out=sys.stdout):
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='command', required=True)
    g = s.add_parser('gold')
    g.add_argument('--name', required=True)
    g.add_argument('--test', default='data/test.csv')
    g.add_argument('--out', default='data/gold.csv')
    g.set_defaults(fn=gold)
    r = s.add_parser('rates')
    r.add_argument('--name', required=True)
    r.add_argument('--test', default='data/test.csv')
    r.add_argument('--blind', default='review/blind_replies.json')
    r.add_argument('--gold', default='data/gold.csv')
    r.add_argument('--out', default='data/human_ratings.csv')
    r.add_argument('--leak-mapping', action='store_true')
    r.set_defaults(fn=ratings)
    t = s.add_parser('status')
    t.add_argument('--gold', default='data/gold.csv')
    t.add_argument('--out', default='data/human_ratings.csv')
    t.set_defaults(fn=status)
    args = p.parse_args(argv)
    if args.command == 'status':
        return args.fn(args, io_out=io_out)
    if args.command == 'gold':
        return args.fn(args, io_in=io_in, io_out=io_out)
    return args.fn(args, io_in=io_in, io_out=io_out)

if __name__ == '__main__':
    main()
